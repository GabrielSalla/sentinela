import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

import prometheus_client
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response, StreamResponse
from pydantic import ValidationError

import components.controller.controller as controller
import components.executor.executor as executor
import registry as registry
from components.http_server.alert_routes import alert_routes
from components.http_server.dashboard_routes import dashboard_routes
from components.http_server.issue_routes import issue_routes
from components.http_server.monitor_routes import monitor_routes
from configs import configs
from utils.log import set_logger_level

_logger = logging.getLogger("http_server")

_runner: web.AppRunner

base_routes = web.RouteTableDef()

STATUS_MESSAGES = [
    "And the science gets done and you make a neat gun for the people who are *still alive*",
    "Think of all the things we learned for the people who are *still alive*",
    "I have experiments to run, there is research to be done, on the people who are *still alive*",
    "Believe me I am *still alive*",
    "I'm doing science and I'm *still alive*",
    "I feel fantastic and I'm *still alive*",
    "While you're dying I'll be *still alive*",
    "When you're dead I'll be *still alive*",
]


@base_routes.get("/")
@base_routes.get("/status")
@base_routes.get("/status/")
async def get_status(request: Request) -> Response:
    """Return the application status"""
    response: dict[str, Any] = {
        "status": "ok",
        "monitors_loaded": [monitor["name"] for monitor in registry.get_monitors()],
        "components": {},
    }

    if controller.running:
        status, issues = await controller.diagnostics()
        response["components"]["controller"] = {"status": status, "issues": issues}
        if len(issues) > 0:
            response["status"] = "degraded"

    if executor.running:
        status, issues = await executor.diagnostics()
        response["components"]["executor"] = {"status": status, "issues": issues}
        if len(issues) > 0:
            response["status"] = "degraded"

    if response["status"] == "ok":
        response["_message"] = (random.choice(STATUS_MESSAGES),)

    return web.json_response(response)


@base_routes.get("/metrics")
@base_routes.get("/metrics/")
async def get_metrics(request: Request) -> Response:
    """Return prometheus metrics"""
    response = web.Response(body=prometheus_client.generate_latest())
    response.content_type = prometheus_client.CONTENT_TYPE_LATEST
    return response


@web.middleware
async def _pydantic_validation_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """Convert pydantic validation errors into HTTP 400 responses"""
    try:
        return await handler(request)
    except ValidationError as error:
        errors = []
        for field_error in error.errors():
            message = field_error["msg"]
            if message.startswith("Value error, "):
                message = message.replace("Value error, ", "", 1)

            location = ".".join(str(part) for part in field_error["loc"])
            errors.append(f"{location}: {message}")

        return web.json_response(
            {
                "status": "error",
                "message": "Invalid request data",
                "errors": errors,
            },
            status=400,
        )


@web.middleware
async def _log_4xx_requests_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """Log HTTP requests that return a 4xx status code"""
    try:
        response = await handler(request)
    except web.HTTPException as error:
        if 400 <= error.status < 500:
            _logger.warning(
                f"HTTP 4xx response: method={request.method} "
                f"path={request.path_qs} "
                f"status={error.status} "
                f"content={error.text}"
            )
        raise

    if 400 <= response.status < 500:
        response_content = response.text if isinstance(response, web.Response) else ""
        _logger.warning(
            f"HTTP 4xx response: method={request.method} "
            f"path={request.path_qs} "
            f"status={response.status} "
            f"content={response_content}"
        )

    return response


async def init(controller_enabled: bool = False) -> None:
    global _runner

    app = web.Application(
        middlewares=[_log_4xx_requests_middleware, _pydantic_validation_middleware]
    )
    set_logger_level(logging.getLogger("aiohttp.web"), configs.http_server.log_level)
    set_logger_level(logging.getLogger("aiohttp.access"), configs.http_server.log_level)

    app.add_routes(base_routes)

    # Only the controller can receive action requests and serve the dashboard
    if controller_enabled:
        app.add_routes(alert_routes)
        app.add_routes(issue_routes)
        app.add_routes(monitor_routes)
        if configs.http_server.dashboard_enabled:
            app.add_routes(dashboard_routes)

    _runner = web.AppRunner(app)
    await _runner.setup()

    port = configs.http_server.port
    site = web.TCPSite(_runner, port=port)
    await site.start()

    _logger.info(f"Listening at port {port}")


async def wait_stop() -> None:
    global _runner
    await _runner.cleanup()

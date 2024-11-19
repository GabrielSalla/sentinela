import logging
import random
from typing import Any

import prometheus_client
from aiohttp import web

import src.components.controller.controller as controller
import src.components.executor.executor as executor
import src.registry as registry
from src.components.http_server.alert_routes import alert_routes
from src.components.http_server.issue_routes import issue_routes
from src.components.http_server.monitor_routes import monitor_routes
from src.configs import configs

_logger = logging.getLogger("api_server")

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
async def get_status(request):
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
async def get_metrics(request):
    """Return prometheus metrics"""
    response = web.Response(body=prometheus_client.generate_latest())
    response.content_type = prometheus_client.CONTENT_TYPE_LATEST
    return response


async def init(controller_enabled: bool = False):
    global _runner

    app = web.Application()
    app.add_routes(base_routes)

    # Only the controller can receive action requests
    if controller_enabled:
        app.add_routes(alert_routes)
        app.add_routes(issue_routes)
        app.add_routes(monitor_routes)

    _runner = web.AppRunner(app)
    await _runner.setup()

    port = configs.http_server["port"]
    site = web.TCPSite(_runner, port=port)
    await site.start()

    _logger.info(f"Listening at port {port}")


async def wait_stop():
    global _runner
    await _runner.cleanup()

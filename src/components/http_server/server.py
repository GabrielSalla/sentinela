import logging
import random
from pathlib import Path
from typing import Any

import prometheus_client
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

import components.controller.controller as controller
import components.executor.executor as executor
import registry as registry
from components.http_server.alert_routes import alert_routes
from components.http_server.issue_routes import issue_routes
from components.http_server.monitor_routes import monitor_routes
from configs import configs

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


@base_routes.get("/dashboard")
@base_routes.get("/dashboard/")
async def get_dashboard(request: Request) -> Response:
    """Serve the dashboard HTML page"""
    dashboard_path = Path(__file__).parent / "dashboard" / "index.html"

    try:
        with open(dashboard_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return web.Response(text=html_content, content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="Dashboard not found", status=404)


@base_routes.get("/dashboard/{path:.*}")
async def serve_dashboard_assets(request: Request) -> Response:
    """Serve dashboard static assets (CSS, JS files)"""
    try:
        asset_path = request.match_info["path"]
    except KeyError:
        return web.Response(text="Asset path not provided", status=400)

    try:
        if ".." in asset_path or asset_path.startswith("/"):
            return web.Response(text="Forbidden", status=403)

        full_path = Path(__file__).parent / "dashboard" / asset_path
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Determine content type based on file extension
        content_type = "text/plain"
        if asset_path.endswith(".css"):
            content_type = "text/css"
        elif asset_path.endswith(".js"):
            content_type = "application/javascript"
        elif asset_path.endswith(".html"):
            content_type = "text/html"

        return web.Response(text=content, content_type=content_type)
    except FileNotFoundError:
        return web.Response(text="Asset not found", status=404)
    except Exception as e:
        _logger.error(f"Error serving dashboard asset {asset_path}: {e}")
        return web.Response(text="Internal server error", status=500)


async def init(controller_enabled: bool = False) -> None:
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

    port = configs.http_server.port
    site = web.TCPSite(_runner, port=port)
    await site.start()

    _logger.info(f"Listening at port {port}")


async def wait_stop() -> None:
    global _runner
    await _runner.cleanup()

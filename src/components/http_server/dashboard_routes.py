import logging
from pathlib import Path

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

import commands as commands

EXTENSIONS_TYPE = {
    ".css": "text/css",
    ".js": "application/javascript",
    ".html": "text/html",
}

_logger = logging.getLogger("dashboard_routes")

dashboard_routes = web.RouteTableDef()
base_route = "/dashboard"

@dashboard_routes.get(base_route)
@dashboard_routes.get(base_route + "/")
async def get_dashboard(request: Request) -> Response:
    """Serve the dashboard page"""
    dashboard_path = Path(__file__).parent / "dashboard" / "index.html"

    with open(dashboard_path, "r") as file:
        html_content = file.read()
    return web.Response(text=html_content, content_type="text/html")


@dashboard_routes.get(base_route + "/{path:.*}")
async def serve_dashboard_assets(request: Request) -> Response:
    """Serve dashboard static assets"""
    asset_path = request.match_info["path"]

    if asset_path is None:
        return web.Response(text="Asset path not provided", status=400)

    if ".." in asset_path or asset_path.startswith("/"):
        return web.Response(text="Forbidden", status=403)

    path = Path(__file__).parent / "dashboard" / asset_path
    try:
        with open(path, "r") as file:
            content = file.read()
    except FileNotFoundError:
        return web.Response(text="Asset not found", status=404)

    content_type = EXTENSIONS_TYPE.get(path.suffix, "text/plain")
    return web.Response(text=content, content_type=content_type)

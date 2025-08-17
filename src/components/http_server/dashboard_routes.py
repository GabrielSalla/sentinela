import logging
from pathlib import Path

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

import commands as commands

DASHBOARD_FILES_PATH = Path(__file__).parent / "dashboard"
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
    dashboard_path = DASHBOARD_FILES_PATH / "index.html"

    with open(dashboard_path, "r") as file:
        html_content = file.read()
    return web.Response(text=html_content, content_type="text/html")


@dashboard_routes.get(base_route + "/{path:.*}")
@dashboard_routes.get(base_route + "/{path:.*}/")
async def get_asset(request: Request) -> Response:
    """Serve dashboard static assets"""
    asset_path = request.match_info["path"]

    path = DASHBOARD_FILES_PATH / asset_path
    try:
        with open(path, "r") as file:
            content = file.read()
    except FileNotFoundError:
        return web.Response(text="Asset not found", status=404)

    content_type = EXTENSIONS_TYPE.get(path.suffix, "text/plain")
    return web.Response(text=content, content_type=content_type)

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

import commands as commands

issue_routes = web.RouteTableDef()
base_route = "/issue"


@issue_routes.post(base_route + "/{issue_id}/drop")
@issue_routes.post(base_route + "/{issue_id}/drop/")
async def issue_drop(request: Request) -> Response:
    """Route to drop an issue"""
    issue_id = int(request.match_info["issue_id"])
    try:
        await commands.issue_drop(issue_id)
    except ValueError as error:
        return web.json_response({"status": "error", "message": str(error)}, status=404)

    success_response = {
        "status": "request_queued",
        "action": "issue_drop",
        "target_id": issue_id,
    }
    return web.json_response(success_response)

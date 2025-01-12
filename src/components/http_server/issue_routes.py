from aiohttp import web
from aiohttp.web_response import Response

import external_requests as external_requests
from models import Issue

issue_routes = web.RouteTableDef()
base_route = "/issue"


@issue_routes.post(base_route + "/{issue_id}/drop")
@issue_routes.post(base_route + "/{issue_id}/drop/")
async def issue_drop(request) -> Response:
    """Route to drop an issue"""
    issue_id = int(request.match_info["issue_id"])

    issue = await Issue.get_by_id(issue_id)
    if not issue:
        error_response = {"status": "error", "message": f"issue '{issue_id}' not found"}
        return web.json_response(error_response, status=404)

    await external_requests.issue_drop(issue_id)

    success_response = {
        "status": "request_queued",
        "action": "issue_drop",
        "target_id": issue_id,
    }
    return web.json_response(success_response)

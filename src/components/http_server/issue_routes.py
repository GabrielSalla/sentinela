from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from pydantic import BaseModel

import commands as commands
from components.http_server.command_config import (
    disabled_command_response,
    is_command_enabled,
)
from exceptions.http_server import IssueNotFoundError

issue_routes = web.RouteTableDef()
base_route = "/issue"


class _IssueIdPathParams(BaseModel):
    issue_id: int


@issue_routes.post(base_route + "/{issue_id}/drop")
@issue_routes.post(base_route + "/{issue_id}/drop/")
async def issue_drop(request: Request) -> Response:
    """Route to drop an issue"""
    if not is_command_enabled("issue_drop"):
        return disabled_command_response("issue_drop")

    params = _IssueIdPathParams.model_validate({"issue_id": request.match_info["issue_id"]})
    issue_id = params.issue_id
    try:
        await commands.issue_drop(issue_id)
    except IssueNotFoundError as e:
        return web.json_response({"status": "error", "message": str(e)}, status=404)

    success_response = {
        "status": "request_queued",
        "action": "issue_drop",
        "target_id": issue_id,
    }
    return web.json_response(success_response)

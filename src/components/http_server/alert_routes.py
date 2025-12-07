from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

import commands as commands
from models import Alert, Issue, IssueStatus
from utils.time import localize

alert_routes = web.RouteTableDef()
base_route = "/alert"


@alert_routes.get(base_route + "/{alert_id}")
@alert_routes.get(base_route + "/{alert_id}/")
async def get_alert(request: Request) -> Response:
    """Route to get the information for an alert"""
    alert_id = int(request.match_info["alert_id"])

    alert = await Alert.get_by_id(alert_id)
    if not alert:
        error_response = {"status": "error", "message": f"alert '{alert_id}' not found"}
        return web.json_response(error_response, status=404)

    response = {
        "id": alert.id,
        "status": alert.status.value,
        "acknowledged": alert.acknowledged,
        "locked": alert.locked,
        "priority": alert.priority,
        "acknowledge_priority": alert.acknowledge_priority,
        "can_acknowledge": alert.can_acknowledge,
        "can_lock": alert.can_lock,
        "can_solve": alert.can_solve,
        "created_at": localize(alert.created_at).strftime("%Y-%m-%d %H:%M:%S"),
    }
    return web.json_response(response)


@alert_routes.get(base_route + "/{alert_id}/issues")
@alert_routes.get(base_route + "/{alert_id}/issues/")
async def list_alert_active_issues(request: Request) -> Response:
    """List active issues for an alert"""
    alert_id = int(request.match_info["alert_id"])

    issues = await Issue.get_all(
        Issue.alert_id == alert_id,
        Issue.status == IssueStatus.active,
        order_by=[Issue.id],
    )

    response = [
        {
            "id": issue.id,
            "status": issue.status.value,
            "model_id": issue.model_id,
            "data": issue.data,
            "created_at": localize(issue.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for issue in issues
    ]
    return web.json_response(response)


@alert_routes.post(base_route + "/{alert_id}/acknowledge")
@alert_routes.post(base_route + "/{alert_id}/acknowledge/")
async def alert_acknowledge(request: Request) -> Response:
    """Route to acknowledge an alert"""
    alert_id = int(request.match_info["alert_id"])

    alert = await Alert.get_by_id(alert_id)
    if not alert:
        error_response = {"status": "error", "message": f"alert '{alert_id}' not found"}
        return web.json_response(error_response, status=404)

    await commands.alert_acknowledge(alert_id)

    success_response = {
        "status": "request_queued",
        "action": "alert_acknowledge",
        "target_id": alert_id,
    }
    return web.json_response(success_response)


@alert_routes.post(base_route + "/{alert_id}/lock")
@alert_routes.post(base_route + "/{alert_id}/lock/")
async def alert_lock(request: Request) -> Response:
    """Route to lock an alert"""
    alert_id = int(request.match_info["alert_id"])

    alert = await Alert.get_by_id(alert_id)
    if not alert:
        error_response = {"status": "error", "message": f"alert '{alert_id}' not found"}
        return web.json_response(error_response, status=404)

    await commands.alert_lock(alert_id)

    success_response = {
        "status": "request_queued",
        "action": "alert_lock",
        "target_id": alert_id,
    }
    return web.json_response(success_response)


@alert_routes.post(base_route + "/{alert_id}/solve")
@alert_routes.post(base_route + "/{alert_id}/solve/")
async def alert_solve(request: Request) -> Response:
    """Route to solve an alert's issues"""
    alert_id = int(request.match_info["alert_id"])

    alert = await Alert.get_by_id(alert_id)
    if not alert:
        error_response = {"status": "error", "message": f"alert '{alert_id}' not found"}
        return web.json_response(error_response, status=404)

    await commands.alert_solve(alert_id)

    success_response = {
        "status": "request_queued",
        "action": "alert_solve",
        "target_id": alert_id,
    }
    return web.json_response(success_response)

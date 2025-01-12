from aiohttp import web
from aiohttp.web_response import Response

import external_requests as external_requests
from models import Alert

alert_routes = web.RouteTableDef()
base_route = "/alert"


@alert_routes.post(base_route + "/{alert_id}/acknowledge")
@alert_routes.post(base_route + "/{alert_id}/acknowledge/")
async def alert_acknowledge(request) -> Response:
    """Route to acknowledge an alert"""
    alert_id = int(request.match_info["alert_id"])

    alert = await Alert.get_by_id(alert_id)
    if not alert:
        error_response = {"status": "error", "message": f"alert '{alert_id}' not found"}
        return web.json_response(error_response, status=404)

    await external_requests.alert_acknowledge(alert_id)

    success_response = {
        "status": "request_queued",
        "action": "alert_acknowledge",
        "target_id": alert_id,
    }
    return web.json_response(success_response)


@alert_routes.post(base_route + "/{alert_id}/lock")
@alert_routes.post(base_route + "/{alert_id}/lock/")
async def alert_lock(request) -> Response:
    """Route to lock an alert"""
    alert_id = int(request.match_info["alert_id"])

    alert = await Alert.get_by_id(alert_id)
    if not alert:
        error_response = {"status": "error", "message": f"alert '{alert_id}' not found"}
        return web.json_response(error_response, status=404)

    await external_requests.alert_lock(alert_id)

    success_response = {
        "status": "request_queued",
        "action": "alert_lock",
        "target_id": alert_id,
    }
    return web.json_response(success_response)


@alert_routes.post(base_route + "/{alert_id}/solve")
@alert_routes.post(base_route + "/{alert_id}/solve/")
async def alert_solve(request) -> Response:
    """Route to solve an alert's issues"""
    alert_id = int(request.match_info["alert_id"])

    alert = await Alert.get_by_id(alert_id)
    if not alert:
        error_response = {"status": "error", "message": f"alert '{alert_id}' not found"}
        return web.json_response(error_response, status=404)

    await external_requests.alert_solve(alert_id)

    success_response = {
        "status": "request_queued",
        "action": "alert_solve",
        "target_id": alert_id,
    }
    return web.json_response(success_response)

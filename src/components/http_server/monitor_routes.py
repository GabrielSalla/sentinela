import logging
import traceback
from collections import Counter
from typing import Any

import pydantic
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

import commands
from components.http_server.format_monitor_name import format_monitor_name
from components.monitors_loader import MonitorValidationError
from models import Alert, AlertStatus, CodeModule, Monitor
from utils.time import localize

_logger = logging.getLogger("monitor_routes")

monitor_routes = web.RouteTableDef()
base_route = "/monitor"


@monitor_routes.get(base_route + "/list")
@monitor_routes.get(base_route + "/list/")
async def list_monitors(request: Request) -> Response:
    """Route to list all monitors"""
    monitors = await Monitor.get_all()
    enabled_monitors = (monitor for monitor in monitors if monitor.enabled)

    active_alerts = await Alert.get_raw(
        columns=[Alert.monitor_id],
        column_filters=[
            Alert.status == AlertStatus.active,
            Alert.monitor_id.in_(monitor.id for monitor in enabled_monitors),
        ],
    )
    alerts_counter = Counter(alert.monitor_id for alert in active_alerts)

    response = [
        {
            "id": monitor.id,
            "name": monitor.name,
            "enabled": monitor.enabled,
            "active_alerts": alerts_counter.get(monitor.id, 0),
        }
        for monitor in monitors
    ]
    return web.json_response(response)


@monitor_routes.get(base_route + "/{monitor_id}/alerts")
@monitor_routes.get(base_route + "/{monitor_id}/alerts/")
async def list_monitor_active_alerts(request: Request) -> Response:
    """Route to list active alerts for a monitor"""
    monitor_id = int(request.match_info["monitor_id"])

    alerts = await Alert.get_all(
        Alert.monitor_id == monitor_id,
        Alert.status == AlertStatus.active,
        order_by=[Alert.id],
    )

    response = [
        {
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
        for alert in alerts
    ]
    return web.json_response(response)


@monitor_routes.get(base_route + "/{monitor_name}")
@monitor_routes.get(base_route + "/{monitor_name}/")
async def get_monitor(request: Request) -> Response:
    """Route to get a monitor by name"""
    monitor_name = request.match_info["monitor_name"]

    monitor = await Monitor.get(Monitor.name == monitor_name)

    if monitor is None:
        error_response = {
            "status": "monitor_not_found",
        }
        return web.json_response(error_response, status=404)

    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)

    if code_module is None:
        error_response = {
            "status": "monitor_code_not_found",
        }
        return web.json_response(error_response, status=404)

    success_response = {
        "id": monitor.id,
        "name": monitor.name,
        "enabled": monitor.enabled,
        "code": code_module.code,
        "additional_files": code_module.additional_files,
    }
    return web.json_response(success_response)


@monitor_routes.post(base_route + "/{monitor_name}/disable")
@monitor_routes.post(base_route + "/{monitor_name}/disable/")
async def monitor_disable(request: Request) -> Response:
    """Route to disable a monitor"""
    monitor_name = request.match_info["monitor_name"]

    try:
        await commands.disable_monitor(monitor_name)
        success_response = {
            "status": "monitor_disabled",
            "monitor_name": monitor_name,
        }
        return web.json_response(success_response)
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
        }
        _logger.error(traceback.format_exc().strip())
        return web.json_response(error_response, status=400)


@monitor_routes.post(base_route + "/{monitor_name}/enable")
@monitor_routes.post(base_route + "/{monitor_name}/enable/")
async def monitor_enable(request: Request) -> Response:
    """Route to enable a monitor"""
    monitor_name = request.match_info["monitor_name"]

    try:
        await commands.enable_monitor(monitor_name)
        success_response = {
            "status": "monitor_enabled",
            "monitor_name": monitor_name,
        }
        return web.json_response(success_response)
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
        }
        _logger.error(traceback.format_exc().strip())
        return web.json_response(error_response, status=400)


@monitor_routes.post(base_route + "/validate")
@monitor_routes.post(base_route + "/validate/")
async def monitor_validate(request: Request) -> Response:
    """Route to check a monitor without registering it"""
    request_data = await request.json()
    monitor_code = request_data.get("monitor_code")

    error_response: dict[str, str | list[Any]]

    if monitor_code is None:
        error_response = {"status": "error", "message": "'monitor_code' parameter is required"}
        return web.json_response(error_response, status=400)

    try:
        await commands.monitor_code_validate(monitor_code)
    except pydantic.ValidationError as e:
        error_response = {
            "status": "error",
            "message": "Type validation error",
            "error": [
                {
                    "loc": list(error["loc"]),
                    "type": error["type"],
                    "msg": error["msg"],
                }
                for error in e.errors()
            ],
        }
        return web.json_response(error_response, status=400)
    except MonitorValidationError as e:
        error_response = {
            "status": "error",
            "message": "Module didn't pass check",
            "error": e.get_error_message(include_monitor_name=False),
        }
        return web.json_response(error_response, status=400)
    except Exception as e:
        error_response = {"status": "error", "error": str(e)}
        _logger.error(traceback.format_exc().strip())
        return web.json_response(error_response, status=400)

    success_response = {"status": "monitor_validated"}
    return web.json_response(success_response)


@monitor_routes.post(base_route + "/format_name/{monitor_name}")
@monitor_routes.post(base_route + "/format_name/{monitor_name}/")
async def format_name(request: Request) -> Response:
    """Route to format a monitor name"""
    monitor_name = request.match_info["monitor_name"]
    return web.json_response(
        {"name": monitor_name, "formatted_name": format_monitor_name(monitor_name)}
    )


@monitor_routes.post(base_route + "/register/{monitor_name}")
@monitor_routes.post(base_route + "/register/{monitor_name}/")
async def monitor_register(request: Request) -> Response:
    """Route to register a monitor"""
    monitor_name = request.match_info["monitor_name"]

    request_data = await request.json()
    monitor_code = request_data.get("monitor_code")
    additional_files = request_data.get("additional_files", {})

    error_response: dict[str, str | list[Any]]

    if monitor_code is None:
        error_response = {"status": "error", "message": "'monitor_code' parameter is required"}
        return web.json_response(error_response, status=400)

    monitor_name = format_monitor_name(monitor_name)

    try:
        monitor = await commands.monitor_register(monitor_name, monitor_code, additional_files)
    except pydantic.ValidationError as e:
        error_response = {
            "status": "error",
            "message": "Type validation error",
            "error": [
                {
                    "loc": list(error["loc"]),
                    "type": error["type"],
                    "msg": error["msg"],
                }
                for error in e.errors()
            ],
        }
        return web.json_response(error_response, status=400)
    except MonitorValidationError as e:
        error_response = {
            "status": "error",
            "message": "Module didn't pass check",
            "error": e.get_error_message(),
        }
        return web.json_response(error_response, status=400)
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
        }
        _logger.error(traceback.format_exc().strip())
        return web.json_response(error_response, status=400)

    success_response = {
        "status": "monitor_registered",
        "monitor_id": monitor.id,
    }
    return web.json_response(success_response)

import logging
import traceback
from typing import Any

import pydantic
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

import commands as commands
from components.monitors_loader import MonitorValidationError
from models import CodeModule, Monitor

_logger = logging.getLogger("monitor_routes")


monitor_routes = web.RouteTableDef()
base_route = "/monitor"


@monitor_routes.get(base_route + "/list")
@monitor_routes.get(base_route + "/list/")
async def list_monitors(request: Request) -> Response:
    monitors = await Monitor.get_raw(columns=[Monitor.id, Monitor.name, Monitor.enabled])
    response = [
        {
            "id": monitor[0],
            "name": monitor[1],
            "enabled": monitor[2],
        }
        for monitor in monitors
    ]
    return web.json_response(response)


@monitor_routes.get(base_route + "/{monitor_name}")
@monitor_routes.get(base_route + "/{monitor_name}/")
async def get_monitor(request: Request) -> Response:
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
            "error": e.get_error_message(),
        }
        return web.json_response(error_response, status=400)
    except Exception as e:
        error_response = {"status": "error", "error": str(e)}
        _logger.error(traceback.format_exc().strip())
        return web.json_response(error_response, status=400)

    success_response = {"status": "monitor_validated"}
    return web.json_response(success_response)


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

    # Remove any dots from the monitor name
    monitor_name = monitor_name.replace(".", "_")

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

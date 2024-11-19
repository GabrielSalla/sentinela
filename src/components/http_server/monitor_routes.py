import logging
import traceback

from aiohttp import web
from dataclass_type_validator import TypeValidationError

import src.external_requests as external_requests
from src.components.monitors_loader import MonitorValidationError

_logger = logging.getLogger("monitor_routes")


monitor_routes = web.RouteTableDef()
base_route = "/monitor"


@monitor_routes.post(base_route + "/{monitor_name}/disable")
@monitor_routes.post(base_route + "/{monitor_name}/disable/")
async def monitor_disable(request):
    """Route to disable a monitor"""
    monitor_name = request.match_info["monitor_name"]

    try:
        await external_requests.disable_monitor(monitor_name)
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
async def monitor_enable(request):
    """Route to enable a monitor"""
    monitor_name = request.match_info["monitor_name"]

    try:
        await external_requests.enable_monitor(monitor_name)
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


@monitor_routes.post(base_route + "/register/{monitor_name}")
@monitor_routes.post(base_route + "/register/{monitor_name}/")
async def monitor_register(request):
    """Route to register a monitor"""
    request_data = await request.json()

    monitor_name = request.match_info["monitor_name"]
    monitor_code = request_data.get("monitor_code")
    additional_files = request_data.get("additional_files", {})

    if monitor_code is None:
        error_response = {
            "status": "error",
            "message": "'monitor_code' parameter is required"
        }
        return web.json_response(error_response, status=400)

    # Remove any dots from the monitor name
    monitor_name = monitor_name.replace(".", "_")

    try:
        monitor = await external_requests.monitor_register(
            monitor_name, monitor_code, additional_files
        )
    except TypeValidationError as e:
        error_response = {
            "status": "error",
            "message": "Type validation error",
            "error": e.errors,
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

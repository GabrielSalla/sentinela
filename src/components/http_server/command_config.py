from aiohttp import web
from aiohttp.web_response import Response

from configs import configs


def is_command_enabled(command: str) -> bool:
    """Return whether a command can be executed"""
    command_config = configs.http_server.commands.get(command, None)
    if command_config is None:
        return True
    return command_config.enabled


def disabled_command_response(command: str) -> Response:
    """Return a response indicating that a command is disabled"""
    return web.json_response(
        {
            "status": "error",
            "message": f"Command `{command}` is disabled",
            "error": f"Command `{command}` is disabled in the configuration",
        },
        status=403,
    )

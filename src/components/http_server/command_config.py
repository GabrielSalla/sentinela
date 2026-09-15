from aiohttp import web
from aiohttp.web_response import Response

from configs import configs
from models import UserRole


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


def is_command_allowed(command: str, role: UserRole) -> bool:
    """Return whether a role can execute a command. Admin can execute any command"""
    if role == UserRole.admin:
        return True
    command_config = configs.http_server.commands.get(command, None)
    if command_config is None:
        return True
    return command_config.required_role == role.name


def forbidden_command_response() -> Response:
    """Return a response indicating that the user role cannot execute a command"""
    return web.json_response({"status": "forbidden"}, status=403)

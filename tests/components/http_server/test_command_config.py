import pytest
from aiohttp import web

from components.http_server import command_config
from configs import CommandConfig, configs
from models import UserRole


@pytest.mark.parametrize(
    "commands, expected",
    [
        ({}, True),
        ({"alert_acknowledge": CommandConfig(enabled=True)}, True),
        ({"alert_acknowledge": CommandConfig(enabled=False)}, False),
    ],
)
def test_is_command_enabled(monkeypatch, commands, expected):
    """'is_command_enabled' should return whether the command is enabled in the configuration"""
    monkeypatch.setattr(configs.http_server, "commands", commands)

    assert command_config.is_command_enabled("alert_acknowledge") is expected


def test_disabled_command_response():
    """'disabled_command_response' should return a forbidden response for a disabled command"""
    response = command_config.disabled_command_response("alert_acknowledge")

    assert isinstance(response, web.Response)
    assert response.status == 403
    assert response.text == (
        '{"status": "error", "message": "Command `alert_acknowledge` is disabled", '
        '"error": "Command `alert_acknowledge` is disabled in the configuration"}'
    )


@pytest.mark.parametrize(
    "commands, role, expected",
    [
        ({}, UserRole.user, True),
        ({}, UserRole.admin, True),
        ({"alert_acknowledge": CommandConfig(required_role="user")}, UserRole.user, True),
        ({"alert_acknowledge": CommandConfig(required_role="user")}, UserRole.admin, True),
        ({"alert_acknowledge": CommandConfig(required_role="admin")}, UserRole.user, False),
        ({"alert_acknowledge": CommandConfig(required_role="admin")}, UserRole.admin, True),
    ],
)
def test_is_command_allowed(monkeypatch, commands, role, expected):
    """'is_command_allowed' should return whether the role can execute the command"""
    monkeypatch.setattr(configs.http_server, "commands", commands)

    assert command_config.is_command_allowed("alert_acknowledge", role) is expected


def test_forbidden_command_response():
    """'forbidden_command_response' should return a forbidden response"""
    response = command_config.forbidden_command_response()

    assert isinstance(response, web.Response)
    assert response.status == 403
    assert response.text == '{"status": "forbidden"}'

import pytest
from aiohttp import web

from components.http_server import command_config
from configs import CommandConfig, configs


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

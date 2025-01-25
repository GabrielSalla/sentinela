import json
import logging
import re
import time

import pytest

import utils.log as log
from configs import FriendlyLogConfig, JsonLogConfig, configs


def set_friendly_formatter(monkeypatch, log_format: str | None) -> None:
    """Set the friendly formatter for the logging configuration"""
    monkeypatch.setattr(logging.root, "handlers", [])
    monkeypatch.setattr(configs, "logging", FriendlyLogConfig(mode="friendly", format=log_format))
    log.setup()


def set_json_formatter(monkeypatch, fields: dict[str, str] | None) -> None:
    """Set the JSON formatter for the logging configuration"""
    monkeypatch.setattr(logging.root, "handlers", [])
    monkeypatch.setattr(configs, "logging", JsonLogConfig(mode="json", fields=fields))
    log.setup()


@pytest.mark.parametrize(
    "log_format",
    [
        "%(asctime)s %(levelname)s: %(message)s",
        "%(asctime)s %(levelname)s %(message)s",
        "%(levelname)s %(message)s",
    ],
)
@pytest.mark.parametrize("level", ["info", "warning", "error"])
def test_friendly_formatter(capsys, monkeypatch, log_format, level):
    """'friendly' formatter should format the log message in a friendly way using the provided log
    format"""
    set_friendly_formatter(monkeypatch, log_format)

    logger = logging.getLogger("test_friendly_formatter")
    message = f"message for '{level}' level"
    getattr(logger, level)(message)

    captured_message = capsys.readouterr().err.strip()

    expected_content = log_format.replace("%(asctime)s", r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d*")
    expected_content = expected_content.replace("%(levelname)s", level.upper())
    expected_content = expected_content.replace("%(message)s", message)
    expected_pattern = "\x1b" + r".*m" + expected_content + "\x1b" + r"\[0m"

    match = re.match(expected_pattern, captured_message)
    assert match is not None


def test_friendly_formatter_no_log_format(capsys, monkeypatch):
    """'friendly' formatter should format the log message in a friendly way using a default log
    format if none was provided"""
    set_friendly_formatter(monkeypatch, None)

    logger = logging.getLogger("test_friendly_formatter_no_log_format")
    message = "message for 'info' level"
    logger.info(message)

    captured_message = capsys.readouterr().err.strip()

    log_format = "%(asctime)s \\[%(levelname)s\\]: %(message)s"
    expected_content = log_format.replace("%(asctime)s", r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d*")
    expected_content = expected_content.replace("%(levelname)s", "INFO")
    expected_content = expected_content.replace("%(message)s", message)
    expected_pattern = "\x1b" + r".*m" + expected_content + "\x1b" + r"\[0m"

    match = re.match(expected_pattern, captured_message)
    assert match is not None


@pytest.mark.parametrize(
    "fields",
    [
        {"message": "message"},
        {"some_message": "message"},
        {"message": "message", "level": "levelname"},
        {"some_message": "message", "log_level": "levelname"},
        {"message": "message", "level": "levelname", "time": "created"},
        {"some_message": "message", "log_level": "levelname", "timestamp": "created"},
    ],
)
@pytest.mark.parametrize("level", ["info", "warning", "error"])
def test_json_formatter(capsys, monkeypatch, fields, level):
    """'json' formatter should format the log message as a JSON object using the provided fields"""
    set_json_formatter(monkeypatch, fields)

    logger = logging.getLogger("test_json_formatter")
    message = f"message for '{level}' level"
    getattr(logger, level)(message)

    captured_message = capsys.readouterr().err.strip()
    message_dict = json.loads(captured_message)

    for key, value in message_dict.items():
        if key in ("message", "some_message"):
            assert value == message
        elif key in ("level", "log_level"):
            assert value == level.upper()
        elif key in ("time", "timestamp"):
            assert isinstance(value, float)
            assert value > time.time() - 0.001
        else:
            assert False, "Unexpected field in log"


def test_json_formatter_no_fields(capsys, monkeypatch):
    """'json' formatter should format the log message as a JSON object only with the 'message' field
    if no fields were provided"""
    set_json_formatter(monkeypatch, None)

    logger = logging.getLogger("test_json_formatter_no_fields")
    message = "message for 'info' level"
    logger.info(message)

    captured_message = capsys.readouterr().err.strip()
    message_dict = json.loads(captured_message)

    assert message_dict == {"message": "message for 'info' level"}

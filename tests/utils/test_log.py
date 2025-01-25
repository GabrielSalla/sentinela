import json
import logging
import re

import pytest

import utils.log as log
from configs import FriendlyLogConfig, JsonLogConfig, configs

TIMESTAMP_PATTERN = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d*"


@pytest.fixture(scope="module", autouse=True)
def reset_logging(monkeypatch_module):
    """Reset the logging configuration during the log tests"""
    monkeypatch_module.setattr(logging.root, "handlers", [])


def set_friendly_formatter(monkeypatch, log_format: str) -> None:
    """Set the friendly formatter for the logging configuration"""
    monkeypatch.setattr(configs, "logging", FriendlyLogConfig(mode="friendly", format=log_format))
    log.setup()


def set_json_formatter(monkeypatch, fields: dict[str, str]) -> None:
    """Set the JSON formatter for the logging configuration"""
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
def test_friendly_formatter(caplog, monkeypatch, log_format, level):
    """'friendly' formatter should format the log message in a friendly way using the provided log
    format"""
    set_friendly_formatter(monkeypatch, log_format)

    logger = logging.getLogger("test_friendly_formatter")
    message = f"message for '{level}' level"
    getattr(logger, level)(message)

    expected_levelname = level.upper()
    log_format = log_format.format(asctime=TIMESTAMP_PATTERN)

    match = re.match(
        log_format.format(levelname=expected_levelname, message=message),
        caplog.records[0].message,
    )
    assert match is not None


@pytest.mark.parametrize(
    "fields",
    [
        {"message": "message"},
        {"some_message": "message"},
        {"message": "message", "level": "level"},
        {"some_message": "message", "log_level": "level"},
        {"message": "message", "level": "level", "time": "asctime"},
        {"some_message": "message", "log_level": "level", "timestamp": "asctime"},

    ],
)
@pytest.mark.parametrize("level", ["info", "warning", "error"])
def test_json_formatter(caplog, monkeypatch, fields, level):
    """'json' formatter should format the log message as a JSON object using the provided fields"""
    set_json_formatter(monkeypatch, fields)

    logger = logging.getLogger("test_json_formatter")
    message = f"message for '{level}' level"
    getattr(logger, level)(message)

    log_info = json.loads(caplog.records[0].message)

    for key, value in log_info.items():
        if key in ("message", "some_message"):
            assert value == message
        elif key in ("level", "log_level"):
            assert value == level.upper()
        elif key in ("time", "timestamp"):
            match = re.match(TIMESTAMP_PATTERN, value)
            assert match is not None
        else:
            assert False, "Unexpected field in log"

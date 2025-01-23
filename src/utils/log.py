import json
import logging

from configs import configs

GREY = "\x1b[38;20m"
YELLOW = "\x1b[33;20m"
RED = "\x1b[31;20m"
BOLD_RED = "\x1b[31;1m"
RESET = "\x1b[0m"
LOG_FORMAT = configs.logging["format"]

FORMATS = {
    logging.DEBUG: GREY + LOG_FORMAT + RESET,
    logging.INFO: GREY + LOG_FORMAT + RESET,
    logging.WARNING: YELLOW + LOG_FORMAT + RESET,
    logging.ERROR: RED + LOG_FORMAT + RESET,
    logging.CRITICAL: BOLD_RED + LOG_FORMAT + RESET,
}


class FriendlyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_format = FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_format)
        return formatter.format(record)


class JsonFormatter(logging.Formatter):
    def __init__(self) -> None:
        self.fields = configs.logging["fields"] or {"message": "message"}
        self.datefmt = None

    def format(self, record: logging.LogRecord) -> str:
        """
        Mostly the same as the parent's class method, the difference being that a dict is
        manipulated and dumped as JSON instead of a string.
        """
        record.message = record.getMessage()
        message_dict = {
            key: record.__dict__[record_info] for key, record_info in self.fields.items()
        }

        if record.exc_info:
            record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            message_dict["exception"] = record.exc_text

        if record.stack_info:
            message_dict["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(message_dict, default=str)


def setup() -> None:
    """Setup the logging"""
    stream = logging.StreamHandler()
    stream.setLevel(logging.INFO)
    if configs.logging["mode"] == "friendly":
        stream.setFormatter(FriendlyFormatter())
    elif configs.logging["mode"] == "json":
        stream.setFormatter(JsonFormatter())

    logging.basicConfig(level=logging.INFO, handlers=[stream])

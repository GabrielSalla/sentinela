import json
import logging

from configs import configs


class FriendlyFormatter(logging.Formatter):
    GREY = "\x1b[38;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET_COLOR = "\x1b[0m"

    COLOR_FORMAT = {
        logging.DEBUG: (GREY, RESET_COLOR),
        logging.INFO: (GREY, RESET_COLOR),
        logging.WARNING: (YELLOW, RESET_COLOR),
        logging.ERROR: (RED, RESET_COLOR),
        logging.CRITICAL: (BOLD_RED, RESET_COLOR),
    }

    _log_format: str

    def __init__(self, log_format: str | None = None) -> None:
        """Initialize the log formatter."""
        if log_format is None:
            log_format = "%(asctime)s [%(levelname)s]: %(message)s"

        self._log_format = log_format

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record in a friendly way"""
        prefix, suffix = self.COLOR_FORMAT.get(record.levelno, ("", ""))

        formatter = logging.Formatter(self._log_format)
        return prefix + formatter.format(record) + suffix


class JsonFormatter(logging.Formatter):
    fields: dict[str, str]

    def __init__(self, fields: dict[str, str] | None = None) -> None:
        """Initialize the JSON log formatter."""
        if fields is None:
            fields = {"message": "message"}

        self.fields = fields

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON object"""
        record.message = record.getMessage()
        message_dict = {
            key: getattr(record, record_field) for key, record_field in self.fields.items()
        }

        if record.exc_info:  # pragma: no cover
            message_dict["exception"] = self.formatException(record.exc_info)

        if record.stack_info:  # pragma: no cover
            message_dict["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(message_dict, default=str)


def setup() -> None:
    """Setup the logging"""
    stream = logging.StreamHandler()
    stream.setLevel(logging.INFO)
    if configs.logging.mode == "friendly":
        stream.setFormatter(FriendlyFormatter(configs.logging.format))
    elif configs.logging.mode == "json":
        stream.setFormatter(JsonFormatter(configs.logging.fields))
    else:
        raise ValueError(f"Unknown logging mode: '{configs.logging.mode}'")

    logging.basicConfig(level=logging.INFO, handlers=[stream])

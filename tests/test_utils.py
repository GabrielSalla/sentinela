import re


def assert_message_in_log(caplog, pattern: str, count: int = 1, regex: bool = False):
    """Check if the logs contain the specified message the specified number of times"""
    found = 0
    for record in caplog.records:
        if regex:
            message_match = re.search(pattern, record.message)
            exception_match = record.exc_text and re.search(pattern, record.exc_text)
            if message_match or exception_match:
                found += 1
        else:
            if pattern in record.message or (record.exc_text and pattern in record.exc_text):
                found += 1
    if found != count:
        assert False, f"Expected {count} log messages '{pattern}', found {found}"


def assert_message_not_in_log(caplog, pattern: str, regex: bool = False):
    """Check if the logs do not contain the specified message"""
    for record in caplog.records:
        if regex:
            message_match = re.search(pattern, record.message)
            exception_match = record.exc_text and re.search(pattern, record.exc_text)
            if message_match or exception_match:
                assert False, f"Found log message: {pattern}"
        else:
            if pattern in record.message or (record.exc_text and pattern in record.exc_text):
                assert False, f"Found log message: {pattern}"

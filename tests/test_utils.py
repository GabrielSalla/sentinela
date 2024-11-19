import re


def assert_message_in_log(caplog, pattern: str, count: int = 1, regex: bool = False):
    """Check if the logs contain the specified message the specified number of times"""
    found = 0
    for record in caplog.records:
        if regex:
            if re.search(pattern, record.message):
                found += 1
        else:
            if pattern in record.message:
                found += 1
    if found != count:
        assert False, f"Expected {count} log messages '{pattern}', found {found}"


def assert_message_not_in_log(caplog, pattern: str, regex: bool = False):
    """Check if the logs do not contain the specified message"""
    for record in caplog.records:
        if regex:
            if re.search(pattern, record.message):
                assert False, f"Found log message: {pattern}"
        else:
            if pattern in record.message:
                assert False, f"Found log message: {pattern}"

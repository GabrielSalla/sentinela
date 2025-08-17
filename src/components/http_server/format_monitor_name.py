import re


def format_monitor_name(monitor_name: str) -> str:
    """Format the monitor name"""
    monitor_name = re.sub(r"[\. ]", "_", monitor_name.lower())
    monitor_name = re.sub(r"[^\w_]", "", monitor_name)
    return re.sub(r"_{2,}", "_", monitor_name).strip("_")

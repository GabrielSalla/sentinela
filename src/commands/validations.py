from models import Alert, Issue, Monitor


async def validate_monitor_request(monitor_name: str) -> Monitor:
    """Validate a monitor request target"""
    monitor = await Monitor.get(Monitor.name == monitor_name)
    if monitor is None:
        raise ValueError(f"Monitor '{monitor_name}' not found")
    return monitor


async def validate_alert_request(alert_id: int) -> Alert:
    """Validate an alert request target"""
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        raise ValueError(f"Alert '{alert_id}' not found")
    return alert


async def validate_issue_request(issue_id: int) -> Issue:
    """Validate an issue request target"""
    issue = await Issue.get_by_id(issue_id)
    if issue is None:
        raise ValueError(f"Issue '{issue_id}' not found")
    return issue

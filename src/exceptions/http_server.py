from .base import BaseSentinelaException


class MonitorNotFoundError(BaseSentinelaException):
    """Exception raised when a monitor is not found"""

    _monitor_name: str

    def __init__(self, monitor_name: str):
        self._monitor_name = monitor_name
        super().__init__(monitor_name)

    def __str__(self) -> str:
        return f"Monitor '{self._monitor_name}' not found"


class AlertNotFoundError(BaseSentinelaException):
    """Exception raised when an alert is not found"""

    _alert_id: int

    def __init__(self, alert_id: int):
        self._alert_id = alert_id
        super().__init__(alert_id)

    def __str__(self) -> str:
        return f"Alert '{self._alert_id}' not found"


class IssueNotFoundError(BaseSentinelaException):
    """Exception raised when an issue is not found"""

    _issue_id: int

    def __init__(self, issue_id: int):
        self._issue_id = issue_id
        super().__init__(issue_id)

    def __str__(self) -> str:
        return f"Issue '{self._issue_id}' not found"

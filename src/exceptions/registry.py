from .base import BaseSentinelaException


class MonitorsLoadError(BaseSentinelaException):
    """Exception raised when monitors fail to load in time"""

    pass


class MonitorNotRegisteredError(BaseSentinelaException):
    """Exception raised when a monitor is not registered"""

    pass

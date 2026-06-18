from .base import InitializationError


class PendingDatabaseUpgrade(InitializationError):
    """Exception raised when database schema is outdated"""

    pass

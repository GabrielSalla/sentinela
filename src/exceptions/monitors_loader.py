class MonitorValidationError(Exception):
    errors_found: list[str]

    def __init__(self, monitor_name: str, errors_found: list[str], *args: object) -> None:
        super().__init__(*args)
        self.monitor_name = monitor_name
        self.errors_found = errors_found

    def get_error_message(self, include_monitor_name: bool = True) -> str:
        """Get the error message for the module validation errors"""
        if include_monitor_name:
            error_message = f"Monitor '{self.monitor_name}' has the following errors:\n  "
        else:
            error_message = "Monitor has the following errors:\n  "
        error_message += "\n  ".join(self.errors_found)
        return error_message

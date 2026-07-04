from .base import BaseSentinelaException


class NestedImport(BaseSentinelaException):
    """Exception raised when there're imports being performed inside functions"""

    function_name: str

    def __init__(self, function_name: str):
        self.function_name = function_name
        super().__init__()

    def __str__(self) -> str:
        return f"Nested import found inside function {self.function_name!r}"


class ProhibitedImport(BaseSentinelaException):
    """Exception raised when a prohibited module is imported"""

    module_name: str

    def __init__(self, module_name: str):
        self.module_name = module_name
        super().__init__()

    def __str__(self) -> str:
        return f"Prohibited import {self.module_name!r}"

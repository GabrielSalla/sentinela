from .base import BaseSentinelaException


class NestedImport(BaseSentinelaException):
    """Exception raised when there're imports being performed inside functions"""

    module_name: str

    def __init__(self, module_name: str):
        self.module_name = module_name
        super().__init__()

    def __str__(self) -> str:
        return f"Import found inside function {self.module_name!r}"



class ProhibitedImport(BaseSentinelaException):
    """Exception raised when a prohibited import is being executed"""

    module_name: str

    def __init__(self, module_name: str):
        self.module_name = module_name
        super().__init__()

    def __str__(self) -> str:
        return f"Prohibited import {self.module_name!r}"

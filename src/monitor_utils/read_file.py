import traceback
from pathlib import Path
from typing import Any


def read_file(file_name: str, mode: str = "r") -> Any:
    """Read a file relative to where the function was called"""
    if mode not in ["r", "rb"]:
        raise ValueError("Only 'r' and 'rb' modes are allowed")

    stack = traceback.extract_stack()
    file_path = Path(stack[-2].filename).parent / file_name

    with open(file_path, mode) as file:
        return file.read()

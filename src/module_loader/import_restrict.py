"""
This module provides tools designed to reduce the risk of unauthorized module access by preventing
monitors from importing restricted modules.
For example, without these protections, a monitor could import the 'internal_database' module and
directly access the production database or use the 'os' module to read sensitive environment
variables.
However, this mechanism should be considered an error prevention measure rather than a complete
security solution. It is not foolproof, and a user intentionally attempting to bypass these
restrictions may still find ways to circumvent them.
"""

import ast
import builtins
import importlib
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Generator

from exceptions.module_loader import NestedImport, ProhibitedImport

ALLOWED_IMPORTS = {"monitor_utils", "plugins"}
BANNED_IMPORTS = {"importlib", "os", "sys"}
SOURCE_FOLDERS = {path.stem for path in Path("src").iterdir() if path.is_dir()}
PROHIBITED_IMPORTS = BANNED_IMPORTS.union(SOURCE_FOLDERS).difference(ALLOWED_IMPORTS)


def scan_nested_imports(module_tree: ast.Module) -> None:
    """Scan for nested imports (imports inside functions), which is not allowed"""
    for node in ast.walk(module_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                raise_conditions = (
                    isinstance(child, (ast.Import, ast.ImportFrom)),
                    (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id == "__import__"
                    ),
                )
                if any(raise_conditions):
                    raise NestedImport(node.name)


def scan_imports(module_tree: ast.Module) -> None:
    """Scan the top level imports for prohibited modules"""
    for node in module_tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Extract the module name: 'os.path' -> 'os'
                module = alias.name.split(".")[0]
                if module in PROHIBITED_IMPORTS:
                    raise ProhibitedImport(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module is None:  # pragma: no cover
                continue
            # Extract the module name: 'os.path' -> 'os'
            module = node.module.split(".")[0]
            if module in PROHIBITED_IMPORTS:
                raise ProhibitedImport(node.module)


@contextmanager
def restrict_imports() -> Generator[None, None, None]:
    """Wrap the import functions into validators to block unauthorized module access"""
    # Overwrite 'builtins.__import__'
    original_builtins_import = builtins.__import__

    def builtins_import_wrapper(*args, **kwargs) -> ModuleType:
        # Extract the module name: 'os.path' -> 'os'
        module = kwargs.get("name", args[0]).split(".")[0]
        if module in PROHIBITED_IMPORTS:
            raise ProhibitedImport(module)
        return original_builtins_import(*args, **kwargs)

    builtins.__import__ = builtins_import_wrapper

    # Overwrite 'importlib.import_module'
    original_importlib_import_module = importlib.import_module

    def importlib_import_module_wrapper(*args, **kwargs) -> ModuleType:
        # Extract the module name: 'os.path' -> 'os'
        module = kwargs.get("name", args[0]).split(".")[0]
        if module in PROHIBITED_IMPORTS:
            raise ProhibitedImport(module)
        return original_importlib_import_module(*args, **kwargs)

    importlib.import_module = importlib_import_module_wrapper

    try:
        yield
    finally:
        # Revert the changes
        builtins.__import__ = original_builtins_import
        importlib.import_module = original_importlib_import_module

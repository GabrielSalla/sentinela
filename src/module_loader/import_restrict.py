"""
This module provides tools designed to reduce the risk of unauthorized module access by preventing
monitors from importing restricted modules.
For example, without these protections, a monitor could import the 'internal_database' module and
directly access the production database or use the 'os' module to read sensitive environment
variables.
However, this mechanism should be considered an error prevention measure rather than a complete
security solution, as a user intentionally attempting to bypass these restrictions may still find
ways to circumvent them.
"""

import ast
import builtins
import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Callable, Generator, ParamSpec

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


P = ParamSpec("P")


def _wrap(original_function: Callable[P, ModuleType], base_path: Path) -> Callable[P, ModuleType]:
    """Wraps the import function in a validation logic that tries to prevent importing prohibited
    modules. The restriction is only made at the module root level, ignoring imports done by deeper
    modules"""

    def _import_wrapper(*args: P.args, **kwargs: P.kwargs) -> ModuleType:
        """Checks if the module can be imported, raising 'ProhibitedImport' when the monitor is
        prohibited"""
        # Check the first 3 frames for the module 'base_path'. Only the imports being done by the
        # files in the current path will be validated
        for stack_level in range(1, 4):
            stack_frame = sys._getframe(stack_level)

            if Path(stack_frame.f_code.co_filename).is_relative_to(base_path.absolute()):
                # Extract the module name: 'os.path' -> 'os'
                param_import = kwargs.get("name", args[0])

                if param_import is None:
                    raise ValueError(f"Error importing module {str(param_import)!r}")

                module_name_import = str(param_import).split(".")[0]

                if module_name_import in PROHIBITED_IMPORTS:
                    raise ProhibitedImport(module_name_import)

                break

        return original_function(*args, **kwargs)

    return _import_wrapper


@contextmanager
def prohibit_imports(base_path: Path) -> Generator[None, None, None]:
    """Wrap the import functions into a validator to block unauthorized module access"""
    # Wrap the 'builtins.__import__' function
    original_builtins_import = builtins.__import__
    builtins.__import__ = _wrap(original_builtins_import, base_path)

    # Wrap the 'importlib.import_module' function
    original_importlib_import_module = importlib.import_module
    importlib.import_module = _wrap(original_importlib_import_module, base_path)

    try:
        yield
    finally:
        # Revert the changes
        builtins.__import__ = original_builtins_import
        importlib.import_module = original_importlib_import_module

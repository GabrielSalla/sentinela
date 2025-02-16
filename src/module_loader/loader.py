import importlib
import logging
import os
import re
import sys
import time
from functools import cache
from pathlib import Path
from types import ModuleType

_logger = logging.getLogger("loader")

RELATIVE_PATH = "src"
MODULES_PATH = "_monitors"


@cache
def init_modules_path(path: Path) -> None:
    """Create a path if it doesn't exist, including the '__init__.py' file in it, as it's required
    to import the modules that will be in it"""
    if not path.exists():
        os.makedirs(path)
        init_file = path / "__init__.py"
        init_file.touch()


def create_module_files(
    module_name: str,
    module_code: str,
    base_path: str | None = None,
    additional_files: dict[str, str] | None = None,
) -> Path:
    """Create a module file with the given code and additional files, returning the module path.
    The files must be created relative to the "src" directory"""
    if base_path is None:
        base_path = MODULES_PATH

    base_module_path = Path(RELATIVE_PATH) / base_path
    init_modules_path(base_module_path)

    module_name = module_name.replace(".", "_")
    module_base_path = base_module_path / module_name
    os.makedirs(module_base_path, exist_ok=True)
    init_file = module_base_path / "__init__.py"
    init_file.touch()

    # Write the code file
    module_path = module_base_path / f"{module_name}.py"
    with open(module_path, "w") as temp_module:
        temp_module.write(module_code)

    # Write the additional files
    if additional_files is not None:
        for file_name, file_content in additional_files.items():
            file_path = module_base_path / file_name
            with open(file_path, "w") as file:
                file.write(file_content)

    # Return the path relative to "src" as it's the path used to import the module
    return module_path.relative_to(RELATIVE_PATH)


def make_module_name(module_path: Path) -> str:
    """Make a module name from a path"""
    return re.sub(r"\.py$", "", module_path.as_posix().replace("/", "."))


def remove_module(module_name: str) -> None:
    """Remove a module from the loaded_modules. The module name should be relative to the 'src'
    folder. Example: '_monitors.test'"""
    if module_name in sys.modules:
        del sys.modules[module_name]


def load_module_from_file(module_path: Path) -> ModuleType:
    """Load a module from a path, returning the module. If this function is called for the same
    path in a short time frame, the module won't be reloaded from the files and will be the same
    that was previously loaded"""
    module_name = make_module_name(module_path)
    monitor_name = module_path.stem

    start_time = time.time()

    remove_module(module_name)
    module = importlib.import_module(module_name)
    _logger.info(f"Monitor '{monitor_name}' loaded")

    end_time = time.time()

    # Check if the monitor is taking too long to load
    total_time = end_time - start_time
    if total_time > 0.2:
        _logger.warning(f"Monitor '{monitor_name}' took {total_time} seconds to load")

    return module


def load_module_from_string(
    module_name: str, module_code: str, base_path: str | None = None
) -> tuple[Path, ModuleType]:
    """Load a module from a code string"""
    if base_path is None:
        base_path = MODULES_PATH

    module_path = create_module_files(
        module_name=module_name, module_code=module_code, base_path=base_path
    )
    return module_path, load_module_from_file(module_path)

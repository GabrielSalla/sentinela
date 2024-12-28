import os
import sys
import time
from pathlib import Path

import pytest
from dataclass_type_validator import TypeValidationError

import module_loader.loader as loader
from tests.test_utils import assert_message_in_log


def test_init_modules_path(temp_dir):
    """'init_modules_path' should create a path if it doesn't exist"""
    path = temp_dir / "test_init_modules_path"
    assert not path.exists()

    loader.init_modules_path(path)

    assert path.exists()
    files_in_folder = path.glob("*.py")
    assert list(files_in_folder) == [path / "__init__.py"]


def test_init_modules_path_already_exists(mocker, temp_dir):
    """'init_modules_path' should do nothing if the path already exists"""
    os_makedirs_spy = mocker.spy(os, "makedirs")

    path = temp_dir / "test_init_modules_path"
    assert not path.exists()

    loader.init_modules_path(path)

    assert path.exists()
    files_in_folder = path.glob("*.py")
    assert list(files_in_folder) == [path / "__init__.py"]
    os_makedirs_spy.assert_called_once_with(path)

    loader.init_modules_path(path)

    assert path.exists()
    files_in_folder = path.glob("*.py")
    assert list(files_in_folder) == [path / "__init__.py"]
    os_makedirs_spy.assert_called_once_with(path)


@pytest.mark.parametrize("module_name, module_code, additional_files", [
    (
        "test_create_module_files_1",
        "import sys",
        None
    ),
    (
        "test_create_module_files_2",
        "import random",
        {"file_1.py": "import os"}
    ),
    (
        "test_create_module_files_3",
        "print('abc123')",
        {"file_1.py": "print('defg456')", "file_2.py": "print('hijk789')"}
    ),
])
def test_create_module_files(module_name, module_code, additional_files):
    """'create_module_files' should create the module file and the additional files provided"""
    module_path = loader.create_module_files(
        module_name, module_code, additional_files=additional_files
    )
    assert isinstance(module_path, Path)

    relative_module_path = Path("src") / module_path

    with open(relative_module_path, "r") as file:
        assert file.read() == module_code

    if additional_files:
        for file_name, file_content in additional_files.items():
            file_path = relative_module_path.parent / file_name
            with open(file_path, "r") as file:
                assert file.read() == file_content


def test_load_module_from_file(caplog):
    """'load_module_from_file' should load a module from a file path"""
    module_name = "load_module_from_file_1"
    module_code = "import sys"

    module_path = loader.create_module_files(module_name, module_code)
    module = loader.load_module_from_file(module_path)

    assert module.sys is sys

    assert_message_in_log(
        caplog,
        f"Monitor '{module_name}' loaded"
    )


@pytest.mark.parametrize(
    "n1, n2, expected_1, expected_2",
    [
        (10, 99, 10, 99),  # In this test case, the file size doesn't change
        (10, 200, 10, 200),
    ],
)
def test_load_module_from_file_reload(caplog, n1, n2, expected_1, expected_2):
    """'load_module_from_file' should be able to reload modules that were previously loaded,
    allowing hot changes"""
    module_name = f"load_module_from_file_reload_{n1}_{n2}"
    module_code = "def get_value(): return {n}"

    module_path = loader.create_module_files(module_name, module_code.format(n=n1))

    module = loader.load_module_from_file(module_path)

    assert module.get_value() == expected_1

    # As python checks for the timestamp to change to reload a module, sleep for 1 second
    time.sleep(1)

    # Write the second version of the file
    module_path = loader.create_module_files(module_name, module_code.format(n=n2))

    module = loader.load_module_from_file(module_path)

    assert module.get_value() == expected_2

    assert_message_in_log(caplog, f"Monitor '{module_name}' reloaded")


def test_load_module_from_file_reload_replace_variables():
    """'load_module_from_file' should be able to reload modules replacing the previous state for a
    new one"""
    module_name = "load_module_from_file_reload_replace_variables"
    module_code = "l = []"

    module_path = loader.create_module_files(module_name, module_code)

    module = loader.load_module_from_file(module_path)

    assert module.l == []
    module.l.append(1)
    assert module.l == [1]

    # As python checks for the timestamp to change to reload a module, sleep for 1 second
    time.sleep(1)

    # Write the second version of the file
    module_path = loader.create_module_files(module_name, module_code)

    module = loader.load_module_from_file(module_path)

    assert module.l == []


def test_load_module_from_file_long_load_time(caplog):
    """'load_module_from_file' should log a warning if the module takes too long to load"""
    module_name = "load_module_from_file_long_load_time_1"
    module_code = "import time\n\ntime.sleep(0.2)"

    module_path = loader.create_module_files(module_name, module_code)
    module = loader.load_module_from_file(module_path)

    assert module.time is time

    assert_message_in_log(
        caplog,
        rf"Monitor '{module_name}' took [\d.]+ seconds to load",
        regex=True,
    )


def test_load_module_from_file_import_error():
    """'load_module_from_file' should raise an 'ImportError' if the module cannot be imported"""
    module_name = "load_module_from_file_import_error_1"
    module_code = "import non_existent_module"

    module_path = loader.create_module_files(module_name, module_code)
    with pytest.raises(ImportError):
        loader.load_module_from_file(module_path)


def test_load_module_from_file_syntax_error():
    """'load_module_from_file' should raise an 'SyntaxError' if the module has syntax errors"""
    module_name = "load_module_from_file_syntax_error_1"
    module_code = "print('Hello, World!'"

    module_path = loader.create_module_files(module_name, module_code)
    with pytest.raises(SyntaxError):
        loader.load_module_from_file(module_path)


def test_load_module_from_file_dataclass_validation_error():
    """'load_module_from_file' should raise a 'TypeValidationError' if the module initializes a
    dataclass with invalid values"""
    module_name = "load_module_from_file_dataclass_validation_error_1"
    module_code = "\n".join([
        "from dataclasses import dataclass",
        "from dataclass_type_validator import dataclass_validate",
        "\n",
        "@dataclass_validate(strict=True)",
        "@dataclass",
        "class Data:",
        "    value: str",
        "\n",
        "data = Data(value=123)",
    ])

    module_path = loader.create_module_files(module_name, module_code)
    expected_error_message = (
        "errors = {'value': \"must be an instance of <class 'str'>, "
        "but received <class 'int'>\"}"
    )
    with pytest.raises(TypeValidationError, match=expected_error_message):
        loader.load_module_from_file(module_path)

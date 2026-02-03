import os
import sys
import time
from pathlib import Path

import pydantic
import pytest

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


@pytest.mark.parametrize(
    "module_name, module_code, additional_files",
    [
        ("test_create_module_files_1", "import sys", None),
        ("test_create_module_files_2", "import random", {"file_1.py": "import os"}),
        (
            "test_create_module_files_3",
            "print('abc123')",
            {"file_1.py": "print('defg456')", "file_2.py": "print('hijk789')"},
        ),
    ],
)
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


@pytest.mark.parametrize(
    "module_path, expected_module_name",
    [
        (Path("src/test/module.py"), "src.test.module"),
        (Path("abc/aa/module_2.py"), "abc.aa.module_2"),
        (Path("ab123/aabbcc/module_3.py"), "ab123.aabbcc.module_3"),
        (Path("ab123/aabbcc/module_y.py"), "ab123.aabbcc.module_y"),
    ],
)
def test_make_module_name(module_path, expected_module_name):
    """'make_module_name' should return the module name from a path"""
    module_name = loader.make_module_name(module_path)
    assert module_name == expected_module_name


def test_remove_module():
    """'remove_module' should remove a module from 'sys.modules'"""
    module_name = "test_remove_module"
    module_code = "def get_value(): return {n}"

    module_path, module = loader.load_module_from_string(module_name, module_code.format(n=10))
    loaded_module_name = loader.make_module_name(module_path)

    assert sys.modules[loaded_module_name] is module

    loader.remove_module(loaded_module_name)

    assert loaded_module_name not in sys.modules


def test_remove_module_not_exists():
    """'remove_module' should just return if the module doesn't exist in 'sys.modules'"""
    module_name = "test_remove_module_not_exists"
    assert module_name not in sys.modules
    loader.remove_module(module_name)
    assert module_name not in sys.modules


def test_load_module_from_file(caplog):
    """'load_module_from_file' should load a module from a file path"""
    module_name = "load_module_from_file_1"
    module_code = "import sys"

    module_path = loader.create_module_files(module_name, module_code)
    module = loader.load_module_from_file(module_path)

    loaded_module_name = loader.make_module_name(module_path)
    assert sys.modules[loaded_module_name] is module

    assert_message_in_log(caplog, f"Monitor '{module_name}' loaded")


@pytest.mark.parametrize(
    "n1, n2",
    [
        (10, 99),  # In this test case, the file size doesn't change
        (10, 200),
    ],
)
def test_load_module_from_file_reload_sleep(caplog, n1, n2):
    """'load_module_from_file' should be able to reload modules that were previously loaded,
    allowing hot changes. To be able reload a file the file timestamp or size must change, or the
    cache must be invalidated"""
    module_name = f"test_load_module_from_file_reload_sleep_{n1}_{n2}"
    module_code = "def get_value(): return {n}"

    module_path = loader.create_module_files(module_name, module_code.format(n=n1))

    module = loader.load_module_from_file(module_path)

    assert module.get_value() == n1
    assert_message_in_log(caplog, f"Monitor '{module_name}' loaded")

    # Sleep until next second
    time.sleep(1 - time.time() % 1 + 0.01)

    module_path = loader.create_module_files(module_name, module_code.format(n=n2))

    module = loader.load_module_from_file(module_path)

    assert module.get_value() == n2
    assert_message_in_log(caplog, f"Monitor '{module_name}' loaded", count=2)


@pytest.mark.flaky(reruns=1)
def test_load_module_from_file_reload_no_time_change(caplog):
    """'load_module_from_file' should not reload the file if the file timestamp or size didn't
    change. Test is marked with 'flaky' because the second might change between the module loads"""
    module_name = "test_load_module_from_file_reload_no_time_change"
    module_code = "def get_value(): return {n}"

    module_path = loader.create_module_files(module_name, module_code.format(n=10))

    module = loader.load_module_from_file(module_path)

    assert module.get_value() == 10
    assert_message_in_log(caplog, f"Monitor '{module_name}' loaded")

    time.sleep(0.1)

    module_path = loader.create_module_files(module_name, module_code.format(n=99))

    module = loader.load_module_from_file(module_path)

    # The value didn't change, even though the module code changed
    assert module.get_value() == 10
    assert_message_in_log(caplog, f"Monitor '{module_name}' loaded", count=2)


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

    module.v = []  # type: ignore[attr-defined]
    module.v.append(10)
    assert module.v == [10]

    # As python checks for the timestamp to change to reload a module, sleep until the next second
    time.sleep(1 - time.time() % 1 + 0.01)

    module = loader.load_module_from_file(module_path)

    assert module.l == []
    # The variable 'v' should not exist anymore when the module is reloaded
    with pytest.raises(AttributeError):
        module.v


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
    """'load_module_from_file' should raise a 'pydantic.ValidationError' if the module initializes a
    dataclass with invalid values"""
    module_name = "load_module_from_file_dataclass_validation_error_1"
    module_code = "\n".join(
        [
            "from pydantic.dataclasses import dataclass",
            "\n",
            "@dataclass",
            "class Data:",
            "    value: str",
            "\n",
            "data = Data(value=123)",
        ]
    )

    module_path = loader.create_module_files(module_name, module_code)

    with pytest.raises(pydantic.ValidationError, match="1 validation error for Data"):
        loader.load_module_from_file(module_path)


def test_load_module_from_string():
    """'load_module_from_string' should create the module file and load it"""
    module_name = "test_load_module_from_string"
    module_code = "def get_value(): return {n}"

    module_path, module = loader.load_module_from_string(module_name, module_code.format(n=10))

    assert module_path == Path("tmp") / module_name / f"{module_name}.py"
    assert module.get_value() == 10

    time.sleep(0.1)

    module_path, module = loader.load_module_from_string(module_name, module_code.format(n=200))

    assert module_path == Path("tmp") / module_name / f"{module_name}.py"
    assert module.get_value() == 200


def test_load_module_from_string_with_base_path():
    """'load_module_from_string' should create the module file and load it with a custom base
    path"""
    module_name = "test_load_module_from_string_with_base_path"
    module_code = "def get_value(): return {n}"

    base_path = Path("tmp") / "some_test_path"
    module_path, module = loader.load_module_from_string(
        module_name, module_code.format(n=987), base_path=str(base_path)
    )

    assert module_path == base_path / module_name / f"{module_name}.py"
    assert module.get_value() == 987

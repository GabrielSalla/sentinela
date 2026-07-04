import ast
import importlib
from pathlib import Path

import pytest

from exceptions.module_loader import NestedImport, ProhibitedImport
from module_loader import import_restrict


def test_scan_nested_imports():
    """'scan_nested_imports' should not raise exceptions when the code doesn't have any nested
    imports"""
    module_tree = ast.parse("print('hi')")
    import_restrict.scan_nested_imports(module_tree)


@pytest.mark.parametrize(
    "module_code, function_name",
    [
        ("def a():\n\timport time", "a"),
        ("def b():\n\ttime = __import__('time')", "b"),
        ("async def c():\n\timport time", "c"),
        ("async def d():\n\ttime = __import__('time')", "d"),
        ("def e():\n\tfrom time import time", "e"),
        ("async def f():\n\tfrom time import time", "f"),
        ("def a():\n\treturn 10\n\ndef b():\n\timport time", "b"),
        ("def a():\n\treturn 10\n\ndef b():\n\ttime = __import__('time')", "b"),
    ],
)
def test_scan_nested_imports_raise(module_code, function_name):
    """'scan_nested_imports' should raise a 'NestedImport' exception when the code have nested
    imports"""
    module_tree = ast.parse(module_code)
    with pytest.raises(NestedImport, match=function_name):
        import_restrict.scan_nested_imports(module_tree)


@pytest.mark.parametrize(
    "module_code",
    [
        "print('hi')",
        "import monitor_utils",
        "import plugins",
        "import plugins.slack.notifications",
        "from monitor_utils import AlertOptions",
        "from plugins.slack.notifications import SlackNotification",
    ],
)
def test_scan_imports_allowed(module_code):
    """'scan_imports' should not raise exceptions when the code doesn't import any prohibited
    modules"""
    module_tree = ast.parse(module_code)
    import_restrict.scan_imports(module_tree)


@pytest.mark.parametrize(
    "module_code, import_name",
    [
        ("import importlib", "importlib"),
        ("import os", "os"),
        ("import sys", "sys"),
        ("import components", "components"),
        ("import components.controller", "components"),
        ("import commands", "commands"),
        ("import internal_database", "internal_database"),
        ("from internal_database import engine", "internal_database"),
        ("from internal_database.internal_database import CallbackSession", "internal_database"),
    ],
)
def test_scan_imports_prohibited(module_code, import_name):
    """'scan_nested_imports' should raise a 'ProhibitedImport' exception when the code imports
    prohibited modules"""
    module_tree = ast.parse(module_code)
    with pytest.raises(ProhibitedImport, match=import_name):
        import_restrict.scan_imports(module_tree)


def import_function(test_case: int) -> None:
    """Test cases for the 'prohibit_imports' function tests"""
    match test_case:
        # Normal import cases
        case 1:
            import os

            os
        case 2:
            from os import environ

            environ
        case 3:
            import sys

            sys
        case 4:
            import components.controller

            components.controller
        case 5:
            import internal_database

            internal_database
        case 6:
            from internal_database import engine

            engine
        case 7:
            from internal_database.internal_database import CallbackSession

            CallbackSession

        # '__import__' cases
        case 8:
            __import__("importlib")
        case 9:
            __import__("os")
        case 10:
            __import__("sys")
        case 11:
            __import__("components")
        case 12:
            __import__("internal_database")

        # 'eval' cases
        case 13:
            eval("__import__('os')")
        case 14:
            eval("importlib.import_module('os')")

        # 'importlib.import_module' cases
        case 15:
            importlib.import_module("os")


def test_prohibit_imports_allowed():
    """'prohibit_imports' should not raise any exceptions if allowed modules are being imported"""
    with import_restrict.prohibit_imports(Path(__file__).parent):
        import time

        time.time()
        importlib.import_module("time")


def test_prohibit_imports_deep_import():
    """'prohibit_imports' should not raise any exceptions if the stack search reaches the end
    without finding any match. This happens when the import is deep relative to the base path"""
    # Using a different base path will prevent the stack search to find a match and break the loop
    with import_restrict.prohibit_imports(Path("src/utils")):
        import time

        time.time()
        importlib.import_module("time")


@pytest.mark.parametrize(
    "test_case, import_name",
    [
        (1, "os"),
        (2, "os"),
        (3, "sys"),
        (4, "components"),
        (5, "internal_database"),
        (6, "internal_database"),
        (7, "internal_database"),
        (8, "importlib"),
        (9, "os"),
        (10, "sys"),
        (11, "components"),
        (12, "internal_database"),
        (13, "os"),
        (14, "os"),
        (15, "os"),
    ],
)
def test_prohibit_imports_prohibited(test_case, import_name):
    """'prohibit_imports' should raise a 'ProhibitedImport' exception if prohibited modules are
    being imported"""
    with pytest.raises(ProhibitedImport, match=import_name):
        with import_restrict.prohibit_imports(Path(__file__).parent):
            import_function(test_case)


def test_prohibit_imports_none():
    """'prohibit_imports' should raise a 'ValueError' exception if a import function is called with
    'None'"""
    with pytest.raises(ValueError, match="Error importing module 'None'"):
        with import_restrict.prohibit_imports(Path(__file__).parent):
            __import__(None)


@pytest.mark.parametrize("test_case", range(16))
def test_prohibit_imports_prohibited_revert(test_case):
    """'prohibit_imports' should revert back the changes to the import functions after the context
    manager finishes"""
    with import_restrict.prohibit_imports(Path(__file__).parent):
        pass

    import_function(test_case)

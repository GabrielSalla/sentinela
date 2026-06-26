import ast
import importlib

import pytest

from exceptions.module_loader import NestedImport, ProhibitedImport
from module_loader import import_restrict


def test_scan_nested_imports():
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
        "from plugins.slack.notifications import SlackNotification"
    ],
)
def test_scan_imports_allowed(module_code):
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
    module_tree = ast.parse(module_code)
    with pytest.raises(ProhibitedImport, match=import_name):
        import_restrict.scan_imports(module_tree)


def test_restrict_imports_allowed():
    with import_restrict.restrict_imports():
        import time
        importlib.import_module("time")


def import_function(test_case):
    match test_case:
        # Normal import cases
        case 1:
            import os
        case 2:
            from os import environ
        case 3:
            import sys
        case 4:
            import components.controller
        case 5:
            import internal_database
        case 6:
            from internal_database import engine
        case 7:
            from internal_database.internal_database import CallbackSession

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
def test_restrict_imports_prohibited(test_case, import_name):
    with pytest.raises(ProhibitedImport, match=import_name):
        with import_restrict.restrict_imports():
            import_function(test_case)


@pytest.mark.parametrize("test_case", range(16))
def test_restrict_imports_prohibited_revert(test_case):
    with import_restrict.restrict_imports():
        pass

    import_function(test_case)

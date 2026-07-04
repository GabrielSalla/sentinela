import ast

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

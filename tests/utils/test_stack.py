import inspect
from types import ModuleType

import pytest

import utils.stack as stack


def test_get_caller():
    """'get_caller' should return the module and function name of the caller, even if nested"""

    def f() -> tuple[ModuleType, str]:
        return stack.get_caller()

    module, function_name = f()

    assert module.__name__ == "test_stack"
    assert function_name == "test_get_caller"


def test_get_caller_nested():
    """'get_caller' should return the module and function name of the caller when using the previous
    parameter, even if nested"""

    def f() -> tuple[ModuleType, str]:
        return stack.get_caller()

    def g() -> tuple[tuple[ModuleType, str], tuple[ModuleType, str]]:
        return f(), stack.get_caller()

    (module, function_name), (module2, function_name2) = g()

    assert module.__name__ == "test_stack"
    assert function_name == "g"
    assert module2.__name__ == "test_stack"
    assert function_name2 == "test_get_caller_nested"


def test_get_caller_previous():
    """'get_caller' should return the module and function name of the caller when using the previous
    parameter"""

    def f() -> tuple[ModuleType, str]:
        return stack.get_caller(previous=1)

    def g() -> tuple[ModuleType, str]:
        return f()

    module, function_name = g()

    assert module.__name__ == "test_stack"
    assert function_name == "test_get_caller_previous"


def test_get_caller_high_previous():
    """'get_caller' should raise an IndexError when the previous parameter is too high"""

    def f() -> tuple[ModuleType, str]:
        return stack.get_caller(previous=999)

    with pytest.raises(IndexError, match="Could not access position 1001 in the stack"):
        f()


def test_get_caller_no_module(monkeypatch):
    """'get_caller' should raise a ValueError when the module cannot be determined"""
    monkeypatch.setattr(inspect, "getmodule", lambda *args, **kwargs: None)

    def f() -> tuple[ModuleType, str]:
        return stack.get_caller()

    with pytest.raises(ValueError, match="Could not determine caller module"):
        f()

"""Compatibility shim for pytest-mock async spies on Python 3.15.

Why this exists:
    Python 3.15's autospec-based 'mocker.spy' records an async call only after the
    coroutine returned by the spy is awaited. Some tests create the coroutine and inspect
    spy calls without awaiting it, so they see zero calls even though the code under test
    invoked the method.
    CPython issue: https://github.com/python/cpython/issues/137594

What this does:
    Replaces 'pytest_mock.MockerFixture.spy' for the test session. Sync spies still use
    pytest-mock. Async spies use 'AsyncMock(spec=method, wraps=method)', which records
    the call immediately and runs the original coroutine when awaited. Descriptors handle
    binding for instance methods and avoid binding for class and static methods.

When to remove:
    The session fixture first verifies that the bug still exists. Once pytest-mock records
    async calls at call time, that check fails with instructions to delete this module and
    its import from 'tests/conftest.py'.
"""

import functools
import inspect
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_mock
from _pytest.monkeypatch import MonkeyPatch

_ORIGINAL_MOCKER_SPY = pytest_mock.MockerFixture.spy


class _AsyncSpyMock(AsyncMock):
    """AsyncMock that binds itself when patched onto a class as a method."""

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return functools.partial(self, instance)


class _AsyncSpyMockNoBind(_AsyncSpyMock):
    """AsyncMock for class and static methods, which must not receive an instance."""

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        return self


def _spy_compat(
    mocker: pytest_mock.MockerFixture,
    obj: object,
    name: str,
    duplicate_iterators: bool = False,
) -> Mock:
    """Make async spies record calls when the coroutine is created.

    Python 3.15's autospec-based 'mocker.spy' only records an async call after the returned
    coroutine is awaited. Tests that only create the coroutine need the call recorded immediately.
    'AsyncMock(wraps=...)' records at call time and still invokes the original when awaited.
    """
    method = getattr(obj, name)
    if not inspect.iscoroutinefunction(method):
        return _ORIGINAL_MOCKER_SPY(mocker, obj, name, duplicate_iterators)

    if inspect.isclass(obj) and isinstance(
        inspect.getattr_static(obj, name), (classmethod, staticmethod)
    ):
        spy_mock = _AsyncSpyMockNoBind(spec=method, wraps=method)
    else:
        spy_mock = _AsyncSpyMock(spec=method, wraps=method)
    return mocker.patch.object(obj, name, new=spy_mock)


def _assert_async_spy_records_calls_late(mocker: pytest_mock.MockerFixture) -> None:
    """Fail once pytest-mock records async spy calls at call time instead of on await."""

    class Target:
        async def method(self, value: int) -> int:
            return value

    target = Target()
    spy = mocker.spy(target, "method")
    task = target.method(1)
    try:
        assert spy.call_count == 0, (
            "pytest-mock now records async spy calls at call time; remove the async spy "
            "compatibility patch from tests/mocker_spy_compat.py"
        )
    finally:
        task.close()
        mocker.stopall()


@pytest.fixture(scope="session", autouse=True)
def patch_mocker_spy(
    session_mocker: pytest_mock.MockerFixture, monkeypatch_session: MonkeyPatch
) -> None:
    """Patch pytest-mock async spies until upstream records calls at call time."""
    _assert_async_spy_records_calls_late(session_mocker)
    monkeypatch_session.setattr(pytest_mock.MockerFixture, "spy", _spy_compat)

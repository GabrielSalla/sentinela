import inspect
import re
from types import ModuleType
from typing import Any, Coroutine, TypedDict
from unittest.mock import MagicMock

import pydantic
import pytest

import module_loader.checker as checker
from data_models.monitor_options import (
    AlertOptions,
    CountRule,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    ReactionOptions,
)
from models.utils.priority import AlertPriority


@pytest.fixture(scope="function")
def monitor_mock():
    """Create a Monitor mock module"""

    class MonitorMock(ModuleType):
        pass

    return MonitorMock


def sync_function(): ...
async def async_function(): ...


# Test _check_async_function


def test_check_async_function_function_types():
    """'_check_async_function' should return no erros if the function is asynchronous, a list of
    errors otherwise"""
    assert checker._check_async_function(sync_function) == [
        "function 'sync_function' must be asynchronous"
    ]
    assert checker._check_async_function(async_function) == []


def test_check_async_function_not_functions():
    """'_check_async_function' should return errors if the object is not a function"""
    assert checker._check_async_function("something") == ["'something' must be a function"]


# Test _check_sync_function


def test_check_sync_function_function_types():
    """'_check_sync_function' should return no erros if the function is synchronous, a list of
    errors otherwise"""
    assert checker._check_sync_function(sync_function) == []
    assert checker._check_sync_function(async_function) == [
        "function 'async_function' must be synchronous"
    ]


def test_check_sync_function_not_functions():
    """'_check_sync_function' should return errors if the object is not a function"""
    assert checker._check_sync_function("another_thing") == ["'another_thing' must be a function"]


# Test _check_monitor_options


def test_check_monitor_options_defined(monitor_mock):
    """'_check_monitor_options' should return no erros if the 'monitor_options' field is defined"""
    monitor_mock.monitor_options = MonitorOptions()

    assert checker._check_monitor_options(monitor_mock) == []


def test_check_monitor_options_not_defined(monitor_mock):
    """'_check_monitor_options' should return errors if the 'monitor_options' field is not
    defined"""
    assert checker._check_monitor_options(monitor_mock) == ["'monitor_options' is required"]


def test_check_monitor_options_wrong_type(monitor_mock):
    """'_check_monitor_options' should return errors if the 'monitor_options' field is not an
    instance of 'MonitorOptions'"""
    monitor_mock.monitor_options = "MonitorOptions()"

    assert checker._check_monitor_options(monitor_mock) == [
        "'monitor_options' must be an instance of 'MonitorOptions'"
    ]


# Test _check_issue_options


def test_check_issue_options_defined(monitor_mock):
    """'_check_issue_options' should return no erros if the 'issue_options' field is defined"""
    monitor_mock.issue_options = IssueOptions(
        model_id_key="id",
    )

    assert checker._check_issue_options(monitor_mock) == []


def test_check_issue_options_not_defined(monitor_mock):
    """'_check_issue_options' should return no erros if the 'issue_options' field is not defined"""
    assert checker._check_issue_options(monitor_mock) == ["'issue_options' is required"]


def test_check_issue_options_wrong_type(monitor_mock):
    """'_check_issue_options' should return errors if the 'issue_options' field is not an instance
    of 'IssueOptions'"""
    monitor_mock.issue_options = "IssueOptions()"

    assert checker._check_issue_options(monitor_mock) == [
        "'issue_options' must be an instance of 'IssueOptions'"
    ]


# Test _check_alert_options


def test_check_alert_options_defined(monitor_mock):
    """'_check_alert_options' should return no erros if the 'alert_options' field is defined"""
    monitor_mock.alert_options = AlertOptions(
        rule=CountRule(priority_levels=PriorityLevels()),
    )

    assert checker._check_alert_options(monitor_mock) == []


def test_check_alert_options_not_defined(monitor_mock):
    """'_check_alert_options' should return no erros if the 'alert_options' field is not defined"""
    assert checker._check_alert_options(monitor_mock) == []


def test_check_alert_options_wrong_type(monitor_mock):
    """'_check_alert_options' should return errors if the 'alert_options' field is not an instance
    of 'AlertOptions'"""
    monitor_mock.alert_options = "AlertOptions()"

    assert checker._check_alert_options(monitor_mock) == [
        "'alert_options' must be an instance of 'AlertOptions' or not defined"
    ]


# Test _check_reaction_functions
# Test ReactionOptions expected errors when creating the instance


def test_check_reaction_options_async_function():
    """Creating an instance of 'ReactionOptions' should return no erros if the function in the list
    is asynchronous"""

    async def async_function(): ...

    ReactionOptions(
        alert_created=[async_function],
    )


def test_check_reaction_options_with_many_async_functions():
    """Creating an instance of 'ReactionOptions' should return no erros if all functions in the
    list are asynchronous"""

    async def another_async_function(): ...

    ReactionOptions(
        alert_created=[async_function, another_async_function],
    )


def test_check_reaction_options_not_list():
    """Creating an instance of 'ReactionOptions' should raise a "pydantic.ValidationError" if any
    of the fields is not a list"""
    with pytest.raises(pydantic.ValidationError, match="1 validation error for ReactionOptions"):
        ReactionOptions(
            alert_created={"func": sync_function},
        )


def test_check_reaction_options_with_sync_function(monkeypatch):
    """'_check_reaction_functions' should return errors if any function in the list is
    synchronous"""
    monkeypatch.setattr(inspect, "isfunction", lambda _: True)

    reaction_options = ReactionOptions(
        alert_created=[sync_function],
    )
    assert checker._check_reaction_functions(reaction_options) == [
        "function 'reaction_options.alert_created.sync_function' must be asynchronous"
    ]


def test_check_reaction_options_with_sync_function_no_name(monkeypatch):
    """'_check_reaction_functions' should return errors if any function in the list is
    synchronous"""
    # As the 'MagicMock' is used as an object without the '__name__' attribute and is not a real
    # function, the 'inspect' functions must be mocked
    monkeypatch.setattr(inspect, "isfunction", lambda _: True)
    monkeypatch.setattr(inspect, "iscoroutinefunction", lambda _: False)

    reaction_options = ReactionOptions(
        alert_created=[MagicMock()],
    )
    errors = checker._check_reaction_functions(reaction_options)

    assert len(errors) == 1
    match = re.match(
        r"function 'reaction_options.alert_created.<MagicMock id='\d+'>' must be asynchronous",
        errors[0],
    )
    assert match is not None


@pytest.mark.parametrize(
    "functions",
    [
        ["string"],
        ["string", async_function],
        [async_function, "string"],
    ],
)
def test_check_reaction_options_with_wrong_functions_type(functions):
    """Creating an instance of 'ReactionOptions' should raise a "pydantic.ValidationError" if any
    of the fields has an item that is not a function"""
    with pytest.raises(pydantic.ValidationError, match="1 validation error for ReactionOptions"):
        ReactionOptions(
            alert_created=functions,
        )


# Test _check_reaction_options


def test_check_reaction_options_defined(monitor_mock):
    """'_check_reaction_options' should return no erros if the 'reaction_options' field is
    defined"""
    monitor_mock.reaction_options = ReactionOptions()

    assert checker._check_reaction_options(monitor_mock) == []


def test_check_reaction_options_not_defined(monitor_mock):
    """'_check_reaction_options' should return no erros if the 'reaction_options' field is not
    defined"""
    assert checker._check_reaction_options(monitor_mock) == []


def test_check_reaction_options_wrong_type(monitor_mock):
    """'_check_reaction_options' should return errors if the 'reaction_options' field is not an
    instance of 'ReactionOptions'"""
    monitor_mock.reaction_options = "ReactionOptions()"

    assert checker._check_reaction_options(monitor_mock) == [
        "'reaction_options' must be an instance of 'ReactionOptions' or not defined"
    ]


# Test _check_notification_options


class BaseNotification:
    """Notification class to be used in the tests"""

    min_priority_to_send: AlertPriority = AlertPriority.informational

    @classmethod
    def create(
        cls: type["BaseNotification"],
        name: str,
        issues_fields: list[str],
        params: dict[str, Any],
    ) -> "BaseNotification": ...

    def reactions_list(self) -> list[tuple[str, list[Coroutine[Any, Any, Any]]]]:
        return []


def test_check_notification_options_defined(monitor_mock):
    """'_check_notification_options' should return no erros if the 'notification_options' field is
    defined"""
    monitor_mock.notification_options = [BaseNotification()]

    assert checker._check_notification_options(monitor_mock) == []


def test_check_notification_options_empty(monitor_mock):
    """'_check_notification_options' should return no erros if the 'notification_options' field is
    an empty list"""
    monitor_mock.notification_options = []

    assert checker._check_notification_options(monitor_mock) == []


def test_check_notification_options_not_defined(monitor_mock):
    """'_check_notification_options' should return no erros if the 'notification_options' field is
    not defined"""
    assert checker._check_notification_options(monitor_mock) == []


def test_check_notification_options_wrong_type(monitor_mock):
    """'_check_notification_options' should return errors if the 'notification_options' field is
    not a list"""
    monitor_mock.notification_options = "BaseNotification()"

    assert checker._check_notification_options(monitor_mock) == [
        "'notification_options' must be an instance of 'list[Notification]' or not defined"
    ]


@pytest.mark.parametrize(
    "notifications, index",
    [
        (["asd"], 0),
        ([BaseNotification(), "asd"], 1),
    ],
)
def test_check_notification_options_notifications_wrong_type(monitor_mock, notifications, index):
    """'_check_notification_options' should return errors if any item in the list is not an
    instance of 'BaseNotification'"""
    monitor_mock.notification_options = notifications

    assert checker._check_notification_options(monitor_mock) == [
        f"'notification_options[{index}]' must be an instance of 'Notification'"
    ]


# Test _check_issue_data_type


def test_check_issue_data_type_defined(monitor_mock):
    """'_check_issue_data_type' should return no erros if the 'IssueDataType' class is defined and
    it inherits from 'TypedDict'"""
    monitor_mock.issue_options = IssueOptions(
        model_id_key="id",
    )

    class IssueDataType(TypedDict):
        id: str
        a: str
        b: int

    monitor_mock.IssueDataType = IssueDataType

    assert checker._check_issue_data_type(monitor_mock) == []


def test_check_issue_data_type_not_defined(monitor_mock):
    """'_check_issue_data_type' should return errors if the 'IssueDataType' class is not defined"""
    assert checker._check_issue_data_type(monitor_mock) == ["'IssueDataType' is required"]


def test_check_issue_data_type_wrong_type(monitor_mock):
    """'_check_issue_data_type' should return errors if the 'IssueDataType' class is not a class
    inherited from 'TypedDict'"""
    monitor_mock.IssueDataType = "IssueDataType"

    assert checker._check_issue_data_type(monitor_mock) == [
        "Class 'IssueDataType' must be inherited from 'typing.TypedDict'"
    ]


def test_check_issue_data_type_no_issue_options(monitor_mock):
    """'_check_issue_data_type' should return errors if the 'IssueDataType' class is defined but
    there is no 'issue_options' field"""

    class IssueDataType(TypedDict):
        id: str
        a: str
        b: int

    monitor_mock.IssueDataType = IssueDataType

    assert checker._check_issue_data_type(monitor_mock) == []


def test_check_issue_data_type_missing_model_id_key(monitor_mock):
    """'_check_issue_data_type' should return errors if the 'IssueDataType' class doesn't have the
    field defined in the 'model_id_key' parameter of the 'issue_options' setting"""
    monitor_mock.issue_options = IssueOptions(
        model_id_key="id",
    )

    class IssueDataType(TypedDict):
        a: str
        b: int

    monitor_mock.IssueDataType = IssueDataType

    assert checker._check_issue_data_type(monitor_mock) == [
        "'IssueDataType' must have the 'id' field, as specified by 'issue_options.model_id_key'"
    ]


# Test _check_search_function


def test_check_search_function_defined(monitor_mock):
    """'_check_search_function' should return no erros if the 'search' function is defined and it is
    an asynchronous function with the correct signature"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    async def search() -> list[IssueDataType] | None: ...

    monitor_mock.IssueDataType = IssueDataType
    monitor_mock.search = search

    assert checker._check_search_function(monitor_mock) == []


def test_check_search_function_not_defined(monitor_mock):
    """'_check_search_function' should return errors if the 'search' function is not defined"""
    assert checker._check_search_function(monitor_mock) == ["'search' function is required"]


def test_check_search_function_sync_function(monitor_mock):
    """'_check_search_function' should return errors if the 'search' function is synchronous"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    def search() -> list[IssueDataType]: ...

    monitor_mock.search = search

    assert checker._check_search_function(monitor_mock) == [
        "function 'search' must be asynchronous"
    ]


def test_check_search_function_no_issue_data_type(monitor_mock):
    """'_check_search_function' should return no erros if the monitor doesn't have the
    'IssueDataType' class defined"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    async def search() -> list[IssueDataType]: ...

    monitor_mock.search = search

    assert checker._check_search_function(monitor_mock) == []


class Test_check_search_function_type_signature:
    class IssueDataType(TypedDict):
        a: str
        b: int

    async def search_arg(a: int) -> list[IssueDataType] | None: ...
    async def search_args(*args) -> list[IssueDataType] | None: ...
    async def search_kwargs(**kwargs) -> list[IssueDataType] | None: ...

    async def search_return_without_none() -> list[IssueDataType]: ...
    async def search_return_none() -> None: ...
    async def search_return_other() -> str: ...

    @pytest.mark.parametrize(
        "function",
        [
            search_arg,
            search_args,
            search_kwargs,
        ],
    )
    def test_check_search_function_wrong_arguments(self, monitor_mock, function):
        """'_check_search_function' should return errors if the 'search' function has arguments"""
        monitor_mock.IssueDataType = self.IssueDataType
        monitor_mock.search = function

        assert checker._check_search_function(monitor_mock) == [
            "'search' function must have no arguments"
        ]

    @pytest.mark.parametrize(
        "function",
        [
            search_return_without_none,
            search_return_none,
            search_return_other,
        ],
    )
    def test_check_search_function_wrong_return(self, monitor_mock, function):
        """'_check_search_function' should return errors if the 'search' function has a return type
        different from 'list[IssueDataType] | None'"""
        monitor_mock.IssueDataType = self.IssueDataType
        monitor_mock.search = function

        assert checker._check_search_function(monitor_mock) == [
            "'search' function must return 'list[IssueDataType] | None'"
        ]


# Test _check_update_function


def test_check_update_function_defined(monitor_mock):
    """'_check_update_function' should return no erros if the 'update' function is defined and it
    is an asynchronous function with the correct signature"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None: ...

    monitor_mock.IssueDataType = IssueDataType
    monitor_mock.update = update

    assert checker._check_update_function(monitor_mock) == []


def test_check_update_function_not_defined(monitor_mock):
    """'_check_update_function' should return errors if the 'update' function is not defined"""
    assert checker._check_update_function(monitor_mock) == ["'update' function is required"]


def test_check_update_function_without_issue_data(monitor_mock):
    """'_check_update_function' should return errors if the 'update' function doesn't have
    'issues_data' as argument"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    async def update(a: IssueDataType) -> list[IssueDataType] | None: ...

    monitor_mock.IssueDataType = IssueDataType
    monitor_mock.update = update

    assert checker._check_update_function(monitor_mock) == [
        "'update' function must have arguments 'issues_data: list[IssueDataType]'"
    ]


def test_check_update_function_sync_function(monitor_mock):
    """'_check_update_function' should return errors if the 'update' function is synchronous"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None: ...

    monitor_mock.update = update

    assert checker._check_update_function(monitor_mock) == [
        "function 'update' must be asynchronous"
    ]


def test_check_update_function_no_issue_data_type(monitor_mock):
    """'_check_update_function' should return no erros if the monitor doesn't have the
    'IssueDataType' class defined"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    async def update(issues_data: list[IssueDataType]) -> list[IssueDataType]: ...

    monitor_mock.update = update

    assert checker._check_update_function(monitor_mock) == []


class Test_check_update_function_type_signature:
    class IssueDataType(TypedDict):
        a: str
        b: int

    async def update_more_args(
        issues_data: list[IssueDataType], a: int
    ) -> list[IssueDataType] | None: ...

    async def update_args(
        issues_data: list[IssueDataType], *args
    ) -> list[IssueDataType] | None: ...

    async def update_kwargs(
        issues_data: list[IssueDataType], **kwargs
    ) -> list[IssueDataType] | None: ...

    async def update_wrong_type(issues_data: list[str]) -> list[IssueDataType] | None: ...

    async def update_return_without_none(
        issues_data: list[IssueDataType],
    ) -> list[IssueDataType]: ...

    async def update_return_none(issues_data: list[IssueDataType]) -> None: ...

    async def update_return_other(issues_data: list[IssueDataType]) -> str: ...

    @pytest.mark.parametrize(
        "function",
        [
            update_more_args,
            update_args,
            update_kwargs,
        ],
    )
    def test_check_update_function_wrong_arguments(self, monitor_mock, function):
        """'_check_update_function' should return errors if the 'update' function has the wrong
        args signature"""
        monitor_mock.IssueDataType = self.IssueDataType
        monitor_mock.update = function

        assert checker._check_update_function(monitor_mock) == [
            "'update' function must have arguments 'issues_data: list[IssueDataType]'"
        ]

    def test_check_update_function_wrong_argument_type(self, monitor_mock):
        """'_check_update_function' should return errors if the 'update' function has the wrong
        argument type"""
        monitor_mock.IssueDataType = self.IssueDataType
        monitor_mock.update = Test_check_update_function_type_signature.update_wrong_type

        assert checker._check_update_function(monitor_mock) == [
            "'update' function must have arguments 'issues_data: list[IssueDataType]'"
        ]

    @pytest.mark.parametrize(
        "function",
        [
            update_return_without_none,
            update_return_none,
            update_return_other,
        ],
    )
    def test_check_update_function_wrong_return(self, monitor_mock, function):
        """'_check_update_function' should return errors if the 'update' function has the wrong
        return type"""
        monitor_mock.IssueDataType = self.IssueDataType
        monitor_mock.update = function

        assert checker._check_update_function(monitor_mock) == [
            "'update' function must return 'list[IssueDataType] | None'"
        ]


# Test _check_is_solved_function


def test_check_is_solved_function_defined(monitor_mock):
    """'_check_is_solved_function' should return no erros if the 'is_solved' function is defined
    and it is a synchronous function with the correct signature"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    def is_solved(issue_data: IssueDataType) -> bool: ...

    monitor_mock.IssueDataType = IssueDataType
    monitor_mock.is_solved = is_solved

    assert checker._check_is_solved_function(monitor_mock) == []


def test_check_is_solved_function_not_defined(monitor_mock):
    """'_check_is_solved_function' should return errors if the 'is_solved' function is not
    defined"""
    monitor_mock.issue_options = IssueOptions(
        model_id_key="id",
    )
    assert checker._check_is_solved_function(monitor_mock) == ["'is_solved' function is required"]


def test_check_is_solved_function_not_defined_solvable(monitor_mock):
    """'_check_is_solved_function' should return no erros if the 'is_solved' function is not defined
    and the 'solvable' field in the 'issue_options' setting is set to 'True'"""
    monitor_mock.issue_options = IssueOptions(
        model_id_key="id",
        solvable=False,
    )

    assert checker._check_is_solved_function(monitor_mock) == []


def test_check_is_solved_function_without_issues_data(monitor_mock):
    """'_check_is_solved_function' should return errors if the 'is_solved' function doesn't have
    the 'issue_data' as argument"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    def is_solved(a: IssueDataType) -> bool: ...

    monitor_mock.IssueDataType = IssueDataType
    monitor_mock.is_solved = is_solved

    assert checker._check_is_solved_function(monitor_mock) == [
        "'is_solved' function must have arguments 'issue_data: IssueDataType'"
    ]


def test_check_is_solved_function_async_function(monitor_mock):
    """'_check_is_solved_function' should return errors if the 'is_solved' function is
    asynchronous"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    async def is_solved(issue_data: IssueDataType) -> bool: ...

    monitor_mock.is_solved = is_solved

    assert checker._check_is_solved_function(monitor_mock) == [
        "function 'is_solved' must be synchronous"
    ]


def test_check_is_solved_function_no_issue_data_type(monitor_mock):
    """'_check_is_solved_function' should return no errors if the monitor doesn't have the
    'IssueDataType' class defined"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    def is_solved(issue_data: IssueDataType) -> bool: ...

    monitor_mock.is_solved = is_solved

    assert checker._check_is_solved_function(monitor_mock) == []


class Test_check_is_solved_function_type_signature:
    class IssueDataType(TypedDict):
        a: str
        b: int

    def is_solved_more_args(issue_data: IssueDataType, a: int) -> bool: ...
    def is_solved_args(issue_data: IssueDataType, *args) -> bool: ...
    def is_solved_kwargs(issue_data: IssueDataType, **kwargs) -> bool: ...
    def is_solved_wrong_type(issue_data: str) -> bool: ...

    def is_solved_return_none(issue_data: IssueDataType) -> None: ...
    def is_solved_return_other(issue_data: IssueDataType) -> str: ...

    @pytest.mark.parametrize(
        "function",
        [
            is_solved_more_args,
            is_solved_args,
            is_solved_kwargs,
        ],
    )
    def test_check_is_solved_function_wrong_arguments(self, monitor_mock, function):
        """'_check_is_solved_function' should return errors if the 'is_solved' function has the
        wrong args signature"""
        monitor_mock.IssueDataType = self.IssueDataType
        monitor_mock.is_solved = function

        assert checker._check_is_solved_function(monitor_mock) == [
            "'is_solved' function must have arguments 'issue_data: IssueDataType'"
        ]

    def test_check_is_solved_function_wrong_argument_type(self, monitor_mock):
        """'_check_is_solved_function' should return errors if the 'is_solved' function has the
        wrong argument type"""
        monitor_mock.IssueDataType = self.IssueDataType
        monitor_mock.is_solved = Test_check_is_solved_function_type_signature.is_solved_wrong_type

        assert checker._check_is_solved_function(monitor_mock) == [
            "'is_solved' function must have arguments 'issue_data: IssueDataType'"
        ]

    @pytest.mark.parametrize(
        "function",
        [
            is_solved_return_none,
            is_solved_return_other,
        ],
    )
    def test_check_is_solved_function_wrong_return(self, monitor_mock, function):
        """'_check_is_solved_function' should return errors if the 'is_solved' function has the
        wrong return type"""
        monitor_mock.IssueDataType = self.IssueDataType
        monitor_mock.is_solved = function

        assert checker._check_is_solved_function(monitor_mock) == [
            "'is_solved' function must return 'bool'"
        ]


# Test check_module


def test_check_module(mocker, monitor_mock):
    """'check_module' should call all the check functions with the correct arguments and return the
    list of errors. If there were no errors, the list should be empty"""

    class IssueDataType(TypedDict):
        id: str
        a: str
        b: int

    monitor_mock.monitor_options = MonitorOptions()
    monitor_mock.issue_options = IssueOptions(
        model_id_key="id",
    )
    monitor_mock.IssueDataType = IssueDataType

    async def search() -> list[IssueDataType] | None: ...
    async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None: ...
    def is_solved(issue_data: IssueDataType) -> bool: ...

    monitor_mock.search = search
    monitor_mock.update = update
    monitor_mock.is_solved = is_solved

    _check_monitor_options_spy: MagicMock = mocker.spy(checker, "_check_monitor_options")
    _check_issue_options_spy: MagicMock = mocker.spy(checker, "_check_issue_options")
    _check_alert_options_spy: MagicMock = mocker.spy(checker, "_check_alert_options")
    _check_reaction_options_spy: MagicMock = mocker.spy(checker, "_check_reaction_options")
    _check_notification_options_spy: MagicMock = mocker.spy(checker, "_check_notification_options")
    _check_issue_data_type_spy: MagicMock = mocker.spy(checker, "_check_issue_data_type")
    _check_search_function_spy: MagicMock = mocker.spy(checker, "_check_search_function")
    _check_update_function_spy: MagicMock = mocker.spy(checker, "_check_update_function")
    _check_is_solved_function_spy: MagicMock = mocker.spy(checker, "_check_is_solved_function")

    checker.check_module(monitor_mock) == []

    _check_monitor_options_spy.assert_called_once_with(monitor_mock)
    _check_issue_options_spy.assert_called_once_with(monitor_mock)
    _check_alert_options_spy.assert_called_once_with(monitor_mock)
    _check_reaction_options_spy.assert_called_once_with(monitor_mock)
    _check_notification_options_spy.assert_called_once_with(monitor_mock)
    _check_issue_data_type_spy.assert_called_once_with(monitor_mock)
    _check_search_function_spy.assert_called_once_with(monitor_mock)
    _check_update_function_spy.assert_called_once_with(monitor_mock)
    _check_is_solved_function_spy.assert_called_once_with(monitor_mock)


def test_check_module_error(mocker, monitor_mock):
    """'check_module' should call all the check functions with the correct arguments and return the
    list of errors. If there were errors, the list should not be empty"""

    class IssueDataType(TypedDict):
        a: str
        b: int

    monitor_mock.monitor_options = MonitorOptions()
    monitor_mock.issue_options = IssueOptions(
        model_id_key="id",
    )
    monitor_mock.IssueDataType = IssueDataType

    async def search() -> list[IssueDataType] | None: ...
    async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None: ...
    def is_solved(issue_data: IssueDataType) -> bool: ...

    monitor_mock.search = search
    monitor_mock.update = update
    monitor_mock.is_solved = is_solved

    _check_monitor_options_spy: MagicMock = mocker.spy(checker, "_check_monitor_options")
    _check_issue_options_spy: MagicMock = mocker.spy(checker, "_check_issue_options")
    _check_alert_options_spy: MagicMock = mocker.spy(checker, "_check_alert_options")
    _check_reaction_options_spy: MagicMock = mocker.spy(checker, "_check_reaction_options")
    _check_notification_options_spy: MagicMock = mocker.spy(checker, "_check_notification_options")
    _check_issue_data_type_spy: MagicMock = mocker.spy(checker, "_check_issue_data_type")
    _check_search_function_spy: MagicMock = mocker.spy(checker, "_check_search_function")
    _check_update_function_spy: MagicMock = mocker.spy(checker, "_check_update_function")
    _check_is_solved_function_spy: MagicMock = mocker.spy(checker, "_check_is_solved_function")

    checker.check_module(monitor_mock) == [
        "'IssueDataType' must have the 'id' field, as specified by 'issue_options.model_id_key'"
    ]

    _check_monitor_options_spy.assert_called_once_with(monitor_mock)
    _check_issue_options_spy.assert_called_once_with(monitor_mock)
    _check_alert_options_spy.assert_called_once_with(monitor_mock)
    _check_reaction_options_spy.assert_called_once_with(monitor_mock)
    _check_notification_options_spy.assert_called_once_with(monitor_mock)
    _check_issue_data_type_spy.assert_called_once_with(monitor_mock)
    _check_search_function_spy.assert_called_once_with(monitor_mock)
    _check_update_function_spy.assert_called_once_with(monitor_mock)
    _check_is_solved_function_spy.assert_called_once_with(monitor_mock)

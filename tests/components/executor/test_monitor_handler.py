import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import components.executor.monitor_handler as monitor_handler
import registry.registry as registry
from base_exception import BaseSentinelaException
from data_models.monitor_options import AlertOptions, CountRule, IssueOptions, PriorityLevels
from models import (
    Alert,
    AlertPriority,
    AlertStatus,
    ExecutionStatus,
    Issue,
    IssueStatus,
    Monitor,
    MonitorExecution,
)
from tests.test_utils import assert_message_in_log, assert_message_not_in_log
from utils.time import now, time_since

pytestmark = pytest.mark.asyncio(loop_scope="session")


# Test _convert_types


async def test_convert_types():
    """'_convert_types' should convert all the data to compatible JSON types recursively"""
    data = {
        "a": "aa",
        "b": 11,
        "c": 2.2,
        "d": True,
        "e": None,
        "f": datetime(2024, 1, 2, 3, 4, 56),
        "g": [1, 2, 3],
        "h": [[datetime(2024, 2, 3, 4, 5, 6, tzinfo=timezone.utc)]],
        "i": {1: datetime(2024, 2, 3, 4, 5, 10, tzinfo=timezone.utc)},
        "j": {1: {2: datetime(2024, 2, 3, 4, 5, 15, tzinfo=timezone.utc)}},
        "k": [{1, 2, 3}, (4, 5)],
    }
    compatible_data = monitor_handler._convert_types(data)

    # Assert the original object hasn't changed
    assert data != compatible_data
    assert compatible_data == {
        "a": "aa",
        "b": 11,
        "c": 2.2,
        "d": True,
        "e": None,
        "f": "2024-01-02T03:04:56.000",
        "g": [1, 2, 3],
        "h": [["2024-02-03T04:05:06.000+00:00"]],
        "i": {1: "2024-02-03T04:05:10.000+00:00"},
        "j": {1: {2: "2024-02-03T04:05:15.000+00:00"}},
        "k": ["{1, 2, 3}", "(4, 5)"],
    }


# Test _get_data_type_compatible


@pytest.mark.parametrize(
    "data",
    [
        [1, 2, 3],
        {1, 2, 3},
        "not a dict",
        1,
        True,
        None,
    ],
)
async def test_make_dict_json_compatible_not_dict(data):
    """'_make_dict_json_compatible' should return 'None' if the data is not a dictionary"""
    compatible_data = monitor_handler._make_dict_json_compatible(data)
    assert compatible_data is None


async def test_make_dict_json_compatible():
    """'_make_dict_json_compatible' should convert all the data to compatible JSON types
    recursively if the root data is a dictionary"""
    data = {
        "a": "aa",
        "b": 11,
        "c": 2.2,
        "d": True,
        "e": None,
        "f": datetime(2024, 1, 2, 3, 4, 56),
        "g": [1, 2, 3],
        "h": [[datetime(2024, 2, 3, 4, 5, 6, tzinfo=timezone.utc)]],
        "i": {1: datetime(2024, 2, 3, 4, 5, 10, tzinfo=timezone.utc)},
        "j": {1: {2: datetime(2024, 2, 3, 4, 5, 15, tzinfo=timezone.utc)}},
        "k": [{1, 2, 3}, (4, 5)],
    }
    compatible_data = monitor_handler._make_dict_json_compatible(data)

    # Assert the original object hasn't changed
    assert data != compatible_data
    assert compatible_data == {
        "a": "aa",
        "b": 11,
        "c": 2.2,
        "d": True,
        "e": None,
        "f": "2024-01-02T03:04:56.000",
        "g": [1, 2, 3],
        "h": [["2024-02-03T04:05:06.000+00:00"]],
        "i": {1: "2024-02-03T04:05:10.000+00:00"},
        "j": {1: {2: "2024-02-03T04:05:15.000+00:00"}},
        "k": ["{1, 2, 3}", "(4, 5)"],
    }


# Test _search_routine


@pytest.mark.parametrize("search_result", [None, []])
async def test_search_routine_no_result(monkeypatch, sample_monitor: Monitor, search_result):
    """'_search_routine' should be able to handle 'None' or empty list returns"""

    async def search_function():
        return search_result

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    await monitor_handler._search_routine(sample_monitor)


@pytest.mark.parametrize("search_result", [(1, 2), {"id": 1}])
async def test_search_routine_not_list(caplog, monkeypatch, sample_monitor: Monitor, search_result):
    """'_search_routine' should ignore the result if it's not a list"""

    async def search_function():
        return search_result

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    await monitor_handler._search_routine(sample_monitor)

    assert_message_in_log(
        caplog, f"Invalid return of 'search' function for {sample_monitor}. Should be a 'list'"
    )


async def test_search_routine_invalid_issues(caplog, monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should ignore the items that are considered as not valid"""

    async def search_function():
        return [
            {"id": 1},
            "not a dict",
            [{"id": 2}],
            {1, 2, 3},
        ]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    assert_message_in_log(
        caplog, f"Invalid issue data from 'search' function for {sample_monitor}: 'not a dict'"
    )
    assert_message_in_log(
        caplog, f"Invalid issue data from 'search' function for {sample_monitor}: '[{{'id': 2}}]'"
    )
    assert_message_in_log(
        caplog, f"Invalid issue data from 'search' function for {sample_monitor}: '{{1, 2, 3}}'"
    )

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 1
    assert issues[0].monitor_id == sample_monitor.id
    assert issues[0].data == {"id": 1}


async def test_search_routine_missing_model_id_key(caplog, monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should ignore the items where the model id key is not present in the
    dict"""

    async def search_function():
        return [
            {"id": 1},
            {"not_id": 2},
            {"another": 3},
        ]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    assert_message_in_log(
        caplog,
        "Invalid issue data from 'search', model id key 'id' not found in "
        f"issue data for {sample_monitor}: '{{'not_id': 2}}'",
    )
    assert_message_in_log(
        caplog,
        "Invalid issue data from 'search', model id key 'id' not found in "
        f"issue data for {sample_monitor}: '{{'another': 3}}'",
    )

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 1
    assert issues[0].monitor_id == sample_monitor.id
    assert issues[0].data == {"id": 1}


@pytest.mark.parametrize("model_id_key", ["id", "model_id", "aaa", "asd123"])
async def test_search_routine_varying_model_id_key(
    monkeypatch, sample_monitor: Monitor, model_id_key
):
    """'_search_routine' should use the model id key defined in the issues options to identify the
    model id of each issue"""

    async def search_function():
        return [
            {model_id_key: 1, "new_value": 10},
            {model_id_key: 2, "new_value": 20},
            {model_id_key: 3, "new_value": 30},
        ]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    issue_options = IssueOptions(model_id_key=model_id_key)
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert all(issue.monitor_id == sample_monitor.id for issue in issues)
    issues_data = {issue.model_id: issue.data for issue in issues}
    assert issues_data == {
        "1": {model_id_key: 1, "new_value": 10},
        "2": {model_id_key: 2, "new_value": 20},
        "3": {model_id_key: 3, "new_value": 30},
    }


async def test_search_routine_skip_duplicate(caplog, monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should skip the items where the 'model_id' is duplicated in the return
    value of the 'search' function"""

    async def search_function():
        return [
            {"id": 1, "some_value": 10},
            {"id": 1, "some_value": 20},
        ]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    assert_message_in_log(caplog, "Found duplicate model id '1'. Skipping this one")

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 1
    assert issues[0].monitor_id == sample_monitor.id
    assert issues[0].data["id"] == 1
    assert issues[0].data["some_value"] == 10


async def test_search_routine_skip_active_issues(monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should skip the items when there's already an active issue with that
    model id"""
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1},
    )
    await sample_monitor.load()

    async def search_function():
        return [
            {"id": 1, "already_exists": True},
            {"id": 2},
        ]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 2

    # The issue with id=1 should be the one that already exists
    assert all(issue.monitor_id == sample_monitor.id for issue in issues)
    issues_data = {issue.model_id: issue.data for issue in issues}
    assert issues_data == {"1": {"id": 1}, "2": {"id": 2}}


async def test_search_routine_skip_not_unique(monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should not skip the items then there's already a solved issue with that
    model id but the 'unique' flag in the issue options is set as 'False'"""
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1},
        status=IssueStatus.solved,
    )
    await sample_monitor.load()

    async def search_function():
        return [
            {"id": 1, "already_exists": True},
            {"id": 2},
        ]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    issue_options = IssueOptions(model_id_key="id", unique=False)
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.active
    )
    assert len(issues) == 2

    # The issue with id=1 should be created again
    assert all(issue.monitor_id == sample_monitor.id for issue in issues)
    issues_data = {issue.model_id: issue.data for issue in issues}
    assert issues_data == {"1": {"id": 1, "already_exists": True}, "2": {"id": 2}}


async def test_search_routine_skip_unique(monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should skip the items then there's already a solved issue with that
    model id and the 'unique' flag in the issue options is set as 'True'"""
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1},
        status=IssueStatus.solved,
    )
    await sample_monitor.load()

    async def search_function():
        return [
            {"id": 1, "already_exists": True},
            {"id": 2},
        ]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    issue_options = IssueOptions(model_id_key="id", unique=True)
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.active
    )
    # The issue with id=1 should not be created again
    assert all(issue.monitor_id == sample_monitor.id for issue in issues)
    assert len(issues) == 1
    assert issues[0].data == {"id": 2}


async def test_search_routine_skip_solved(monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should skip the items that are considered as solved by the 'is_solved'
    function"""

    async def search_function():
        return [
            {"id": 1},
            {"id": 2},
        ]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    def is_solved_function(issue_data):
        return issue_data["id"] == 1

    monkeypatch.setattr(sample_monitor.code, "is_solved", is_solved_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.active
    )
    # The issue with id=1 should not be created
    assert all(issue.monitor_id == sample_monitor.id for issue in issues)
    assert len(issues) == 1
    assert issues[0].data == {"id": 2}


async def test_search_routine_limit_max_issues(monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should limit the maximum number of issues that can be created at once"""

    async def search_function():
        return [{"id": i} for i in range(1, 6)]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)
    monkeypatch.setattr(sample_monitor.code.monitor_options, "max_issues_creation", 3)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.active
    )
    assert len(issues) == 3
    assert all(issue.monitor_id == sample_monitor.id for issue in issues)
    assert {issue.model_id for issue in issues} == {str(i) for i in range(1, 4)}


async def test_search_routine_limit_max_issues_include_new(monkeypatch, sample_monitor: Monitor):
    """'_search_routine' should limit the maximum number of issues that can be created at once, but
    only new issues should count towards this limit"""
    for i in range(1, 4):
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=str(i),
            data={"id": i},
        )
        await sample_monitor.load()

    async def search_function():
        return [{"id": i} for i in range(1, 10)]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)
    monkeypatch.setattr(sample_monitor.code.monitor_options, "max_issues_creation", 3)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.active
    )
    assert len(issues) == 6
    assert all(issue.monitor_id == sample_monitor.id for issue in issues)
    assert {issue.model_id for issue in issues} == {str(i) for i in range(1, 7)}


@pytest.mark.parametrize("number_of_issues", [1, 2, 5, 10, 20])
async def test_search_routine_store_to_monitor(
    monkeypatch, sample_monitor: Monitor, number_of_issues
):
    """'_search_routine' store the created issues into the monitor's instance so it can be easily
    accessed from other parts of the code, without needing to reload it from the database"""

    async def search_function():
        return [{"id": i} for i in range(number_of_issues)]

    monkeypatch.setattr(sample_monitor.code, "search", search_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._search_routine(sample_monitor)

    issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.active
    )
    assert len(issues) == number_of_issues
    assert all(issue.monitor_id == sample_monitor.id for issue in issues)
    issues_ids = {issue.id for issue in issues}
    monitors_issues_ids = {issue.id for issue in sample_monitor.active_issues}
    assert monitors_issues_ids == issues_ids


# Test _update_routine


async def test_update_routine_no_active_issues(mocker, monkeypatch, sample_monitor: Monitor):
    """'_update_routine' should just return if there're no active issues"""
    update_mock = AsyncMock()
    monkeypatch.setattr(sample_monitor.code, "update", update_mock)

    assert sample_monitor.active_issues == []

    await monitor_handler._update_routine(sample_monitor)

    update_mock.assert_not_called()


async def test_update_routine_call_with_issues(monkeypatch, sample_monitor: Monitor):
    """'_update_routine' should call the 'update' function passing the issues data as an argument"""
    # The monitor need active issues to run the update routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="900",
        data={"id": 900},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="901",
        data={"id": 901},
    )
    await sample_monitor.load()

    async def update_function(issues_data):
        return []

    update_mock = AsyncMock(side_effect=update_function)
    monkeypatch.setattr(sample_monitor.code, "update", update_mock)

    await monitor_handler._update_routine(sample_monitor)

    update_mock.assert_awaited_once()

    for issue_data in update_mock.call_args.kwargs["issues_data"]:
        assert issue_data in [{"id": 900}, {"id": 901}]


@pytest.mark.parametrize("update_result", [None, []])
async def test_update_routine_no_result(monkeypatch, sample_monitor: Monitor, update_result):
    """'_update_routine' should be able to handle None or empty list returns"""
    # The monitor need active issues to run the update routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="999",
        data={"id": 999},
    )
    await sample_monitor.load()

    async def update_function(issues_data):
        return update_result

    update_mock = AsyncMock(side_effect=update_function)
    monkeypatch.setattr(sample_monitor.code, "update", update_mock)
    await monitor_handler._update_routine(sample_monitor)

    update_mock.assert_awaited_once()


@pytest.mark.parametrize("update_result", [(1, 2), {"id": 1}])
async def test_update_routine_not_list(caplog, monkeypatch, sample_monitor: Monitor, update_result):
    """'_update_routine' should ignore the result if it's not a list"""
    # The monitor need active issues to run the update routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="999",
        data={"id": 999},
    )
    await sample_monitor.load()

    async def update_function(issues_data):
        return update_result

    monkeypatch.setattr(sample_monitor.code, "update", update_function)

    await monitor_handler._update_routine(sample_monitor)

    assert_message_in_log(
        caplog, f"Invalid return of 'update' function for {sample_monitor}. Should be a 'list'"
    )


async def test_update_routine_invalid_issues(caplog, monkeypatch, sample_monitor: Monitor):
    """'_update_routine' should ignore the items that are considered as not valid"""
    # The monitor need active issues to run the update routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1, "value": 1},
    )
    await sample_monitor.load()

    async def update_function(issues_data):
        return [
            {"id": 1, "value": 2},
            "not a dict",
            [{"id": 2}],
            {1, 2, 3},
        ]

    monkeypatch.setattr(sample_monitor.code, "update", update_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._update_routine(sample_monitor)

    assert_message_in_log(
        caplog, f"Invalid issue data from 'update' function for {sample_monitor}: 'not a dict'"
    )
    assert_message_in_log(
        caplog, f"Invalid issue data from 'update' function for {sample_monitor}: '[{{'id': 2}}]'"
    )
    assert_message_in_log(
        caplog, f"Invalid issue data from 'update' function for {sample_monitor}: '{{1, 2, 3}}'"
    )

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 1
    assert issues[0].data == {"id": 1, "value": 2}


async def test_update_routine_missing_model_id_key(caplog, monkeypatch, sample_monitor: Monitor):
    """'_update_routine' should ignore the items where the model id key is not present in the
    dict"""
    # The monitor need active issues to run the update routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1},
    )
    await sample_monitor.load()

    async def update_function(issues_data):
        return [
            {"id": 1, "new_value": 10},
            {"not_id": 2},
            {"another": 3},
        ]

    monkeypatch.setattr(sample_monitor.code, "update", update_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._update_routine(sample_monitor)

    assert_message_in_log(
        caplog,
        "Invalid issue data from 'update', model id key 'id' not found in "
        f"issue data for {sample_monitor}: '{{'not_id': 2}}'",
    )
    assert_message_in_log(
        caplog,
        "Invalid issue data from 'update', model id key 'id' not found in "
        f"issue data for {sample_monitor}: '{{'another': 3}}'",
    )

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 1
    assert issues[0].data == {"id": 1, "new_value": 10}


@pytest.mark.parametrize("model_id_key", ["id", "model_id", "aaa", "asd123"])
async def test_update_routine_varying_model_id_key(
    monkeypatch, sample_monitor: Monitor, model_id_key
):
    """'_update_routine' should use the model id key defined in the issues options"""
    # The monitor need active issues to run the update routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={model_id_key: 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        data={model_id_key: 2},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="3",
        data={model_id_key: 3},
    )
    await sample_monitor.load()

    async def update_function(issues_data):
        return [
            {model_id_key: 1, "new_value": 10},
            {model_id_key: 2, "new_value": 20},
            {model_id_key: 3, "new_value": 30},
        ]

    monkeypatch.setattr(sample_monitor.code, "update", update_function)

    issue_options = IssueOptions(model_id_key=model_id_key)
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._update_routine(sample_monitor)

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    issues_data = {issue.model_id: issue.data for issue in issues}
    assert issues_data == {
        "1": {model_id_key: 1, "new_value": 10},
        "2": {model_id_key: 2, "new_value": 20},
        "3": {model_id_key: 3, "new_value": 30},
    }


async def test_update_routine_skip_duplicate(caplog, monkeypatch, sample_monitor: Monitor):
    """'_update_routine' should skip the items where the 'model_id' is duplicated in the data"""
    # The monitor need active issues to run the update routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1},
    )
    await sample_monitor.load()

    async def update_function(issues_data):
        return [
            {"id": 1, "some_value": 10},
            {"id": 1, "some_value": 20},
        ]

    monkeypatch.setattr(sample_monitor.code, "update", update_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._update_routine(sample_monitor)

    assert_message_in_log(caplog, "Found duplicate model id '1'. Skipping this one")

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 1
    assert issues[0].data["id"] == 1
    assert issues[0].data["some_value"] == 10


async def test_update_routine_not_active_model_id(caplog, monkeypatch, sample_monitor: Monitor):
    """'_update_routine' should ignore the items where  there isn't an active issue for the monitor
    with that model id"""
    # The monitor need active issues to run the update routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="999",
        data={"id": 999},
    )
    await sample_monitor.load()

    async def update_function(issues_data):
        return [{"id": 1}]

    monkeypatch.setattr(sample_monitor.code, "update", update_function)

    issue_options = IssueOptions(model_id_key="id")
    monkeypatch.setattr(sample_monitor.code, "issue_options", issue_options)

    await monitor_handler._update_routine(sample_monitor)

    assert_message_in_log(
        caplog,
        "Issue with model id '1' not found in active issues. Maybe it changed in the update "
        "process",
    )

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 1
    assert issues[0].data == {"id": 999}


# Test _issues_solve_routine


async def test_issues_solve_routine_no_issues(monkeypatch, sample_monitor: Monitor):
    """'_issues_solve_routine' should do nothing if there're no active issues"""

    def is_solved_function(issue_data):
        return issue_data["id"] == 1

    monkeypatch.setattr(sample_monitor.code, "is_solved", is_solved_function)

    await monitor_handler._issues_solve_routine(sample_monitor)

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert len(issues) == 0


async def test_issues_solve_routine_solve_issues(monkeypatch, sample_monitor: Monitor):
    """'_issues_solve_routine' should check if every monitor's active issue is solved"""
    # The monitor need active issues to run the issues solve routine
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1, "value": 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        data={"id": 2, "value": 2},
    )
    await sample_monitor.load()

    def is_solved(issue_data):
        return issue_data["id"] == 1

    is_solved_mock = MagicMock(side_effect=is_solved)
    monkeypatch.setattr(sample_monitor.code, "is_solved", is_solved_mock)

    await monitor_handler._issues_solve_routine(sample_monitor)

    assert is_solved_mock.call_count == 2

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    result = {issue.model_id: issue.status for issue in issues}
    assert result == {"1": IssueStatus.solved, "2": IssueStatus.active}


# Test _alerts_routine


async def test_alerts_routine_no_alert_options(monkeypatch, sample_monitor: Monitor):
    """'_alerts_routine' should just return if the monitor's 'alert_option' is not defined"""
    assert sample_monitor.alert_options is None
    await monitor_handler._issues_solve_routine(sample_monitor)


async def test_alerts_routine_create_alert(monkeypatch, sample_monitor: Monitor):
    """'_alerts_routine' should create an alert if it's triggered by the active issues and there're
    no other available alerts, linking the active issues without alerts to it"""
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1, "value": 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        data={"id": 2, "value": 2},
    )
    await sample_monitor.load()

    alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels(low=0)))
    monkeypatch.setattr(sample_monitor.code, "alert_options", alert_options, raising=False)

    await monitor_handler._alerts_routine(sample_monitor)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 1

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert all(issue.alert_id == alerts[0].id for issue in issues)


async def test_alerts_routine_not_triggered(monkeypatch, sample_monitor: Monitor):
    """'_alerts_routine' should not create an alert if it's not triggered by the active issues"""
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1, "value": 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        data={"id": 2, "value": 2},
    )
    await sample_monitor.load()

    alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels(low=100)))
    monkeypatch.setattr(sample_monitor.code, "alert_options", alert_options, raising=False)

    await monitor_handler._alerts_routine(sample_monitor)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 0

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert all(issue.alert_id is None for issue in issues)


async def test_alerts_routine_alert_locked_triggered(monkeypatch, sample_monitor: Monitor):
    """'_alerts_routine' should create an alert if all active alerts are locked and the unlinked
    active issues triggers a new alert"""
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1, "value": 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        data={"id": 2, "value": 2},
    )
    locked_alert = await Alert.create(monitor_id=sample_monitor.id, locked=True)
    await sample_monitor.load()

    alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels(low=0)))
    monkeypatch.setattr(sample_monitor.code, "alert_options", alert_options, raising=False)

    await monitor_handler._alerts_routine(sample_monitor)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 2

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert all(issue.alert_id is not None for issue in issues)
    assert all(issue.alert_id != locked_alert.id for issue in issues)


async def test_alerts_routine_alert_locked_not_triggered(monkeypatch, sample_monitor: Monitor):
    """'_alerts_routine' should create an alert if all active alerts are locked and the unlinked
    active issues triggers a new alert"""
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1, "value": 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        data={"id": 2, "value": 2},
    )
    await Alert.create(monitor_id=sample_monitor.id, locked=True)
    await sample_monitor.load()

    alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels(low=100)))
    monkeypatch.setattr(sample_monitor.code, "alert_options", alert_options, raising=False)

    await monitor_handler._alerts_routine(sample_monitor)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 1

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    assert all(issue.alert_id is None for issue in issues)


async def test_alerts_routine_alert_locked_new_issues(monkeypatch, sample_monitor: Monitor):
    """'_alerts_routine' should create an alert if it's triggered and any other active alerts are
    locked and should link the active issues without alerts to it, but should not change other
    active issues"""
    # The first issue will be linked to the locked alert
    locked_alert = await Alert.create(monitor_id=sample_monitor.id, locked=True)
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        alert_id=locked_alert.id,
        data={"id": 1, "value": 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        data={"id": 2, "value": 2},
    )
    await sample_monitor.load()

    alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels(low=0)))
    monkeypatch.setattr(sample_monitor.code, "alert_options", alert_options, raising=False)

    await monitor_handler._alerts_routine(sample_monitor)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 2

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    issues_alerts = {issue.model_id: issue.alert_id for issue in issues}
    assert issues_alerts["1"] == locked_alert.id
    assert issues_alerts["2"] is not None
    assert issues_alerts["2"] != locked_alert.id


async def test_alerts_routine_priority_updated(monkeypatch, sample_monitor: Monitor):
    """'_alerts_routine' should update it's priority after linking all the issues"""
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1, "value": 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        data={"id": 2, "value": 2},
    )
    await Alert.create(monitor_id=sample_monitor.id)
    await sample_monitor.load()

    alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels(low=0, critical=1)))
    monkeypatch.setattr(sample_monitor.code, "alert_options", alert_options, raising=False)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 1
    assert alerts[0].priority == AlertPriority.low

    await monitor_handler._alerts_routine(sample_monitor)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 1
    assert alerts[0].priority == AlertPriority.critical


async def test_alerts_routine_solved(monkeypatch, sample_monitor: Monitor):
    """'_alerts_routine' should solve if there're no active issues linked to it"""
    alert = await Alert.create(monitor_id=sample_monitor.id)
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        alert_id=alert.id,
        status=IssueStatus.solved,
        data={"id": 1, "value": 1},
    )
    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="2",
        alert_id=alert.id,
        status=IssueStatus.solved,
        data={"id": 2, "value": 2},
    )
    await sample_monitor.load()

    alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels(low=0, critical=1)))
    monkeypatch.setattr(sample_monitor.code, "alert_options", alert_options, raising=False)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 1
    assert alerts[0].status == AlertStatus.active

    await monitor_handler._alerts_routine(sample_monitor)

    alerts = await Alert.get_all(Alert.monitor_id == sample_monitor.id)
    assert len(alerts) == 1
    assert alerts[0].status == AlertStatus.solved


# Test _run_routines


@pytest.mark.parametrize(
    "tasks",
    [
        [],
        ["search"],
        ["update"],
        ["search", "update"],
    ],
)
async def test_run_routines(monkeypatch, sample_monitor: Monitor, tasks):
    """'_run_routines' should execute the routines for the module based on the provided tasks"""

    async def do_nothing(monitor): ...

    update_routine_mock = AsyncMock(side_effect=do_nothing)
    issues_solve_routine_mock = AsyncMock(side_effect=do_nothing)
    search_routine_mock = AsyncMock(side_effect=do_nothing)
    alerts_routine_mock = AsyncMock(side_effect=do_nothing)

    monkeypatch.setattr(monitor_handler, "_update_routine", update_routine_mock)
    monkeypatch.setattr(monitor_handler, "_issues_solve_routine", issues_solve_routine_mock)
    monkeypatch.setattr(monitor_handler, "_search_routine", search_routine_mock)
    monkeypatch.setattr(monitor_handler, "_alerts_routine", alerts_routine_mock)

    await monitor_handler._run_routines(sample_monitor, tasks)

    await sample_monitor.refresh()

    if "update" in tasks:
        update_routine_mock.assert_awaited_once_with(sample_monitor)
        assert time_since(sample_monitor.update_executed_at) < 0.1
    else:
        update_routine_mock.assert_not_called()
        assert sample_monitor.update_executed_at is None

    issues_solve_routine_mock.assert_awaited_once_with(sample_monitor)

    if "search" in tasks:
        search_routine_mock.assert_awaited_once_with(sample_monitor)
        assert time_since(sample_monitor.search_executed_at) < 0.1
    else:
        search_routine_mock.assert_not_called()
        assert sample_monitor.search_executed_at is None

    alerts_routine_mock.assert_awaited_once_with(sample_monitor)


async def test_run_routines_load_modules(mocker, monkeypatch, sample_monitor: Monitor):
    """'_run_routines' should load the active issues and alerts before executing the routines"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1, "value": 1},
    )

    async def do_nothing(monitor): ...

    monkeypatch.setattr(monitor_handler, "_update_routine", do_nothing)
    monkeypatch.setattr(monitor_handler, "_issues_solve_routine", do_nothing)
    monkeypatch.setattr(monitor_handler, "_search_routine", do_nothing)

    alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels(critical=0)))
    monkeypatch.setattr(sample_monitor.code, "alert_options", alert_options, raising=False)

    load_spy: AsyncMock = mocker.spy(sample_monitor, "load")

    assert sample_monitor.active_issues == []
    assert sample_monitor.active_alerts == []

    await monitor_handler._run_routines(sample_monitor, [])

    load_spy.assert_called_once()
    assert len(sample_monitor.active_issues) == 1
    assert sample_monitor.active_issues[0].id == issue.id
    assert len(sample_monitor.active_alerts) == 1
    assert sample_monitor.active_alerts[0].id == alert.id


# Test _heartbeat_routine


async def test_heartbeat_routine(monkeypatch, sample_monitor: Monitor):
    """'_heartbeat_routine' should handle execution timeouts while running the monitor routines"""
    monkeypatch.setattr(monitor_handler.configs, "executor_monitor_heartbeat_time", 0.5)

    await sample_monitor.refresh()
    assert sample_monitor.last_heartbeat is None

    heartbeat_task = asyncio.create_task(monitor_handler._heartbeat_routine(sample_monitor))

    await asyncio.sleep(0)
    for _ in range(4):
        await sample_monitor.refresh()
        assert sample_monitor.last_heartbeat > now() - timedelta(seconds=0.1)
        await asyncio.sleep(0.5)

    heartbeat_task.cancel()


# Test run


async def test_run_invalid_payload(caplog):
    """'run' should log an error if the payload is invalid and just return"""
    await monitor_handler.run({})
    assert_message_in_log(caplog, "Message '{}' missing 'payload' field")


async def test_run_payload_wrong_structure(caplog):
    """'run' should log an error if the payload has the wrong structure and just return"""
    await monitor_handler.run({"payload": {}})
    assert_message_in_log(caplog, "Invalid payload: 2 validation errors for ProcessMonitorPayload")


async def test_run_monitor_not_found(caplog):
    """'run' should ignore the message if a monitor with the provided id was not found"""
    await monitor_handler.run({"payload": {"monitor_id": 999999999, "tasks": []}})
    assert_message_in_log(caplog, "Monitor 999999999 not found. Skipping message")


@pytest.mark.flaky(reruns=2)
async def test_run_monitor_not_registered(monkeypatch, sample_monitor: Monitor):
    """'run' should handle raise a 'MonitorNotRegisteredError' exception if the monitor is not
    registered"""
    monkeypatch.setattr(registry, "MONITORS_READY_TIMEOUT", 0.2)
    del registry._monitors[sample_monitor.id]

    run_task = asyncio.create_task(
        monitor_handler.run({"payload": {"monitor_id": sample_monitor.id, "tasks": ["search"]}})
    )

    start_time = time.perf_counter()
    await asyncio.sleep(0.1)
    registry.monitors_ready.set()
    registry.monitors_pending.clear()

    with pytest.raises(registry.MonitorNotRegisteredError):
        await run_task
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.1 - 0.001
    assert total_time < 0.1 + 0.03

    monitor_execution = await MonitorExecution.get(MonitorExecution.monitor_id == sample_monitor.id)
    assert monitor_execution is None


async def test_run_monitor_skip_running(caplog, mocker, sample_monitor: Monitor):
    """'run' should skip running the monitor if it's 'running' flag is 'True'"""
    await sample_monitor.set_running(True)

    run_routines_spy: AsyncMock = mocker.spy(monitor_handler, "_run_routines")

    await monitor_handler.run({"payload": {"monitor_id": sample_monitor.id, "tasks": ["search"]}})

    assert_message_not_in_log(caplog, "Invalid payload")
    run_routines_spy.assert_not_called()

    monitor_execution = await MonitorExecution.get(MonitorExecution.monitor_id == sample_monitor.id)
    assert monitor_execution is None


@pytest.mark.flaky(reruns=2)
async def test_run_monitor_heartbeat(monkeypatch, sample_monitor: Monitor):
    """'run' should handle execution timeouts while running the monitor routines"""

    async def sleep(monitor, tasks):
        await asyncio.sleep(2.1)

    monkeypatch.setattr(monitor_handler, "_run_routines", sleep)

    monkeypatch.setattr(monitor_handler.configs, "executor_monitor_heartbeat_time", 0.5)

    await sample_monitor.refresh()
    assert sample_monitor.last_heartbeat is None

    run_task = asyncio.create_task(
        monitor_handler.run({"payload": {"monitor_id": sample_monitor.id, "tasks": ["search"]}})
    )

    await asyncio.sleep(0.05)
    for _ in range(4):
        await sample_monitor.refresh()
        assert sample_monitor.last_heartbeat > now() - timedelta(seconds=0.1)
        await asyncio.sleep(0.5)

    await run_task

    monitor_execution = await MonitorExecution.get(MonitorExecution.monitor_id == sample_monitor.id)
    assert monitor_execution is not None
    assert monitor_execution.status == ExecutionStatus.success
    assert monitor_execution.error_type is None


@pytest.mark.parametrize("tasks", [["search"], ["update"], ["search", "update"]])
async def test_run_monitor_set_running(mocker, sample_monitor: Monitor, tasks):
    """'run' should set the monitor's 'running' flag to 'True' while running the routines"""
    run_routines_spy: AsyncMock = mocker.spy(monitor_handler, "_run_routines")
    set_running_spy: AsyncMock = mocker.spy(Monitor, "set_running")

    await monitor_handler.run({"payload": {"monitor_id": sample_monitor.id, "tasks": tasks}})

    run_routines_spy.assert_awaited_once()

    assert set_running_spy.await_count == 2
    assert set_running_spy.await_args_list[0].args[0].id == sample_monitor.id
    assert set_running_spy.await_args_list[0].args[1] is True
    assert set_running_spy.await_args_list[1].args[0].id == sample_monitor.id
    assert set_running_spy.await_args_list[1].args[1] is False

    monitor_execution = await MonitorExecution.get(MonitorExecution.monitor_id == sample_monitor.id)
    assert monitor_execution is not None
    assert monitor_execution.status == ExecutionStatus.success
    assert monitor_execution.error_type is None


@pytest.mark.flaky(reruns=2)
@pytest.mark.parametrize("tasks", [["search"], ["update"], ["search", "update"]])
async def test_run_monitor_timeout(caplog, mocker, monkeypatch, sample_monitor: Monitor, tasks):
    """'run' should handle execution timeouts while running the monitor routines"""

    async def sleep(monitor, tasks):
        await asyncio.sleep(1)

    monkeypatch.setattr(monitor_handler, "_run_routines", sleep)

    monkeypatch.setattr(sample_monitor.code.monitor_options, "execution_timeout", 0.5)

    set_running_spy: AsyncMock = mocker.spy(Monitor, "set_running")
    set_queued_spy: AsyncMock = mocker.spy(Monitor, "set_queued")

    start_time = time.perf_counter()
    await monitor_handler.run({"payload": {"monitor_id": sample_monitor.id, "tasks": tasks}})
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.5 - 0.001
    assert total_time < 0.5 + 0.03

    assert_message_in_log(caplog, f"Execution for monitor '{sample_monitor}' timed out")

    assert set_running_spy.await_count == 2
    assert set_running_spy.await_args_list[0].args[0].id == sample_monitor.id
    assert set_running_spy.await_args_list[0].args[1] is True
    assert set_running_spy.await_args_list[1].args[0].id == sample_monitor.id
    assert set_running_spy.await_args_list[1].args[1] is False

    set_queued_spy.assert_awaited_once()
    assert set_queued_spy.await_args_list[0].args[0].id == sample_monitor.id
    assert set_queued_spy.await_args_list[0].args[1] is False

    monitor_execution = await MonitorExecution.get(MonitorExecution.monitor_id == sample_monitor.id)
    assert monitor_execution is not None
    assert monitor_execution.status == ExecutionStatus.failed
    assert monitor_execution.error_type == "timeout"


@pytest.mark.parametrize("tasks", [["search"], ["update"], ["search", "update"]])
async def test_run_monitor_sentinela_exception(mocker, monkeypatch, sample_monitor: Monitor, tasks):
    """'run' should re-raise Sentinela exceptions"""

    class SomeException(BaseSentinelaException):
        pass

    async def error(monitor, tasks):
        raise SomeException("Something is not right")

    monkeypatch.setattr(monitor_handler, "_run_routines", error)

    set_running_spy: AsyncMock = mocker.spy(Monitor, "set_running")
    set_queued_spy: AsyncMock = mocker.spy(Monitor, "set_queued")

    with pytest.raises(SomeException):
        await monitor_handler.run({"payload": {"monitor_id": sample_monitor.id, "tasks": tasks}})

    assert set_running_spy.await_count == 2
    assert set_running_spy.await_args_list[0].args[0].id == sample_monitor.id
    assert set_running_spy.await_args_list[0].args[1] is True
    assert set_running_spy.await_args_list[1].args[0].id == sample_monitor.id
    assert set_running_spy.await_args_list[1].args[1] is False

    set_queued_spy.assert_awaited_once()
    assert set_queued_spy.await_args_list[0].args[0].id == sample_monitor.id
    assert set_queued_spy.await_args_list[0].args[1] is False

    monitor_execution = await MonitorExecution.get(MonitorExecution.monitor_id == sample_monitor.id)
    assert monitor_execution is not None
    assert monitor_execution.status == ExecutionStatus.failed
    assert monitor_execution.error_type == "SomeException: Something is not right"


@pytest.mark.parametrize("tasks", [["search"], ["update"], ["search", "update"]])
async def test_run_monitor_error(caplog, mocker, monkeypatch, sample_monitor: Monitor, tasks):
    """'run' should handle errors when running the monitor routines"""

    async def error(monitor, tasks):
        raise ValueError("Something is not right")

    monkeypatch.setattr(monitor_handler, "_run_routines", error)

    set_running_spy: AsyncMock = mocker.spy(Monitor, "set_running")
    set_queued_spy: AsyncMock = mocker.spy(Monitor, "set_queued")

    await monitor_handler.run({"payload": {"monitor_id": sample_monitor.id, "tasks": tasks}})

    assert_message_in_log(caplog, f"Error in execution for monitor '{sample_monitor}'")
    assert_message_in_log(caplog, "ValueError: Something is not right")
    assert_message_in_log(caplog, "Exception caught successfully, going on")

    assert set_running_spy.await_count == 2
    assert set_running_spy.await_args_list[0].args[0].id == sample_monitor.id
    assert set_running_spy.await_args_list[0].args[1] is True
    assert set_running_spy.await_args_list[1].args[0].id == sample_monitor.id
    assert set_running_spy.await_args_list[1].args[1] is False

    set_queued_spy.assert_awaited_once()
    assert set_queued_spy.await_args_list[0].args[0].id == sample_monitor.id
    assert set_queued_spy.await_args_list[0].args[1] is False

    monitor_execution = await MonitorExecution.get(MonitorExecution.monitor_id == sample_monitor.id)
    assert monitor_execution is not None
    assert monitor_execution.status == ExecutionStatus.failed
    assert monitor_execution.error_type == "Something is not right"

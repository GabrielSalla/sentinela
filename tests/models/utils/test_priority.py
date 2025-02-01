from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import models.utils.priority as priority
import utils.time as time_utils
from data_models.monitor_options import AgeRule, CountRule, PriorityLevels, ValueRule
from models import Issue, Monitor
from models.utils.priority import AlertPriority

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "seconds_ago, expected_priority",
    [
        (0, None),
        (5, None),
        (6, AlertPriority.informational),
        (15, AlertPriority.informational),
        (16, AlertPriority.low),
        (25, AlertPriority.low),
        (26, AlertPriority.moderate),
        (35, AlertPriority.moderate),
        (36, AlertPriority.high),
        (45, AlertPriority.high),
        (46, AlertPriority.critical),
        (120, AlertPriority.critical),
    ],
)
async def test_calculate_age_rule(sample_monitor: Monitor, seconds_ago, expected_priority):
    """'_calculate_age_rule' should return the priority calculated from the issues' ages and 'None'
    if no priority triggered"""
    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i},
            # Even though the calculation uses a ">" instead of a ">=" comparison, the issue age
            # when 'seconds_ago + i = 10' will be some milliseconds above 10 seconds and, therefore,
            # greater than 10 seconds, for the 'informational' priority. The same applies to the
            # other priorities that are right on the edge of each priority level
            created_at=time_utils.now() - timedelta(seconds=seconds_ago + i),
        )
        for i in range(5)
    ]

    rule = AgeRule(
        priority_levels=PriorityLevels(informational=10, low=20, moderate=30, high=40, critical=50)
    )

    result_priority = priority._calculate_age_rule(rule, issues)

    assert result_priority == expected_priority


@pytest.mark.parametrize("provided_level", AlertPriority)
async def test_calculate_age_rule_missing_priorities(sample_monitor: Monitor, provided_level):
    """'_calculate_age_rule' should handle when not all priority levels are defined"""
    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i},
            created_at=time_utils.now() - timedelta(seconds=10),
        )
        for i in range(5)
    ]

    rule = AgeRule(priority_levels=PriorityLevels(**{provided_level.name: 10}))

    result_priority = priority._calculate_age_rule(rule, issues)

    assert result_priority == provided_level


@pytest.mark.parametrize(
    "number_of_issues, expected_priority",
    [
        (0, None),
        (2, None),
        (3, AlertPriority.informational),
        (4, AlertPriority.informational),
        (5, AlertPriority.low),
        (6, AlertPriority.low),
        (7, AlertPriority.moderate),
        (8, AlertPriority.moderate),
        (9, AlertPriority.high),
        (10, AlertPriority.high),
        (11, AlertPriority.critical),
        (15, AlertPriority.critical),
    ],
)
async def test_calculate_count_rule(sample_monitor: Monitor, number_of_issues, expected_priority):
    """'_calculate_count_rule' should return the priority calculated from number of issues and None
    if no priority triggered"""
    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i},
        )
        for i in range(number_of_issues)
    ]

    rule = CountRule(
        priority_levels=PriorityLevels(informational=2, low=4, moderate=6, high=8, critical=10)
    )

    result_priority = priority._calculate_count_rule(rule, issues)

    assert result_priority == expected_priority


@pytest.mark.parametrize("provided_level", AlertPriority)
async def test_calculate_count_rule_missing_priorities(sample_monitor: Monitor, provided_level):
    """'_calculate_count_rule' should handle when not all priority levels are defined"""
    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i},
        )
        for i in range(5)
    ]

    rule = CountRule(priority_levels=PriorityLevels(**{provided_level.name: 4}))

    result_priority = priority._calculate_count_rule(rule, issues)

    assert result_priority == provided_level


@pytest.mark.parametrize(
    "base_value, expected_priority",
    [
        (0, None),
        (6, None),
        (7, AlertPriority.informational),
        (16, AlertPriority.informational),
        (17, AlertPriority.low),
        (26, AlertPriority.low),
        (27, AlertPriority.moderate),
        (36, AlertPriority.moderate),
        (37, AlertPriority.high),
        (46, AlertPriority.high),
        (47, AlertPriority.critical),
        (120, AlertPriority.critical),
    ],
)
async def test_calculate_value_rule_greater_than(
    sample_monitor: Monitor, base_value, expected_priority
):
    """'_calculate_value_rule' should return the priority calculated from number of issues and None
    if no priority triggered. When using the 'greater_than' rule the priority triggered should be
    the highest that the value is greater than the issues' data value"""
    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i, "value": base_value + i},
        )
        for i in range(5)
    ]

    rule = ValueRule(
        value_key="value",
        operation="greater_than",
        priority_levels=PriorityLevels(informational=10, low=20, moderate=30, high=40, critical=50),
    )

    result_priority = priority._calculate_value_rule(rule, issues)

    assert result_priority == expected_priority


@pytest.mark.parametrize("provided_level", AlertPriority)
async def test_calculate_value_rule_greater_than_missing_priorities(
    sample_monitor: Monitor, provided_level
):
    """'_calculate_value_rule' should handle when not all priority levels are defined"""
    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i, "value": 10},
        )
        for i in range(5)
    ]

    rule = ValueRule(
        value_key="value",
        operation="greater_than",
        priority_levels=PriorityLevels(**{provided_level.name: 9}),
    )

    result_priority = priority._calculate_value_rule(rule, issues)

    assert result_priority == provided_level


@pytest.mark.parametrize(
    "base_value, expected_priority",
    [
        (0, AlertPriority.critical),
        (6, AlertPriority.critical),
        (7, AlertPriority.critical),
        (16, AlertPriority.high),
        (17, AlertPriority.high),
        (26, AlertPriority.moderate),
        (27, AlertPriority.moderate),
        (36, AlertPriority.low),
        (37, AlertPriority.low),
        (46, AlertPriority.informational),
        (49, AlertPriority.informational),
        (50, None),
        (120, None),
    ],
)
async def test_calculate_value_rule_lesser_than(
    sample_monitor: Monitor, base_value, expected_priority
):
    """'_calculate_value_rule' should return the priority calculated from number of issues and None
    if no priority triggered. When using the 'lesser_than' rule the priority triggered should be
    the highest that the value is lesser than the issues' data value"""
    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i, "other_value": base_value + i},
        )
        for i in range(5)
    ]

    rule = ValueRule(
        value_key="other_value",
        operation="lesser_than",
        priority_levels=PriorityLevels(informational=50, low=40, moderate=30, high=20, critical=10),
    )

    result_priority = priority._calculate_value_rule(rule, issues)

    assert result_priority == expected_priority


@pytest.mark.parametrize("provided_level", AlertPriority)
async def test_calculate_value_rule_lesser_than_missing_priorities(
    sample_monitor: Monitor, provided_level
):
    """'_calculate_value_rule' should handle when not all priority levels are defined"""
    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i, "value": 10},
        )
        for i in range(5)
    ]

    rule = ValueRule(
        value_key="value",
        operation="lesser_than",
        priority_levels=PriorityLevels(**{provided_level.name: 11}),
    )

    result_priority = priority._calculate_value_rule(rule, issues)

    assert result_priority == provided_level


@pytest.mark.parametrize(
    "rule",
    [
        AgeRule(priority_levels=PriorityLevels()),
        CountRule(priority_levels=PriorityLevels()),
        ValueRule(value_key="value", operation="greater_than", priority_levels=PriorityLevels()),
    ],
)
async def test_calculate_priority(mocker, sample_monitor: Monitor, rule):
    """'_calculate_value_rule' should call the correct calculation function based on the provided
    rule"""
    calculate_age_rule_spy: MagicMock = mocker.spy(priority, "_calculate_age_rule")
    calculate_count_rule_spy: MagicMock = mocker.spy(priority, "_calculate_count_rule")
    calculate_value_rule_spy: MagicMock = mocker.spy(priority, "_calculate_value_rule")

    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i, "value": 10},
        )
        for i in range(5)
    ]

    priority.calculate_priority(rule, issues)

    if isinstance(rule, AgeRule):
        calculate_age_rule_spy.assert_called_once_with(rule, issues)
    else:
        calculate_age_rule_spy.assert_not_called()

    if isinstance(rule, CountRule):
        calculate_count_rule_spy.assert_called_once_with(rule, issues)
    else:
        calculate_count_rule_spy.assert_not_called()

    if isinstance(rule, ValueRule):
        calculate_value_rule_spy.assert_called_once_with(rule, issues)
    else:
        calculate_value_rule_spy.assert_not_called()


async def test_calculate_priority_invalid_rule(mocker, sample_monitor: Monitor):
    """'_calculate_value_rule' raise a 'ValueError' exception when the provided rule is invalid"""
    calculate_age_rule_spy: MagicMock = mocker.spy(priority, "_calculate_age_rule")
    calculate_count_rule_spy: MagicMock = mocker.spy(priority, "_calculate_count_rule")
    calculate_value_rule_spy: MagicMock = mocker.spy(priority, "_calculate_value_rule")

    issues = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id=f"{i}",
            data={"id": i, "value": 10},
        )
        for i in range(5)
    ]

    with pytest.raises(ValueError, match="Invalid rule value 'rule'"):
        priority.calculate_priority("rule", issues)

    calculate_age_rule_spy.assert_not_called()
    calculate_count_rule_spy.assert_not_called()
    calculate_value_rule_spy.assert_not_called()

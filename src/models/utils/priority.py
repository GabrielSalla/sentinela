import enum
from typing import Sequence

from src.models.issue import Issue
from src.options import AgeRule, CountRule, ValueRule
from src.utils.time import time_since

_operators = {
    "greater_than": lambda a, b: a > b,
    "lesser_than": lambda a, b: a < b,
}


class AlertPriority(enum.IntEnum):
    """Alert priority levels"""
    critical = 1
    high = 2
    moderate = 3
    low = 4
    informational = 5


def _calculate_age_rule(rule: AgeRule, issues: list[Issue] | Sequence[Issue]) -> int | None:
    """Calculate the priority based on the issues' ages"""
    issues_ages = [time_since(issue.created_at) for issue in issues]

    for priority in sorted(AlertPriority):
        if rule.priority_levels[priority.name] is None:
            continue

        reference_value = rule.priority_levels[priority.name]

        for issue_age in issues_ages:
            if issue_age > reference_value:
                return priority

    return None


def _calculate_count_rule(rule: CountRule, issues: list[Issue] | Sequence[Issue]) -> int | None:
    """Calculate the priority based on the number of issues"""
    count = len(issues)

    for priority in sorted(AlertPriority):
        if rule.priority_levels[priority.name] is None:
            continue

        if count > rule.priority_levels[priority.name]:
            return priority

    return None


def _calculate_value_rule(rule: ValueRule, issues: list[Issue] | Sequence[Issue]) -> int | None:
    """Calculate the priority based on a value in the issues' data field. The highest priority is
    triggered when at least 1 issue has the 'value' of the provided 'value_key' above or below the
    priority value, based to the 'operation' parameter"""
    issues_values = [issue.data.get(rule.value_key) for issue in issues]
    operator = _operators[rule.operation]

    for priority in sorted(AlertPriority):
        if rule.priority_levels[priority.name] is None:
            continue

        reference_value = rule.priority_levels[priority.name]

        for issue_value in issues_values:
            priority_triggered = operator(issue_value, reference_value)
            if priority_triggered:
                return priority

    return None


def calculate_priority(
    rule: AgeRule | CountRule | ValueRule, issues: list[Issue] | Sequence[Issue]
) -> int | None:
    """Calculate the priority based on the rule and the provided issues"""
    if isinstance(rule, AgeRule):
        return _calculate_age_rule(rule, issues)
    elif isinstance(rule, CountRule):
        return _calculate_count_rule(rule, issues)
    elif isinstance(rule, ValueRule):
        return _calculate_value_rule(rule, issues)
    else:
        raise ValueError(f"Invalid rule value '{rule}'")

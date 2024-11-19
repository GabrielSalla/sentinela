from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from dataclass_type_validator import dataclass_validate

from src.configs import configs


@dataclass_validate(strict=True)
@dataclass
class MonitorOptions:
    """
    Define the primary configuration for the monitor in the `monitor_options` variable.
    - `search_cron`: Cron expression that schedules when to **search** for new issues.
    - `update_cron`: Cron expression that schedules when to **update** issues.
    - `max_issues_creation`: Sets the maximum number of new issues that can be created during each
    **search** routine. Defaults to the `max_issues_creation` value in `configs.yaml`.
    - `execution_timeout`: Sets a timeout for both search and update routines. Defaults to
    `executor_monitor_timeout` in `configs.yaml`.
    """
    search_cron: str | None = None
    update_cron: str | None = None
    max_issues_creation: int = configs.max_issues_creation
    execution_timeout: int = configs.executor_monitor_timeout


@dataclass_validate(strict=True)
@dataclass
class IssueOptions:
    """
    Specify settings for issue management in the `issue_options` variable.
    - `model_id_key`: A key that uniquely identifies each issue, such as an ID column in a database.
    - `solvable`: Indicates if an issue can be resolved automatically. Issues set as non-solvable
    require manual intervention. Defaults to `true`.
    - `unique`: Ensures that only one instance of a given issue (based on the `model_id_key`) is
    created. Non-solvable issues are often set as unique to avoid duplicate entries. Defaults to
    `false`.
    """

    model_id_key: str
    solvable: bool = True
    unique: bool = False


@dataclass_validate(strict=True)
@dataclass
class PriorityLevels:
    """
    Priority levels definition. For the defined rule, what value should trigger each level.
    - `informational`: level that triggers **informational P5** alerts
    - `low`: level that triggers **low P4** alerts
    - `moderate`: level that triggers **moderate P3** alerts
    - `high`: level that triggers **high P2** alerts
    - `critical`: level that triggers **critical P1** alerts
    """

    informational: int | None = None
    low: int | None = None
    moderate: int | None = None
    high: int | None = None
    critical: int | None = None

    def __getitem__(self, name: str):
        return getattr(self, name)


@dataclass_validate(strict=True)
@dataclass
class AgeRule:
    """
    The **Age Rule** calculates the alert priority based on the age of the active issues. The alert
    level will be determined by the **oldest active issue** in the alert. The priority value
    represents the issue age in **seconds** that triggers each alert level.
    - `priority_levels`: Defines the values to trigger each alert level based on the issue age.
    """

    priority_levels: PriorityLevels


@dataclass_validate(strict=True)
@dataclass
class CountRule:
    """
    The **Count Rule** calculates the alert priority based on the number of active issues linked to
    the alert. The alert level will be determined by the **highest number of active issues**.
    The priority value indicates how many active issues trigger each alert level.
    - `priority_levels`: Defines the values to trigger each alert level based on the number of
    active issues.
    """

    priority_levels: PriorityLevels


@dataclass_validate(strict=True)
@dataclass
class ValueRule:
    """
    The **Value Rule** calculates the alert priority based on a specific value from the issue's
    data. The alert level will be determined by the **'value'** of the provided `value_key`.
    - `value_key`: The key in the issue data that contains the numeric value. This value will be
    compared against the priority levels to define the alert level.
    - `operation`: Defines the comparison operation to use between the value and the priority
    levels. Can be either `greater_than` (to trigger the level when the value exceeds the priority
    level) or `lesser_than` (to trigger the level when the value is below the priority level).
    - `priority_levels`: Defines the values to trigger each alert level based on the issue's value.
    """

    value_key: str
    operation: str
    priority_levels: PriorityLevels


@dataclass_validate(strict=True)
@dataclass
class AlertOptions:
    """
    Configure alert behavior in the alert_options variable, setting rules for alert levels and
    handling acknowledgments.
    - `rule`: Specifies the rule to use for alert level calculations. Available options are
    `AgeRule`, `CountRule`, and `ValueRule`.
    - `dismiss_acknowledge_on_new_issues` Determines if acknowledgment for an alert should be reset
    when new issues are linked to it. Defaults to `false`.
    """
    rule: AgeRule | CountRule | ValueRule
    dismiss_acknowledge_on_new_issues: bool = False


reaction_function_type = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]


@dataclass_validate(strict=True)
@dataclass
class ReactionOptions:
    """
    Reactions are optional and can be configured reactions to specific events by creating a
    `reaction_options` variable with an instance of the `ReactionOptions` class.

    Reactions are defined as a list of **async functions** that are triggered when specified events
    occur. Each function is called with the event's payload, allowing customized actions based on
    the event data.

    The event payload provided to each reaction function contains structured information about the
    event source, details, and any additional context. This allows reaction functions to respond
    precisely to specific events.

    ```python
    {
        "event_source": "Specifies the model that generated the event (e.g., `monitor`, `issue`,
        `alert`)."
        "event_source_id": "The unique identifier of the object that triggered the event (e.g.,
        `monitor_id`, `issue_id`)."
        "event_source_monitor_id": "The monitor ID associated with the object that generated the
        event."
        "event_name": "Name of the event, such as `alert_created` or `issue_solved`.",
        "event_data": {
            "Object with detailed information about the event source."
        },
        "extra_payload": "Additional information that may be sent along with the event, providing
        further context.",
    }
    ```

    Check the documentation for a more detailed explanation of each event.
    """
    alert_acknowledge_dismissed: list[reaction_function_type] = field(default_factory=list)
    alert_acknowledged: list[reaction_function_type] = field(default_factory=list)
    alert_created: list[reaction_function_type] = field(default_factory=list)
    alert_issues_linked: list[reaction_function_type] = field(default_factory=list)
    alert_locked: list[reaction_function_type] = field(default_factory=list)
    alert_priority_decreased: list[reaction_function_type] = field(default_factory=list)
    alert_priority_increased: list[reaction_function_type] = field(default_factory=list)
    alert_solved: list[reaction_function_type] = field(default_factory=list)
    alert_unlocked: list[reaction_function_type] = field(default_factory=list)
    alert_updated: list[reaction_function_type] = field(default_factory=list)

    issue_linked: list[reaction_function_type] = field(default_factory=list)
    issue_created: list[reaction_function_type] = field(default_factory=list)
    issue_dropped: list[reaction_function_type] = field(default_factory=list)
    issue_solved: list[reaction_function_type] = field(default_factory=list)
    issue_updated_not_solved: list[reaction_function_type] = field(default_factory=list)
    issue_updated_solved: list[reaction_function_type] = field(default_factory=list)

    monitor_enabled_changed: list[reaction_function_type] = field(default_factory=list)

    notification_closed: list[reaction_function_type] = field(default_factory=list)
    notification_created: list[reaction_function_type] = field(default_factory=list)

    def __getitem__(self, name: str):
        return getattr(self, name)

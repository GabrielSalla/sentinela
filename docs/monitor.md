# Creating a new monitor
This guide will walk through the steps to set up a new monitor.

# Set up the monitor directory
To ensure proper organization and avoid conflicts between monitors, it's recommended to have a dedicated directory for each monitor. This separation prevents conflicts caused by files with identical names, ensuring that each monitor's resources remain distinct and do not overwrite one another.
1. Select a directory where the monitors will be stored.
2. Create a new folder named after the monitor (e.g., `my_monitor`). This folder will have all files related to the monitor, including its code and any additional resources.
3. Place the monitor's main file inside its corresponding folder.

```
monitors/
└── my_monitor/
    └── my_monitor.py
```

# Importing the dependencies
To create a monitor, import specific dependencies from `monitor_utils`. Available objects are:

**Settings options**
- [`MonitorOptions`](#monitor-options)
- [`IssueOptions`](#issue-options)
- [`AlertOptions`](#alert-options)
- [`ReactionOptions`](#reactions)

**Alerts triggering settings**
- [`AgeRule`](#age-rule)
- [`CountRule`](#count-rule)
- [`ValueRule`](#value-rule)
- [`PriorityLevels`](#priority-levels)

**Functions**
- [`query`](#query)
- [`read_file`](#read-file)

To get started with a simple monitor, use the following imports:

```python
from typing import TypedDict

from monitor_utils import (
    AlertOptions,
    CountRule,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
)
```

# The settings
To set up the monitor’s behavior, issues, and alerts, use the provided Options dataclasses. These settings define how the monitor will manage issues and alerts.

## Monitor options
Define the primary configuration for the monitor in the `monitor_options` variable.

Parameters:
- `search_cron`: Cron expression that schedules when to **search** for new issues.
- `update_cron`: Cron expression that schedules when to **update** issues.
- `max_issues_creation`: Sets the maximum number of new issues that can be created during each **search** routine. Defaults to the `max_issues_creation` value in `configs.yaml`.
- `execution_timeout`: Sets a timeout for both search and update routines. Defaults to `executor_monitor_timeout` in `configs.yaml`.

```python
monitor_options = MonitorOptions(
    update_cron="* * * * *",
    search_cron="* * * * *",
)
```

## Issue options
Specify settings for issue management in the `issue_options` variable.

Parameters:
- `model_id_key`: A key that uniquely identifies each issue, such as an ID column in a database.
- `solvable`: Indicates if an issue can be resolved automatically. Issues set as non-solvable require manual intervention. Defaults to `true`.
- `unique`: Ensures that only one instance of a given issue (based on the `model_id_key`) is created. Non-solvable issues are often set as unique to avoid duplicate entries. Defaults to `false`.

The `solvable` and `unique` settings can be nuanced to understand, so an example is helpful. Consider a monitor that detects users deactivating their accounts. This state, once detected, is permanent. If an user deactivates their account, it will always be considered a problem (as the monitor is configured to do so). In this case, the issue is **not solvable** since nothing will alter this state for that particular user.

In scenarios like this, the recommended configuration for `solvable` and `unique` settings is as follows:
- Set `solvable` to `False` because the state of what’s being monitored is final and cannot change, unable to reach a "solved" state.
- Set `unique` to `True` because, once the problem is detected for a specific user, it should not be re-flagged for the same user.

> **Note**: This example is solely for illustrating how these settings operate. The problem presented here should not be monitored in this exact way as there're better ways to do it.


```python
issue_options = IssueOptions(
    model_id_key="id",
    solvable=False,
)
```

## Alert options
Configure alert behavior in the `alert_options` variable, setting rules for alert levels and handling acknowledgments.
- `rule`: Specifies the rule to use for alert level calculations. Available options are `AgeRule`, `CountRule`, and `ValueRule`.
- `dismiss_acknowledge_on_new_issues` Determines if acknowledgment for an alert should be reset when new issues are linked to it. Defaults to `false`.

```python
alert_options = AlertOptions(
    rule=CountRule(
        priority_levels=PriorityLevels(
            low=0,
            moderate=10,
            high=20,
            critical=30,
        )
    )
)
```

## Age rule
The **Age Rule** calculates the alert priority based on the age of the active issues. The alert level will be determined by the **oldest active issue** in the alert. The priority value represents the issue age in **seconds** that triggers each alert level.
- `priority_levels`: Defines the values to trigger each alert level based on the issue age. The priority will be triggered when the **age of the oldest active issue is greater than the level defined** for that priority.

## Count rule
The **Count Rule** calculates the alert priority based on the number of active issues linked to the alert. The alert level will be determined by the **number of active issues**. The priority value indicates how many active issues trigger each alert level.
- `priority_levels`: Defines the values to trigger each alert level based on the number of active issues. The priority will be triggered when the **number of active issues is greater than the level defined** for that priority.

## Value rule
The **Value Rule** calculates the alert priority based on a specific value from the issue's data. For each active issue the priority level will be determined by the **'value'** of the provided `value_key` in the issue data. The alert priority level will be the highest priority level triggered between all the active issues.
- `value_key`: The **key in the issue data** that contains the numeric value. This value will be compared against the priority levels to calculate the priority level.
- `operation`: Defines the comparison operation to use between the value and the priority levels. Can be either `greater_than` (to trigger the level when the value exceeds the value for each priority) or `lesser_than` (to trigger the level when the value is below the level for each priority). A value exactly equal to the priority level will not trigger it and will, instead, trigger a lower priority or `None` if it's the lowest priority level defined.
- `priority_levels`: Defines the values that the issues data values will be compared to, to calculate the alert priority level.

## Priority levels
Priority levels definition. For the defined rule, what value should trigger each level.
- `informational`: Level that triggers **informational P5** alerts.
- `low`: Level that triggers **low P4** alerts.
- `moderate`: Level that triggers **moderate P3** alerts.
- `high`: Level that triggers **high P2** alerts.
- `critical`: Level that triggers **critical P1** alerts.

All priority levels defaults to `None`. If a level is set to `None`, it will not be triggered.

# The issue data type
The `IssueDataType` class defines the structure of the data that represents an issue. It serves as a type annotation in the monitor's default functions, making development more intuitive and error-resistant.

Define a class called `IssueDataType`, that inherits from `TypedDict`, and includes all the fields that will be present in the issue data for the monitor.

```python
class IssueDataType(TypedDict):
    id: int
    name: int
```

**Attention**: The `IssueDataType` must contain the field specified in the `model_id_key` parameter of the `IssueOptions` setting. This ensures that the issue’s unique identifier is consistently used across your monitor’s configuration.

# The functions
There are 3 functions that control the monitor's execution. They are `search`, `update` and `is_solved`.

## Search function
The **search function** is an asynchronous function that identifies and returns a list of issues in the form of dictionaries. Each dictionary should adhere to the structure defined by the `IssueDataType` class.
- The function must be **async** and should not take any arguments.
- It returns a list of dictionaries, where each dictionary contains the fields specified in `IssueDataType`.
- This function can execute any asynchronous code required to gather information, such as querying a database or making API calls.
- The function should return all identified issues, without the need to check if they were already found in a previous iteration.

Example: If no user should have a `name` equal to `null`, the search function would locate all such users and return a list of dictionaries. Each dictionary must include fields like the user `id` and `name`.

**Attention: all dictionaries must have the field set in the `model_id_key` parameter of the `IssueOptions` class, as they should have the same structure defined by the `IssueDataType` class. Issues without the field will be discarded.**

If no issues are detected, the function can return an empty list, `None`, or simply not return at all (equivalent to returning `None`).

Issues that are considered as "already solved", will be discarded. Check the [**Is solved function**](#is-solved-function) section for more details.

```python
async def search() -> list[IssueDataType] | None:
    users = await get_user_data()  # users = [{"id": 1234, "name": none}, {"id": 2345, "name": none}]
    return [
        user
        for user in users
        if user["name"] is None
    ]
```

## Update function
The **update function** is an asynchronous function that gets the updated data for existing issues, enabling the platform to automatically manage and refresh issue information.
- The function must be **async** and takes a list of active issue data as its argument.
- It returns a list of dictionaries, each containing updated information for the issues, structured according to the `IssueDataType` class.

**Why does the update function receives all active issues data?**

Unlike the search function, the update function does not identify new issues. While looking for new issues might be slow, getting the updated information for them, usually, is faster, as it's identifier (e.g. the ID column) allows the use of an efficient method to get the information.

Example: To update the issue data with current user information, the update function can query for each user’s ID in the database, returning updated values in a dictionary for each. As the ID column in the database is a primary key, this kind of query is very fast.

The updated data returned by this function will be used to updated the active issues. The issues that will be updated will be identified by the `model_id_key`.

If no updates are needed, the function can return an empty list, `None`, or simply not return at all (equivalent to returning `None`). Only issues included in the returned list will be updated. Issues not present in the list will retain their existing data.

```python
async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    user_ids = [user["id"] for user in issues_data]
    users = await get_users_data(user_ids)  # Getting the updated users data for the active issues
    return users  # Return all the updated data, without any filters
```

## Is solved function
The **is solved function** is a synchronous function that determines if an issue is resolved based on its data.
- The function must be **sync** and takes an active issue data as its argument.
- It returns `True` if the issue is considered solved and `False` if it is unresolved.

This function not only checks the resolution status of existing issues but also validates issues returned by the **search function**. Issues where `is_solved` returns `True` are discarded, preventing the creation of issues that are already resolved.

```python
def is_solved(issue_data: IssueDataType) -> bool:
    return issue_data["name"] is not None
```

## Slow blocking operations
The Monitor execution process in Sentinela relies on the defined functions to handle all necessary steps. Sentinela operates on a cooperative concurrency model, meaning that **no slow blocking operations** should be executed directly within the Monitors or elsewhere in the application.

If a slow, blocking operation cannot be **awaited**, it should be executed using `asyncio.to_thread`. This approach delegates the operation to a separate thread, preventing it from blocking the entire application.

```python
import asyncio

# Example of running a blocking operation in a separate thread
result = await asyncio.to_thread(blocking_function)
```

# Notifications
Notifications are optional and can be configured to send notifications to different targets without needing extensive settings for ech monitor. Configure notifications by creating the `notification_options` variable with a list of the desired notifications. Each notification has it's own settings and behaviors.

Notifications are provided as plugins. Check the [plugins documentation](./plugins.md) for more information.

# Reactions
Reactions are optional and can be configured reactions to specific events by creating a `reaction_options` variable with an instance of the `ReactionOptions` class, available in the `monitor_utils` module.

Reactions are defined as a list of **async functions** that are triggered when specified events occur. Each function is called with the event's payload, allowing customized actions based on the event data.

Below is an example of defining a reaction function that responds to the creation of a new issue:

```python
async def reaction_issue_created(event_payload: dict[str, Any]):
    # Do something
```

The event payload provided to each reaction function contains structured information about the event source, details, and any additional context. This allows reaction functions to respond precisely to specific events.

```python
{
    "event_source": "Specifies the model that generated the event (e.g., `monitor`, `issue`, `alert`)."
    "event_source_id": "The unique identifier of the object that triggered the event (e.g., `monitor_id`, `issue_id`)."
    "event_source_monitor_id": "The monitor ID associated with the object that generated the event."
    "event_name": "Name of the event, such as `alert_created` or `issue_solved`.",
    "event_data": {
        "Object with detailed information about the event source."
    },
    "extra_payload": "Additional information that may be sent along with the event, providing further context.",
}
```

Reaction functions can be assigned to specific events when creating an instance of `ReactionOptions`. This configuration ensures that designated functions are triggered whenever specified events occur.

```python
reaction_options = ReactionOptions(
    issue_created=[reaction_issue_created],
)
```

With this configuration, every time an issue is created, the provided function will be executed with the event payload that corresponds to the issue create event.

The available events are:
**Alert events**
- `alert_acknowledge_dismissed`: Alert acknowledgement was dismissed
- `alert_acknowledged`: Alert was acknowledged
- `alert_created`: Alert was created
- `alert_issues_linked`: Alert has new issues linked to it
- `alert_locked`: Alert was locked
- `alert_priority_decreased`: Alert priority decreased
- `alert_priority_increased`: Alert priority increased
- `alert_solved`: Alert was solved
- `alert_unlocked`: Alert was unlocked
- `alert_updated`: Alert was updated. It doesn't means that any information changed, only that the alert went through the update process. Not triggered when the alert was solved

**Issue events**
- `issue_linked`: Issue was linked to an alert
- `issue_created`: Issue was created
- `issue_dropped`: Issue was dropped
- `issue_solved`: Issue was solved
- `issue_updated_not_solved`: Issue data updated but it's considered as not solved
- `issue_updated_solved`: Issue data updated and it's considered as solved

**Monitor events**
- `monitor_enabled_changed`: Monitor was enabled or disabled

**Notification events**
- `notification_closed`: Notification was closed
- `notification_created`: Notification was created

# Functions
The monitor utils module also provides useful functions for developing a monitor.

## Query
The `query` function allows querying data from available databases. For more details, refer to the [Querying Databases](./querying.md) documentation.

## Read file
The `read_file` function reads files in the same directory as the monitor code, making it useful for accessing other resources that the monitor relies on, such as SQL query files.

The `read_file` is used to read files relative to the monitor path. It's useful when there're resources used by the monitor that are not, necessarily, defined in it's code, like SQL query files.

The function takes 2 parameters:
- `file_name`: The name of the file located in the same directory as the monitor code.
- `mode`: Specifies the file access mode. Values allowed are `r` and `rb`. Defaults to `r`.

```python
content = read_file("search_query.sql")
```

# Registering
After creating the monitor, the next step is to register it on Sentinela. Check the [Registering a monitor](monitor_registering.md) documentation for more information.

# Creating a new monitor
This guide will walk through the steps to set up a new Monitor.

As a demonstration, the Monitor that will be designed is intended to **search for users with invalid registration data**, specifically when their name is empty.

# Modeling the problem
The most important process when creating a Monitor is to model it. Modeling means deeply understanding what's being monitored and how to obtain the necessary information to be able to monitor it.

## Understanding the problem
The first step when building a Monitor is to define what constitutes the **unit of problem**. This refers to the entity or object that represents a single issue in your monitoring system. Here are some examples:
- **User Registration Issues**: When monitoring user registration data, the unit of problem will likely be a **user**, identified by their internal **user ID**.
- **Failed Transactions**: When monitoring failed transactions, the unit of problem will be a **transaction**, identified by its unique **transaction ID**.
- **Payment Provider Conversion Rates**: When monitoring the conversion rates of different **payment providers**, the unit of problem will be the **payment provider**, identified by its **name**.

While some of these examples might be more appropriately monitored using system metrics rather than Sentinela, they help demonstrate how to model the problem.

This step defines the key information used to identify a unique issue. As in the first example, two different transaction IDs will result in two distinct issues. When updating the issues, the same transaction ID is used to ensure the correct issue is updated with the new information.

## Obtaining the information
After understanding the problem, the next step is to obtain the necessary information for monitoring. This step will vary significantly depending on the system and technologies in use.

The key point is that throughout the monitoring process, each issue must have the information required to track and check if it's solved. In this case, to monitor users with invalid registration data, the essential information for each user includes:
- The **user ID**, which uniquely identifies each user. This will be used to identify individual issues, as each issue corresponds to one user.
- The **user name**, which will be checked to determine if it is missing or incorrectly configured, while also used to verify when the issue is resolved, i.e., when the user name is correctly filled in.

The information gathering process can be split into two distinct use cases:
1. **Get all the users with incorrect registration data**: This use case is intended to search for issues, returning every user whose registration data is incorrect (e.g., users with missing or invalid names).
2. **Get the updated registration data for one or more users, based on the provided user IDs**: This use case retrieves the latest registration data for the specified user IDs. **Note that no conditions on the registration being correct or not are being applied**. This is a critical requirement, as this method will be used to fetch updated information for users, whether their registration data is incorrect or correctly filled.

Once the required information to search for and update issues can be obtained, a Monitor can be implemented.

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

**Available functions and modules**
- [`query`](#query)
- [`read_file`](#read-file)
- [`variables`](#variables)

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
    search_cron="* * * * *",
    update_cron="* * * * *",
)
```

It is recommended to avoid excessively frequent search intervals (e.g., a cron configuration of * * * * *), as this is often unnecessary.

When configuring update intervals, it is recommended to set them equal to or more frequent than the search intervals. For instance, if issues are searched every 15 minutes, updates can be performed every 5 minutes.

## Issue options
Specify settings for issue management in the `issue_options` variable.

Parameters:
- `model_id_key`: A key that uniquely identifies each issue, such as an ID column in a database. The configured key references the field in the issues data returned by the `search` and `update` functions that will identify the unique id for the issue.
- `solvable`: Indicates if an issue can reach a solved state automatically. Issues set as non-solvable require manual intervention by solving the alert. Defaults to `true`.
- `unique`: Ensures that only one instance of a given issue (based on the `model_id_key`) is created. Non-solvable issues are often set as unique to avoid duplicate entries. Defaults to `false`.

The `solvable` and `unique` settings can be nuanced to understand, so an example is helpful. Consider a monitor that detects users deactivating their accounts. This state, once detected, is permanent. If a user deactivates their account, it will always be considered a problem (as the monitor is configured to do so). In this case, the issue is **not solvable** since nothing will alter this state for that particular user.

In scenarios like this, the recommended configuration for `solvable` and `unique` settings is as follows:
- Set `solvable` to `False` because the state of what’s being monitored is final and cannot change, unable to reach a "solved" state.
- Set `unique` to `True` because, once the problem is detected for a specific user, it should not be re-flagged for the same user.

> **Note**: This example is solely for illustrating how these settings operate. The problem presented here should not be monitored in this exact way as there're better ways to do it.

### Example
Considering the monitor is implemented to monitor user registration data, it's expected that the issues are `solvable`, as the registration data can be corrected and Sentinela can detect when the issue is solved. Additionally, the issue is not `unique` because a user may have invalid registration data, fix it, and later have it changed incorrectly again, indicating a new issue must be created.

```python
issue_options = IssueOptions(
    model_id_key="id",
    solvable=True,
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

### Age rule
The **Age Rule** calculates the alert priority based on the age of the active issues. The alert level will be determined by the **oldest active issue** in the alert. The priority value represents the issue age in **seconds** that triggers each alert level.
- `priority_levels`: Defines the values to trigger each alert level based on the issue age. The priority will be triggered when the **age of the oldest active issue is greater than the level defined** for that priority.

### Count rule
The **Count Rule** calculates the alert priority based on the number of active issues linked to the alert. The alert level will be determined by the **number of active issues**. The priority value indicates how many active issues trigger each alert level.
- `priority_levels`: Defines the values to trigger each alert level based on the number of active issues. The priority will be triggered when the **number of active issues is greater than the level defined** for that priority.

### Value rule
The **Value Rule** calculates the alert priority based on a specific value from the issue's data. For each active issue the priority level will be determined by the **'value'** of the provided `value_key` in the issue data. The alert priority level will be the highest priority level triggered between all the active issues.
- `value_key`: The **key in the issue data** that contains the numeric value. This value will be compared against the priority levels to calculate the priority level.
- `operation`: Defines the comparison operation to use between the value and the priority levels. Can be either `greater_than` (to trigger the level when the value exceeds the value for each priority) or `lesser_than` (to trigger the level when the value is below the level for each priority). A value exactly equal to the priority level will not trigger it and will, instead, trigger a lower priority or `None` if it's the lowest priority level defined.
- `priority_levels`: Defines the values that the issues data values will be compared to, to calculate the alert priority level.

### Priority levels
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

**Attention**: The `IssueDataType` class must contain the field specified in the `model_id_key` parameter of the `IssueOptions` setting. This ensures that the issue’s unique identifier is consistently used across your monitor’s configuration.

### Example
For the user registration monitor, the issue data type should include the `id` and `name` fields, as these are the essential fields for identifying and tracking the issue.

```python
class IssueDataType(TypedDict):
    id: int
    name: str
```

# The functions
There are 3 functions that control the monitor's execution. They are `search`, `update` and `is_solved`.

## Search function
The **search function** is an asynchronous function that identifies and returns a list of issues in the form of dictionaries. Each dictionary should adhere to the structure defined by the `IssueDataType` class.
- The function must be **async** and should not take any arguments.
- It returns a list of dictionaries, where each dictionary contains the fields specified in `IssueDataType`.
- This function can execute any asynchronous code required to gather information, such as querying a database or making API calls.
- The function should return all identified issues, without the need to check if they were already found in a previous iteration.

Each issue returned by the search function will have their fields converted to JSON compatible types according to the following rules:
- Nested objects, like dictionaries and lists will be recursively converted.
- `datetime` objects will be converted to ISO format `YYYY-MM-DD HH:MM:SS.mmm+HH:MM`.
- Strings, integers, floats, booleans and `None` values will be kept as they are.
- All other types will be converted to strings using the default `str()` operation.

These conversions must be taken into account in the **update** and **is solved** functions, as they will be called with the converted data, instead of the data in with the same types that were returned by the search function.

**Attention: all issues must have the field set in the `model_id_key` parameter of the `IssueOptions` class, as they should have the same structure defined by the `IssueDataType` class. Issues without the field will be discarded.**

If no issues are detected, the function can return an empty list, `None`, or simply not return at all (equivalent to returning `None`).

Issues that are considered as "already solved", will be discarded. Check the [**Is solved function**](#is-solved-function) section for more details.

### Example
If no user should have a `name` equal to `null`, the search function would locate all such users and return a list of dictionaries, each one representing an issue. Each issue should include the fields defined in the `IssueDataType` class.

```python
async def search() -> list[IssueDataType] | None:
    # users = [{"id": 1234, "name": None}, {"id": 2345, "name": None}]
    users = await get_invalid_users()
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

Each issue returned by the update function will have their fields converted to JSON compatible types following the same rules as the search function.

**Why does the update function receives all active issues data?**

Unlike the search function, the update function does not identify new issues. While looking for new issues might be slow, getting the updated information for them, usually, is faster, as it's identifier (e.g. the ID column) allows the use of an efficient method to get the information.

To update the issue data with current user information, the update function can query for each user’s ID in the database, returning updated values in a dictionary for each. As the ID column in the database is a primary key, this kind of query is very fast.

The updated data returned by this function will be used to updated the active issues. The issues that will be updated will be identified by the `model_id_key`.

If no updates are needed, the function can return an empty list, `None`, or simply not return at all (equivalent to returning `None`). Only issues included in the returned list will be updated. Issues not present in the list will retain their existing data.

### Example
The update function should get the updated data for all the users that were identified as having invalid registration data. The function should return a list of dictionaries, each containing the updated information for the issues.

```python
async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    user_ids = [user["id"] for user in issues_data]
    # Getting the updated users data for the active issues
    # updated_users = [{"id": 1234, "name": "Some name"}, {"id": 2345, "name": None}]
    updated_users = await get_users_data(user_ids)
    # Return all the updated data, without any filters
    return updated_users
```

## Is solved function
The **is solved function** is a synchronous function that determines if an issue is solved based on its data.
- The function must be **sync** and takes an active issue data as its argument.
- It returns `True` if the issue is considered solved and `False` if it is unresolved.

This function not only checks the solved status of existing issues but also validates issues returned by the **search function**. Issues where `is_solved` returns `True` are discarded, preventing the creation of issues that are already solved.

### Example
The is solved function should check if the user's `name` is not `None`. If the name is not `None`, the issue is considered solved.

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

Notifications are provided as plugins. Check the [plugins documentation](./plugins/plugins.md) for more information.

# Reactions
Reactions are optional and can be configured reactions to specific events by creating a `reaction_options` variable with an instance of the `ReactionOptions` class, available in the `monitor_utils` module.

Reactions are defined as a list of **async functions** that are triggered when specified events occur. Each function is called with the event's payload, allowing customized actions based on the event data.

Below is an example of defining a reaction function that responds to the creation of a new issue:

```python
from monitor_utils import EventPayload


async def reaction_issue_created(event_payload: EventPayload) -> None:
    # Do something
```

### Event payload
The event payload provided to each reaction function contains structured information about the event source, details, and any additional context. This allows reaction functions to respond precisely to specific events.
- `event_source`: Specifies the model that generated the event (e.g., `monitor`, `issue`, `alert`).
- `event_source_id`: The unique identifier of the object that triggered the event (e.g., `monitor_id`, `issue_id`).
- `event_source_monitor_id`: The monitor ID associated with the object that generated the event.
- `event_name`: Name of the event (e.g., `alert_created`, `issue_solved`).
- `event_data`: Dictionary with detailed information about the event source.
- `extra_payload`: Additional information that may be sent along with the event, providing further context.

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

The function takes 2 parameters:
- `file_name`: The name of the file located in the same directory as the monitor code.
- `mode`: Specifies the file access mode. Values allowed are `r` and `rb`. Defaults to `r`.

```python
content = read_file("search_query.sql")
```

## Variables
The `variables` module allows storing and retrieving variables that can be used across executions of the monitor. This is useful for maintaining state or configuration information.

Available functions are:

**`get_variable`**

The function takes one parameter:
- `name`: The name of the variable to retrieve.

Return the value of a variable. If the variable does not exist, returns `None`.

**`set_variable`**

The function takes two parameters:
- `name`: The name of the variable to set.
- `value`: The value to assign to the variable.

Sets the value of a variable. If the variable does not exist yet, it's created.

Both functions must be called from functions defined in the monitor base code. If they're called from any other Python file, they will raise an error as they won't be able to identify the monitor that's calling it.

```python
from monitor_utils import variables

async def search() -> list[IssueDataType] | None:
    # Set a variable
    await variables.set_variable("my_var", "some_value")

async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    value = await variables.get_variable("my_var")
```

# Registering
After creating the monitor, the next step is to register it on Sentinela. Check the [Registering a monitor](monitor_registering.md) documentation for more information.

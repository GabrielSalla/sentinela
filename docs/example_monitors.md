# Example Monitors
This page describes all available example monitors that demonstrate different features and patterns.

The described behaviors can be visualized in the dashboard and are useful for learning how to implement various monitoring scenarios using Sentinela.

## Alert Options - Age Rule Monitor
Demonstrates the `AgeRule`. The alert priority is determined by the age of the oldest active issue. Issues age over time, and older issues trigger higher priority alerts.

**How it works**: The monitor creates a new issue every 5 minutes and measures its age in seconds. As issues get older, they trigger higher priority alerts according to the configured thresholds. Issues are automatically resolved after 5 minutes have passed since creation.

**Monitor code**: [Age Rule Monitor](/example_monitors/alert_options/age_rule_monitor/age_rule_monitor.py)

## Alert Options - Count Rule Monitor
Demonstrates the `CountRule`. The alert priority is determined by the number of active issues. More active issues trigger higher priority alerts.

**How it works**: The monitor creates 5 random issues every search cycle. The alert priority increases based on the total count of active issues linked to the alert. Issues can be automatically solved based on a severity field that fluctuates randomly.

**Monitor code**: [Count Rule Monitor](/example_monitors/alert_options/count_rule_monitor/count_rule_monitor.py)

## Alert Options - Value Rule Greater Than Monitor
Demonstrates the `ValueRule` with the `greater_than` operation. The alert priority is determined by a specific numerical value from the issue data.

**How it works**: The monitor tracks a single issue with an `error_rate` that oscillates from 0 to 100, back and forth. Alert priority increases when the error rate exceeds configured thresholds. The issue is never automatically solved, demonstrating continuous monitoring of a metric.

**Monitor code**: [Value Rule Greater Than Monitor](/example_monitors/alert_options/value_rule_greater_than_monitor/value_rule_greater_than_monitor.py)

## Alert Options - Value Rule Less Than Monitor
Demonstrates the `ValueRule` with the `less_than` operation. The alert priority is determined by a specific numerical value from the issue data.

**How it works**: Similar to the Greater Than Monitor but in reverse. This monitor tracks a single issue with a `success_rate` that oscillates from 0 to 100, back and forth. Alert priority increases when the success rate drops below thresholds, demonstrating monitoring for degraded performance.

**Monitor code**: [Value Rule Less Than Monitor](/example_monitors/alert_options/value_rule_lesser_than_monitor/value_rule_lesser_than_monitor.py)

## Blocking Operations Monitor
Demonstrates how to handle blocking operations in search and update functions without blocking the async event loop.

**How it works**: The monitor simulates a long blocking operation that would typically block the entire application. Using `asyncio.to_thread()`, the blocking call is executed in a separate thread, allowing the async event loop to remain responsive. Both `search()` and `update()` demonstrate this pattern, showing how to safely integrate synchronous blocking code into async monitor functions.

**Monitor code**: [Blocking Operations Monitor](/example_monitors/blocking_operations_monitor/blocking_operations_monitor.py)

## Non-Solvable Issues Monitor
Demonstrates configuring issues as non-solvable. Non-solvable issues require manual intervention to be solved and cannot be automatically resolved by the monitor logic.

**How it works**: The monitor simulates finding deactivated users and creates issues for them. With `solvable=False` and `unique=True`, only one issue per user is created. If the same user appears in subsequent searches, no new issue is generated. These issues can only be solved manually through the dashboard or notifications, when available.

**Monitor code**: [Non-Solvable Issues Monitor](/example_monitors/non_solvable_issues_monitor/non_solvable_issues_monitor.py)

## Plugin Slack Notification Monitor
Demonstrates how to configure Slack notifications for alerts.

**How it works**: This monitor is similar to the Count Rule Monitor but includes Slack notification configuration. It sends alerts to a configured Slack channel with customizable fields and optional mentions, showing how to integrate Sentinela alerts with Slack.

**Monitor code**: [Plugin Slack Notification Monitor](/example_monitors/plugin_slack_notification_monitor/plugin_slack_notification_monitor.py)

## Query Monitor
Demonstrates using the `query` function to fetch data from a database. Shows how to connect to and execute queries against configured databases.

**How it works**: The monitor executes a simple `SELECT current_timestamp;` query on the 'local' database. In `search()`, it creates a single non-solvable issue with the database timestamp. In `update()`, it refreshes the timestamp field with the latest database value. The actual query can be replaced with real data retrieval for production monitoring.

**Monitor code**: [Query Monitor](/example_monitors/query_monitor/query_monitor.py)

## Reactions Monitor
Demonstrates how to configure reactions. Reactions are async callbacks triggered by specific events during monitor execution.

**How it works**: Reactions are async functions that execute in response to specific monitor events (search completion, update completion, issue creation, etc.). They receive event payloads containing monitor and issue data. This example shows the available reactions with comments explaining when each runs and what data is available.

**Monitor code**: [Reactions Monitor](/example_monitors/reactions_monitor/reactions_monitor.py)

## Variables Monitor
Demonstrates the variables feature for maintaining monitor-level state. Variables store information about the monitor's execution, not about individual issues.

**How it works**: The monitor uses a variable to bookmark the last timestamp processed. This prevents reprocessing the same events across multiple monitor executions and makes searches more efficient. Variables are persisted across monitor runs and can store any data needed for monitor-level state management.

**Monitor code**: [Variables Monitor](/example_monitors/variables_monitor/variables_monitor.py)

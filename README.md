# Sentinela monitoring platform
> [!WARNING]
> This is a **work in progress** project and many things are still not ideal to be used

> [!IMPORTANT]
> **This application is not intended to replace, and will not replace, your current observability stack.**

The Sentinela monitoring platform was created to cover a special case of monitoring that is hardly solved by the usual observability and monitoring tools. It's main purpose is to help teams to identify issues through data that is not easily obtained by logs or similar metrics.

# Use case
Sentinela is designed to provide users with the ability to implement custom Python code that will be used to search, update and check if detected issues are solved. It excels when information is not easily accessible through conventional logs or metrics, such as querying databases or APIs, or when complex logic is required to retrieve and interpret the necessary data.

An **issue** is an unique unit of a problem that is identified and tracked by Sentinela. When monitoring invalid **user** data, an issue will represent an **user**. When tracking failed **transactions**, each issue represents a specific **transaction**.

A Sentinela Monitor is configured through 3 main parts, along some basic settings:
1. **Data Retrieval and Issue Detection**: Define how to get the information and what’s considered an issue.
2. **Issue Updates**: Specify how to update the information of identified issues.
3. **Issue Resolution**: Define the criteria that determine when an issue is considered resolved.

These implementations are enough for Sentinela to autonomously execute monitoring logic and automatically manages the issues.

## Example scenario: Monitoring orders without shipments
An online store where orders are expected to be shipped within 5 days. If an order is delayed beyond this threshold, someone might need to check what’s wrong with the shipment system.

To identify orders that haven't been shipped within the 5-day window, it’s necessary to cross-reference orders and shipments data, requiring a more complex logic than what can be easily achieved through conventional logs or metrics.

This kind of problem is one that is, usually, detected when the customer opens a support ticket asking why the order hasn’t been shipped yet. Without a dedicated internal routine to check for unsent orders, this problem may go unnoticed until a complaint is raised.

Sentinela addresses this issue by enabling users to configure a monitor that queries the database for orders that exceed the 5-day threshold without a corresponding shipment. When such an order is found, the monitor can trigger notifications to alert the appropriate team.

When an issue is found, it'll be tracked and updated periodically by Sentinela (using the provided implementations) and, when it's detected that the order has a shipment, the issue will be automatically solved.

The Monitor implementation that demonstrates this behavior is shown below. This example clarifies what's needed to be implemented to monitor the outlined scenario. **Note that the code provided is an overly simplified version meant to demonstrate the core concepts, and will need to be adjusted for each use case**.

```python
# Each issue represents an order that has not been shipped after 5 days of
# creation
def search():
    # The 'get_orders_without_shipments' function queries the database or an
    # API and returns the orders that have not been shipped after 5 days
    issues = get_orders_without_shipments()
    return issues

def update(issues):
    # The 'get_orders_shipments' function fetches updated shipment information
    # for the provided order IDs. The issues will be updated with this new data
    order_ids = [issue["order_id"] for issue in issues]
    updated_issues = get_orders_shipments(order_ids)
    return updated_issues

def is_solved(issue):
    # This step validates if the issue has a valid shipment ID. The issue is
    # considered solved when a shipment ID is assigned
    return issue["shipment_id"] is not None
```

## Monitoring state machines
where it is crucial to track and verify the consistency of an entity's state. This is especially useful in scenarios where processes involve multiple transitions between states, and business logic must be enforced.

Common use cases:
- **Detecting Invalid States**: Identify when a process enters an invalid or unexpected state according to predefined business logic.
- **State Transition Monitoring**: Ensure that state transitions occur as expected and that no erroneous states are introduced.

State machine-related issues often require several data checks and conditional logic to identify. These issues are typically difficult to capture using standard logs and metrics but can be easily addressed using Sentinela Monitoring.

# Documentation
1. [Overview](./docs/overview.md)
2. [Building a Monitor](./docs/monitor.md)
3. [Querying data from databases](./docs/querying.md)
4. [Registering a monitor](./docs/monitor_registering.md)
5. [How to run](./docs/how_to_run.md)
6. [Plugins](./docs/plugins.md)
    1. [Slack](./docs/plugin_slack.md)
7. Interacting with Sentinela
    1. [HTTP server](./docs/http_server.md)
8. Special cases
    1. [Dropping issues](./docs/dropping_issues.md)

# Sentinela monitoring platform
> [!WARNING]
> This is a **work in progress** project and many things are still not ideal to be used

> [!IMPORTANT]
> **This application is not intended to replace, and will not replace, your current observability stack.**

The Sentinela monitoring platform was created to cover a special case of monitoring that is hardly solved by the usual observability and monitoring tools. It's main purpose is to help teams to identify issues through data that is not easily obtained by logs or similar metrics.

# Use case
Sentinela is designed to monitor "information" that progresses through specific steps in its lifecycle and may occasionally indicate a problem. It excels in scenarios where this information is not easily accessible through conventional logs or automated checks, providing users with the flexibility to define custom monitoring rules using Python code.

## Example scenario: Monitoring late shipments
Consider a database where shipments are tracked, and every shipment is expected to be delivered within 5 days. If a shipment is delayed beyond this time frame, it should be flagged for further action. However, if the application managing shipments does not automatically identify and log late deliveries, these delayed shipments might go unnoticed.

By leveraging Python code, Sentinela empowers users to create highly tailored monitors to address these and similar challenges effectively. It provides a robust interface for identifying, updating, and resolving issues, while also sending notifications or performing actions in specific scenarios.

Using Sentinela, it's possible to configure a monitor to query the database for shipments exceeding the 5-day threshold and trigger notifications when it happens.

## Monitoring state machines
Sentinela is also well-suited for monitoring state machines, where it is essential to track the current state of an entity and verify its consistency. For example:
- Identify if a process has entered an invalid state, according to the business logic of that product.
- Ensure that transitions between states occur as expected.

# Documentation
1. [Overview](./docs/overview.md)
2. [Monitor](./docs/monitor.md)
2. [Plugins](./docs/plugins.md)
    1. [Slack](./docs/plugin_slack.md)
3. [Querying data from databases](./docs/querying.md)
4. [Registering a monitor](./docs/monitor_registering.md)
5. [Usage](./docs/usage.md)
6. Interacting with Sentinela
    1. [HTTP server](./docs/http_server.md)
7. Special cases
    1. [Dropping issues](.docs/dropping_issues.md)

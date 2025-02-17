# HTTP server
The HTTP server provides an API to interact with Sentinela. The available routes are organized into two main categories, based on the deployment setup.

If the container is deployed with the **Controller** (either standalone or alongside the Executor in the same container), all routes are available, allowing interactions with Monitors, Issues, and Alerts.

If the container is deployed with only the **Executor**, only base routes are available.

The HTTP server configuration variables can be set at the `configs.yaml` file.

# Base routes
The following routes are always available, regardless of the deployment setup.

## Status
**`GET /status`**

Returns the current status of the container components, along with internal metrics for system insights.

## Prometheus Metrics
**`GET /metrics`**

Exposes Prometheus-formatted metrics, enabling external monitoring and observability of the application.

# Interaction routes
These routes are available only when the container deployment includes the **Controller** component.

## List monitors
**`GET /monitors/list`**

Returns a list of all monitors currently registered with the `id`, `name` and `enabled` fields for each monitor.

Response example:
```json
[
    {
        "id": 123,
        "name": "monitor_name",
        "enabled": true
    },
    {
        "id": 124,
        "name": "another_monitor",
        "enabled": false
    }
]
```

## Get monitor
**`GET /monitor/{monitor_name}`**

Returns the monitor details for the monitor with the provided `monitor_name`.

Response example:
```json
{
    "id": 123,
    "name": "monitor_name",
    "enabled": true,
    "code": "...",
    "additional_files": {"file_name.txt": "..."}
}
```

## Disable monitor
**`POST /monitor/{monitor_name}/disable`**

Disable the monitor with the provided `monitor_name`.

## Enable monitor
**`POST /monitor/{monitor_name}/enable`**

Enable the monitor with the provided `monitor_name`.

## Validate monitor
**`POST /monitor/validate`**

Validate the monitor code provided without registering it.

For more information, check the [Validating a monitor](./monitor_validating.md) documentation.

Request body example:
```json
{
    "monitor_code": "...",
}
```

Response example:
```json
{
    "status": "monitor_validated"
}
```

## Register monitor
**`POST /monitor/register/{monitor_name}`**

Register the monitor with the provided `monitor_name`.

For more information, check the [Registering a monitor](./monitor_registering.md) documentation.

Request body example:
```json
{
    "monitor_code": "...",
    "additional_files": {"file_name.txt": "..."}
}
```

Response example:
```json
{
    "status": "monitor_registered",
    "monitor_id": 123
}
```

## Acknowledge alert
**`POST /alert/{alert_id}/acknowledge`**

Acknowledge the alert with the provided `alert_id`.

## Lock alert
**`POST /alert/{alert_id}/lock`**

Lock the alert with the provided `alert_id`.

## Solve alert
**`POST /alert/{alert_id}/solve`**

Solve the alert with the provided `alert_id`.

## Drop issue
**`POST /issue/{issue_id}/drop`**

Drop the issue with the provided `issue_id`.

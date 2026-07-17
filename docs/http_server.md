# HTTP server
The HTTP server provides an API to interact with Sentinela. The available routes are organized into two main categories, based on the deployment setup.

> [!IMPORTANT]
> By default the API is served at port `8000`. The docker compose files also expose the port `8000`, so if the port for the server changes, the compose files should be updated accordingly. Another option is to keep the server port at `8000` and changing only the compose files. Using the configuration `8080:8000`, for example, will keep the server running at port `8000`, but it will be accessible through the container's port `8080`.

If the container is deployed with the **Controller** (either standalone or alongside the Executor in the same container), all routes are available, allowing interactions with Monitors, Issues, Alerts and the dashboard.

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

## Dashboard
**`/dashboard`**

Serves a simple dashboard interface, providing a quick way to create, enable or disable and change the monitors code.

## List monitors
**`GET /monitors/list`**

Returns a list of all monitors currently registered with the `id`, `name` and `enabled` fields for each monitor.

Response example:
```json
[
    {
        "id": 123,
        "name": "monitor_name",
        "enabled": true,
        "active_alerts": 3,
        "not_acknowledged_alerts": 1
    },
    {
        "id": 124,
        "name": "another_monitor",
        "enabled": false,
        "active_alerts": 0,
        "not_acknowledged_alerts": 0
    }
]
```

## List monitors active alerts
**`GET /monitor/{monitor_id}/alerts`**

Returns a list of all active alerts for the provided monitor id.

Response example:
```json
[
    {
        "id": 12,
        "status": "active",
        "acknowledged": false,
        "is_priority_acknowledged": false,
        "locked": false,
        "priority": 2,
        "acknowledge_priority": null,
        "can_acknowledge": true,
        "can_lock": true,
        "can_solve": false,
        "created_at": "2025-01-01 12:34:56",  # Already localized from UTC
    },
    {
        "id": 34,
        "status": "active",
        "acknowledged": true,
        "is_priority_acknowledged": true,
        "locked": true,
        "priority": 2,
        "acknowledge_priority": 2,
        "can_acknowledge": false,
        "can_lock": false,
        "can_solve": false,
        "created_at": "2025-01-01 23:45:55",  # Already localized from UTC
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
    "queued": false,
    "running": false,
    "search_executed_at": "2025-01-01 09:34:56",  # Already localized from UTC
    "update_executed_at": "2025-11-12 10:14:15",  # Already localized from UTC
    "last_heartbeat": "2025-01-02 00:04:05",  # Already localized from UTC
    "code": "...",
    "additional_files": {"file_name.txt": "..."}
}
```

## Disable monitor
**`POST /monitor/{monitor_name}/disable`**

Disable the monitor with the provided `monitor_name`.
This request is not executed immediately, it's queued for an Executor to run.

## Enable monitor
**`POST /monitor/{monitor_name}/enable`**

Enable the monitor with the provided `monitor_name`.
This request is not executed immediately, it's queued for an Executor to run.

## Refresh monitor
**`POST /monitor/{monitor_name}/refresh`**

Queue the monitor with the provided `monitor_name` for refresh.
This request is not executed immediately, it's queued for an Executor to run.

Request body example:
```json
{
    "tasks": ["search", "update"]
}
```

The `tasks` field must be a non-empty list containing only `search` and/or `update`.

Response example:
```json
{
    "status": "monitor_refresh_queued",
    "monitor_name": "monitor_name",
    "tasks": ["search", "update"]
}
```

## Validate monitor
**`POST /monitor/validate`**

Validate the monitor code provided without registering it.

For more information, check the [Validating a monitor](monitor_validating.md) documentation.

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

For more information, check the [Registering a monitor](monitor_registering.md) documentation.

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

## Get alert
**`GET /alert/{alert_id}`**

Returns the details for the alert with the provided `alert_id`.

Response example:
```json
{
    "id": 12,
    "status": "active",
    "acknowledged": false,
    "is_priority_acknowledged": false,
    "locked": false,
    "priority": 2,
    "acknowledge_priority": null,
    "can_acknowledge": true,
    "can_lock": true,
    "can_solve": false,
    "created_at": "2025-01-01 12:34:56"  # Already localized from UTC
}
```

## List alert active issues
**`GET /alert/{alert_id}/issues`**

Returns a list of all active issues for the provided `alert_id`.

Response example:
```json
[
    {
        "id": 123,
        "status": "active",
        "model_id": 456,
        "data": {...},
        "created_at": "2025-01-01 12:34:56"  # Already localized from UTC
    },
    {
        "id": 124,
        "status": "active",
        "model_id": 567,
        "data": {...},
        "created_at": "2025-01-01 13:34:45"  # Already localized from UTC
    }
]
```

## Acknowledge alert
**`POST /alert/{alert_id}/acknowledge`**

Acknowledge the alert with the provided `alert_id`.
This request is not executed immediately, it's queued for an Executor to run.

## Lock alert
**`POST /alert/{alert_id}/lock`**

Lock the alert with the provided `alert_id`.
This request is not executed immediately, it's queued for an Executor to run.

## Solve alert
**`POST /alert/{alert_id}/solve`**

Solve the alert with the provided `alert_id`.
This request is not executed immediately, it's queued for an Executor to run.

## Drop issue
**`POST /issue/{issue_id}/drop`**

Drop the issue with the provided `issue_id`.
This request is not executed immediately, it's queued for an Executor to run.

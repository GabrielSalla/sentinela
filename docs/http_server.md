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

## Disable monitor
**`POST /{monitor_name}/disable`**

Disable the monitor with the provided `monitor_name`.

## Enable monitor
**`POST /{monitor_name}/enable`**

Enable the monitor with the provided `monitor_name`.

## Acknowledge alert
**`POST /{alert_id}/acknowledge`**

Acknowledge the alert with the provided `alert_id`.

## Lock alert
**`POST /{alert_id}/lock`**

Lock the alert with the provided `alert_id`.

## Solve alert
**`POST /{alert_id}/solve`**

Solve the alert with the provided `alert_id`.

## Drop issue
**`POST /{issue_id}/drop`**

Drop the issue with the provided `issue_id`.

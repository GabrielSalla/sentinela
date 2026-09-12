# Configuration file
This document provides an overview of the configuration parameters available in the `configs.yaml` file.

## Plugins
- `plugins`: List of strings. Plugins to be used by Sentinela. Check each plugin documentation to learn how to enable them.
- `plugins_configs`: Map. Configuration settings for each plugin, keyed by plugin name. Check each plugin documentation to learn the available settings. Example:
  ```yaml
  plugins_configs:
    slack:
      < Slack plugin settings >
  ```

## Monitors
- `load_example_monitors`: Boolean. Flag to enable the example monitors.
- `example_monitors_path`: String. Path relative to the project root, where the example monitors are stored.
- `internal_monitors_path`: String. Path relative to the project root, where the internal monitors are stored.
- `internal_monitors_notification`: Map. Settings for the notification to be sent by the internal monitors.
  - `enabled`: Boolean. Flag to enable the internal monitors notification.
  - `notification_class`: String. Class to be used for the notification. Example: `plugin.my_plugin.notifications.SomeNotificationClass`.
  - `params`: Map. The desired parameters for the notification. Each notification class will have its own set of parameters. Check the documentation for each notification class to learn more about the available parameters.
- `monitors_load_schedule`: String using Cron format. Schedule to reload monitors from the database.
- `save_events_mode`: String. Controls whether events are saved to the application database: `all` saves all events, `monitor` lets each monitor decide whether to save its events (defaults to disabled), and `off` disables event storage globally, regardless of monitor settings. Can be `all`, `monitor` or `off`.

## Logging
- `logging`: Map. Settings for logging.
  - `mode`: String. Logging mode. Can be "friendly" or "json".
  - `format`: String. Settings for formatting the "friendly" logs.
  - `fields`: Map. Fields to include in the "json" logs and their name from the `logging` module.

Suggested configuration for `friendly` logs:
```yaml
logging:
  mode: friendly
  format: "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s.%(lineno)d: %(message)s"
```

Suggested configuration for `json` logs:
```yaml
logging:
  mode: json
  fields:
    timestamp: created
    level: levelname
    file_path: pathname
    function_name: funcName
    line_number: lineno
    logger_name: name
    message: message
```

## Database Settings
- `application_database_settings.pool_size`: Integer. Application database pool size.

## Queue
- `application_queue`: Map. Settings for the application queue.
  - `type`: String. Queue to be used. Can be `internal` or a queue from an installed plugin.
  - `queue_wait_message_time`: Integer. Time, in seconds, to wait for a message when using the internal queue.

Suggested configuration for the internal queue when running locally or developing:
```yaml
application_queue:
  type: internal
  queue_wait_message_time: 2
```

## HTTP Server
- `http_server`:
  - `port`: Integer. Port for the HTTP server.
  - `log_level`: String. Log level for the HTTP server. Can be `default`, `warning`, `error` or `none`. Defaults to `default`.
  - `dashboard_enabled`: Boolean. Flag to enable the Sentinela dashboard. Defaults to `false`.
  - `commands`: Map. Configuration settings for each HTTP command, allowing commands to be disabled. When a command is not configured, it will be considered as enabled.
    - `alert_acknowledge`: Map. Settings for the alert acknowledge command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
    - `alert_lock`: Map. Settings for the alert lock command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
    - `alert_solve`: Map. Settings for the alert solve command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
    - `issue_drop`: Map. Settings for the issue drop command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
    - `monitor_disable`: Map. Settings for the monitor disable command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
    - `monitor_enable`: Map. Settings for the monitor enable command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
    - `monitor_refresh`: Map. Settings for the monitor refresh command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
    - `monitor_register`: Map. Settings for the monitor register command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
    - `monitor_validate`: Map. Settings for the monitor validate command.
      - `enabled`: Boolean. Flag to enable the command. Defaults to `true`.
  - `auth`: Map. Settings for dashboard authentication.
    - `session_expire_hours`: Integer. Session lifetime in hours. Defaults to `24`.
    - `invite_expire_hours`: Integer. Invite link lifetime in hours. Defaults to `1`.
    - `cookie_secure`: Boolean. Set the `Secure` flag on the session cookie. Enable it when serving the dashboard over HTTPS, otherwise the cookie can be stolen over plain HTTP. Keep it `false` for plain HTTP deployments (browsers won't send `Secure` cookies over HTTP). Defaults to `false`.

  Example:
  ```yaml
  http_server:
    port: 8000
    auth:
      session_expire_hours: 24
      invite_expire_hours: 1
      cookie_secure: false
    commands:
      alert_acknowledge:
        enabled: true
      alert_lock:
        enabled: true
      alert_solve:
        enabled: true
      issue_drop:
        enabled: true
      monitor_disable:
        enabled: true
      monitor_enable:
        enabled: true
      monitor_refresh:
        enabled: true
      monitor_register:
        enabled: true
      monitor_validate:
        enabled: true
  ```

  > [!WARNING]
  > On the first startup with an empty users table, a default `admin` user with password `admin` is created. Change the password immediately after the first login.

## Time Zone
- `time_zone`: String. Time zone to use for cron scheduling and notification messages.

## Heartbeat
- `heartbeat_time`: Integer. Time, in seconds, between each heartbeat. This heartbeat is used to identify when a task is not yielding the control back to the event loop for too much time, generating a Warning log.

## Controller Settings
- `controller_process_schedule`: String using Cron format. Schedule to check if monitors need to be processed.
- `controller_concurrency`: Integer. Number of monitors that can be processed at the same time by the Controller.
- `controller_procedures`: Map. Procedures to be executed by the Controller and their settings.
  - `clean_old_events`: Map. Settings for the procedure to clean old events from the application database.
    - `schedule`: String using Cron format. Schedule to execute the `clean_old_events` procedure.
    - `params`: Map. Configuration parameters for the `clean_old_events` procedure.
      - `age_days`: Integer. Event's older than the provided age, in days, will be deleted from the database.
  - `monitors_stuck`: Map. Settings for the procedure to fix monitors stuck in "queued" or "running" status.
    - `schedule`: String using Cron format. Schedule to execute the `monitors_stuck` procedure.
    - `params`: Map. Configuration parameters for the `monitors_stuck` procedure.
      - `time_tolerance`: Integer. Time tolerance in seconds for a monitor to be considered as stuck. This parameter is directly impacted by the `executor_monitor_heartbeat_time` setting and the recommended value is 2 times the heartbeat time.
  - `notifications_alert_solved`: Map. Settings for the procedure to identify and fix active notifications linked to alerts that have already been solved.
    - `schedule`: String using Cron format. Schedule to execute the `notifications_alert_solved` procedure.

To disable a procedure from executing you can set its schedule to `null`.

## Executor Settings
- `executor_concurrency`: Integer. Number of tasks that can be executed at the same time by each Executor.
- `executor_sleep`: Integer. Time, in seconds, the Executor will sleep when there are no tasks in the queue before trying again.
- `executor_monitor_timeout`: Integer. Timeout, in seconds, for monitor execution.
- `executor_reaction_timeout`: Integer. Timeout, in seconds, for reactions execution.
- `executor_request_timeout`: Integer. Timeout, in seconds, for requests execution.
- `executor_monitor_heartbeat_time`: Integer. Time, in seconds, between each executor heartbeat during monitor execution. This parameter impacts the controller procedure `monitors_stuck.time_tolerance` parameter.

## Issues Creation
- `max_issues_creation`: Integer. Maximum number of issues that can be created by each monitor in a single search. Can be overridden by the monitors' configuration.

## Database Defaults
Settings that will be applied to database queries executed by the monitors.
- `database_default_acquire_timeout`: Integer. Timeout to acquire a connection if a pool doesn't have any available.
- `database_default_query_timeout`: Integer. Timeout to execute a query.
- `database_close_timeout`: Integer. Timeout to close the connection pools when finishing the application.
- `database_log_query_metrics`: Boolean. Flag to log query metrics, useful for debugging slow monitors.

## Database Pools Configs
Settings for the database pools that were defined in the environment variables. See the [Querying databases](querying.md) document for more information.

The object defined for each database are the parameters that will be provided when creating the database pool.

## Event Logging
- `log_all_events`: Boolean. Flag to log all events, even if they don't have a reaction set for them. Events that have a reaction set will always be logged. This setting, when enabled, will increase the log length significantly.

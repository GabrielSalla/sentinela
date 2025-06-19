# Configuration file
This document provides an overview of the configuration parameters available in the `configs.yaml` file.

## Plugins
- `plugins`: List of strings. Plugins to be used by Sentinela. Check each plugin documentation to learn how to enable them.

## Monitors
- `load_sample_monitors`: Boolean. Flag to enable the sample monitors.
- `sample_monitors_path`: String. Path relative to the project root, where the sample monitors are stored.
- `internal_monitors_path`: String. Path relative to the project root, where the internal monitors are stored.
- `internal_monitors_notification`: Map. Settings for the notification to be sent by the internal monitors.
  - `enabled`: Boolean. Flag to enable the internal monitors notification.
  - `notification_class`: String. Class to be used for the notification. Example: `plugin.my_plugin.notifications.SomeNotificationClass`.
  - `params`: Map. The desired parameters for the notification. Each notification class will have its own set of parameters. Check the documentation for each notification class to learn more about the available parameters.
- `monitors_load_schedule`: String using Cron format. Schedule to reload monitors from the database.

## Logging
- `logging.mode`: String. Logging mode. Can be "friendly" or "json".
- `logging.format`: String. Settings for formatting the "friendly" logs.
- `logging.fields`: Map. Fields to include in the "json" logs and their name from the `logging` module.

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
- `application_queue.type`: String. Queue to be used. Can be `internal` or a queue from an installed plugin.
- `application_queue.queue_wait_message_time`: Integer. Time, in seconds, to wait for a message when using the internal queue.

Suggested configuration for the internal queue when running locally or developing:
```yaml
application_queue:
  type: internal
  queue_wait_message_time: 2
```

## HTTP Server
- `http_server.port`: Integer. Port for the HTTP server.

## Time Zone
- `time_zone`: String. Time zone to use for cron scheduling and notification messages.

## Controller Settings
- `controller_process_schedule`: String using Cron format. Schedule to check if monitors need to be processed.
- `controller_concurrency`: Integer. Number of monitors that can be processed at the same time by the Controller.
- `controller_procedures`: Map. Procedures to be executed by the Controller and their settings.
- `controller_procedures.monitors_stuck`: Map. Settings for the procedure to fix monitors stuck in "queued" or "running" status.
- `controller_procedures.monitors_stuck.schedule`: String using Cron format. Schedule to execute the `monitors_stuck` procedure.
- `controller_procedures.monitors_stuck.params.time_tolerance`: Integer. Time tolerance in seconds for a monitor to be considered as stuck. This parameter is directly impacted by the `executor_monitor_heartbeat_time` setting and the recommended value is 2 times the heartbeat time.

## Executor Settings
- `executor_concurrency`: Integer. Number of tasks that can be executed at the same time by each Executor.
- `executor_sleep`: Integer. Time, in seconds, the Executor will sleep when there are no tasks in the queue before trying again.
- `executor_monitor_timeout`: Integer. Timeout, in seconds, for monitor execution.
- `executor_reaction_timeout`: Integer. Timeout, in seconds, for reactions execution.
- `executor_request_timeout`: Integer. Timeout, in seconds, for requests execution.
- `executor_monitor_heartbeat_time`: Integer. Time, in seconds, between each monitor heartbeat. This parameter impacts the controller procedure `monitors_stuck.time_tolerance` parameter.

## Issues Creation
- `max_issues_creation`: Integer. Maximum number of issues that can be created by each monitor in a single search. Can be overridden by the monitors' configuration.

## Database Defaults
Settings that will be applied to database queries executed by the monitors.
- `database_default_acquire_timeout`: Integer. Timeout to acquire a connection if a pool doesn't have any available.
- `database_default_query_timeout`: Integer. Timeout to execute a query.
- `database_close_timeout`: Integer. Timeout to close the connection pools when finishing the application.
- `database_log_query_metrics`: Boolean. Flag to log query metrics, useful for debugging slow monitors.

## Database Pools Configs
Settings for the database pools that were defined in the environment variables. See the [Querying databases](docs/querying.md) document for more information.

The object defined for each database are the parameters that will be provided when creating the database pool.

## Event Logging
- `log_all_events`: Boolean. Flag to log all events, even if they don't have a reaction set for them. Events that have a reaction set will always be logged. This setting, when enabled, will increase the log length significantly.

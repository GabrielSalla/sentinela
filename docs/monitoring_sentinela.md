# Monitoring Sentinela
Sentinela provides logs and Prometheus metrics that can be used to monitor its status.

## Logs
Logs are separated in **informational**, **warnings** and **errors**.
- **Informational logs**: These logs provide details about the normal operation and execution progress of Sentinela. They are helpful for tracking routine activities and verifying that the system is functioning as expected.
- **Warning logs**: Warning logs indicate potential issues or suboptimal behaviors that may not immediately impact the system’s operation but should be addressed to prevent future problems. While the system may continue to operate, these logs may point to areas that require attention or further investigation.
- **Error logs**: Error logs signal critical issues that require immediate attention. They typically indicate a failure in Sentinela, an external service, or a monitor. These logs should be prioritized as they often point to significant problems that can affect the stability or performance of the system.

## Metrics
The Prometheus metrics provided by Sentinela are:
- `controller_monitors_processed_count`: Counter - Count of monitors processed by the controller
- `controller_monitor_not_registered_count`: Counter - Count of times the controller tries to process a monitor that isn't registered
- `controller_task_queue_error_count`: Counter - Count of times the controller fails to queue a task
- `executor_message_count`: Counter - Count of messages consumed by the executors.
    - Labels: `message_type`
- `executor_message_error_count`: Counter - Count of errors when processing messages
    - Labels: `message_type`
- `executor_message_processing_count`: Gauge - Count of messages being processed by the executors
    - Labels: `message_type`
- `executor_monitor_execution_error`: Counter - Error count for monitors
    - Labels: `monitor_id`, `monitor_name`
- `executor_monitor_execution_timeout`: Counter - Timeout count for monitors
    - Labels: `monitor_id`, `monitor_name`
- `executor_monitor_running`: Gauge - Flag indicating if the monitor is running
    - Labels: `monitor_id`, `monitor_name`
- `executor_monitor_execution_seconds`: Summary - Time to run the monitor
    - Labels: `monitor_id`, `monitor_name`
- `executor_monitor_execution_search_seconds`: Summary - Time to run the monitor's 'search' routine
    - Labels: `monitor_id`, `monitor_name`
- `executor_monitor_search_issues_limit_reached`: Counter - Count of times the monitor's 'search' routine reached the issues limit
    - Labels: `monitor_id`, `monitor_name`
- `executor_monitor_execution_update_seconds`: Summary - Time to run the monitor's 'update' routine
    - Labels: `monitor_id`, `monitor_name`
- `executor_monitor_execution_solve_seconds`: Summary - Time to run the monitor's 'solve' routine
    - Labels: `monitor_id`, `monitor_name`
- `executor_monitor_execution_alert_seconds`: Summary - Time to run the monitor's 'alert' routine
    - Labels: `monitor_id`, `monitor_name`
- `executor_reaction_execution_error`: Counter - Error count for reactions
    - Labels: `monitor_id`, `monitor_name`, `event_name`
- `executor_reaction_execution_timeout`: Counter - Timeout count for reactions
    - Labels: `monitor_id`, `monitor_name`, `event_name`
- `executor_reaction_execution_seconds`: Summary - Time to run the reaction
    - Labels: `monitor_id`, `monitor_name`, `event_name`
- `executor_request_execution_error`: Counter - Error count for requests
    - Labels: `action_name`
- `executor_request_execution_timeout`: Counter - Timeout count for requests
    - Labels: `action_name`
- `executor_request_execution_seconds`: Summary - Time to run the request
    - Labels: `action_name`
- `heartbeat_average_time`: Gauge - Average time between heartbeats in seconds
- `registry_monitors_ready_timeout_count`: Counter - Count of times the application timed out waiting for monitors to be ready
- `registry_monitor_not_registered_count`: Counter - Count of times a monitor is not registered after a load attempt

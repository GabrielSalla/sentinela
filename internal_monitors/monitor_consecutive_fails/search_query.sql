select
  monitors.id as monitor_id,
  monitors.name as monitor_name,
  monitors.enabled as monitor_enabled,
  coalesce(failed_count, 0) as failed_count
from "Monitors" as monitors
  left join lateral (
    select count(id) as failed_count
    from "MonitorExecutions" as monitor_executions
    where
      monitor_executions.monitor_id = monitors.id and
      monitor_executions.started_at > coalesce(monitors.last_successful_execution, to_timestamp(0))
  ) as monitor_executions
    on true
where
  monitors.enabled and
  failed_count >= 3;

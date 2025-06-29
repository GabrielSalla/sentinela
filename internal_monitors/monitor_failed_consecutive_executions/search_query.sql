with monitors_execution_events as (
  select
    id,
    created_at,
    model_id,
    row_number() over (partition by model_id order by created_at desc) as row_number
  from "Events"
  where event_type in ('monitor_execution_error', 'monitor_execution_success')
),
last_execution_success as (
  select
    model_id,
    max(created_at) as last_success_created_at,
    min(row_number) as row_number
  from monitors_execution_events
  where event_type = 'monitor_execution_success'
  group by model_id
),
last_consecutive_errors as (
  select
    model_id,
    count(id) as error_count
  from monitors_execution_events
    left join last_execution_success
      using (model_id)
  where
    monitors_execution_events.event_type = 'monitor_execution_error' and
    (
      monitors_execution_events.row_number < last_execution_success.row_number or
      last_execution_success.row_number is null
    )
  group by model_id
)
select
  last_consecutive_errors.model_id as monitor_id,
  monitors.name as monitor_name,
  monitors.enabled as monitor_enabled,
  last_consecutive_errors.error_count as consecutive_errors,
  last_execution_success.last_success_created_at as last_success
from last_consecutive_errors
  left join last_execution_success
    using (model_id)
  left join "Monitors" as monitors
    on monitors_events.model_id = monitors.id;

with monitors as (
  select
    id as monitor_id,
    enabled as monitor_enabled
    (queued or running) as monitor_pending,
    extract(epoch from current_timestamp - least(search_executed_at, update_executed_at)) :: int as seconds_queued
  from "Monitors"
  where
    id = any($1 :: int[])
)
select
  monitor_id,
  monitor_enabled,
  monitor_pending,
  seconds_queued
from monitors;

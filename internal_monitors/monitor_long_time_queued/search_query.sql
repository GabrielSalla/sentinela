with monitors as (
  select
    id as monitor_id,
    queued as monitor_queued,
    extract(epoch from current_timestamp - least(search_executed_at, update_executed_at)) :: int as seconds_queued
  from "Monitors"
  where
    enabled and
    queued
)
select
  monitor_id,
  monitor_queued,
  seconds_queued
from monitors
where
  seconds_queued > $1 :: int;

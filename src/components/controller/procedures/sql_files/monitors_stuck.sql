with monitors as (
  select
    id,
    extract(epoch from current_timestamp - last_heartbeat) :: int as time_since_last_heartbeat
  from "Monitors"
  where
    enabled and (queued or running)
)
select id
from monitors
where time_since_last_heartbeat > $1 :: int;

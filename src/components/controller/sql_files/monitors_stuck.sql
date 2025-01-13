with monitors as (
  select
    id,
    extract(epoch from current_timestamp - greatest(queued_at, running_at)) :: int as seconds_queued
  from "Monitors"
  where
    enabled and (queued or running)
)
select id
from monitors
where seconds_queued > $1 :: int;

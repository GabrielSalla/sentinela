with active_issues as (
  select
    monitor_id,
    count(id) as issues_count
  from "Issues"
  where status = 'active'
  group by monitor_id
  having count(id) > $1 :: int
)
select
  monitors.id as monitor_id,
  monitors.name as monitor_name,
  active_issues.issues_count as active_issues_count
from active_issues
  left join "Monitors" as monitors
    on monitors.id = active_issues.monitor_id;

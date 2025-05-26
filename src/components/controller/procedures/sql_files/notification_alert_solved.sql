with active_notifications as (
  select
    id,
    alert_id as notification_alert_id,
    status as notification_status
  from "Notifications"
  where
    status = 'active'
)
select active_notifications.id as id
from active_notifications
  inner join "Alerts" as alerts
    on active_notifications.notification_alert_id = alerts.id
where
  alerts.status = 'solved' and
  alerts.solved_at < current_timestamp - interval '5 minutes';

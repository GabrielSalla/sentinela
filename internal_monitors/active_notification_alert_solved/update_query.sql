select
  id as notification_id,
  status as notification_status
from "Notifications"
where
  id = any($1 :: int[]);

delete from "Events"
where created_at < current_timestamp - ($1 * INTERVAL '1 day');

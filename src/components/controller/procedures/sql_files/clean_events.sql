delete from "Events"
where created_at < current_timestamp - ($1 * interval '1 day');

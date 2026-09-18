# Plugin ntfy Notification Monitor
Demonstrates how to configure ntfy notifications for alerts.

**How it works**: This monitor is similar to the Value Rule Monitor but includes ntfy notification configuration. A single issue's error rate climbs every cycle, escalating the alert priority up to critical (P1). Once the error rate reaches the top, the issue is solved in the next cycle, solving the alert, and the cycle starts over. It sends a short summary message to the configured ntfy topic on alert creation, priority increase, acknowledgement and solution, showing how to integrate Sentinela alerts with ntfy.

> [!WARNING]
> Change the `topic` in the monitor's `notification_options` to your own topic before enabling it. The shipped `sentinela-example` topic is public so anyone subscribed to it receives these demo alerts. Also change `NTFY_SERVER_URL` in the `.env.general` file to point to the correct ntfy server instead of the fake host.

# FLAGS
MONITOR_REGISTER_ENABLED=false

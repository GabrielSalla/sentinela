# Slack commands
Sentinela provides two main ways to interact through Slack:
1. **Buttons** in notifications sent to a Slack channel.
2. **Messages** mentioning the Sentinela Slack app directly.

## Buttons in notifications
Slack notifications can include buttons to interact with the notifications, depending on it's priority and status. Buttons are shown only for active notifications.

Possible buttons:
- **Ack**: Acknowledge the alert. Visible if the alert has not yet been acknowledged at the priority level.
- **Lock**: Lock the alert. Visible if the alert is not already locked.
- **Solve**: Solves the alert. Visible only if the monitor’s issue settings is set as **not solvable**.

![Slack message with buttons](./images/slack_notification_message_with_buttons.png)

## Messages mentioning Sentinela
As a Slack app, Sentinela can also respond to direct commands sent in a message. To interact this way, mention the Sentinela app, followed by the desired action.

Available commands:
- `disable monitor {monitor_name}`: Disable the specified monitor.
- `enable monitor {monitor_name}`: Enable the specified monitor.
- `ack {alert_id}`: Acknowledge the specified alert.
- `lock {alert_id}`: Lock the specified alert.
- `solve {alert_id}`: Solve the specified alert.
- `drop issue {issue_id}`: Drop the specified issue.
- `resend notifications`: Delete and resend all active notifications for the current channel. Sometimes a Slack channel can have a lot of messages and a notification might get lost in the past. This command will resend the notification message so it'll be among the latest messages.

Examples:
- `@Sentinela disable monitor some_monitor`
- `@Sentinela enable monitor some_monitor`
- `@Sentinela ack 1234`
- `@Sentinela lock 2345`
- `@Sentinela solve 3456`
- `@Sentinela drop issue 1212`
- `@Sentinela resend notifications`

> [!WARNING]
> Ensure the message is using the correct `@` mention for the Sentinela Slack app in your workspace.

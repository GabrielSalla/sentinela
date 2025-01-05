# Slack Plugin
The Slack plugin offers an interface to interact with Sentinela through Slack. It allows users to receive notifications from Sentinela in a Slack channel while also providing useful commands from notification buttons or Slack messages mentioning the Sentinela bot.

## Environment variables
The following environment variables are used by the Slack plugin:
- `SLACK_TOKEN`: Used to send messages to Slack. Example: `xoxb-1234567890-1234567890123-12345678901234567890abcdef`
- `SLACK_WEBSOCKET_ENABLED`: Used to enable the websocket to receive events from Slack. Possible values are `true` or `false`.
- `SLACK_APP_TOKEN` Used to start the websocket, to receive the events from interactions with the Sentinela Slack app. Example: `xapp-1234567890-1234567890123-12345678901234567890abcdef`

## Slack commands
Sentinela provides two main ways to interact through Slack:
1. **Buttons** in notifications sent to a Slack channel.
2. **Messages** mentioning the Sentinela Slack app directly.

### Buttons in notifications
Slack notifications can include buttons to interact with the notifications, depending on it's priority and status. Buttons are shown only for active notifications.

Possible buttons:
- **Ack**: Acknowledge the alert. Visible if the alert has not yet been acknowledged at the priority level.
- **Lock**: Lock the alert. Visible if the alert is not already locked.
- **Solve**: Solves the alert. Visible only if the monitor’s issue settings is set as **not solvable**.

![Slack message with buttons](./images/slack_notification_message_with_buttons.png)

### Messages mentioning Sentinela
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

## Actions
Slack plugin implements a single action to handle the `resend notification` command.

## Notifications
```python
from plugins.slack.notifications import SlackNotification
```

The **SlackNotification** class manages sending notifications for alerts to a specified Slack channel.

Parameters:
- `channel`: The Slack channel where notifications will be sent.
- `title`: A title for the notification to help users to identify the problem.
- `issues_fields`: A list of fields from the issue data to include in the notification.
- `mention`: Slack user or group to mention if the alert reaches a specified priority. Provide the Slack identifier for a user (e.g., `U0011223344`) or a group (e.g., `G0011223344`). Set to `None` to avoid mentioning anyone. Defaults to `None`.
- `min_priority_to_mention`: Minimum alert priority that triggers a mention. Mentions will occur if the alert is not acknowledged at the current priority level and it's is greater than or equal to this setting. Defaults to `moderate` (P3).
- `issue_show_limit`: Maximum number of issues to show in the notification. If the limit is reached, the message `XXX more...` will be shown at the and of the issues list, where `XXX` is the number of issues that are not being shown. Defaults to 10.

The Slack message will show the alert and it's issues information. The notification will persist and will be updated until the alert is solved, even if it's priority falls to P5.

The notification also includes buttons to interact with the alert, allowing it to be acknowledged, locked or solved. The latest is only included if the issues setting was set as **not solvable**.

```python
notification_options = [
    SlackNotification(
        channel="C0011223344",
        title="Alert name",
        issues_fields=["id", "name"],
        mention="U0011223344",
    )
]
```

## Services
The Slack plugin includes a service that connects to the Slack websocket API to receive mentions and button press events. Any event received will queue an action to be processed by Sentinela.

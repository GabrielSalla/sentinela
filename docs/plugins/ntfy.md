# ntfy Plugin
The ntfy plugin sends Sentinela alert notifications to an [ntfy](https://ntfy.sh) topic via simple HTTP requests. It works with both the hosted `ntfy.sh` service and self-hosted ntfy servers. Unlike Slack messages, ntfy messages can't be updated or deleted, so a new message is published for each configured event.

By default, ntfy notifications trigger on:
- `alert_created`
- `alert_priority_increased`
- `alert_acknowledged`
- `alert_solved`

Use `notify_on_events` to customize which alert events trigger notifications.

## Enabling
To enable the ntfy plugin, add `ntfy` to the `plugins` list in the configuration file.

## Environment variables
The following environment variables are used by the ntfy plugin:
- `NTFY_SERVER_URL`: The ntfy server URL, used when `server_url` is not set in the notification params. Example: `https://ntfy.example.com`.
- `NTFY_TOKEN_{token_name}`: The token used for Bearer auth against servers requiring it. The `{token_name}` part must match the `token_name` notification setting, e.g. `token_name: my_app` reads the token from `NTFY_TOKEN_MY_APP`. Example: `NTFY_TOKEN_MY_APP=tk_abcdef123456`. When `token_name` is set, the matching environment variable is required.

## Notifications
```python
from plugins.ntfy.notifications import NtfyNotification
```

The **NtfyNotification** class manages sending notifications for alerts to an ntfy topic. Only the alert summary is sent (event name, priority and state), without the issues content, to keep the notification short. NtfyNotification objects with a different combination of `title`, `topic` and `min_priority_to_send` are considered different notification targets.

```python
class NtfyNotification:
    title: str
    topic: str
    server_url: str = field(default_factory=_default_server_url)  # NTFY_SERVER_URL or https://ntfy.sh
    token_name: str | None = None
    min_priority_to_send: AlertPriority = AlertPriority.low
    notify_on_events: list[str] = [
        "alert_created",
        "alert_priority_increased",
        "alert_acknowledged",
        "alert_solved",
    ]
```

Parameters:
- `title`: A title for the notification to help users to identify the problem.
- `topic`: The ntfy topic where notifications will be sent.
- `server_url`: The ntfy server URL. Uses the given value. If no value was provided, uses `NTFY_SERVER_URL` environment variable. If environment variable not defined, uses the default `https://ntfy.sh`.
- `token_name`: Name identifying which token to use for Bearer auth, read from the `NTFY_TOKEN_{token_name}` environment variable. Defaults to `None`.
- `min_priority_to_send`: Minimum alert priority that triggers a notification. Notifications will be sent if the alert is not acknowledged at the current priority level and it's is greater than or equal to this setting. Defaults to `low` (P4).
- `notify_on_events`: List of alert events that trigger a notification. Defaults to `alert_created`, `alert_priority_increased`, `alert_acknowledged` and `alert_solved`. Example: `["alert_created", "alert_solved"]`.

The alert priority is mapped to the ntfy `Priority` header (reversed scales): critical (P1) → max (5), high (P2) → high (4), moderate (P3) → default (3), low (P4) → low (2), informational (P5) → min (1). Solved alerts are sent with the default priority (3).

```python
notification_options = [
    NtfyNotification(
        title="Alert name",
        topic="sentinela-alerts",
        server_url="https://ntfy.sh",
    )
]
```

### Using ntfy notification for internal monitors
To use the ntfy notification for internal monitors, the settings for the `internal_monitors_notification` key in the `configs.yaml` file must be configured as follows:
- `notification_class`: Should be set to `plugin.ntfy.notifications.NtfyNotification`
- `params`: Should include the desired parameters for the notification.
  - `title` is specific to each monitor and is already defined in the internal monitors. If configured in the `params` field, it will be ignored.
  - `topic` is required and must be set in the `params` field.
  - `server_url` can be set in the `params` field. If not set, `server_url` falls back to the `NTFY_SERVER_URL` environment variable and then to the default.
  - `token_name` can be set in the `params` field. Defaults to `None`. When `token_name` is set, define the matching `NTFY_TOKEN_{token_name}` environment variable with the token value.
  - `min_priority_to_send` and `notify_on_events` can be set in the `params` field to customize the notification behavior. If not set, the default values will be used.

```yaml
internal_monitors_notification:
  enabled: true
  notification_class: plugin.ntfy.notifications.NtfyNotification
  params:
    topic: sentinela-alerts
    server_url: https://ntfy.sh
    token_name: my_app
```

With `token_name: my_app`, set the token value for the `NTFY_TOKEN_MY_APP` environment variable.

# Plugins
Plugins are a way to add functionality to Sentinela without needing to edit the application code. Plugins can be added to the `src/plugins` directory and will be automatically loaded by Sentinela.

Each plugin is a module that can implement it's own behaviors. Each plugin should follow the following basic structure:

```
src/plugins/my_plugin
├── __init__.py
├── actions
│   └── __init__.py
├── notifications
│   └── __init__.py
└── services
    └── __init__.py
```

More files or functionalities can be included with the plugin as long as they are available in each internal `actions`, `notifications` or `services` module.

**Each plugin should provide it's own documentation to guide users on how to use their functionalities.**

## Actions
Actions are used as custom behaviors to requests received by sentinela. If sentinela receives an action request named `plugin.my_plugin.some_action`, it'll look for the `some_action` function in the `actions` module of `my_plugin`.

Actions must have the following signature:
```python
async def action_name(message_payload: dict[Any, Any]):
```

An example of the action call made by Sentinela is:
```python
await plugin.my_plugin.actions.action_name({"key": "value"})
```

## Notifications
Notifications are used by monitors, usually to notify about an event. Each notification has it's own settings and behaviors.

Notifications must have the structure defined by the `src.notifications.base_notification.BaseNotification` **protocol**. The method `reactions_list` returns a list of reactions that will trigger an action. Each reaction is a tuple with the reaction name and a list of coroutines that must be called when the reaction is triggered.

Notification base structure:
```python
class Notification:
    min_priority_to_send: int = 5

    def reactions_list(self) -> list[tuple[str, list[Coroutine | partial[Coroutine]]]]:
        ...
```

A notification can have more parameters necessary to control their behavior. An example of a notification implementation is:
```python
class MyNotification:
    min_priority_to_send: int = 5

    def reactions_list(self) -> list[tuple[str, list[Coroutine | partial[Coroutine]]]]:
        """Get a list of events that the notification will react to"""
        return [
            ("alert_acknowledged", [handle_event_acknowledged]),
            ("alert_created", [handle_event_created]),
            ("alert_solved", [handle_event_solved]),
        ]
```

The reaction functions must follow the same structure presented in the [Monitor](./monitors.md) documentation.

## Services
Services are used when the plugin has some initialization or running service. An example of a running service is a websocket connection to an external provider.

Each service in the services directory should have the `start` and `stop` async functions. The `start` function is called when Sentinela is starting and the `stop` function is called when Sentinela is finishing.

The `start` function will receive, as parameters, the `controller_enabled` and `executor_enabled` booleans. These parameters are used to know if the controller and executor are running in the current process and can be used to control which functionalities might be enabled or provided in each scenario.

The `start` and `stop` functions must have the following signatures:

```python
async def init(controller_enabled: bool, executor_enabled: bool): ...

async def stop(): ...
```

## Built-in plugins
Sentinela comes with some built-in plugins that can be used to extend the application's functionality.
- [Slack](./plugin_slack.md)

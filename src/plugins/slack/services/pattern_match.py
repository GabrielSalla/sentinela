import re
from typing import Any, Coroutine

import commands as commands
import message_queue as message_queue
from configs import configs
from models import Monitor

from .. import slack


def monitor_disable(
    message_match: re.Match[Any], context: dict[str, Any]
) -> Coroutine[Any, Any, Any]:
    """Disable a monitor"""
    return commands.monitor_disable(message_match.group(1))


def monitor_enable(
    message_match: re.Match[Any], context: dict[str, Any]
) -> Coroutine[Any, Any, Any]:
    """Enable a monitor"""
    return commands.monitor_enable(message_match.group(1))


async def monitor_refresh(message_match: re.Match[Any], context: dict[str, Any]) -> None:
    """Refresh monitor"""
    monitor_name = message_match.group(1)
    task = message_match.group(2)
    tasks = [task] if task is not None else ["search", "update"]
    await commands.monitor_refresh(monitor_name, tasks)


async def monitor_documentation(message_match: re.Match[Any], context: dict[str, Any]) -> None:
    """Send monitor documentation as a thread reply"""
    monitor_name = message_match.group(1)

    monitor = await Monitor.get(Monitor.name == monitor_name)
    if monitor is None:
        return

    channel = context["channel"]
    # The message may not contain the 'thread_ts' field, so fallback to 'ts'
    thread_ts = context.get("thread_ts", context.get("ts"))

    if not monitor.documentation:
        await slack.send(channel=channel, thread_ts=thread_ts, text="No documentation available")
        return

    doc_block = slack.get_document_block(monitor.documentation)
    await slack.send(
        channel=channel,
        thread_ts=thread_ts,
        text="**Monitor documentation**",
        blocks=[doc_block] if doc_block else [],
    )


def alert_acknowledge(
    message_match: re.Match[Any], context: dict[str, Any]
) -> Coroutine[Any, Any, Any]:
    """Get the alert acknowledge action"""
    alert_id = int(message_match.group(1))
    return commands.alert_acknowledge(alert_id)


def alert_lock(message_match: re.Match[Any], context: dict[str, Any]) -> Coroutine[Any, Any, Any]:
    """Get the alert lock action"""
    alert_id = int(message_match.group(1))
    return commands.alert_lock(alert_id)


def alert_solve(message_match: re.Match[Any], context: dict[str, Any]) -> Coroutine[Any, Any, Any]:
    """Get the alert solve action"""
    alert_id = int(message_match.group(1))
    return commands.alert_solve(alert_id)


def issue_drop(message_match: re.Match[Any], context: dict[str, Any]) -> Coroutine[Any, Any, Any]:
    """Get the issue drop action"""
    issue_id = int(message_match.group(1))
    return commands.issue_drop(issue_id)


def resend_notifications(
    message_match: re.Match[Any], context: dict[str, Any]
) -> Coroutine[Any, Any, Any]:
    """Get the resend slack notifications action"""
    return message_queue.send_message(
        type="request",
        payload={
            "action": "plugin.slack.resend_notifications",
            "params": {"slack_channel": context["channel"]},
        },
    )


async def disabled_command_message(message_match: re.Match[Any], context: dict[str, Any]) -> None:
    """Send a message indicating that the command is disabled"""
    channel = context["channel"]
    # The message may not contain the 'thread_ts' field, so fallback to 'ts'
    thread_ts = context.get("thread_ts", context.get("ts"))

    await slack.send(
        channel=channel,
        thread_ts=thread_ts,
        text=f"Command for the message `{message_match.group(0)}` is disabled",
    )


MENTION_PATTERN = r"(?:<@\w+>)? "
PATTERNS = {
    r"?disable monitor +(\w+)": monitor_disable,
    r"?enable monitor +(\w+)": monitor_enable,
    r"?refresh +(\w+)(?: +(search|update))?": monitor_refresh,
    r"?ack +(\d+)": alert_acknowledge,
    r"?lock +(\d+)": alert_lock,
    r"?solve +(\d+)": alert_solve,
    r"?drop issue +(\d+)": issue_drop,
    r"?docs +(\w+)": monitor_documentation,
    r"?resend notifications": resend_notifications,
}


def get_message_request(message: str, context: dict[str, Any]) -> Coroutine[Any, Any, Any] | None:
    """Get a coroutine to be awaited corresponding to the provided request"""
    commands_configs = configs.plugins_configs.get("slack", {}).get("commands", {})

    for pattern, get_action_function in PATTERNS.items():
        match = re.match(MENTION_PATTERN + pattern, message)

        if match is None:
            continue

        if not commands_configs.get(get_action_function.__name__, {}).get("enabled", True):
            return disabled_command_message(message_match=match, context=context)

        return get_action_function(message_match=match, context=context)

    return None

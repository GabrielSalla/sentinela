import re
from typing import Any, Coroutine

import commands as commands
import message_queue as message_queue


def disable_monitor(
    message_match: re.Match[Any], context: dict[str, Any]
) -> Coroutine[Any, Any, Any]:
    """Disable a monitor"""
    return commands.disable_monitor(message_match.group(1))


def enable_monitor(
    message_match: re.Match[Any], context: dict[str, Any]
) -> Coroutine[Any, Any, Any]:
    """Enable a monitor"""
    return commands.enable_monitor(message_match.group(1))


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
            "slack_channel": context["channel"],
        },
    )


PATTERNS = {
    r"(?:<@\w+>)? ?disable monitor +(\w+)": disable_monitor,
    r"(?:<@\w+>)? ?enable monitor +(\w+)": enable_monitor,
    r"(?:<@\w+>)? ?ack +(\d+)": alert_acknowledge,
    r"(?:<@\w+>)? ?lock +(\d+)": alert_lock,
    r"(?:<@\w+>)? ?solve +(\d+)": alert_solve,
    r"(?:<@\w+>)? ?drop issue +(\d+)": issue_drop,
    r"(?:<@\w+>)? ?resend notifications": resend_notifications,
}


def get_message_request(message: str, context: dict[str, Any]) -> Coroutine[Any, Any, Any] | None:
    """Get a coroutine to be awaited corresponding to the provided request"""
    for pattern, get_action_function in PATTERNS.items():
        match = re.match(pattern, message)

        if match is None:
            continue

        # Get the action from 'requests'
        return get_action_function(
            message_match=match,
            context=context,
        )

    return None

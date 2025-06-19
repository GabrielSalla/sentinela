import asyncio
import json
import logging
import traceback
from typing import Any, Callable, Coroutine, cast

import prometheus_client
from pydantic import ValidationError

import registry as registry
from base_exception import BaseSentinelaException
from configs import configs
from data_models.request_payload import RequestPayload
from models import Alert, Issue
from plugins.attribute_select import get_plugin_attribute

_logger = logging.getLogger("request_handler")

prometheus_request_error_count = prometheus_client.Counter(
    "executor_request_execution_error",
    "Error count for requests",
    ["action_name"],
)
prometheus_request_timeout_count = prometheus_client.Counter(
    "executor_request_execution_timeout",
    "Timeout count for requests",
    ["action_name"],
)
prometheus_request_execution_time = prometheus_client.Summary(
    "executor_request_execution_seconds",
    "Time to run the request",
    ["action_name"],
)


async def alert_acknowledge(message_payload: RequestPayload) -> None:
    """Acknowledge an alert"""
    alert_id = message_payload.params["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.acknowledge()


async def alert_lock(message_payload: RequestPayload) -> None:
    """Lock an alert"""
    alert_id = message_payload.params["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.lock()


async def alert_solve(message_payload: RequestPayload) -> None:
    """Solve all alert's issues"""
    alert_id = message_payload.params["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.solve_issues()


async def issue_drop(message_payload: RequestPayload) -> None:
    """Drop an issue"""
    issue_id = message_payload.params["target_id"]
    issue = await Issue.get_by_id(issue_id)
    if issue is None:
        _logger.info(f"Issue '{issue_id}' not found")
        return
    await registry.wait_monitor_loaded(issue.monitor_id)
    await issue.drop()


actions = {
    "alert_acknowledge": alert_acknowledge,
    "alert_lock": alert_lock,
    "alert_solve": alert_solve,
    "issue_drop": issue_drop,
}


def get_action(action_name: str) -> Callable[[RequestPayload], Coroutine[Any, Any, None]] | None:
    """Get the action function by its name, checking if it is a plugin action"""
    if action_name.startswith("plugin."):
        try:
            action = get_plugin_attribute(action_name)
        except ValueError as e:
            _logger.warning(e.args[0])
            return None

        return cast(Callable[[RequestPayload], Coroutine[Any, Any, None]], action)

    return actions.get(action_name)


async def run(message: dict[Any, Any]) -> None:
    """Process a received request"""
    try:
        message_payload = RequestPayload(**message["payload"])
    except KeyError:
        _logger.error(f"Message '{json.dumps(message)}' missing 'payload' field")
        return
    except ValidationError as e:
        _logger.error(f"Invalid payload: {e}")
        return

    action_name = message_payload.action

    action = get_action(action_name)

    if action is None:
        _logger.warning(
            f"Got request with unknown action '{json.dumps(message_payload.to_dict())}'"
        )
        return

    try:
        with prometheus_request_execution_time.labels(action_name=action_name).time():
            await asyncio.wait_for(action(message_payload), configs.executor_request_timeout)
    except asyncio.TimeoutError:
        prometheus_request_timeout_count.labels(action_name=action_name).inc()
        _logger.error(f"Timed out executing request '{json.dumps(message_payload.to_dict())}'")
    except BaseSentinelaException as e:
        raise e
    except Exception:
        prometheus_request_error_count.labels(action_name=action_name).inc()
        _logger.error(f"Error executing request '{json.dumps(message_payload.to_dict())}'")
        _logger.error(traceback.format_exc().strip())

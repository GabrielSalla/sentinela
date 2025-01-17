import asyncio
import json
import logging
import traceback
from typing import Any

import plugins
import registry as registry
from base_exception import BaseSentinelaException
from configs import configs
from models import Alert, Issue

_logger = logging.getLogger("request_handler")


async def alert_acknowledge(message_payload: dict[Any, Any]):
    """Acknowledge an alert"""
    alert_id = message_payload["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.acknowledge()


async def alert_lock(message_payload: dict[Any, Any]):
    """Lock an alert"""
    alert_id = message_payload["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.lock()


async def alert_solve(message_payload: dict[Any, Any]):
    """Solve all alert's issues"""
    alert_id = message_payload["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.solve_issues()


async def issue_drop(message_payload: dict[Any, Any]):
    """Drop an issue"""
    issue_id = message_payload["target_id"]
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


def get_action(action_name: str):
    """Get the action function by its name, checking if it is a plugin action"""
    if action_name.startswith("plugin."):
        plugin_name, action_name = action_name.split(".")[1:3]

        plugin = plugins.loaded_plugins.get(plugin_name)
        if plugin is None:
            _logger.warning(f"Plugin '{plugin_name}' unknown")
            return None

        plugin_actions = getattr(plugin, "actions", None)
        if plugin_actions is None:
            _logger.warning(f"Plugin '{plugin_name}' doesn't have actions")
            return None

        action = getattr(plugin_actions, action_name, None)
        if action is None:
            _logger.warning(f"Action '{plugin_name}.{action_name}' unknown")
            return None

        return action

    return actions.get(action_name)


async def run(message: dict[Any, Any]):
    """Process a received request"""
    message_payload = message["payload"]
    action_name = message_payload["action"]

    action = get_action(action_name)

    if action is None:
        _logger.warning(f"Got request with unknown action '{json.dumps(message_payload)}'")
        return

    try:
        await asyncio.wait_for(action(message_payload), configs.executor_request_timeout)
    except asyncio.TimeoutError:
        _logger.error(f"Timed out executing request '{json.dumps(message_payload)}'")
    except BaseSentinelaException as e:
        raise e
    except Exception:
        _logger.error(f"Error executing request '{json.dumps(message_payload)}'")
        _logger.error(traceback.format_exc().strip())

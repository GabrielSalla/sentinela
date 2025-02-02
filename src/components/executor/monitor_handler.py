import asyncio
import json
import logging
import traceback
from datetime import datetime
from typing import Any, Literal, cast

import prometheus_client
from pydantic import ValidationError

import registry as registry
from base_exception import BaseSentinelaException
from data_models.process_monitor_payload import ProcessMonitorPayload
from internal_database import get_session
from models import Alert, Issue, Monitor
from utils.async_tools import do_concurrently

_logger = logging.getLogger("monitor_handler")

prometheus_monitor_error_count = prometheus_client.Counter(
    "executor_monitor_execution_error",
    "Error count for monitors",
    ["monitor_id", "monitor_name"],
)
prometheus_monitor_timeout_count = prometheus_client.Counter(
    "executor_monitor_execution_timeout",
    "Timeout count for monitors",
    ["monitor_id", "monitor_name"],
)
prometheus_monitor_running = prometheus_client.Gauge(
    "executor_monitor_running",
    "Flag indicating if the monitor is running",
    ["monitor_id", "monitor_name"],
)
prometheus_monitor_execution_time = prometheus_client.Summary(
    "executor_monitor_execution_seconds",
    "Time to run the monitor",
    ["monitor_id", "monitor_name"],
)
prometheus_monitor_search_time = prometheus_client.Summary(
    "executor_monitor_execution_search_seconds",
    "Time to run the monitor's 'search' routine",
    ["monitor_id", "monitor_name"],
)
prometheus_monitor_search_issues_limit_reached = prometheus_client.Counter(
    "executor_monitor_search_issues_limit_reached",
    "Count of times the monitor's 'search' routine reached the issues limit",
    ["monitor_id", "monitor_name"],
)
prometheus_monitor_update_time = prometheus_client.Summary(
    "executor_monitor_execution_update_seconds",
    "Time to run the monitor's 'update' routine",
    ["monitor_id", "monitor_name"],
)
prometheus_monitor_solve_time = prometheus_client.Summary(
    "executor_monitor_execution_solve_seconds",
    "Time to run the monitor's 'solve' routine",
    ["monitor_id", "monitor_name"],
)
prometheus_monitor_alert_time = prometheus_client.Summary(
    "executor_monitor_execution_alert_seconds",
    "Time to run the monitor's 'alert' routine",
    ["monitor_id", "monitor_name"],
)


def _convert_types(data: Any) -> Any:
    """Recursive function to convert all object types to JSON compatible ones, casting to string
    when it's a not mapped type"""
    if isinstance(data, list):
        return [_convert_types(value) for value in data]
    if isinstance(data, dict):
        return {key: _convert_types(value) for key, value in data.items()}
    if isinstance(data, datetime):
        return data.isoformat(timespec="milliseconds")
    if data is None or isinstance(data, (str, int, float, bool)):
        return data
    return str(data)


def _make_dict_json_compatible(data: Any) -> dict[Any, Any] | None:
    """If the data is a dictionary, convert the types to JSON compatible ones, otherwise,
    return None"""
    if not isinstance(data, dict):
        return None

    return cast(dict[Any, Any] | None, _convert_types(data))


async def _search_routine(monitor: Monitor) -> None:
    """Search routine for the monitor, executing the 'search' function and processing the returned
    data"""
    found_issues_data = await monitor.search_function()

    if not found_issues_data:
        return

    if not isinstance(found_issues_data, list):
        _logger.warning(
            f"Invalid return of 'search' function for {monitor}. Should be a 'list', "
            f"got: '{str(found_issues_data)}'"
        )
        return

    # Get the active issues ids to check if any of the found issues already exists
    active_issues_ids = {issue.model_id for issue in monitor.active_issues}

    # Check all the found issues
    new_issues_data = {}
    for raw_issue_data in found_issues_data:
        issue_data = _make_dict_json_compatible(raw_issue_data)

        if issue_data is None:
            _logger.warning(
                f"Invalid issue data from 'search' function for {monitor}: '{str(raw_issue_data)}'"
            )
            continue

        model_id_key = monitor.issue_options.model_id_key

        # Checking if the model id key is in the dictionary
        if model_id_key not in issue_data:
            _logger.warning(
                f"Invalid issue data from 'search', model id key '{model_id_key}' not found in "
                f"issue data for {monitor}: '{str(issue_data)}'"
            )
            continue

        # Check if it's an active issue
        model_id = str(issue_data.get(model_id_key))
        if model_id in active_issues_ids:
            continue

        # Check if it's a duplicate in the found issues
        if model_id in new_issues_data:
            _logger.warning(f"Found duplicate model id '{model_id}'. Skipping this one")
            continue

        # Check it's uniqueness
        if monitor.issue_options.unique:
            if not await Issue.is_unique(monitor_id=monitor.id, model_id=model_id):
                continue

        # Check if it's considered as solved
        if monitor.is_solved_function(issue_data):
            continue

        # Add it to the new issues list if all checks passed
        new_issues_data[model_id] = issue_data

    # Limit the number of issues being created
    # Doing it after filtering the new issues to avoid losing newer ones
    max_issues = monitor.options.max_issues_creation
    if len(new_issues_data) > max_issues:
        search_issues_limit_count = prometheus_monitor_search_issues_limit_reached.labels(
            monitor_id=monitor.id, monitor_name=monitor.name
        )
        search_issues_limit_count.inc()

        new_issues_data = {
            key: new_issues_data[key] for key in list(new_issues_data.keys())[:max_issues]
        }

    # Create the issues
    issues = [
        Issue(
            monitor_id=monitor.id,
            model_id=model_id,
            data=issue_data,
        )
        for model_id, issue_data in new_issues_data.items()
    ]
    issues = await Issue.create_batch(issues)

    # Add them to the monitor
    monitor.add_issues(issues)


async def _update_routine(monitor: Monitor) -> None:
    """Update routine for the monitor, executing the 'update' function and processing the returned
    data"""
    # Skip the update routine if there're no active issues
    if len(monitor.active_issues) == 0:
        return

    active_issues_data = [issue.data for issue in monitor.active_issues]

    issues_updates_data = await monitor.update_function(issues_data=active_issues_data)

    if not issues_updates_data:
        return

    if not isinstance(issues_updates_data, list):
        _logger.warning(
            f"Invalid return of 'update' function for {monitor}. Should be a 'list', "
            f"got: '{str(issues_updates_data)}'"
        )
        return

    active_issues_map = {issue.model_id: issue for issue in monitor.active_issues}

    # Check all the found issues
    issues_update_tasks_info: dict[str, tuple[Issue, dict[Any, Any]]] = {}
    for raw_issue_data in issues_updates_data:
        issue_data = _make_dict_json_compatible(raw_issue_data)

        if issue_data is None:
            _logger.warning(
                f"Invalid issue data from 'update' function for {monitor}: '{str(raw_issue_data)}'"
            )
            continue

        model_id_key = monitor.issue_options.model_id_key

        # Checking if the model id key is in the dictionary
        if model_id_key not in issue_data:
            _logger.warning(
                f"Invalid issue data from 'update', model id key '{model_id_key}' not found in "
                f"issue data for {monitor}: '{str(issue_data)}'"
            )
            continue

        model_id = str(issue_data[model_id_key])

        # Check if it's a duplicate in the issues update tasks
        if model_id in issues_update_tasks_info:
            _logger.warning(f"Found duplicate model id '{model_id}'. Skipping this one")
            continue

        try:
            active_issue = active_issues_map[model_id]
            issues_update_tasks_info[model_id] = (active_issue, issue_data)
        except KeyError:
            _logger.warning(
                f"Issue with model id '{model_id}' not found in active issues. "
                "Maybe it changed in the update process"
            )
            continue

    async with get_session() as session:
        for issue, raw_issue_data in issues_update_tasks_info.values():
            await issue.update_data(raw_issue_data, session=session)


async def _issues_solve_routine(monitor: Monitor) -> None:
    """Issue solve routine for the monitor, checking all issues against the 'is_solved' function"""
    async with get_session() as session:
        for issue in monitor.active_issues:
            await issue.check_solved(session=session)


async def _alerts_routine(monitor: Monitor) -> None:
    """Alert routine for the monitor, creating, linking issues, updating and solving them"""
    # As 'alert_options' can be None, check it before executing
    if monitor.alert_options is None:
        return

    alert: Alert | None
    issue_without_alerts = [issue for issue in monitor.active_issues if issue.alert_id is None]

    if len(issue_without_alerts) > 0:
        # Look for an active and not locked Alert
        for alert in monitor.active_alerts:
            if not alert.locked:
                break
        # If didn't find one, check if one should be created
        else:
            alert_priority = Alert.calculate_priority(
                monitor.alert_options.rule, issue_without_alerts
            )
            if alert_priority is None:
                alert = None
            else:
                alert = await Alert().create(monitor_id=monitor.id)
                monitor.add_alert(alert)

        # If got an alert, link the issues to it
        if alert is not None:
            await alert.link_issues(issue_without_alerts)

    await do_concurrently(*[alert.update_priority() for alert in monitor.active_alerts])
    await do_concurrently(*[alert.update() for alert in monitor.active_alerts])


async def _run_routines(monitor: Monitor, tasks: list[Literal["search", "update"]]) -> None:
    """Run all routines for a monitor, based on a list of tasks"""
    # Monitor instrumentation metrics
    prometheus_labels = {
        "monitor_id": monitor.id,
        "monitor_name": monitor.name,
    }
    monitor_update_time = prometheus_monitor_execution_time.labels(**prometheus_labels)
    monitor_solve_time = prometheus_monitor_solve_time.labels(**prometheus_labels)
    monitor_search_time = prometheus_monitor_search_time.labels(**prometheus_labels)
    monitor_alert_time = prometheus_monitor_alert_time.labels(**prometheus_labels)

    await monitor.load()

    if "update" in tasks:
        with monitor_update_time.time():
            await _update_routine(monitor)

        await monitor.refresh()
        monitor.set_update_executed_at()
        await monitor.save()
        # Reload all objects to prevent some kind of injection
        await monitor.load()

    with monitor_solve_time.time():
        await _issues_solve_routine(monitor)

    if "search" in tasks:
        with monitor_search_time.time():
            await _search_routine(monitor)

        await monitor.refresh()
        monitor.set_search_executed_at()
        await monitor.save()

    with monitor_alert_time.time():
        await _alerts_routine(monitor)


async def run(message: dict[Any, Any]) -> None:
    """Process a message with type 'process_monitor', loading the monitor and executing it's
    routines, while also detecting errors and reporting them accordingly"""
    try:
        message_payload = ProcessMonitorPayload(**message["payload"])
    except KeyError:
        _logger.error(f"Message '{json.dumps(message)}' missing 'payload' field")
        return
    except ValidationError as e:
        _logger.error(f"Invalid payload: {e}")
        return

    monitor_id = message_payload.monitor_id
    monitor = await Monitor.get_by_id(monitor_id)
    if monitor is None:
        _logger.error(f"Monitor {monitor_id} not found. Skipping message")
        return

    await registry.wait_monitor_loaded(monitor_id)

    # Skip executing the monitor if it's already running
    if monitor.running:
        return

    prometheus_labels = {
        "monitor_id": monitor.id,
        "monitor_name": monitor.name,
    }

    monitor_running = prometheus_monitor_running.labels(**prometheus_labels)
    monitor_running.inc()

    try:
        monitor.set_running(True)
        await monitor.save()

        monitor_execution_time = prometheus_monitor_execution_time.labels(**prometheus_labels)
        with monitor_execution_time.time():
            await asyncio.wait_for(
                _run_routines(monitor, message_payload.tasks), monitor.options.execution_timeout
            )
    except asyncio.TimeoutError:
        monitor_timeout_count = prometheus_monitor_timeout_count.labels(**prometheus_labels)
        monitor_timeout_count.inc()

        _logger.warning(f"Execution for monitor '{monitor}' timed out")
    except BaseSentinelaException as e:
        raise e
    except Exception:
        monitor_error_count = prometheus_monitor_error_count.labels(**prometheus_labels)
        monitor_error_count.inc()

        _logger.error(f"Error in execution for monitor '{monitor}'")
        _logger.error(traceback.format_exc().strip())
        _logger.info("Exception caught successfully, going on")
    finally:
        # Refresh the monitor before updating to prevent overwriting information that might have
        # changed while the routines were executing
        await monitor.refresh()
        # Set the monitor's running and queued variables to False, to allow the monitor to be
        # queued and run again
        monitor.set_running(False)
        monitor.set_queued(False)
        await monitor.save()

        monitor_running.dec()

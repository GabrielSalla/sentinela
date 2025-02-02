import asyncio
import time
from functools import partial
from typing import Any, Coroutine
from unittest.mock import AsyncMock, MagicMock

import pytest

import components.executor.reaction_handler as reaction_handler
import registry.registry as registry
from base_exception import BaseSentinelaException
from configs import configs
from data_models.event_payload import EventPayload
from data_models.monitor_options import ReactionOptions
from models import Monitor
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


def get_event_payload(
    event_source: str = "",
    event_source_id: int = 0,
    event_source_monitor_id: int = 0,
    event_name: str = "",
    event_data: dict[str, Any] = {},
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a sample event payload with default values for the fields that were not provided"""
    return {
        "event_source": event_source,
        "event_source_id": event_source_id,
        "event_source_monitor_id": event_source_monitor_id,
        "event_name": event_name,
        "event_data": event_data,
        "extra_payload": extra_payload,
    }


async def test_run_invalid_payload(caplog):
    """'run' should log an error if the payload is invalid and just return"""
    await reaction_handler.run({})
    assert_message_in_log(caplog, "Message '{}' missing 'payload' field")


async def test_run_payload_wrong_structure(caplog):
    """'run' should log an error if the payload has the wrong structure and just return"""
    await reaction_handler.run({"payload": {}})
    assert_message_in_log(caplog, "Invalid payload: 5 validation errors for EventPayload")


async def test_run_monitor_not_found(caplog):
    """'run' should ignore the message if a monitor with the provided id was not found"""
    await reaction_handler.run(
        {
            "payload": get_event_payload(
                event_source_monitor_id=999999999, event_name="alert_created"
            )
        }
    )
    assert_message_in_log(caplog, "Monitor 999999999 not found. Skipping message")


@pytest.mark.flaky(reruns=2)
async def test_run_monitor_not_registered(caplog, monkeypatch, sample_monitor: Monitor):
    """'run' should handle raise a 'MonitorNotRegisteredError' exception if the monitor is not
    registered"""
    monkeypatch.setattr(registry, "MONITORS_READY_TIMEOUT", 0.2)
    del registry._monitors[sample_monitor.id]

    run_task = asyncio.create_task(
        reaction_handler.run(
            {
                "payload": get_event_payload(
                    event_source_monitor_id=sample_monitor.id, event_name="alert_created"
                )
            }
        )
    )

    start_time = time.perf_counter()
    await asyncio.sleep(0.1)
    registry.monitors_ready.set()
    registry.monitors_pending.clear()

    with pytest.raises(registry.MonitorNotRegisteredError):
        await run_task
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.1 - 0.001
    assert total_time < 0.1 + 0.03


async def test_run_no_reactions(monkeypatch, sample_monitor: Monitor):
    """'run' should do nothing if there're no reactions registered for the event"""
    monkeypatch.setattr(sample_monitor.code, "reaction_options", ReactionOptions(), raising=False)

    await reaction_handler.run(
        {
            "payload": get_event_payload(
                event_source_monitor_id=sample_monitor.id, event_name="alert_created"
            )
        }
    )


async def test_run_single_reaction(monkeypatch, sample_monitor: Monitor):
    """'run' should execute the reaction when there's only one registered for the event"""

    async def do_nothing(message_payload): ...

    reaction_mock = AsyncMock(side_effect=do_nothing)
    monkeypatch.setattr(
        sample_monitor.code,
        "reaction_options",
        ReactionOptions(alert_created=[reaction_mock]),
        raising=False,
    )

    message_payload = {
        "payload": get_event_payload(
            event_source_monitor_id=sample_monitor.id, event_name="alert_created"
        )
    }
    await reaction_handler.run(message_payload)

    reaction_mock.assert_awaited_once_with(EventPayload(**message_payload["payload"]))


@pytest.mark.parametrize(
    "event_name", ["alert_created", "alert_updated", "issue_created", "issue_solved"]
)
@pytest.mark.parametrize("number_of_events", [2, 5, 10])
async def test_run_multiple_reaction(
    monkeypatch, sample_monitor: Monitor, event_name, number_of_events
):
    """'run' should execute the reactions when there're multiple ones registered for the event"""

    async def do_nothing(message_payload): ...

    reaction_mock = AsyncMock(side_effect=do_nothing)
    monkeypatch.setattr(
        sample_monitor.code,
        "reaction_options",
        ReactionOptions(**{event_name: [reaction_mock] * number_of_events}),
        raising=False,
    )

    message_payload = {
        "payload": get_event_payload(
            event_source_monitor_id=sample_monitor.id, event_name=event_name
        )
    }
    await reaction_handler.run(message_payload)

    assert reaction_mock.await_count == number_of_events
    call_args = (EventPayload(**message_payload["payload"]),)
    assert reaction_mock.call_args_list == [(call_args,)] * number_of_events


async def test_run_multiple_reaction_error(caplog, monkeypatch, sample_monitor: Monitor):
    """'run' should execute all the reactions even if some of them raise any errors"""

    async def error(message_payload):
        raise ValueError("Something happened")

    async def do_nothing(message_payload): ...

    reaction_mock = AsyncMock(side_effect=do_nothing)
    monkeypatch.setattr(
        sample_monitor.code,
        "reaction_options",
        ReactionOptions(alert_created=[reaction_mock, error, reaction_mock]),
        raising=False,
    )

    message_payload = {
        "payload": get_event_payload(
            event_source_monitor_id=sample_monitor.id, event_name="alert_created"
        )
    }
    await reaction_handler.run(message_payload)

    assert reaction_mock.await_count == 2
    call_args = (EventPayload(**message_payload["payload"]),)
    assert reaction_mock.call_args_list == [(call_args,)] * 2
    assert_message_in_log(caplog, "ValueError: Something happened")
    assert_message_in_log(caplog, "Error executing reaction")


async def test_run_partial(monkeypatch, sample_monitor: Monitor):
    """'run' should be able to handle partial functions, as notifications will use this feature"""

    async def do_nothing(message_payload, something): ...

    reaction_mock = AsyncMock(side_effect=do_nothing)
    do_nothing_partial = partial(reaction_mock, something="other thing")
    monkeypatch.setattr(
        sample_monitor.code,
        "reaction_options",
        ReactionOptions(alert_created=[do_nothing_partial]),
        raising=False,
    )

    message_payload = {
        "payload": get_event_payload(
            event_source_monitor_id=sample_monitor.id, event_name="alert_created"
        )
    }
    await reaction_handler.run(message_payload)

    reaction_mock.assert_awaited_once_with(
        EventPayload(**message_payload["payload"]), something="other thing"
    )


async def test_run_function_no_name(caplog, mocker, monkeypatch, sample_monitor: Monitor):
    """'run' should handle reactions that doesn't have a name. The function name is for logging"""
    monkeypatch.setattr(configs, "executor_reaction_timeout", 0.1)

    # Create an object that has no '__name__' attribute but is callable
    class Mock:
        def __call__(self, message_payload) -> Coroutine[None, None, None]:
            async def long_sleep() -> None:
                await asyncio.sleep(1)

            return long_sleep()

    call_spy: MagicMock = mocker.spy(Mock, "__call__")
    mock_function = Mock()

    with pytest.raises(AttributeError):
        mock_function.__name__  # type: ignore[attr-defined]

    monkeypatch.setattr(
        sample_monitor.code,
        "reaction_options",
        ReactionOptions(alert_created=[mock_function]),
        raising=False,
    )

    call_spy.assert_not_called()

    message_payload = {
        "payload": get_event_payload(
            event_source_monitor_id=sample_monitor.id, event_name="alert_created"
        )
    }
    await reaction_handler.run(message_payload)

    assert call_spy.call_args[0][1] == EventPayload(**message_payload["payload"])

    assert_message_in_log(
        caplog,
        "Timed out executing reaction "
        "'<test_reaction_handler.test_run_function_no_name.<locals>.Mock object at 0x",
    )
    assert_message_in_log(caplog, "' with payload '")


@pytest.mark.flaky(reruns=2)
async def test_run_timeout(caplog, monkeypatch, sample_monitor: Monitor):
    """'run' should execute all the reactions and the timeout should be independent for each
    function"""
    monkeypatch.setattr(configs, "executor_reaction_timeout", 0.2)

    async def long_sleep(message_payload):
        await asyncio.sleep(1)

    long_sleep_mock = AsyncMock(side_effect=long_sleep)

    async def short_sleep(message_payload):
        await asyncio.sleep(0.1)

    short_sleep_mock = AsyncMock(side_effect=short_sleep)

    monkeypatch.setattr(
        sample_monitor.code,
        "reaction_options",
        ReactionOptions(
            alert_created=[long_sleep_mock] * 2 + [short_sleep_mock] * 2 + [long_sleep_mock] * 2
        ),
        raising=False,
    )

    message_payload = {
        "payload": get_event_payload(
            event_source_monitor_id=sample_monitor.id, event_name="alert_created"
        )
    }

    start_time = time.perf_counter()
    await reaction_handler.run(message_payload)
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 1 - 0.001
    assert total_time < 1 + 0.03

    assert long_sleep_mock.call_count == 4
    assert_message_in_log(caplog, "Timed out executing reaction", count=4)

    assert short_sleep_mock.call_count == 2


async def test_run_sentinela_exception(monkeypatch, sample_monitor: Monitor):
    """'run' should re-raise Sentinela exceptions"""

    class SomeException(BaseSentinelaException):
        pass

    async def error(message_payload):
        raise SomeException("Some Sentinela exception")

    monkeypatch.setattr(
        sample_monitor.code,
        "reaction_options",
        ReactionOptions(alert_created=[error]),
        raising=False,
    )

    message_payload = {
        "payload": get_event_payload(
            event_source_monitor_id=sample_monitor.id, event_name="alert_created"
        )
    }

    with pytest.raises(SomeException):
        await reaction_handler.run(message_payload)

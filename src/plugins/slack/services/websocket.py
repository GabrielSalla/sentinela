import logging
import os
import re
import ssl
from typing import Any, Callable, Coroutine

import certifi
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from .. import slack
from .pattern_match import get_message_request

_logger = logging.getLogger("plugin.slack.websocket")

_handler: AsyncSocketModeHandler | None = None


async def app_mention(body: dict[Any, Any]) -> None:
    message = body["event"]["text"]
    context = body["event"]

    channel = context["channel"]
    ts = context["ts"]

    action = get_message_request(message, context)
    if action is None:
        await slack.add_reaction(
            channel=channel,
            ts=ts,
            reaction="x",
        )
        return

    try:
        await action
        await slack.add_reaction(
            channel=channel,
            ts=ts,
            reaction="ballot_box_with_check",
        )
    except Exception as e:
        log_message = (
            f"Error processing message {message!r} from channel {channel!r} ts {ts}: {str(e)}"
        )
        _logger.warning(log_message)

        await slack.add_reaction(
            channel=channel,
            ts=ts,
            reaction="x",
        )
        await slack.send(
            channel=channel,
            thread_ts=ts,
            text=str(e),
        )


async def command(
    ack: Callable[..., Coroutine[None, None, None]],
    body: dict[Any, Any],
    say: Callable[..., Coroutine[None, None, None]],
) -> None:
    await ack()

    message = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    thread_ts = body["message"]["ts"]

    action = get_message_request(message, {})
    if action is not None:
        try:
            await action
        except Exception as e:
            log_message = (
                f"Error processing message {message!r} from channel {channel!r} "
                f"thread_ts {thread_ts}: {str(e)}"
            )
            _logger.warning(log_message)

            await slack.send(
                channel=channel,
                thread_ts=thread_ts,
                text=str(e),
            )


async def init(controller_enabled: bool, executor_enabled: bool) -> None:  # pragma: no cover
    global _handler

    slack_websocket_enabled = os.environ.get("SLACK_WEBSOCKET_ENABLED", "false") == "true"

    if not (controller_enabled and slack_websocket_enabled):
        _handler = None
        return

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    client = AsyncWebClient(token=os.environ["SLACK_APP_TOKEN"], ssl=ssl_context)

    try:
        await client.auth_test()
    except SlackApiError as e:
        response_data = e.response.data
        if response_data["error"] == "invalid_auth":
            _logger.error("Invalid Slack application token. Slack websocket won't be enabled")
            return

    app = AsyncApp(client=client)
    app.event("app_mention")(app_mention)
    app.action(re.compile(r"sentinela_.*"))(command)

    _handler = AsyncSocketModeHandler(app, app_token=os.environ["SLACK_APP_TOKEN"])
    # Clear the environment variable
    del os.environ["SLACK_APP_TOKEN"]

    _logger.info("Starting Slack websocket")

    await _handler.connect_async()


async def stop(controller_enabled: bool, executor_enabled: bool) -> None:  # pragma: no cover
    global _handler

    if _handler is not None:
        _logger.info("Stopping Slack websocket")
        await _handler.close_async()

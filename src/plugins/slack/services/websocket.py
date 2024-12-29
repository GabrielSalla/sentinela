import logging
import os
import re
import ssl

import certifi
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from .. import slack
from .pattern_match import get_message_request

_logger = logging.getLogger("plugin.slack.websocket")

_handler: AsyncSocketModeHandler | None


async def app_mention(body):
    message = body["event"]["text"]
    context = body["event"]

    action = get_message_request(message, context)
    if action is None:
        await slack.add_reaction(
            channel=context["channel"],
            ts=context["ts"],
            reaction="x",
        )
        return

    try:
        await action
        await slack.add_reaction(
            channel=context["channel"],
            ts=context["ts"],
            reaction="ballot_box_with_check",
        )
    except Exception as e:
        await slack.add_reaction(
            channel=context["channel"],
            ts=context["ts"],
            reaction="x",
        )
        await slack.send(
            channel=context["channel"],
            thread_ts=context["ts"],
            text=str(e),
        )


async def command(ack, body, say):
    await ack()

    message = body["actions"][0]["value"]

    action = get_message_request(message, {})
    if action is not None:
        await action


async def init(controller_enabled: bool, executor_enabled: bool):  # pragma: no cover
    global _handler

    if not controller_enabled:
        _handler = None
        return

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    client = AsyncWebClient(token=os.environ["SLACK_APP_TOKEN"], ssl=ssl_context)

    app = AsyncApp(client=client)
    app.event("app_mention")(app_mention)
    app.action(re.compile(r"sentinela_.*"))(command)

    _handler = AsyncSocketModeHandler(app, app_token=os.environ["SLACK_APP_TOKEN"])

    _logger.info("Starting Slack websocket")

    await _handler.connect_async()


async def stop():  # pragma: no cover
    global _handler

    if _handler is not None:
        _logger.info("Stopping Slack websocket")
        await _handler.close_async()

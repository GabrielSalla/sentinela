import logging
import time

from aiohttp import web
from aiohttp.web_request import Request
from slack_sdk.web.async_client import AsyncWebClient

import src.services.slack.slack as slack
import src.services.slack.websocket as slack_websocket

_logger = logging.getLogger("slack_mock")

_runner: web.AppRunner

base_routes = web.RouteTableDef()


error: str | None = None
response_ts: str | None = None


@base_routes.post("/chat.postMessage")
@base_routes.post("/chat.update")
async def post_or_update_message(request: Request):
    """Mock the post or update message requests"""
    if error is not None:
        return web.json_response({"ok": False, "error": error})

    request_data = await request.json()

    ts = request_data.get("ts") or response_ts or str(time.time())

    message = {
        "user": "U1234567890",
        "type": "message",
        "ts": ts,
        "bot_id": "B1234567890",
        "app_id": "A1234567890",
        "text": request_data.get("text", ""),
        "team": "T1234567890",
        "bot_profile": {},
    }
    if request_data.get("attachments") is not None:
        message["attachments"] = request_data["attachments"]
    if request_data.get("thread_ts") is not None:
        message["thread_ts"] = request_data["thread_ts"]

    return web.json_response(
        {
            "ok": True,
            "channel": request_data["channel"],
            "ts": ts,
            "message": message,
        }
    )


@base_routes.post("/chat.delete")
async def delete_message(request: Request):
    """Mock the delete message requests"""
    if error is not None:
        return web.json_response({"ok": False, "error": error})

    request_data = request.query

    return web.json_response(
        {
            "ok": True,
            "channel": request_data["channel"],
            "ts": request_data.get("ts", ""),
        }
    )


@base_routes.post("/reactions.add")
async def add_reaction(request: Request):
    """Mock the add reaction requests"""
    if error is not None:
        return web.json_response({"ok": False, "error": error})

    return web.json_response({"ok": True})


async def init(monkeypatch):
    """Init the Slack mock server, while also disabling the websocket"""
    global _runner

    port = 8080

    monkeypatch.setattr(
        slack,
        "client",
        AsyncWebClient(token="xoxb-***", base_url=f"http://localhost:{port}/"),
    )

    async def do_nothing(): ...

    monkeypatch.setattr(slack_websocket, "init", do_nothing)
    monkeypatch.setattr(slack_websocket, "close", do_nothing)

    app = web.Application()
    app.add_routes(base_routes)

    _runner = web.AppRunner(app)
    await _runner.setup()

    site = web.TCPSite(_runner, port=port)
    await site.start()


async def stop():
    """Stop the Slack mock server"""
    global _runner
    await _runner.cleanup()

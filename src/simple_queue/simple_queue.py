import asyncio
from time import monotonic
from typing import Any
from uuid import uuid4

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

PORT = 5000
WAIT_MESSAGE_TIME = 2.0
VISIBILITY_TIME = 15.0

_queue: asyncio.Queue[dict[str, Any]]
_in_flight: dict[str, dict[str, Any]]


def _requeue_expired_messages() -> None:
    """Make messages with expired visibility leases available again."""
    current_time = monotonic()
    expired_ids = [
        message_id
        for message_id, message in _in_flight.items()
        if message["visible_at"] <= current_time
    ]

    for message_id in expired_ids:
        message = _in_flight.pop(message_id)
        _queue.put_nowait({**message["message"], "id": str(uuid4())})


def _next_expiration() -> float | None:
    """Return earliest visibility expiration among in-flight messages."""
    if not _in_flight:
        return None
    return min(float(message["visible_at"]) for message in _in_flight.values())


async def _get_next_message() -> dict[str, Any] | None:
    """Wait for one available message, requeueing expired messages while waiting."""
    _requeue_expired_messages()
    try:
        return _queue.get_nowait()
    except asyncio.QueueEmpty:
        pass

    if WAIT_MESSAGE_TIME == 0:
        return None

    deadline = monotonic() + WAIT_MESSAGE_TIME

    while True:
        _requeue_expired_messages()
        remaining = deadline - monotonic()
        if remaining <= 0:
            return None

        expiration = _next_expiration()
        if expiration is not None:
            remaining = min(remaining, max(expiration - monotonic(), 0))

        try:
            return await asyncio.wait_for(_queue.get(), timeout=remaining)
        except asyncio.TimeoutError:
            if monotonic() >= deadline:
                return None


async def _request_json(request: Request) -> dict[str, Any] | None:
    """Parse request JSON, returning None for invalid or non-object bodies."""
    try:
        body = await request.json()
    except (TypeError, ValueError):
        return None
    return body if isinstance(body, dict) else None


async def send_message(request: Request) -> Response:
    """Add message to queue."""
    body = await _request_json(request)
    if not isinstance(body, dict) or not isinstance(body.get("type"), str):
        return web.json_response({"error": "'type' must be a string"}, status=400)
    if not isinstance(body.get("payload"), dict):
        return web.json_response({"error": "'payload' must be an object"}, status=400)

    message_id = str(uuid4())
    message = {
        "id": message_id,
        "content": {"type": body["type"], "payload": body["payload"]},
    }
    await _queue.put(message)
    return web.json_response({"id": message_id}, status=201)


async def get_message(request: Request) -> Response:
    """Return one message or 204 when no message arrives before timeout."""
    message = await _get_next_message()
    if message is None:
        return web.Response(status=204)

    _in_flight[message["id"]] = {
        "message": message,
        "visible_at": monotonic() + VISIBILITY_TIME,
    }
    return web.json_response(message)


async def change_visibility(request: Request) -> Response:
    """Extend visibility lease for an in-flight message."""
    _requeue_expired_messages()
    message_id = request.match_info["message_id"]
    message = _in_flight.get(message_id)
    if message is None:
        return web.json_response({"error": "Message not found"}, status=404)

    message["visible_at"] = monotonic() + VISIBILITY_TIME
    return web.Response(status=204)


async def delete_message(request: Request) -> Response:
    """Delete an in-flight message after successful processing."""
    _requeue_expired_messages()
    message_id = request.match_info["message_id"]
    if _in_flight.pop(message_id, None) is None:
        return web.json_response({"error": "Message not found"}, status=404)
    return web.Response(status=204)


async def status(request: Request) -> Response:
    """Report that the queue service is ready to accept requests."""
    return web.Response()


def create_app() -> web.Application:
    """Create HTTP queue application."""
    global _queue
    global _in_flight

    _queue = asyncio.Queue()
    _in_flight = {}
    app = web.Application()
    app.add_routes(
        [
            web.get("/status", status),
            web.post("/messages", send_message),
            web.get("/messages", get_message),
            web.post("/messages/{message_id}/visibility", change_visibility),
            web.delete("/messages/{message_id}", delete_message),
        ]
    )
    return app


def main() -> None:
    """Start queue HTTP server."""
    web.run_app(create_app(), host="0.0.0.0", port=PORT)


if __name__ == "__main__":  # pragma: no cover
    main()

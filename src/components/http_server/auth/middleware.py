from collections.abc import Awaitable, Callable

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse

from components.http_server.auth import service as auth_service


def _is_public_path(method: str, path: str) -> bool:
    """Return whether the request path is public and skips authentication"""
    if path in ("/", "/status", "/status/", "/metrics", "/metrics/"):
        return True
    if method == "POST" and path.rstrip("/") in (
        "/auth/login",
        "/auth/logout",
        "/auth/set-password",
    ):
        return True
    if method == "GET" and path.rstrip("/") == "/auth/invite/validate":
        return True
    if method == "GET" and path in ("/dashboard/login.html", "/dashboard/set-password.html"):
        return True
    if method == "GET" and (
        path.startswith("/dashboard/css/") or path in ("/dashboard/js/auth.js",)
    ):
        return True
    return False


def _is_html_path(request: Request) -> bool:
    """Return whether the request expects an HTML page instead of JSON"""
    if request.path.startswith("/dashboard"):
        return True
    return "text/html" in request.headers.get("Accept", "")


def _is_password_change_allowed(method: str, path: str) -> bool:
    """Return whether the path is allowed while the user must change the password"""
    if (method, path.rstrip("/")) in (
        ("GET", "/auth/me"),
        ("POST", "/auth/logout"),
        ("POST", "/auth/change-password"),
        ("POST", "/auth/set-password"),
        ("GET", "/dashboard/change-password.html"),
    ):
        return True
    return _is_public_path(method, path)


@web.middleware
async def auth_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """Require a valid session for protected routes"""
    if _is_public_path(request.method, request.path):
        return await handler(request)

    user = await auth_service.get_request_user(request)
    if user is None:
        # If is fetching a HTML file, redirect to it
        if _is_html_path(request):
            raise web.HTTPFound("/dashboard/login.html")
        return web.json_response({"status": "unauthorized"}, status=401)

    # Check if the user is using routes or pages that require password change
    request[auth_service.USER_REQUEST_KEY] = user
    required_change_password_navigation = all(
        [
            user.require_change_password,
            not _is_password_change_allowed(request.method, request.path),
        ]
    )
    if required_change_password_navigation:
        if _is_html_path(request):
            raise web.HTTPFound("/dashboard/change-password.html")
        return web.json_response({"status": "password_change_required"}, status=403)

    return await handler(request)

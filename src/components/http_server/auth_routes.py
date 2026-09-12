import logging
from typing import Literal

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from pydantic import BaseModel
from yarl import URL

from components.http_server.auth import service
from components.http_server.auth.service import (
    COOKIE_NAME,
    CannotDisableSelfError,
    ExpiredInviteError,
    InvalidInviteError,
    InvalidPasswordError,
    InvalidUsernameError,
    UserExistsError,
    UserNotFoundError,
    WeakPasswordError,
)
from configs import configs
from models import User, UserRole

_logger = logging.getLogger("auth_routes")

auth_routes = web.RouteTableDef()
base_route = "/auth"


class _LoginPayload(BaseModel):
    username: str
    password: str


class _CreateUserPayload(BaseModel):
    username: str
    role: Literal["admin", "user"] = "user"


class _SetPasswordPayload(BaseModel):
    token: str
    password: str


class _ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str


def _set_session_cookie(response: Response, raw_token: str) -> None:
    """Set the session cookie on the response"""
    response.set_cookie(
        COOKIE_NAME,
        raw_token,
        max_age=configs.http_server.auth.session_expire_hours * 3600,
        path="/",
        httponly=True,
        samesite="Lax",
        secure=configs.http_server.auth.cookie_secure,
    )


def _user_response(user: User) -> dict[str, object]:
    """Build the public user payload"""
    return {
        "username": user.username,
        "role": user.role.value,
        "require_change_password": user.require_change_password,
        "is_active": user.is_active,
    }


@auth_routes.post(base_route + "/login")
@auth_routes.post(base_route + "/login/")
async def login(request: Request) -> Response:
    """Route to login with username and password"""
    payload = _LoginPayload(**await request.json())

    user = await service.authenticate(payload.username, payload.password)
    if user is None:
        return web.json_response({"status": "invalid_credentials"}, status=401)

    raw_token = service.create_session(user)
    response = web.json_response({"status": "ok", **_user_response(user)})
    _set_session_cookie(response, raw_token)
    return response


@auth_routes.post(base_route + "/logout")
@auth_routes.post(base_route + "/logout/")
async def logout(request: Request) -> Response:
    """Route to logout, clearing the session cookie"""
    response = web.json_response({"status": "ok"})
    response.del_cookie(
        COOKIE_NAME,
        path="/",
        samesite="Lax",
        httponly=True,
        secure=configs.http_server.auth.cookie_secure,
    )
    return response


@auth_routes.get(base_route + "/me")
@auth_routes.get(base_route + "/me/")
async def me(request: Request) -> Response:
    """Route to get the current user"""
    user: User = request[service.USER_REQUEST_KEY]
    return web.json_response({"status": "ok", **_user_response(user)})


@auth_routes.get(base_route + "/users")
@auth_routes.get(base_route + "/users/")
async def list_users(request: Request) -> Response:
    """Route to list all users, admin only"""
    user: User = request[service.USER_REQUEST_KEY]
    if user.role != UserRole.admin:
        return web.json_response({"status": "forbidden"}, status=403)

    users = await User.get_all(order_by=[User.id])
    response = [
        {
            "id": listed.id,
            "username": listed.username,
            "role": listed.role.value,
            "has_password": listed.password_hash is not None,
            "require_change_password": listed.require_change_password,
            "is_active": listed.is_active,
        }
        for listed in users
    ]
    return web.json_response(response)


@auth_routes.post(base_route + "/users")
@auth_routes.post(base_route + "/users/")
async def create_user(request: Request) -> Response:
    """Route to create a user with an invite token, admin only"""
    user: User = request[service.USER_REQUEST_KEY]
    if user.role != UserRole.admin:
        return web.json_response({"status": "forbidden"}, status=403)

    payload = _CreateUserPayload(**await request.json())

    try:
        new_user, raw_token = await service.create_user_with_invite(
            payload.username, UserRole(payload.role)
        )
    except InvalidUsernameError as e:
        return web.json_response({"status": "error", "message": str(e)}, status=400)
    except UserExistsError as e:
        return web.json_response({"status": "user_exists", "message": str(e)}, status=409)

    return web.json_response(
        {
            "status": "user_created",
            "id": new_user.id,
            "username": new_user.username,
            "role": new_user.role.value,
            "invite_url": str(URL("/dashboard/set-password.html").with_query({"token": raw_token})),
        },
        status=201,
    )


@auth_routes.post(base_route + "/users/{username}/disable")
@auth_routes.post(base_route + "/users/{username}/disable/")
async def disable_user(request: Request) -> Response:
    """Route to disable a user, admin only. Admins cannot disable themselves"""
    user: User = request[service.USER_REQUEST_KEY]
    if user.role != UserRole.admin:
        return web.json_response({"status": "forbidden"}, status=403)

    try:
        target = await service.disable_user(user, request.match_info["username"])
    except CannotDisableSelfError as e:
        return web.json_response({"status": "cannot_disable_self", "message": str(e)}, status=400)
    except UserNotFoundError:
        return web.json_response({"status": "user_not_found"}, status=404)

    return web.json_response({"status": "user_disabled", **_user_response(target)})


@auth_routes.post(base_route + "/users/{username}/enable")
@auth_routes.post(base_route + "/users/{username}/enable/")
async def enable_user(request: Request) -> Response:
    """Route to enable a disabled user, admin only"""
    user: User = request[service.USER_REQUEST_KEY]
    if user.role != UserRole.admin:
        return web.json_response({"status": "forbidden"}, status=403)

    try:
        target = await service.enable_user(request.match_info["username"])
    except UserNotFoundError:
        return web.json_response({"status": "user_not_found"}, status=404)

    return web.json_response({"status": "user_enabled", **_user_response(target)})


@auth_routes.get(base_route + "/invite/validate")
@auth_routes.get(base_route + "/invite/validate/")
async def validate_invite(request: Request) -> Response:
    """Route to check if an invite token is valid"""
    raw_token = request.query.get("token", "")
    if not raw_token:
        return web.json_response({"status": "invalid_token"}, status=404)

    try:
        await service.validate_invite(raw_token)
    except InvalidInviteError:
        return web.json_response({"status": "invalid_token"}, status=404)
    except ExpiredInviteError:
        return web.json_response({"status": "expired_token"}, status=410)

    return web.json_response({"status": "valid"})


@auth_routes.post(base_route + "/set-password")
@auth_routes.post(base_route + "/set-password/")
async def set_password(request: Request) -> Response:
    """Route to set the password with an invite token"""
    payload = _SetPasswordPayload(**await request.json())

    try:
        user = await service.consume_invite(payload.token, payload.password)
    except InvalidInviteError:
        return web.json_response({"status": "invalid_token"}, status=404)
    except ExpiredInviteError:
        return web.json_response({"status": "expired_token"}, status=410)
    except WeakPasswordError as e:
        return web.json_response(
            {"status": "error", "message": "Weak password", "errors": e.errors}, status=400
        )

    raw_token = service.create_session(user)
    response = web.json_response({"status": "password_set"})
    _set_session_cookie(response, raw_token)
    return response


@auth_routes.post(base_route + "/change-password")
@auth_routes.post(base_route + "/change-password/")
async def change_password(request: Request) -> Response:
    """Route to change the current user's password"""
    user: User = request[service.USER_REQUEST_KEY]

    payload = _ChangePasswordPayload(**await request.json())

    try:
        await service.change_password(user, payload.current_password, payload.new_password)
    except InvalidPasswordError:
        return web.json_response({"status": "invalid_credentials"}, status=401)
    except WeakPasswordError as e:
        return web.json_response(
            {"status": "error", "message": "Weak password", "errors": e.errors}, status=400
        )

    response = web.json_response({"status": "password_changed"})
    _set_session_cookie(response, service.create_session(user))
    return response

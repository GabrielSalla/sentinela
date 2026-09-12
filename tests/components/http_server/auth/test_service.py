import os
from types import SimpleNamespace
from typing import cast

import pytest
import pytest_asyncio
from aiohttp.web_request import Request
from sqlalchemy import select

import components.http_server as http_server
from components.http_server.auth import service
from components.http_server.auth.password import hash_password
from components.http_server.auth.service import (
    CannotDisableSelfError,
    ExpiredInviteError,
    InvalidInviteError,
    InvalidPasswordError,
    InvalidUsernameError,
    UserExistsError,
    UserNotFoundError,
    WeakPasswordError,
)
from components.http_server.auth.tokens import create_token
from internal_database import get_session
from models import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

STRONG_PASSWORD = "StrongPass123!"


def _request_with_cookie(token: str | None) -> Request:
    """Build a request stub with the session cookie"""
    cookies = {} if token is None else {service.COOKIE_NAME: token}
    return cast(Request, SimpleNamespace(cookies=cookies))


async def _create_user(
    username: str, password: str = STRONG_PASSWORD, role: UserRole = UserRole.user
) -> User:
    """Create a user with a known password"""
    password_hash, salt = hash_password(password)
    return await User.create(
        username=username,
        password_hash=password_hash,
        password_salt=salt,
        role=role,
        require_change_password=False,
    )


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    await http_server.init(controller_enabled=True)
    yield
    await http_server.wait_stop()


@pytest_asyncio.fixture(loop_scope="session", scope="function", autouse=True)
async def clean_test_users():
    """Delete users created during the test"""
    before = {user.id for user in await User.get_all()}
    yield
    for user in await User.get_all():
        if user.id not in before:
            await _delete_user(user.username)


async def _delete_user(username: str) -> None:
    """Delete the user with the username, if it exists"""
    async with get_session() as db_session:
        result = await db_session.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        if user is not None:
            await db_session.delete(user)


async def test_ensure_default_admin_empty(monkeypatch):
    """'ensure_default_admin' should create the default admin when no users exist"""
    monkeypatch.setattr(service, "DEFAULT_ADMIN_USERNAME", "bootstrap_admin")

    admin = await service.ensure_default_admin()

    assert admin is not None
    assert admin.username == "bootstrap_admin"
    assert admin.role == UserRole.admin
    assert admin.require_change_password is False

    same_admin = await service.ensure_default_admin()
    assert same_admin is not None
    assert same_admin.id == admin.id


async def test_get_secret_env(monkeypatch):
    """'get_secret' should read and clear the environment variable"""
    monkeypatch.setenv("SENTINELA_AUTH_SECRET", "env-secret")
    service.get_secret.cache_clear()

    assert service.get_secret() == "env-secret"
    assert "SENTINELA_AUTH_SECRET" not in os.environ
    assert service.get_secret() == "env-secret"


async def test_get_secret_ephemeral(monkeypatch):
    """'get_secret' should generate an ephemeral secret when none is configured"""
    monkeypatch.delenv("SENTINELA_AUTH_SECRET", raising=False)
    service.get_secret.cache_clear()

    assert service.get_secret() == service.get_secret()


async def test_authenticate():
    """'authenticate' should validate credentials"""
    await _create_user("test_authenticate")

    user = await service.authenticate("test_authenticate", STRONG_PASSWORD)
    assert user is not None
    assert user.username == "test_authenticate"

    assert await service.authenticate("test_authenticate", "WrongPass123!") is None
    assert await service.authenticate("unknown_user", STRONG_PASSWORD) is None


@pytest.mark.parametrize(
    "username, password",
    [
        ("test_authenticate_fail", "WrongPass123!"),
        ("test_authenticate_fail_not_exist", STRONG_PASSWORD),
    ],
)
async def test_authenticate_fail(username, password):
    """'authenticate' should validate incorrect credentials"""
    await _create_user("test_authenticate_fail")

    assert await service.authenticate(username, password) is None


async def test_authenticate_invited_no_password():
    """'authenticate' should reject invited users without a password"""
    await service.create_user_with_invite("test_authenticate_invited_no_password")

    assert await service.authenticate("invited_user", STRONG_PASSWORD) is None


async def test_create_session_get_request_user():
    """'create_session' and 'get_request_user' should roundtrip the user"""
    user = await _create_user("test_create_session_get_request_user")

    raw_token = service.create_session(user)
    found = await service.get_request_user(_request_with_cookie(raw_token))

    assert found is not None
    assert found.id == user.id


async def test_get_request_user_no_cookie():
    """'get_request_user' should return None without a cookie"""
    result = await service.get_request_user(_request_with_cookie(None))
    assert result is None


async def test_get_request_user_invalid_token():
    """'get_request_user' should return None for an unknown token"""
    result = await service.get_request_user(_request_with_cookie("unknown"))
    assert result is None


async def test_get_request_user_expired():
    """'get_request_user' should return None for expired tokens"""
    user = await _create_user("test_get_request_user_expired")
    raw_token = create_token(
        {"sub": str(user.id), "type": "session", "v": user.token_version},
        service.get_secret(),
        expire_hours=-1,
    )

    result = await service.get_request_user(_request_with_cookie(raw_token))
    assert result is None


async def test_get_request_user_wrong_type():
    """'get_request_user' should reject invite tokens"""
    _, invite = await service.create_user_with_invite("test_get_request_user_wrong_type")

    result = await service.get_request_user(_request_with_cookie(invite))
    assert result is None


async def test_get_request_user_invalid_sub():
    """'get_request_user' should return None for tokens with an invalid subject"""
    raw_token = create_token(
        {"sub": "not-an-id", "type": "session", "v": 0},
        service.get_secret(),
        expire_hours=1,
    )

    result = await service.get_request_user(_request_with_cookie(raw_token))
    assert result is None


async def test_get_request_user_deleted_user():
    """'get_request_user' should return None when the user no longer exists"""
    user = await _create_user("test_get_request_user_deleted_user")
    raw_token = service.create_session(user)

    await _delete_user("test_get_request_user_deleted_user")

    result = await service.get_request_user(_request_with_cookie(raw_token))
    assert result is None


async def test_get_request_user_revoked():
    """'get_request_user' should return None after the token version changes"""
    user = await _create_user("test_get_request_user_revoked")
    raw_token = service.create_session(user)

    user.token_version += 1
    await user.save()

    result = await service.get_request_user(_request_with_cookie(raw_token))
    assert result is None


async def test_create_user_with_invite():
    """'create_user_with_invite' should create a password-less user with a token"""
    user, raw_token = await service.create_user_with_invite(
        "test_create_user_with_invite", UserRole.admin
    )

    assert user.username == "test_create_user_with_invite"
    assert user.password_hash is None
    assert user.role == UserRole.admin
    assert user.require_change_password is True
    assert user.is_active is True
    assert raw_token != ""

    found = await service.validate_invite(raw_token)
    assert found.id == user.id


async def test_create_user_with_invite_default_role():
    """'create_user_with_invite' should default to the user role"""
    user, _ = await service.create_user_with_invite("test_create_user_with_invite_default_role")

    assert user.role == UserRole.user


async def test_create_user_with_invite_invalid_username():
    """'create_user_with_invite' should reject invalid usernames"""
    with pytest.raises(InvalidUsernameError):
        await service.create_user_with_invite("ab")


async def test_create_user_with_invite_duplicate():
    """'create_user_with_invite' should reject duplicate usernames"""
    await _create_user("test_create_user_with_invite_duplicate")

    with pytest.raises(UserExistsError):
        await service.create_user_with_invite("test_create_user_with_invite_duplicate")


async def test_validate_invite_invalid():
    """'validate_invite' should reject unknown tokens"""
    with pytest.raises(InvalidInviteError):
        await service.validate_invite("unknown")


async def test_validate_invite_wrong_type():
    """'validate_invite' should reject session tokens"""
    user = await _create_user("test_validate_invite_wrong_type")
    raw_token = service.create_session(user)

    with pytest.raises(InvalidInviteError):
        await service.validate_invite(raw_token)


async def test_validate_invite_invalid_sub():
    """'validate_invite' should reject tokens with an invalid subject"""
    raw_token = create_token({"type": "invite", "v": 0}, service.get_secret(), expire_hours=1)

    with pytest.raises(InvalidInviteError):
        await service.validate_invite(raw_token)


async def test_validate_invite_expired():
    """'validate_invite' should reject expired tokens"""
    user, _ = await service.create_user_with_invite("test_validate_invite_expired")
    raw_token = create_token(
        {"sub": str(user.id), "type": "invite", "v": user.token_version},
        service.get_secret(),
        expire_hours=-1,
    )

    with pytest.raises(ExpiredInviteError):
        await service.validate_invite(raw_token)


async def test_validate_invite_revoked():
    """'validate_invite' should reject tokens after the version changes"""
    user, raw_token = await service.create_user_with_invite("test_validate_invite_revoked")
    user.token_version += 1
    await user.save()

    with pytest.raises(InvalidInviteError):
        await service.validate_invite(raw_token)


async def test_consume_invite_weak():
    """'consume_invite' should reject weak passwords"""
    _, raw_token = await service.create_user_with_invite("test_consume_invite_weak")

    with pytest.raises(WeakPasswordError):
        await service.consume_invite(raw_token, "weak")


async def test_consume_invite():
    """'consume_invite' should set the password and invalidate the token"""
    _, raw_token = await service.create_user_with_invite("test_consume_invite")

    user = await service.consume_invite(raw_token, "NewStrong123!")

    assert user.password_hash is not None
    assert await service.authenticate("test_consume_invite", "NewStrong123!") is not None

    with pytest.raises(InvalidInviteError):
        await service.validate_invite(raw_token)


async def test_disable_user():
    """'disable_user' should deactivate the user and revoke sessions"""
    admin = await _create_user("test_disable_user_admin", role=UserRole.admin)
    user = await _create_user("test_disable_user")
    old_token = service.create_session(user)

    disabled = await service.disable_user(admin, "test_disable_user")

    assert disabled.is_active is False
    assert await service.authenticate("test_disable_user", STRONG_PASSWORD) is None
    assert await service.get_request_user(_request_with_cookie(old_token)) is None


async def test_disable_user_self():
    """'disable_user' should reject admins disabling themselves"""
    admin = await _create_user("test_disable_user_self", role=UserRole.admin)

    with pytest.raises(CannotDisableSelfError):
        await service.disable_user(admin, "test_disable_user_self")


async def test_disable_user_not_found():
    """'disable_user' should raise for unknown users"""
    admin = await _create_user("test_disable_user_not_found_admin", role=UserRole.admin)

    with pytest.raises(UserNotFoundError):
        await service.disable_user(admin, "unknown_user")


async def test_enable_user():
    """'enable_user' should reactivate a disabled user"""
    admin = await _create_user("test_enable_user_admin", role=UserRole.admin)
    await _create_user("test_enable_user")
    await service.disable_user(admin, "test_enable_user")

    enabled = await service.enable_user("test_enable_user")

    assert enabled.is_active is True
    assert await service.authenticate("test_enable_user", STRONG_PASSWORD) is not None


async def test_enable_user_not_found():
    """'enable_user' should raise for unknown users"""
    with pytest.raises(UserNotFoundError):
        await service.enable_user("unknown_user")


async def test_change_password():
    """'change_password' should change the password and revoke sessions"""
    user = await _create_user("test_change_password")
    user.require_change_password = True
    await user.save()
    old_token = service.create_session(user)

    await service.change_password(user, STRONG_PASSWORD, "NewStrong123!")

    assert user.require_change_password is False
    assert await service.authenticate("test_change_password", "NewStrong123!") is not None
    assert await service.get_request_user(_request_with_cookie(old_token)) is None


async def test_change_password_invalid_current():
    """'change_password' should reject a wrong current password"""
    user = await _create_user("test_change_password_invalid_current")

    with pytest.raises(InvalidPasswordError):
        await service.change_password(user, "WrongPass123!", "NewStrong123!")


async def test_change_password_weak():
    """'change_password' should reject a weak new password"""
    user = await _create_user("test_change_password_weak")

    with pytest.raises(WeakPasswordError):
        await service.change_password(user, STRONG_PASSWORD, "weak")

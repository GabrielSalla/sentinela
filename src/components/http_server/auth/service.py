import logging
import os
import re
import secrets
from functools import cache

from aiohttp import web
from aiohttp.web_request import Request
from sqlalchemy.exc import IntegrityError

from configs import configs
from models import User, UserRole

from .password import (
    USERNAME_PATTERN,
    hash_password,
    validate_password_strength,
    verify_dummy,
    verify_password,
)
from .tokens import ExpiredTokenError, InvalidTokenError, create_token, decode_token

_logger = logging.getLogger("auth_service")

COOKIE_NAME = "sentinela_session"
USER_REQUEST_KEY: web.RequestKey[User] = web.RequestKey("user", User)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"

_USERNAME_REGEX = re.compile(USERNAME_PATTERN)


class InvalidUsernameError(ValueError):
    pass


class UserExistsError(ValueError):
    pass


class InvalidInviteError(ValueError):
    pass


class ExpiredInviteError(ValueError):
    pass


class InvalidPasswordError(ValueError):
    pass


class UserNotFoundError(ValueError):
    pass


class CannotDisableSelfError(ValueError):
    pass


class WeakPasswordError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


async def ensure_default_admin() -> User | None:
    """Create the default 'admin' user if missing, returning the admin user"""
    admin = await User.get(User.username == DEFAULT_ADMIN_USERNAME)
    if admin is not None:
        return admin

    password_hash, salt = hash_password(DEFAULT_ADMIN_PASSWORD)
    try:
        admin = await User.create(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=password_hash,
            password_salt=salt,
            role=UserRole.admin,
            require_change_password=False,
        )
        _logger.info("Created default admin user")
    except IntegrityError:
        return await User.get(User.username == DEFAULT_ADMIN_USERNAME)

    return admin


@cache
def get_secret() -> str:
    """Return the JWT signing secret, generating an ephemeral one if none is configured"""
    secret = os.environ.pop("SENTINELA_AUTH_SECRET", None)
    if secret is not None:
        return secret

    _logger.warning(
        "No auth secret configured, using an ephemeral one (sessions invalidate on restart)"
    )
    return secrets.token_hex(32)


async def authenticate(username: str, password: str) -> User | None:
    """Return the user if the credentials are valid, otherwise return 'None'"""
    user = await User.get(User.username == username)
    if user is None:
        # Run a password verification that always fails, to equalize login timing
        verify_dummy(password)
        return None
    if not verify_password(password, user.password_hash, user.password_salt):
        return None
    if not user.is_active:
        return None
    return user


def create_session(user: User) -> str:
    """Create a signed session token for the user"""
    return create_token(
        {"sub": str(user.id), "type": "session", "v": user.token_version},
        get_secret(),
        configs.http_server.auth.session_expire_hours,
    )


async def get_request_user(request: Request) -> User | None:
    """Return the session cookie user, or 'None' if invalid, expired or disabled"""
    raw_token = request.cookies.get(COOKIE_NAME)
    if not raw_token:
        return None

    try:
        claims = decode_token(raw_token, get_secret())
    except (ExpiredTokenError, InvalidTokenError):
        return None

    if claims.get("type") != "session":
        return None

    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError):
        return None

    user = await User.get_by_id(user_id)
    if user is None or user.token_version != claims.get("v"):
        return None
    if not user.is_active:
        return None
    return user


async def create_user_with_invite(
    username: str, role: UserRole = UserRole.user
) -> tuple[User, str]:
    """Create a password-less user with an invite token, returning the user and raw token"""
    if not _USERNAME_REGEX.fullmatch(username):
        raise InvalidUsernameError(
            "Username must be 3-64 characters long and contain only letters, numbers, '_', '.', '-'"
        )

    existing = await User.get(User.username == username)
    if existing is not None:
        raise UserExistsError(f"User {username!r} already exists")

    user = await User.create(
        username=username,
        password_hash=None,
        password_salt=None,
        role=role,
        require_change_password=True,
    )
    raw_token = create_token(
        {"sub": str(user.id), "type": "invite", "v": user.token_version},
        get_secret(),
        configs.http_server.auth.invite_expire_hours,
    )
    return user, raw_token


async def validate_invite(raw_token: str) -> User:
    """Return the user for a valid invite token, raising if invalid or expired"""
    try:
        claims = decode_token(raw_token, get_secret())
    except ExpiredTokenError as e:
        raise ExpiredInviteError("Invite token expired") from e
    except InvalidTokenError as e:
        raise InvalidInviteError("Invalid invite token") from e

    if claims.get("type") != "invite":
        raise InvalidInviteError("Invalid invite token")

    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError) as e:
        raise InvalidInviteError("Invalid invite token") from e

    user = await User.get_by_id(user_id)
    if user is None or user.token_version != claims.get("v"):
        raise InvalidInviteError("Invalid invite token")
    return user


async def consume_invite(raw_token: str, password: str) -> User:
    """Set the password for an invite token, invalidating the token"""
    user = await validate_invite(raw_token)

    errors = validate_password_strength(user.username, password)
    if errors:
        raise WeakPasswordError(errors)

    password_hash, salt = hash_password(password)
    user.password_hash = password_hash
    user.password_salt = salt
    user.require_change_password = False
    user.token_version += 1
    await user.save()
    return user


async def disable_user(admin: User, username: str) -> User:
    """Disable a user, revoking all existing sessions. Admins cannot disable themselves"""
    if username == admin.username:
        raise CannotDisableSelfError("Admins cannot disable themselves")

    user = await User.get(User.username == username)
    if user is None:
        raise UserNotFoundError(f"User {username!r} not found")

    user.is_active = False
    user.token_version += 1
    await user.save()
    return user


async def enable_user(username: str) -> User:
    """Enable a disabled user"""
    user = await User.get(User.username == username)
    if user is None:
        raise UserNotFoundError(f"User {username!r} not found")

    user.is_active = True
    await user.save()
    return user


async def change_password(user: User, current_password: str, new_password: str) -> User:
    """Change the user's password, revoking all existing sessions"""
    if not verify_password(current_password, user.password_hash, user.password_salt):
        raise InvalidPasswordError("Invalid current password")

    errors = validate_password_strength(user.username, new_password)
    if errors:
        raise WeakPasswordError(errors)

    password_hash, salt = hash_password(new_password)
    user.password_hash = password_hash
    user.password_salt = salt
    user.require_change_password = False
    user.token_version += 1
    await user.save()
    return user

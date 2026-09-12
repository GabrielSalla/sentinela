from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

ALGORITHM = "HS256"


class ExpiredTokenError(ValueError):
    pass


class InvalidTokenError(ValueError):
    pass


def create_token(payload: dict[str, Any], secret: str, expire_hours: float) -> str:
    """Create a signed JWT with the payload and an expiry, returning the raw token"""
    now = datetime.now(tz=timezone.utc)
    claims = {
        **payload,
        "iat": now,
        "exp": now + timedelta(hours=expire_hours),
    }
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> dict[str, Any]:
    """Decode a JWT, raising 'ExpiredTokenError' if expired or 'InvalidTokenError' if invalid"""
    try:
        decoded: dict[str, Any] = jwt.decode(
            token, secret, algorithms=[ALGORITHM], options={"require": ["exp"]}
        )
        return decoded
    except jwt.ExpiredSignatureError as e:
        raise ExpiredTokenError("Token expired") from e
    except jwt.PyJWTError as e:
        raise InvalidTokenError("Invalid token") from e

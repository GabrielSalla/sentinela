import pytest

from components.http_server.auth.tokens import (
    ExpiredTokenError,
    InvalidTokenError,
    create_token,
    decode_token,
)

SECRET = "test-secret-with-at-least-32-bytes!"


def test_create_token_decode():
    """'create_token' should create a token decoded by 'decode_token'"""
    token = create_token({"sub": "1", "type": "session"}, SECRET, expire_hours=1)

    claims = decode_token(token, SECRET)

    assert claims["sub"] == "1"
    assert claims["type"] == "session"
    assert "exp" in claims


def test_decode_token_expired():
    """'decode_token' should raise 'ExpiredTokenError' for expired tokens"""
    token = create_token({"sub": "1"}, SECRET, expire_hours=-1)

    with pytest.raises(ExpiredTokenError):
        decode_token(token, SECRET)


def test_decode_token_invalid():
    """'decode_token' should raise 'InvalidTokenError' for tampered tokens"""
    token = create_token({"sub": "1"}, SECRET, expire_hours=1)

    with pytest.raises(InvalidTokenError):
        decode_token(token + "tampered", SECRET)

    with pytest.raises(InvalidTokenError):
        decode_token(token, "wrong-secret-with-at-least-32-bytes!")

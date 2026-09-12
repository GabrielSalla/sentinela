import pytest

from components.http_server.auth.password import (
    hash_password,
    validate_password_strength,
    verify_dummy,
    verify_password,
)


@pytest.mark.parametrize(
    "candidate,expected_result",
    [("StrongPass123!", True), ("WrongPass123!", False)],
)
def test_verify_password(candidate, expected_result):
    """'verify_password' should accept the correct password and reject a wrong one"""
    password_hash, salt = hash_password("StrongPass123!")

    assert verify_password(candidate, password_hash, salt) is expected_result


def test_verify_dummy():
    """'verify_dummy' should run without errors"""
    verify_dummy("StrongPass123!")


@pytest.mark.parametrize("missing_hash,missing_salt", [(True, False), (False, True)])
def test_verify_password_missing_values(missing_hash, missing_salt):
    """'verify_password' should reject missing hash or salt"""
    password_hash, salt = hash_password("StrongPass123!")
    result = verify_password(
        "StrongPass123!",
        None if missing_hash else password_hash,
        None if missing_salt else salt,
    )
    assert result is False


def test_verify_password_invalid_salt():
    """'verify_password' should reject an invalid salt"""
    password_hash, _ = hash_password("StrongPass123!")

    assert verify_password("StrongPass123!", password_hash, "not-hex") is False


@pytest.mark.parametrize(
    "username,password",
    [("someuser", "StrongPass123!"), ("ab", "XxAb123!xxxx")],
)
def test_validate_password_strength_accepts(username, password):
    """'validate_password_strength' should return no errors for strong passwords"""
    assert validate_password_strength(username, password) == []


@pytest.mark.parametrize(
    "password,expected_error",
    [
        ("Sh0rt!", "password must be at least 12 characters"),
        ("Aa1!" + "x" * 200, "password must be at most 128 characters"),
        ("lowercase123!", "password must contain at least one uppercase letter"),
        ("UPPERCASE123!", "password must contain at least one lowercase letter"),
        ("NoDigitsHere!", "password must contain at least one digit"),
        ("NoSpecial1234", "password must contain at least one special character"),
        ("XxSomeuser123!", "password must not contain the username"),
    ],
)
def test_validate_password_strength_rejects(password, expected_error):
    """'validate_password_strength' should report the violated rule"""
    assert expected_error in validate_password_strength("someuser", password)

from datetime import timedelta

import pytest

import utils.time as time_utils
from models import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_defaults():
    """'User.create' should create a user with default role and flags"""
    user = await User.create(username="test_user")

    assert user.username == "test_user"
    assert user.role == UserRole.user
    assert user.password_hash is None
    assert user.password_salt is None
    assert user.require_change_password is True
    assert user.token_version == 0
    assert user.created_at > time_utils.now() - timedelta(seconds=60)


async def test_is_admin():
    """'User.is_admin' should be True only for the admin role"""
    admin = await User.create(username="test_is_admin_admin", role=UserRole.admin)
    user = await User.create(username="test_is_admin_user", role=UserRole.user)

    assert admin.is_admin is True
    assert user.is_admin is False

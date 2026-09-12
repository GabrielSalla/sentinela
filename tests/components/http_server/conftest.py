import aiohttp
import pytest
import pytest_asyncio

from components.http_server.auth.password import hash_password
from models import User, UserRole

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "StrongAdmin123!pass"
TEST_USER_USERNAME = "plain_user"
TEST_USER_PASSWORD = "StrongUser123!pass"


@pytest.fixture(scope="session")
def admin_credentials() -> tuple[str, str]:
    """Return the test admin username and password"""
    return TEST_ADMIN_USERNAME, TEST_ADMIN_PASSWORD


@pytest_asyncio.fixture(loop_scope="session", scope="module")
async def admin_cookies(admin_credentials):
    """Create or reset a test admin user and login once per module, returning cookies"""
    username, password = admin_credentials
    user = await User.get(User.username == username)
    password_hash, salt = hash_password(password)

    if user is None:
        await User.create(
            username=username,
            password_hash=password_hash,
            password_salt=salt,
            role=UserRole.admin,
            require_change_password=False,
        )
    else:
        user.password_hash = password_hash
        user.password_salt = salt
        user.role = UserRole.admin
        user.require_change_password = False
        user.token_version += 1
        await user.save()

    async with aiohttp.ClientSession() as session:
        payload = {"username": username, "password": password}
        async with session.post("http://localhost:8000/auth/login", json=payload) as response:
            assert response.status == 200
            return {cookie.key: cookie.value for cookie in response.cookies.values()}


@pytest.fixture(scope="session")
def user_credentials() -> tuple[str, str]:
    """Return the test non-admin username and password"""
    return TEST_USER_USERNAME, TEST_USER_PASSWORD


@pytest_asyncio.fixture(loop_scope="session", scope="module")
async def user_cookies(user_credentials):
    """Create or reset a test non-admin user and login once per module, returning cookies"""
    username, password = user_credentials
    user = await User.get(User.username == username)
    password_hash, salt = hash_password(password)

    if user is None:
        await User.create(
            username=username,
            password_hash=password_hash,
            password_salt=salt,
            role=UserRole.user,
            require_change_password=False,
        )
    else:
        user.password_hash = password_hash
        user.password_salt = salt
        user.role = UserRole.user
        user.require_change_password = False
        user.token_version += 1
        await user.save()

    async with aiohttp.ClientSession() as session:
        payload = {"username": username, "password": password}
        async with session.post("http://localhost:8000/auth/login", json=payload) as response:
            assert response.status == 200
            return {cookie.key: cookie.value for cookie in response.cookies.values()}

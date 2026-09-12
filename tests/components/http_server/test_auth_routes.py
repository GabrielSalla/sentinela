import aiohttp
import pytest
import pytest_asyncio

import components.http_server as http_server
from components.http_server.auth import service
from components.http_server.auth.password import hash_password
from components.http_server.auth.tokens import create_token
from configs import configs
from models import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000"

STRONG_PASSWORD = "StrongPass123!"


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    await http_server.init(controller_enabled=True)
    yield
    await http_server.wait_stop()


async def test_login(admin_cookies, admin_credentials):
    """The 'login' route should set a session cookie on valid credentials"""
    username, password = admin_credentials

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": username, "password": password},
        ) as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {
                "status": "ok",
                "username": username,
                "role": "admin",
                "require_change_password": False,
                "is_active": True,
            }
            assert service.COOKIE_NAME in {c.key for c in response.cookies.values()}


@pytest.mark.parametrize(
    "username,password",
    [("admin", "WrongPass123!"), ("unknown", STRONG_PASSWORD)],
)
async def test_login_invalid_credentials(username, password):
    """The 'login' route should reject invalid credentials"""

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": username, "password": password},
        ) as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "invalid_credentials"}


async def test_login_require_change_password():
    """The 'login' route should flag users that must change the password"""
    password_hash, salt = hash_password("FlaggedStrong123!")
    await User.create(
        username="flagged_user",
        password_hash=password_hash,
        password_salt=salt,
        role=UserRole.user,
        require_change_password=True,
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": "flagged_user", "password": "FlaggedStrong123!"},
        ) as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {
                "status": "ok",
                "username": "flagged_user",
                "role": "user",
                "require_change_password": True,
                "is_active": True,
            }


@pytest.mark.parametrize("cookie_secure", [True, False])
async def test_login_secure_cookie_flag(monkeypatch, admin_credentials, cookie_secure):
    """The 'login' route should set the Secure cookie flag only when enabled"""
    monkeypatch.setattr(configs.http_server.auth, "cookie_secure", cookie_secure)
    username, password = admin_credentials

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": username, "password": password},
        ) as response:
            assert response.status == 200
            set_cookie = response.headers.get("Set-Cookie", "")
            assert ("Secure" in set_cookie) is cookie_secure


async def test_logout(admin_cookies, admin_credentials):
    """The 'logout' route should clear the session"""
    username, password = admin_credentials
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": username, "password": password},
        ) as response:
            assert response.status == 200

        async with session.post(BASE_URL + "/auth/logout") as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {"status": "ok"}

        async with session.get(BASE_URL + "/auth/me") as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}


async def test_logout_no_cookie():
    """The 'logout' route should succeed without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/auth/logout") as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {"status": "ok"}


async def test_me(admin_cookies):
    """The 'me' route should return the current user"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.get(BASE_URL + "/auth/me") as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {
                "status": "ok",
                "username": "admin",
                "role": "admin",
                "require_change_password": False,
                "is_active": True,
            }


async def test_me_unauthorized():
    """The 'me' route should reject requests without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/auth/me") as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}


async def test_list_users(admin_cookies):
    """The 'users list' route should list all users for admins"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.get(BASE_URL + "/auth/users") as response:
            assert response.status == 200
            users = await response.json()
            admin = next(user for user in users if user["username"] == "admin")
            assert admin["role"] == "admin"
            assert admin["has_password"] is True
            assert admin["is_active"] is True


async def test_list_users_forbidden(user_cookies):
    """The 'users list' route should reject non-admin users"""
    async with aiohttp.ClientSession(cookies=user_cookies) as session:
        async with session.get(BASE_URL + "/auth/users") as response:
            assert response.status == 403
            response_data = await response.json()
            assert response_data == {"status": "forbidden"}


async def test_list_users_unauthorized():
    """The 'users list' route should reject requests without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/auth/users") as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}


async def test_create_user(admin_cookies):
    """The 'users create' route should create a user with an invite link"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "new_user", "role": "user"}
        ) as response:
            assert response.status == 201
            response_data = await response.json()
            assert response_data["status"] == "user_created"
            assert response_data["username"] == "new_user"
            assert response_data["role"] == "user"
            assert response_data["invite_url"].startswith("/dashboard/set-password.html?token=")


async def test_create_user_admin_role(admin_cookies):
    """The 'users create' route should create admin users"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "new_admin", "role": "admin"}
        ) as response:
            assert response.status == 201
            response_data = await response.json()
            assert response_data["role"] == "admin"


async def test_create_user_duplicate(admin_cookies):
    """The 'users create' route should reject duplicate usernames"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "dup_user"}
        ) as response:
            assert response.status == 201

        async with session.post(
            BASE_URL + "/auth/users", json={"username": "dup_user"}
        ) as response:
            assert response.status == 409
            response_data = await response.json()
            assert response_data == {
                "status": "user_exists",
                "message": "User 'dup_user' already exists",
            }


async def test_create_user_invalid_username(admin_cookies):
    """The 'users create' route should reject invalid usernames"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(BASE_URL + "/auth/users", json={"username": "ab"}) as response:
            assert response.status == 400
            response_data = await response.json()
            assert response_data == {
                "status": "error",
                "message": (
                    "Username must be 3-64 characters long and contain only "
                    "letters, numbers, '_', '.', '-'"
                ),
            }


async def test_create_user_invalid_role(admin_cookies):
    """The 'users create' route should reject invalid roles"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "role_user", "role": "superuser"}
        ) as response:
            assert response.status == 400
            response_data = await response.json()
            assert response_data["status"] == "error"


async def test_create_user_unauthorized():
    """The 'users create' route should reject requests without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "no_auth_user"}
        ) as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}


async def test_disable_user(admin_cookies):
    """The 'users disable' route should deactivate a user and revoke sessions"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "test_disable_user"}
        ) as response:
            assert response.status == 201
            response_data = await response.json()
            invite_url = response_data["invite_url"]

    token = invite_url.split("token=")[1]
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/set-password",
            json={"token": token, "password": "UserStrong123!"},
        ) as response:
            assert response.status == 200
            user_cookies = {c.key: c.value for c in response.cookies.values()}

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(BASE_URL + "/auth/users/test_disable_user/disable") as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {
                "status": "user_disabled",
                "username": "test_disable_user",
                "role": "user",
                "require_change_password": False,
                "is_active": False,
            }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": "test_disable_user", "password": "UserStrong123!"},
        ) as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "invalid_credentials"}

    async with aiohttp.ClientSession(cookies=user_cookies) as session:
        async with session.get(BASE_URL + "/auth/me") as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}


async def test_disable_user_self(admin_cookies, admin_credentials):
    """The 'users disable' route should reject admins disabling themselves"""
    username, _ = admin_credentials

    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.post(f"{BASE_URL}/auth/users/{username}/disable") as response:
            assert response.status == 400
            response_data = await response.json()
            assert response_data == {
                "status": "cannot_disable_self",
                "message": "Admins cannot disable themselves",
            }


async def test_disable_user_not_found(admin_cookies):
    """The 'users disable' route should return 404 for unknown users"""
    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.post(BASE_URL + "/auth/users/unknown_user/disable") as response:
            assert response.status == 404
            response_data = await response.json()
            assert response_data == {"status": "user_not_found"}


async def test_disable_user_forbidden(user_cookies):
    """The 'users disable' route should reject non-admin users"""
    async with aiohttp.ClientSession(cookies=user_cookies) as session:
        async with session.post(BASE_URL + "/auth/users/some_user/disable") as response:
            assert response.status == 403
            response_data = await response.json()
            assert response_data == {"status": "forbidden"}


async def test_enable_user(admin_cookies):
    """The 'users enable' route should reactivate a disabled user"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "test_enable_user"}
        ) as response:
            assert response.status == 201

        async with session.post(BASE_URL + "/auth/users/test_enable_user/disable") as response:
            assert response.status == 200

        async with session.post(BASE_URL + "/auth/users/test_enable_user/enable") as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {
                "status": "user_enabled",
                "username": "test_enable_user",
                "role": "user",
                "require_change_password": True,
                "is_active": True,
            }


async def test_enable_user_not_found(admin_cookies):
    """The 'users enable' route should return 404 for unknown users"""
    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.post(BASE_URL + "/auth/users/unknown_user/enable") as response:
            assert response.status == 404
            response_data = await response.json()
            assert response_data == {"status": "user_not_found"}


async def test_enable_user_forbidden(user_cookies):
    """The 'users enable' route should reject non-admin users"""
    async with aiohttp.ClientSession(cookies=user_cookies) as session:
        async with session.post(BASE_URL + "/auth/users/some_user/enable") as response:
            assert response.status == 403
            response_data = await response.json()
            assert response_data == {"status": "forbidden"}


async def test_validate_invite(admin_cookies):
    """The 'invite validate' route should validate invite tokens"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "invite_user"}
        ) as response:
            assert response.status == 201
            response_data = await response.json()
            invite_url = response_data["invite_url"]

    token = invite_url.split("token=")[1]
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + f"/auth/invite/validate?token={token}") as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {"status": "valid"}


async def test_validate_invite_invalid():
    """The 'invite validate' route should reject unknown tokens"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/auth/invite/validate?token=unknown") as response:
            assert response.status == 404
            response_data = await response.json()
            assert response_data == {"status": "invalid_token"}

        async with session.get(BASE_URL + "/auth/invite/validate") as response:
            assert response.status == 404
            response_data = await response.json()
            assert response_data == {"status": "invalid_token"}


async def test_validate_invite_invalid_token_not_logged(caplog):
    """Failed invite validation should not leak the token into the logs"""
    caplog.clear()
    raw_token = "eyJhbGciOiJIUzI1NiJ9.bogus-token-value.signature"

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + f"/auth/invite/validate?token={raw_token}") as response:
            assert response.status == 404

    assert raw_token not in caplog.text
    assert "token=REDACTED" in caplog.text


async def test_validate_invite_expired(admin_cookies):
    """The 'invite validate' route should reject expired tokens"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "expired_user"}
        ) as response:
            assert response.status == 201

    user = await User.get(User.username == "expired_user")
    assert user is not None
    token = create_token(
        {"sub": str(user.id), "type": "invite", "v": user.token_version},
        service.get_secret(),
        expire_hours=-1,
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + f"/auth/invite/validate?token={token}") as response:
            assert response.status == 410
            response_data = await response.json()
            assert response_data == {"status": "expired_token"}


async def test_set_password(admin_cookies):
    """The 'set password' route should set the password and login"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "password_user"}
        ) as response:
            assert response.status == 201
            response_data = await response.json()
            invite_url = response_data["invite_url"]

    token = invite_url.split("token=")[1]
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/set-password",
            json={"token": token, "password": "UserStrong123!"},
        ) as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {"status": "password_set"}
            assert service.COOKIE_NAME in {c.key for c in response.cookies.values()}

        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": "password_user", "password": "UserStrong123!"},
        ) as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {
                "status": "ok",
                "username": "password_user",
                "role": "user",
                "require_change_password": False,
                "is_active": True,
            }


async def test_set_password_invalid():
    """The 'set password' route should reject unknown tokens"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/set-password",
            json={"token": "unknown", "password": "UserStrong123!"},
        ) as response:
            assert response.status == 404
            response_data = await response.json()
            assert response_data == {"status": "invalid_token"}


async def test_set_password_expired(admin_cookies):
    """The 'set password' route should reject expired tokens"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "expired_pw_user"}
        ) as response:
            assert response.status == 201

    user = await User.get(User.username == "expired_pw_user")
    assert user is not None
    token = create_token(
        {"sub": str(user.id), "type": "invite", "v": user.token_version},
        service.get_secret(),
        expire_hours=-1,
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/set-password",
            json={"token": token, "password": "UserStrong123!"},
        ) as response:
            assert response.status == 410
            response_data = await response.json()
            assert response_data == {"status": "expired_token"}


async def test_set_password_weak(admin_cookies):
    """The 'set password' route should reject weak passwords"""
    cookies = admin_cookies

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(
            BASE_URL + "/auth/users", json={"username": "weak_pw_user"}
        ) as response:
            assert response.status == 201
            response_data = await response.json()
            invite_url = response_data["invite_url"]

    token = invite_url.split("token=")[1]
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/set-password", json={"token": token, "password": "weak"}
        ) as response:
            assert response.status == 400
            response_data = await response.json()
            assert response_data["status"] == "error"
            assert "errors" in response_data


async def test_change_password():
    """The 'change password' route should change the password"""
    password_hash, salt = hash_password("ChangeMeStrong123!")
    user = await User.create(
        username="change_pw_user",
        password_hash=password_hash,
        password_salt=salt,
        role=UserRole.user,
        require_change_password=False,
    )
    old_token = service.create_session(user)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": "change_pw_user", "password": "ChangeMeStrong123!"},
        ) as response:
            assert response.status == 200

        async with session.post(
            BASE_URL + "/auth/change-password",
            json={
                "current_password": "ChangeMeStrong123!",
                "new_password": "ChangedStrong123!",
            },
        ) as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {"status": "password_changed"}

    async with aiohttp.ClientSession(cookies={service.COOKIE_NAME: old_token}) as session:
        async with session.get(BASE_URL + "/auth/me") as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": "change_pw_user", "password": "ChangedStrong123!"},
        ) as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {
                "status": "ok",
                "username": "change_pw_user",
                "role": "user",
                "require_change_password": False,
                "is_active": True,
            }


@pytest.mark.parametrize(
    "username,current_password,new_password,expected_status,expected_data",
    [
        (
            "wrong_current_user",
            "WrongPass123!",
            "NewStrong123!",
            401,
            {"status": "invalid_credentials"},
        ),
        (
            "weak_new_user",
            "ChangeMeStrong123!",
            "weak",
            400,
            {
                "status": "error",
                "message": "Weak password",
                "errors": [
                    "password must be at least 12 characters",
                    "password must contain at least one uppercase letter",
                    "password must contain at least one digit",
                    "password must contain at least one special character",
                ],
            },
        ),
    ],
)
async def test_change_password_invalid(
    username, current_password, new_password, expected_status, expected_data
):
    """The 'change password' route should reject invalid password changes"""
    password_hash, salt = hash_password("ChangeMeStrong123!")
    await User.create(
        username=username,
        password_hash=password_hash,
        password_salt=salt,
        role=UserRole.user,
        require_change_password=False,
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": username, "password": "ChangeMeStrong123!"},
        ) as response:
            assert response.status == 200

        async with session.post(
            BASE_URL + "/auth/change-password",
            json={"current_password": current_password, "new_password": new_password},
        ) as response:
            assert response.status == expected_status
            response_data = await response.json()
            assert response_data == expected_data


async def test_change_password_unauthorized():
    """The 'change password' route should reject requests without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/change-password",
            json={"current_password": "a", "new_password": "NewStrong123!"},
        ) as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}


async def test_protected_api_unauthorized():
    """Protected API routes should reject requests without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/monitor/list") as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}

        async with session.get(
            BASE_URL + "/monitor/list", headers={"Accept": "text/html"}
        ) as response:
            assert response.status == 200
            assert "Sentinela Login" in await response.text()


async def test_require_change_password_gate():
    """Users flagged to change the password should be blocked from other routes"""
    password_hash, salt = hash_password("GatedStrong123!")
    await User.create(
        username="gated_user",
        password_hash=password_hash,
        password_salt=salt,
        role=UserRole.user,
        require_change_password=True,
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL + "/auth/login",
            json={"username": "gated_user", "password": "GatedStrong123!"},
        ) as response:
            assert response.status == 200
            response_data = await response.json()
            assert response_data == {
                "status": "ok",
                "username": "gated_user",
                "role": "user",
                "require_change_password": True,
                "is_active": True,
            }
            cookies = {c.key: c.value for c in response.cookies.values()}

    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.get(BASE_URL + "/auth/me") as response:
            assert response.status == 200

        async with session.get(BASE_URL + "/monitor/list") as response:
            assert response.status == 403
            response_data = await response.json()
            assert response_data == {"status": "password_change_required"}

        async with session.get(BASE_URL + "/dashboard/", allow_redirects=False) as response:
            assert response.status == 302
            assert response.headers["Location"] == "/dashboard/change-password.html"

        async with session.get(BASE_URL + "/dashboard/change-password.html") as response:
            assert response.status == 200
            assert response.content_type == "text/html"


async def test_expired_session_unauthorized():
    """Requests with an expired session should be rejected"""
    user = await User.create(username="expiring_session_user")
    assert user is not None

    raw_token = create_token(
        {"sub": str(user.id), "type": "session", "v": user.token_version},
        service.get_secret(),
        expire_hours=-1,
    )

    async with aiohttp.ClientSession(cookies={service.COOKIE_NAME: raw_token}) as session:
        async with session.get(BASE_URL + "/auth/me") as response:
            assert response.status == 401
            response_data = await response.json()
            assert response_data == {"status": "unauthorized"}

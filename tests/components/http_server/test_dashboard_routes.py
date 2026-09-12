import aiohttp
import pytest
import pytest_asyncio

import components.http_server as http_server

pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000/dashboard"


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    await http_server.init(controller_enabled=True)
    yield
    await http_server.wait_stop()


async def test_get_dashboard(admin_cookies):
    """The 'dashboard' route should serve the index.html file"""
    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.get(BASE_URL) as response:
            assert response.status == 200
            assert response.content_type == "text/html"
            content = await response.text()
            assert "<!DOCTYPE html>" in content or "<html" in content


async def test_get_asset_css(admin_cookies):
    """The dashboard should serve CSS assets correctly"""
    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.get(BASE_URL + "/css/styles.css") as response:
            assert response.status == 200
            assert response.content_type == "text/css"


async def test_get_asset_js(admin_cookies):
    """The dashboard should serve JavaScript assets correctly"""
    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.get(BASE_URL + "/js/dashboard.js") as response:
            assert response.status == 200
            assert response.content_type == "application/javascript"


async def test_get_asset_not_found(admin_cookies):
    """The dashboard should return 404 for non-existent assets"""
    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.get(BASE_URL + "/nonexistent.js") as response:
            assert response.status == 404
            assert await response.text() == "Asset not found"


@pytest.mark.parametrize(
    ("traversal_path", "expected_body"),
    [
        ("/../server.py", "404: Not Found"),
        ("/css", "Asset not found"),
        ("/..%2fserver.py", "Asset not found"),
        ("/..%2fauth%2fservice.py", "Asset not found"),
        ("/..%2f..%2f..%2f..%2fpyproject.toml", "Asset not found"),
    ],
)
async def test_get_asset_forbidden_path_traversal(admin_cookies, traversal_path, expected_body):
    """The dashboard should return 404 for path traversal attempts"""
    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.get(BASE_URL + traversal_path) as response:
            assert response.status == 404
            assert await response.text() == expected_body


async def test_get_dashboard_unauthorized():
    """The 'dashboard' route should redirect to the login page without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL, allow_redirects=False) as response:
            assert response.status == 302
            assert response.headers["Location"] == "/dashboard/login.html"


async def test_get_login_page_unauthorized():
    """The login page should be public without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/login.html") as response:
            assert response.status == 200
            assert response.content_type == "text/html"


async def test_get_asset_unauthorized():
    """Dashboard assets should redirect to the login page without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/js/dashboard.js", allow_redirects=False) as response:
            assert response.status == 302
            assert response.headers["Location"] == "/dashboard/login.html"


async def test_get_change_password_page(admin_cookies):
    """The change password page should be served with a session"""
    async with aiohttp.ClientSession(cookies=admin_cookies) as session:
        async with session.get(BASE_URL + "/change-password.html") as response:
            assert response.status == 200
            assert response.content_type == "text/html"


async def test_get_change_password_page_unauthorized():
    """The change password page should redirect to the login page without a session"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            BASE_URL + "/change-password.html", allow_redirects=False
        ) as response:
            assert response.status == 302
            assert response.headers["Location"] == "/dashboard/login.html"

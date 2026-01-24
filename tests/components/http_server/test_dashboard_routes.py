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


async def test_get_dashboard():
    """The 'dashboard' route should serve the index.html file"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            assert response.status == 200
            assert response.content_type == "text/html"
            content = await response.text()
            assert "<!DOCTYPE html>" in content or "<html" in content


async def test_get_asset_css():
    """The dashboard should serve CSS assets correctly"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/css/styles.css") as response:
            assert response.status == 200
            assert response.content_type == "text/css"


async def test_get_asset_js():
    """The dashboard should serve JavaScript assets correctly"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/js/dashboard.js") as response:
            assert response.status == 200
            assert response.content_type == "application/javascript"


async def test_get_asset_not_found():
    """The dashboard should return 404 for non-existent assets"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/nonexistent.js") as response:
            assert response.status == 404
            assert await response.text() == "Asset not found"


async def test_get_asset_forbidden_path_traversal():
    """The dashboard should return 404 for path traversal attempts"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/../../../secret.txt") as response:
            assert response.status == 404
            assert await response.text() == "404: Not Found"

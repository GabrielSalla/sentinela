import pytest_asyncio

from . import slack_mock


@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def mock_slack_requests(monkeypatch_session):
    """Mock the slack requests"""
    await slack_mock.init(monkeypatch_session)
    yield
    await slack_mock.stop()

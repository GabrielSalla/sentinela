from unittest.mock import AsyncMock

import pytest

import components.controller.procedures.clean_old_events as clean_old_events
from configs import configs
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_configuration():
    assert "clean_old_events" in configs.controller_procedures


@pytest.mark.parametrize("age_days", [7, 30, 90])
async def test_clean_old_events_enabled(monkeypatch, caplog, age_days):
    """'clean_old_events' should execute the cleanup query when enabled"""
    execute_application = AsyncMock()
    monkeypatch.setattr(clean_old_events.databases, "execute_application", execute_application)

    await clean_old_events.clean_old_events(age_days=age_days)

    execute_application.assert_awaited_once_with(
        "delete from \"Events\"\nwhere created_at < current_timestamp - ($1 * INTERVAL '1 day');\n",
        age_days,
    )
    assert_message_in_log(caplog, f"Events older than {age_days} cleaned from the database")

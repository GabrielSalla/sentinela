import alembic.runtime
import alembic.script
import pytest

from internal_database import PendingDatabaseUpgrade, check_database

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize("current_version, current_revision", [("123", "123"), ("456", "456")])
async def test_check_database_up_to_date(monkeypatch, current_version, current_revision):
    """'check_database' should not raise an error if the database is up to date."""
    monkeypatch.setattr(
        alembic.script.ScriptDirectory,
        "get_current_head",
        lambda self: current_version,
    )
    monkeypatch.setattr(
        alembic.runtime.migration.MigrationContext,
        "get_current_revision",
        lambda self: current_revision,
    )

    await check_database()


@pytest.mark.parametrize(
    "current_version, current_revision", [("123", "456"), ("456", "789"), ("1234", None)]
)
async def test_check_database_not_up_to_date(monkeypatch, current_version, current_revision):
    """'check_database' should raise an error if the database is not up to date."""
    monkeypatch.setattr(
        alembic.script.ScriptDirectory,
        "get_current_head",
        lambda self: current_version,
    )
    monkeypatch.setattr(
        alembic.runtime.migration.MigrationContext,
        "get_current_revision",
        lambda self: current_revision,
    )

    with pytest.raises(PendingDatabaseUpgrade):
        await check_database()

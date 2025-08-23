import alembic.config
import alembic.runtime
import alembic.script
from sqlalchemy.engine.base import Connection

import internal_database

from .exceptions import PendingDatabaseUpgrade


async def check_database() -> None:
    """Check the database for pending migrations."""

    def check_migration_revision(connection: Connection) -> None:
        alembic_config = alembic.config.Config("alembic.ini")
        alembic_script = alembic.script.ScriptDirectory.from_config(alembic_config)
        current_head = alembic_script.get_current_head()

        context = alembic.runtime.migration.MigrationContext.configure(connection)
        current_revision = context.get_current_revision()

        if current_head != current_revision:
            error = (
                "Target database is not up to date. "
                "Execute migrations before running the application."
            )
            raise PendingDatabaseUpgrade(error)

    async with internal_database.engine.begin() as connection:
        await connection.run_sync(check_migration_revision)

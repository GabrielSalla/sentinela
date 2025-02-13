import decimal
import logging
from typing import Any

import asyncpg

from configs import configs

_logger = logging.getLogger("plugin.postgres.pool")


def _convert_decimal_to_float(row: asyncpg.Record) -> dict[str, Any]:
    """Convert all 'Decimal' values in the data to 'float'"""
    return {
        key: float(value) if isinstance(value, decimal.Decimal) else value
        for key, value in dict(row).items()
    }


class PostgresPool:
    PATTERNS = [
        "postgres",
        "postgres+asyncpg",
        "postgresql",
        "postgresql+asyncpg",
    ]

    name: str = ""
    _pool: asyncpg.Pool
    __dsn: str
    __connection_params: dict[str, Any]

    def __init__(self, dsn: str, name: str, **configs: Any) -> None:
        """Create a PostgreSQL pool with the provided parameters"""
        # Use the connection parameters from the configs file if it's not defined
        self.__dsn = dsn.replace("+asyncpg://", "://")
        self.name = name

        self.__connection_params = {
            "min_size": 0,
            "max_size": 5,
            "timeout": 10,
            "max_inactive_connection_lifetime": 120,
            "server_settings": {
                "application_name": "sentinela_pool",
            },
        }
        self.__connection_params.update(**configs)

    async def init(self) -> None:
        self._pool = await asyncpg.create_pool(dsn=self.__dsn, **self.__connection_params)
        await self.fetch("select 1;")

    async def execute(
        self,
        sql: str,
        *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
    ) -> None:
        """Execute a query in the PostgreSQL database through the pool"""
        async with self._pool.acquire() as connection:
            await connection.execute(sql, *args)

    async def fetch(
        self,
        sql: str,
        *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
        acquire_timeout: int = configs.database_default_acquire_timeout,
        query_timeout: int = configs.database_default_query_timeout,
    ) -> list[dict[str, Any]]:
        """Fetch data from the PostgreSQL database through the pool"""
        async with self._pool.acquire(timeout=acquire_timeout) as connection:
            result = await connection.fetch(sql, *args, timeout=query_timeout)

        return [_convert_decimal_to_float(row) for row in result]

    async def close(self) -> None:
        """Close all the connections from the pool"""
        _logger.info(f"Closing pool '{self.name}'")
        await self._pool.close()
        _logger.info(f"Pool '{self.name}' closed")

import asyncio
import decimal
import logging
from typing import Any

import aioodbc

from configs import configs

_logger = logging.getLogger("plugin.odbc.pool")


def _convert_decimal_to_float(row: dict[str, Any]) -> dict[str, Any]:
    """Convert all 'Decimal' values in the data to 'float'"""
    return {
        key: float(value) if isinstance(value, decimal.Decimal) else value
        for key, value in row.items()
    }


class OdbcPool:
    PATTERNS = [
        "odbc",
    ]

    name: str = ""
    _pool: aioodbc.Pool
    __dsn: str
    __connection_params: dict[str, Any]

    def __init__(self, dsn: str, name: str, **configs: Any) -> None:
        """Create an ODBC pool with the provided parameters"""
        self.__dsn = dsn.replace("odbc://", "")
        self.name = name

        self.__connection_params = {
            "minsize": 0,
            "maxsize": 5,
            "timeout": 10,
            "max_inactive_connection_lifetime": 120,
        }
        self.__connection_params.update(configs)

        connection_lifetime = self.__connection_params["max_inactive_connection_lifetime"]
        self.__connection_params["pool_recycle"] = connection_lifetime
        del self.__connection_params["max_inactive_connection_lifetime"]

    async def init(self) -> None:
        self._pool = await aioodbc.create_pool(
            dsn=self.__dsn, **self.__connection_params
        )
        await self.fetch("select 1;")

    async def execute(
        self,
        sql: str,
        *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
    ) -> None:
        """Execute a query in the ODBC database through the pool"""
        async with self._pool.acquire() as connection:
            cursor = await connection.cursor()
            await cursor.execute(sql, args)
            await cursor.close()

    async def fetch(
        self,
        sql: str,
        *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
        acquire_timeout: int = configs.database_default_acquire_timeout,
        query_timeout: int = configs.database_default_query_timeout,
    ) -> list[dict[str, Any]]:
        """Fetch data from the ODBC database through the pool"""
        # connection = await asyncio.wait_for(self._pool.acquire(), timeout=acquire_timeout)
        async with self._pool.acquire() as connection:
            cursor = await connection.cursor()
            await asyncio.wait_for(cursor.execute(sql, args), timeout=query_timeout)
            rows = await cursor.fetchall()
            column_names = [description[0] for description in cursor.description]
            await cursor.close()

        result = [
            dict(zip(column_names, row))
            for row in rows
        ]
        return result

        return [_convert_decimal_to_float(row) for row in result]

    async def close(self) -> None:
        """Close all the connections from the pool"""
        _logger.info(f"Closing pool '{self.name}'")
        self._pool.close()
        await self._pool.wait_closed()
        _logger.info(f"Pool '{self.name}' closed")

import asyncio
import decimal
import logging
from typing import Any

import asyncpg

from configs import configs
from utils.async_tools import do_concurrently

_logger = logging.getLogger("postgresql_pools")

_pools: dict[str, asyncpg.Pool] = {}


async def create_pool(dsn: str, name: str) -> None:
    """Create a PostgreSQL pool with the provided parameters"""
    # Use the connection parameters from the configs file if it's not defined
    connection_params = {
        "min_size": 0,
        "max_size": 5,
        "timeout": 10,
        "max_inactive_connection_lifetime": 120,
        "server_settings": {
            "application_name": "sentinela_pool",
        },
    }

    configs_params = configs.databases_pools_configs.get(name)
    if configs_params is not None:
        connection_params.update(configs_params)

    dsn = dsn.replace("+asyncpg", "")

    _pools[name] = await asyncpg.create_pool(dsn=dsn, **connection_params)


async def execute(
    name: str,
    sql: str,
    *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
) -> None:
    """Execute a query in the provided PostgreSQL database"""
    if name not in _pools:
        raise ValueError(f"Database '{name}' not loaded in environment variables")

    async with _pools[name].acquire() as connection:
        await connection.execute(sql, *args)


def _convert_decimal_to_float(row: asyncpg.Record) -> dict[str, Any]:
    """Convert all 'Decimal' values in the data to 'float'"""
    return {
        key: float(value) if isinstance(value, decimal.Decimal) else value
        for key, value in dict(row).items()
    }


async def fetch(
    name: str,
    sql: str,
    *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
    acquire_timeout: int = configs.database_default_acquire_timeout,
    query_timeout: int = configs.database_default_query_timeout,
) -> list[dict[str, Any]]:
    """Fetch data from a PostgreSQL database"""
    if name not in _pools:
        raise ValueError(f"Database '{name}' not loaded in environment variables")

    async with _pools[name].acquire(timeout=acquire_timeout) as connection:
        result = await connection.fetch(sql, *args, timeout=query_timeout)

    return [_convert_decimal_to_float(row) for row in result]


async def _close_pool(name: str) -> None:
    """Close a single PostgreSQL pool"""
    await asyncio.wait_for(_pools[name].close(), timeout=configs.database_close_timeout)
    _logger.info(f"Pool '{name}' closed")


async def close() -> None:
    """Close all the PostgreSQL pools"""
    await do_concurrently(*[_close_pool(name) for name in _pools.keys()])
    _pools.clear()

import asyncio
import enum
import json
import logging
import os
import time
import traceback
from typing import Coroutine, cast

import databases.postgresql_pools as postgresql_pools
from configs import configs
from data_types.issue_data_types import IssueDataType
from utils.async_tools import do_concurrently

_logger = logging.getLogger("database")

_pools: dict[str, str] = {}


class QueryStatus(enum.Enum):
    success = "success"
    canceled = "canceled"
    error = "error"


async def init():
    """Init all the database pools"""
    for env_var_name, env_var_value in os.environ.items():
        if not env_var_name.startswith("DATABASE_"):
            continue

        database_name = env_var_name.split("DATABASE_")[1].lower()
        dsn = env_var_value
        if dsn.startswith("postgres"):
            _pools[database_name] = "postgresql"
            await postgresql_pools.create_pool(name=database_name, dsn=dsn)
        else:
            _logger.warning(f"Invalid DSN for database pool '{env_var_name}'")


async def _fetch(fetch_task: Coroutine, metrics: dict) -> list[IssueDataType] | None:
    """Await a fetch coroutine, update the metrics and log them"""
    try:
        start_time = time.time()
        metrics["start_time"] = start_time
        result = await fetch_task
        metrics["status"] = QueryStatus.success.value
        return cast(list[IssueDataType] | None, result)
    except asyncio.CancelledError:
        metrics["status"] = QueryStatus.canceled.value
        return None
    except Exception as e:
        _logger.error(e)
        metrics["status"] = QueryStatus.error.value
        metrics["error"] = traceback.format_exc().strip()
        raise e
    finally:
        end_time = time.time()
        metrics["end_time"] = end_time
        metrics["query_time"] = end_time - start_time
        if configs.database_log_query_metrics:
            _logger.info(json.dumps(metrics))


async def query(
    name: str,
    sql: str,
    *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
    acquire_timeout: int = configs.database_default_acquire_timeout,
    query_timeout: int = configs.database_default_query_timeout,
) -> list[IssueDataType] | None:
    """Query data from a database identifying it's engine and using the correct engine pool.
    Querying from the application database is not allowed"""
    if name == "application":
        raise RuntimeError("Querying application database not allowed")

    engine_pool = _pools.get(name)
    if engine_pool is None:
        raise ValueError(f"Database '{name}' not loaded in environment variables")

    # Identify the engine pool and create the fetch coroutine that will be awaited
    if engine_pool == "postgresql":
        fetch_task = postgresql_pools.fetch(
            name, sql, *args, acquire_timeout=acquire_timeout, query_timeout=query_timeout
        )
    else:
        raise ValueError(f"Invalid pool type '{engine_pool}'")

    metrics = {
        "pool_name": name,
        "query": sql,
        "args": args,
        "status": None,
        "error": None,
        "start_time": None,
        "end_time": None,
        "query_time": None,
    }

    return await _fetch(fetch_task, metrics)


async def execute_application(
    sql: str,
    *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
):
    """Function to be used internally by the application or by the internal modules.
    Execute a query in the application database"""
    await postgresql_pools.execute("application", sql, *args)


async def query_application(
    sql: str,
    *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
    acquire_timeout: int = configs.database_default_acquire_timeout,
    query_timeout: int = configs.database_default_query_timeout,
) -> list[IssueDataType] | None:
    """Function to be used internally by the application or by the internal modules.
    Query data from the application database"""
    fetch_task = postgresql_pools.fetch(
        "application", sql, *args, acquire_timeout=acquire_timeout, query_timeout=query_timeout
    )

    metrics = {
        "pool_name": "application",
        "query": sql,
        "args": args,
        "status": None,
        "error": None,
        "start_time": None,
        "end_time": None,
        "query_time": None,
    }

    return await _fetch(fetch_task, metrics)


async def close():
    """Close all the database pools"""
    await do_concurrently(
        *[
            postgresql_pools.close(),
        ]
    )

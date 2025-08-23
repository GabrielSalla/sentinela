import asyncio
import enum
import json
import logging
import os
import time
import traceback
from typing import Any, Coroutine, cast

from configs import configs
from plugins.pool_select import get_plugin_pool
from utils.async_tools import do_concurrently

from .protocols import Pool

_logger = logging.getLogger("database")

_pool_cache: dict[str, type[Pool]] = {}
_pools: dict[str, Pool] = {}


class QueryStatus(enum.Enum):
    success = "success"
    canceled = "canceled"
    error = "error"


async def init() -> None:
    """Init all the database pools"""
    for env_var_name, env_var_value in os.environ.items():
        if not env_var_name.startswith("DATABASE_"):
            continue

        dsn = env_var_value
        pool_type = dsn.split("://")[0]

        pool_class: type[Pool] | None
        if pool_type in _pool_cache:
            pool_class = _pool_cache[pool_type]
        else:
            pool_class = get_plugin_pool(pool_type)

        if pool_class is None:
            _logger.warning(f"Invalid DSN for database pool '{env_var_name}'")
            continue

        _pool_cache[pool_type] = pool_class

        # Get the pool configs
        database_name = env_var_name.split("DATABASE_")[1].lower()
        pool_configs = configs.databases_pools_configs.get(database_name) or {}

        try:
            pool = pool_class(dsn=dsn, name=database_name, **pool_configs)
            await pool.init()
            _pools[database_name] = pool
        except Exception:
            _logger.error(
                f"Error initializing pool for database '{env_var_name}', skipping", exc_info=True
            )


async def _fetch(
    fetch_task: Coroutine[Any, Any, list[dict[Any, Any]]],
    metrics: dict[str, Any],
) -> list[dict[Any, Any]] | None:
    """Await a fetch coroutine, update the metrics and log them"""
    try:
        start_time = time.time()
        metrics["start_time"] = start_time
        result = await fetch_task
        metrics["status"] = QueryStatus.success.value
        return cast(list[dict[Any, Any]] | None, result)
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
            _logger.info(json.dumps(metrics, default=str))


async def query(
    name: str,
    sql: str,
    *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
    acquire_timeout: int = configs.database_default_acquire_timeout,
    query_timeout: int = configs.database_default_query_timeout,
) -> list[dict[Any, Any]] | None:
    """Query data from a database identifying it's engine and using the correct engine pool.
    Querying from the application database is not allowed"""
    if name == "application":
        raise RuntimeError("Querying application database not allowed")

    pool = _pools.get(name)
    if pool is None:
        raise ValueError(f"Database '{name}' not loaded in environment variables")

    # Identify the engine pool and create the fetch coroutine that will be awaited
    fetch_task = pool.fetch(
        sql, *args, acquire_timeout=acquire_timeout, query_timeout=query_timeout
    )

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
) -> None:
    """Function to be used internally by the application or by the internal modules.
    Execute a query in the application database"""
    await _pools["application"].execute(sql, *args)


async def query_application(
    sql: str,
    *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
    acquire_timeout: int = configs.database_default_acquire_timeout,
    query_timeout: int = configs.database_default_query_timeout,
) -> list[dict[Any, Any]] | None:
    """Function to be used internally by the application or by the internal modules.
    Query data from the application database"""
    fetch_task = _pools["application"].fetch(
        sql, *args, acquire_timeout=acquire_timeout, query_timeout=query_timeout
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


async def close() -> None:
    """Close all the database pools"""
    await do_concurrently(*[pool.close() for pool in _pools.values()])

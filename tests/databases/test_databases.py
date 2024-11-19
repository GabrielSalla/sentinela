import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
import pytest_asyncio

import src.databases.databases as databases
import src.databases.postgresql_pools as postgresql_pools
from src.configs import configs
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="function")
async def reload_databases():
    """Used in the tests that close the databases pools"""
    yield
    await databases.init()


@pytest_asyncio.fixture(loop_scope="session", scope="function", autouse=True)
async def drop_test_tables():
    try:
        await postgresql_pools.execute("application", "drop table test_table cascade")
    except asyncpg.exceptions.UndefinedTableError:
        pass


async def test_init(caplog, monkeypatch):
    """'init' should create the database pools for each environment variable that starts with
    'DATABASE_', using the correct database pool engine"""
    monkeypatch.setitem(os.environ, "DATABASE_INVALID", "invalid_dsn")

    await databases.init()

    assert databases._pools["application"] == "postgresql"
    assert databases._pools["local"] == "postgresql"

    assert_message_in_log(caplog, "Invalid DSN for database pool 'DATABASE_INVALID'")


async def test_fetch(caplog, monkeypatch):
    """'_fetch' should await the coroutine and return it's return value, while logging the
    metrics"""
    monkeypatch.setattr(configs, "database_log_query_metrics", True)

    async def sleep():
        await asyncio.sleep(0.1)
        return 10

    metrics = {
        "pool_name": "name",
        "query": "sql",
        "args": "args",
        "status": None,
        "error": None,
        "start_time": None,
        "end_time": None,
        "query_time": None,
    }

    result = await databases._fetch(sleep(), metrics)

    assert result == 10

    log_metrics = json.loads(caplog.records[-1].message)

    assert log_metrics["pool_name"] == "name"
    assert log_metrics["query"] == "sql"
    assert log_metrics["args"] == "args"
    assert log_metrics["status"] == databases.QueryStatus.success.value
    assert log_metrics["error"] is None
    assert log_metrics["start_time"] > time.time() - 0.105
    assert log_metrics["end_time"] > time.time() - 0.05
    assert log_metrics["query_time"] > 0.1
    assert log_metrics["query_time"] < 0.105


async def test_fetch_cancelled(caplog, monkeypatch):
    """'_fetch' should return 'None' and log the metrics if the coroutine is cancelled while
    executing"""
    monkeypatch.setattr(configs, "database_log_query_metrics", True)

    async def sleep():
        await asyncio.sleep(1)
        return 20

    metrics = {
        "pool_name": "new name",
        "query": "other sql",
        "args": "more args",
        "status": None,
        "error": None,
        "start_time": None,
        "end_time": None,
        "query_time": None,
    }

    sleep_task = asyncio.create_task(sleep())
    fetch_task = asyncio.create_task(databases._fetch(sleep_task, metrics))

    await asyncio.sleep(0.1)
    sleep_task.cancel()
    result = await fetch_task

    assert result is None

    log_metrics = json.loads(caplog.records[-1].message)

    assert log_metrics["pool_name"] == "new name"
    assert log_metrics["query"] == "other sql"
    assert log_metrics["args"] == "more args"
    assert log_metrics["status"] == databases.QueryStatus.canceled.value
    assert log_metrics["error"] is None
    assert log_metrics["start_time"] > time.time() - 0.105
    assert log_metrics["end_time"] > time.time() - 0.05
    assert log_metrics["query_time"] > 0.1
    assert log_metrics["query_time"] < 0.105


async def test_fetch_error(caplog, monkeypatch):
    """'_fetch' should raise the same exception raised by the coroutine, while logging the
    metrics"""
    monkeypatch.setattr(configs, "database_log_query_metrics", True)

    async def error():
        raise ValueError("some error")

    metrics = {
        "pool_name": "no name",
        "query": "some sql",
        "args": "many args",
        "status": None,
        "error": None,
        "start_time": None,
        "end_time": None,
        "query_time": None,
    }

    with pytest.raises(ValueError, match="some error"):
        await databases._fetch(error(), metrics)

    log_metrics = json.loads(caplog.records[-1].message)

    assert log_metrics["pool_name"] == "no name"
    assert log_metrics["query"] == "some sql"
    assert log_metrics["args"] == "many args"
    assert log_metrics["status"] == databases.QueryStatus.error.value
    assert log_metrics["error"] is not None
    assert "ValueError: some error" in log_metrics["error"]
    assert log_metrics["start_time"] > time.time() - 0.05
    assert log_metrics["end_time"] > time.time() - 0.05
    assert log_metrics["end_time"] > log_metrics["start_time"]
    assert log_metrics["query_time"] > 0
    assert log_metrics["query_time"] < 0.01


async def test_query_postgresql(mocker):
    """'query' should execute a query using the specified database pool"""
    pool_fetch_spy: MagicMock = mocker.spy(postgresql_pools, "fetch")

    result = await databases.query("local", "select $1 :: int as value", 123)

    assert result == [{"value": 123}]
    pool_fetch_spy.assert_called_once_with(
        "local",
        "select $1 :: int as value",
        123,
        acquire_timeout=configs.database_default_acquire_timeout,
        query_timeout=configs.database_default_query_timeout,
    )


async def test_query_postgresql_timeouts(mocker):
    """'query' should execute a query using the specified database pool with the provided
    timeouts"""
    pool_fetch_spy: MagicMock = mocker.spy(postgresql_pools, "fetch")

    result = await databases.query(
        "local", "select $1 :: int as value", 123, acquire_timeout=12, query_timeout=34
    )

    assert result == [{"value": 123}]
    pool_fetch_spy.assert_called_once_with(
        "local", "select $1 :: int as value", 123, acquire_timeout=12, query_timeout=34
    )


async def test_query_error_application():
    """'query' should not allow querying the application database, raising an 'RuntimeError'
    exception"""
    with pytest.raises(RuntimeError, match="Querying application database not allowed"):
        await databases.query("application", "select 1")


async def test_query_invalid_pool():
    """'query' should raise an 'ValueError' exception if the provided database name doesn't
    exists"""
    with pytest.raises(
        ValueError, match="Database 'some_database' not loaded in environment variables"
    ):
        await databases.query("some_database", "select 1")


async def test_query_invalid_engine(monkeypatch):
    """'query' should raise an 'ValueError' exception if the provided database uses a not
    implemented engine"""
    monkeypatch.setitem(databases._pools, "invalid", "invalid_engine")
    with pytest.raises(ValueError, match="Invalid pool type 'invalid_engine'"):
        await databases.query("invalid", "select 1")


async def test_execute_application(mocker):
    """'execute_application' should run the provided query in the application database pool"""
    pool_execute_spy: MagicMock = mocker.spy(postgresql_pools, "execute")

    await databases.execute_application("create table test_table (value int);")
    pool_execute_spy.assert_called_with("application", "create table test_table (value int);")

    await databases.execute_application("insert into test_table values (1), (2);")
    pool_execute_spy.assert_called_with("application", "insert into test_table values (1), (2);")


async def test_query_application(mocker):
    """'query_application' should run the provided query in the application database pool and
    return the result"""
    pool_fetch_spy: MagicMock = mocker.spy(postgresql_pools, "fetch")

    result = await databases.query_application("select 2 * $1 :: int as value", 234)

    assert result == [{"value": 468}]
    pool_fetch_spy.assert_called_once_with(
        "application",
        "select 2 * $1 :: int as value",
        234,
        acquire_timeout=configs.database_default_acquire_timeout,
        query_timeout=configs.database_default_query_timeout,
    )


async def test_close(mocker, reload_databases):
    """'close' should close all the pools"""
    postgresql_pools_close_spy: AsyncMock = mocker.spy(postgresql_pools, "close")

    await databases.close()

    postgresql_pools_close_spy.assert_awaited_once()

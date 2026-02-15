import asyncio
import decimal
from unittest.mock import AsyncMock

import aioodbc
import pytest
import pytest_asyncio

from databases import Pool
from plugins.odbc.pools import OdbcPool
from plugins.odbc.pools.odbc_pool import _convert_decimal_to_float

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def close_pools(monkeypatch_module):
    """Automatically close all the pools created in the tests"""
    created_pools = []
    original_init = OdbcPool.init

    async def init_mock(self):
        nonlocal created_pools
        await original_init(self)
        created_pools.append(self)
        print(self._pool)

    monkeypatch_module.setattr(OdbcPool, "init", init_mock)

    yield

    for pool in created_pools:
        await pool.close()


@pytest_asyncio.fixture(loop_scope="session", scope="function", autouse=True)
async def drop_test_tables():
    """Drop test tables from the database"""
    pool = OdbcPool(
        dsn="odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=postgres;UID=postgres;PWD=postgres",
        name="db1",
    )
    await pool.init()
    try:
        await pool.execute("drop table if exists test_table cascade;")
    except Exception:
        # Table might not exist, which is fine
        pass


@pytest.mark.parametrize("value", [1.234, 56.789])
async def test_convert_decimal_to_float(value):
    """'_convert_decimal_to_float' should convert a dict object, converting
    all 'Decimal' fields to float"""
    result_dict = {"value": decimal.Decimal(str(value)), "other_value": "abc"}

    result = _convert_decimal_to_float(result_dict)

    assert result == {"value": value, "other_value": "abc"}
    assert isinstance(result["value"], float)
    assert isinstance(result["other_value"], str)


async def test_odbcpool_protocol():
    """'OdbcPool' should follow the 'Pool' protocol"""
    assert isinstance(OdbcPool, Pool)


@pytest.mark.parametrize(
    "dsn, connection_params",
    [
        (
            "odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=postgres;UID=postgres;PWD=postgres",
            {},
        ),
        (
            "odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=postgres;UID=postgres;PWD=postgres",
            {"maxsize": 123},
        ),
        (
            "odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=postgres;UID=postgres;PWD=postgres",
            {"minsize": 1, "maxsize": 4},
        ),
    ],
)
async def test_odbcpool_init(dsn, connection_params):
    """'OdbcPool' should create a pool with the provided parameters using the default parameters
    if one wasn't provided"""
    pool = OdbcPool(dsn=dsn, name="db1", **connection_params)
    await pool.init()

    if connection_params is None:
        assert pool._pool._minsize == 0
        assert pool._pool._maxsize == 5
    else:
        assert pool._pool._minsize == connection_params.get("minsize", 0)
        assert pool._pool._maxsize == connection_params.get("maxsize", 5)

    result = await pool.fetch("select 1 as value")
    assert result == [{"value": 1}]


async def test_odbcpool_init_incorrect_credentials():
    """'OdbcPool.init' should raise an error if the credentials are incorrect"""
    pool = OdbcPool(
        dsn="odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=postgres;UID=postgres;PWD=wrong_password",
        name="db1",
    )
    with pytest.raises(Exception):  # aioodbc raises various exceptions for auth failures
        await pool.init()


async def test_odbcpool_init_incorrect_database():
    """'OdbcPool.init' should raise an error if the database is incorrect"""
    pool = OdbcPool(
        dsn="odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=wrong_database;UID=postgres;PWD=postgres",
        name="db1",
    )
    with pytest.raises(Exception):  # aioodbc raises various exceptions for database errors
        await pool.init()


async def test_odbcpool_execute():
    """'OdbcPool.execute' should execute a query in the provided database"""
    pool = OdbcPool(
        dsn="odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=postgres;UID=postgres;PWD=postgres",
        name="db1",
    )
    await pool.init()

    await pool.execute("create table test_table (value int);")
    await pool.execute("insert into test_table values (1), (2);")
    data = await pool.fetch("select * from test_table order by value")
    assert data == [{"value": 1}, {"value": 2}]


async def test_odbcpool_fetch():
    """'OdbcPool.fetch' should execute a query in the provided database and return the result"""
    pool = OdbcPool(
        dsn="odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=postgres;UID=postgres;PWD=postgres",
        name="db1",
    )
    await asyncio.wait_for(pool.init(), timeout=2)
    await asyncio.wait_for(pool.execute("create table test_table (value int, float_value float);"), timeout=2)
    await asyncio.wait_for(pool.execute("insert into test_table(value, float_value) values (1, 1.11), (2, 2.22);"), timeout=2)
    data = await pool.fetch("select * from test_table order by value")
    assert data == [{"value": 1, "float_value": 1.11}, {"value": 2, "float_value": 2.22}]


async def test_odbcpool_close(mocker):
    """'OdbcPool.close' should close the pool connections"""
    pool_close_mock: AsyncMock = mocker.spy(aioodbc.Pool, "close")

    pool = OdbcPool(
        dsn="odbc://Driver=postgresql;Server=postgres;Port=5432;"
            "Database=postgres;UID=postgres;PWD=postgres",
        name="db1",
    )
    await pool.init()

    await pool.close()

    pool_close_mock.assert_called_once()

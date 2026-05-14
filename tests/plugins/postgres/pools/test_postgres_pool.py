import decimal
from unittest.mock import AsyncMock

import asyncpg
import pytest
import pytest_asyncio

from databases import Pool
from plugins.postgres.pools import PostgresPool
from plugins.postgres.pools.postgres_pool import _convert_decimal_to_float

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def close_pools(monkeypatch_module):
    """Automatically close all the pools created in the tests"""
    created_pools = []
    original_init = PostgresPool.init

    async def init_mock(self):
        nonlocal created_pools
        created_pools.append(self)
        await original_init(self)

    monkeypatch_module.setattr(PostgresPool, "init", init_mock)

    yield

    for pool in created_pools:
        await pool.close()


@pytest_asyncio.fixture(loop_scope="session", scope="function", autouse=True)
async def drop_test_tables():
    """Drop test tables from the database"""
    pool = PostgresPool(dsn="postgres://postgres:postgres@postgres:5432/postgres", name="db1")
    await pool.init()
    await pool.execute("drop table if exists test_table cascade")


@pytest.mark.parametrize("value", [1.234, 56.789])
async def test_convert_decimal_to_float(value):
    """'_convert_decimal_to_float' should convert a 'asyncpg.Record' object into a dict, converting
    all 'Decimal' fields to float"""
    pool = PostgresPool(dsn="postgres://postgres:postgres@postgres:5432/postgres", name="db1")
    await pool.init()

    async with pool._pool.acquire() as connection:
        data = await connection.fetch(f"select {value} as value, 'abc' as other_value")

    assert isinstance(data[0]["value"], decimal.Decimal)
    assert isinstance(data[0]["other_value"], str)

    result = _convert_decimal_to_float(data[0])

    assert result == {"value": value, "other_value": "abc"}
    assert isinstance(result["value"], float)
    assert isinstance(result["other_value"], str)


async def test_postgrespool_protocol():
    """'PostgresPool' should follow the 'Pool' protocol"""
    assert isinstance(PostgresPool, Pool)


@pytest.mark.parametrize(
    "dsn, connection_params",
    [
        ("postgres+asyncpg://postgres:postgres@postgres:5432/postgres", {}),
        ("postgres+asyncpg://postgres:postgres@postgres:5432/postgres", {"max_size": 123}),
        ("postgres://postgres:postgres@postgres:5432/postgres", {"min_size": 1, "max_size": 4}),
    ],
)
async def test_postgrespool_init(dsn, connection_params):
    """'PostgresPool' should create a pool with the provided parameters using the default parameters
    if one wasn't provided"""
    pool = PostgresPool(dsn=dsn, name="db1", **connection_params)
    await pool.init()

    if connection_params is None:
        assert pool._pool.get_min_size() == 0
        assert pool._pool.get_max_size() == 5
    else:
        assert pool._pool.get_min_size() == connection_params.get("min_size", 0)
        assert pool._pool.get_max_size() == connection_params.get("max_size", 5)

    result = await pool.fetch("select 1 as value")
    assert result == [{"value": 1}]


async def test_postgrespool_init_incorrect_password():
    """'PostgresPool.init' should raise an error if the password is incorrect"""
    pool = PostgresPool(dsn="postgres://postgres:wrong_password@postgres:5432/postgres", name="db1")
    with pytest.raises(asyncpg.InvalidPasswordError):
        await pool.init()


async def test_postgrespool_init_incorrect_database():
    """'PostgresPool.init' should raise an error if the database is incorrect"""
    pool = PostgresPool(dsn="postgres://postgres:postgres@postgres:5432/wrong_database", name="db1")
    with pytest.raises(asyncpg.InvalidCatalogNameError):
        await pool.init()


async def test_postgrespool_execute():
    """'PostgresPool.execute' should execute a query in the provided database"""
    pool = PostgresPool(dsn="postgres://postgres:postgres@postgres:5432/postgres", name="db1")
    await pool.init()

    await pool.execute("create table test_table (value int);")
    await pool.execute("insert into test_table values (1), (2);")
    data = await pool.fetch("select * from test_table order by value")
    assert data == [{"value": 1}, {"value": 2}]


async def test_postgrespool_fetch():
    """'PostgresPool.fetch' should execute a query in the provided database and return the result"""
    pool = PostgresPool(dsn="postgres://postgres:postgres@postgres:5432/postgres", name="db1")
    await pool.init()
    await pool.execute("create table test_table (value int, float_value float);")
    await pool.execute("insert into test_table(value, float_value) values (1, 1.11), (2, 2.22);")
    data = await pool.fetch("select * from test_table order by value")
    assert data == [{"value": 1, "float_value": 1.11}, {"value": 2, "float_value": 2.22}]


async def test_postgrespool_close(mocker):
    """'PostgresPool.close' should close the pool connections"""
    pool_close_mock: AsyncMock = mocker.spy(asyncpg.Pool, "close")

    pool = PostgresPool(dsn="postgres://postgres:postgres@postgres:5432/postgres", name="db1")
    await pool.init()

    await pool.close()

    pool_close_mock.assert_awaited_once()

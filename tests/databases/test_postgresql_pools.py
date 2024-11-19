import decimal

import asyncpg
import pytest
import pytest_asyncio

import src.databases.postgresql_pools as postgresql_pools
from src.configs import configs
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def keep_pools(monkeypatch_module):
    """Clear the pools in the beginning of the test module and recover it at the end, to not
    interfere with other test files"""
    monkeypatch_module.delitem(postgresql_pools._pools, "application")
    yield


@pytest_asyncio.fixture(loop_scope="session", scope="function")
async def drop_test_tables():
    """Drop test tables from the database"""
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "temp",
    )
    try:
        await postgresql_pools.execute("temp", "drop table test_table cascade")
    except asyncpg.exceptions.UndefinedTableError:
        pass


@pytest_asyncio.fixture(loop_scope="session", scope="function", autouse=True)
async def clear_pools(drop_test_tables):
    """Close all PostgreSQL pools between tests"""
    for pool_name in postgresql_pools._pools.keys():
        await postgresql_pools._close_pool(pool_name)
    postgresql_pools._pools.clear()


@pytest.mark.parametrize(
    "dsn, name, connection_params",
    [
        ("postgres://postgres:postgres@postgres:5432/postgres", "db1", None),
        ("postgres+asyncpg://postgres:postgres@postgres:5432/postgres", "db2", {"max_size": 123}),
        (
            "postgres://postgres:postgres@postgres:5432/postgres",
            "db2",
            {"min_size": 1, "max_size": 4}
        ),
    ],
)
async def test_create_pool(monkeypatch, dsn, name, connection_params):
    """'create_pool' should create a pool with the provided parameters using the default parameters
    if one wasn't provided and there isn't a configuration for it in the configs YAML file"""
    monkeypatch.setitem(configs.databases_pools_configs, name, connection_params)
    await postgresql_pools.create_pool(dsn, name)

    pool = postgresql_pools._pools[name]

    if connection_params is None:
        assert pool.get_min_size() == 0
        assert pool.get_max_size() == 5
    else:
        assert pool.get_min_size() == connection_params.get("min_size", 0)
        assert pool.get_max_size() == connection_params.get("max_size", 5)

    result = await postgresql_pools.fetch(name, "select 1 as value")
    assert result == [{"value": 1}]


async def test_execute():
    """'execute' should execute a query in the provided database"""
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "db1",
    )
    await postgresql_pools.execute("db1", "create table test_table (value int);")
    await postgresql_pools.execute("db1", "insert into test_table values (1), (2);")
    data = await postgresql_pools.fetch("db1", "select * from test_table order by value")
    assert data == [{"value": 1}, {"value": 2}]


async def test_execute_not_in_pool():
    """'execute' should raise a 'ValueError' exception if the provided database name doesn't exists
    in the pools"""
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "db1",
    )
    with pytest.raises(ValueError, match="Database 'not_a_db' not loaded in environment variables"):
        await postgresql_pools.execute("not_a_db", "select 1")


@pytest.mark.parametrize("value", [1.234, 56.789])
async def test_convert_decimal_to_float(value):
    """'_convert_decimal_to_float' should convert a 'asyncpg.Record' object into a dict, converting
    all 'Decimal' fields to float"""
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "db1",
    )
    async with postgresql_pools._pools["db1"].acquire() as connection:
        data = await connection.fetch(f"select {value} as value, 'abc' as other_value")

    assert isinstance(data[0]["value"], decimal.Decimal)
    assert isinstance(data[0]["other_value"], str)

    result = postgresql_pools._convert_decimal_to_float(data[0])

    assert result == {"value": value, "other_value": "abc"}
    assert isinstance(result["value"], float)
    assert isinstance(result["other_value"], str)


async def test_fetch():
    """'fetch' should execute a query in the provided database and return the result"""
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "db1",
    )
    await postgresql_pools.fetch("db1", "create table test_table (value int, float_value float);")
    await postgresql_pools.fetch(
        "db1", "insert into test_table(value, float_value) values (1, 1.11), (2, 2.22);"
    )
    data = await postgresql_pools.fetch("db1", "select * from test_table order by value")
    assert data == [{"value": 1, "float_value": 1.11}, {"value": 2, "float_value": 2.22}]


async def test_fetch_not_in_pool():
    """'fetch' should raise a 'ValueError' exception if the provided database name doesn't exists
    in the pools"""
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "db1",
    )
    with pytest.raises(ValueError, match="Database 'not_a_db' not loaded in environment variables"):
        await postgresql_pools.fetch("not_a_db", "select 1")


async def test_close_pool(caplog):
    """'_close_pool' should close a PostgreSQL pool"""
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "db1",
    )

    await postgresql_pools._close_pool("db1")

    assert postgresql_pools._pools["db1"].is_closing
    assert_message_in_log(caplog, "Pool 'db1' closed")


async def test_close(caplog):
    """'close' should close all PostgreSQL pools"""
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "db1",
    )
    await postgresql_pools.create_pool(
        "postgres://postgres:postgres@postgres:5432/postgres",
        "db2",
    )

    db1 = postgresql_pools._pools["db1"]
    db2 = postgresql_pools._pools["db2"]

    await postgresql_pools.close()

    assert len(postgresql_pools._pools) == 0

    assert db1.is_closing
    assert_message_in_log(caplog, "Pool 'db1' closed")
    assert db2.is_closing
    assert_message_in_log(caplog, "Pool 'db2' closed")

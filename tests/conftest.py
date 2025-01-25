import logging
import os
import random
import shutil
import string
import time
from pathlib import Path

import aiohttp
import alembic.command
import alembic.config
import pytest
import pytest_asyncio
import uvloop
from _pytest.monkeypatch import MonkeyPatch

import components.monitors_loader.monitors_loader as monitors_loader
import databases as databases
import internal_database as internal_database
import message_queue as message_queue
import module_loader as module_loader
import utils.app as app
from models import CodeModule, Monitor
from registry import registry
from tests.message_queue.utils import get_queue_items


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy to uvloop's policy"""
    return uvloop.EventLoopPolicy()


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Monkeypatch objet to be used in "module" scoped fixture"""
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="session")
def monkeypatch_session():
    """Monkeypatch objet to be used in "session" scoped fixture"""
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="session", autouse=True)
def cleanup_logging_handlers():
    yield

    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler):
            logging.root.removeHandler(handler)


@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def reset_motoserver():
    """Reset the moto server before each test session"""
    async with aiohttp.ClientSession() as session:
        async with session.post("http://motoserver:5000/moto-api/reset"):
            pass


@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def init_databases():
    """Start the database pools"""
    await databases.init()
    yield
    await databases.close()


@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def init_application_database():
    """Recreate all tables in the database for each test session"""

    def reset_database(connection, config):
        config.attributes["connection"] = connection
        alembic.command.downgrade(alembic_config, "base")
        alembic.command.upgrade(alembic_config, "head")

    alembic_config = alembic.config.Config("alembic.ini")
    async with internal_database.engine.begin() as connection:
        await connection.run_sync(reset_database, alembic_config)

    yield

    await internal_database.close()


@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def clean_database_environment(init_databases):
    """Clean the test database environment after the test session"""
    yield
    await databases.query_application('truncate "Monitors" cascade;')


@pytest_asyncio.fixture(loop_scope="session", scope="function")
async def clear_database(init_databases):
    """Clear all the tables by truncating the Monitors table"""
    await databases.query_application('truncate "Monitors" cascade;')


@pytest.fixture(scope="session", autouse=True)
def _temp_dir(monkeypatch_session):
    """Create a temporary directory for all the tests that will be removed at the end"""
    os.makedirs("src/tmp", exist_ok=True)
    monkeypatch_session.setattr(monitors_loader, "MONITORS_LOAD_PATH", "tmp")
    monkeypatch_session.setattr(module_loader.loader, "MODULES_PATH", "tmp")
    yield "src/tmp"
    shutil.rmtree("src/tmp", ignore_errors=True)


@pytest.fixture(scope="function")
def temp_dir(_temp_dir):
    """Create a temporary directory for a test"""
    folder_name = "".join(random.choice(string.ascii_lowercase) for _ in range(15))
    temp_path = os.path.join(_temp_dir, folder_name)
    os.makedirs(temp_path, exist_ok=True)
    yield Path(temp_path)


@pytest.fixture(scope="function", autouse=True)
def app_running():
    """Set the app running for each test"""
    app._stop_event.clear()


@pytest.fixture(scope="function", autouse=True)
def clear_monitors():
    """Clear all the monitors for each test"""
    registry._monitors = {}
    registry.init()


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def start_queue():
    """Reset the queue for each new test file"""
    await message_queue.init()


@pytest.fixture(scope="function")
def clear_queue():
    """Clear the internal queue. Ignoring the 'attr-defined' error because the Protocol doesn't
    have the attribute '_queue', but the 'InternalQueue' class does"""
    get_queue_items()


@pytest.fixture(scope="session")
def sample_monitor_code():
    """Sample monitor code to be used in the tests"""
    with open("tests/sample_monitor_code.py") as file:
        return file.read()


@pytest_asyncio.fixture(loop_scope="session", scope="function")
async def sample_monitor(clear_monitors, sample_monitor_code) -> Monitor:
    """Create a sample monitor to be used in the test"""
    monitor_name = f"test_monitor_{int(time.time() * 1000000)}"

    new_monitor = await Monitor.create(name=monitor_name)
    await CodeModule.create(monitor_id=new_monitor.id, code=sample_monitor_code)
    monitor_path = module_loader.create_module_files(monitor_name, sample_monitor_code)
    module = module_loader.load_module_from_file(monitor_path)

    registry.add_monitor(new_monitor.id, new_monitor.name, module)

    return new_monitor

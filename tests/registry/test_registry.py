import asyncio
import time
from types import ModuleType

import pytest

import src.registry.registry as registry

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_wait_monitors_ready(monkeypatch):
    """'_wait_monitors_ready' should wait for the registry monitors to be ready and don't raise an
    exception if the timeout is not reached"""
    monkeypatch.setattr(registry, "MONITORS_READY_TIMEOUT", 0.2)
    registry.monitors_ready.clear()

    start_time = time.perf_counter()
    wait_monitors_ready_task = asyncio.create_task(registry.wait_monitors_ready())
    await asyncio.sleep(0.1)
    assert not wait_monitors_ready_task.done()
    registry.monitors_ready.set()
    await wait_monitors_ready_task
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time >= 0.1 - 0.001
    assert total_time < 0.1 + 0.005


async def test_wait_monitors_ready_timeout(monkeypatch):
    """'_wait_monitors_ready' should wait for the registry monitors to be ready and raise a
    'MonitorsLoadError' exception if the timeout is reached"""
    monkeypatch.setattr(registry, "MONITORS_READY_TIMEOUT", 0.2)
    registry.monitors_ready.clear()

    start_time = time.perf_counter()
    exception_message = "MonitorsLoadError: Waiting for monitors to be ready timed out"
    with pytest.raises(registry.MonitorsLoadError, match=exception_message):
        await registry.wait_monitors_ready()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time >= 0.2 - 0.001
    assert total_time < 0.2 + 0.005


async def test_is_monitor_registered():
    """'is_monitor_registered' should return True if the monitor is registered"""
    registry.add_monitor(1, "Monitor 1", ModuleType(name="MockMonitorModule1"))
    registry.add_monitor(2, "Monitor 2", ModuleType(name="MockMonitorModule2"))
    registry.add_monitor(3, "Monitor 3", ModuleType(name="MockMonitorModule3"))

    assert registry.is_monitor_registered(1)
    assert registry.is_monitor_registered(2)
    assert registry.is_monitor_registered(3)
    assert not registry.is_monitor_registered(4)


async def test_get_monitors():
    """'get_monitors' should return all the registered monitors"""
    registry.add_monitor(1, "Monitor 1", ModuleType(name="MockMonitorModule1"))
    registry.add_monitor(2, "Monitor 2", ModuleType(name="MockMonitorModule2"))
    registry.add_monitor(3, "Monitor 3", ModuleType(name="MockMonitorModule3"))

    monitors = registry.get_monitors()

    assert len(monitors) == 3
    assert all(isinstance(monitor["module"], ModuleType) for monitor in monitors)
    assert {monitor["name"] for monitor in monitors} == {"Monitor 1", "Monitor 2", "Monitor 3"}


async def test_get_monitor_module():
    """'get_monitor_module' should return the monitor module by the given ID"""
    module_1 = ModuleType(name="MockMonitorModule1")
    module_2 = ModuleType(name="MockMonitorModule2")
    module_3 = ModuleType(name="MockMonitorModule3")
    registry.add_monitor(1, "Monitor 1", module_1)
    registry.add_monitor(2, "Monitor 2", module_2)
    registry.add_monitor(3, "Monitor 3", module_3)

    assert registry._monitors[1]["name"] == "Monitor 1"
    assert registry._monitors[1]["module"] == module_1
    assert registry.get_monitor_module(1) == module_1
    assert registry._monitors[2]["name"] == "Monitor 2"
    assert registry._monitors[2]["module"] == module_2
    assert registry.get_monitor_module(2) == module_2
    assert registry._monitors[3]["name"] == "Monitor 3"
    assert registry._monitors[3]["module"] == module_3
    assert registry.get_monitor_module(3) == module_3


async def test_init():
    """'init' should reset the 'monitors_ready' and 'monitors_pending' events to their initial
    states"""
    registry.monitors_ready.set()
    registry.monitors_pending.clear()

    registry.init()

    assert not registry.monitors_ready.is_set()
    assert registry.monitors_pending.is_set()

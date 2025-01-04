import asyncio
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

import components.monitors_loader.monitors_loader as monitors_loader
import databases.databases as databases
import utils.app as app
import utils.time as time_utils
from configs import configs
from models import CodeModule, Monitor
from options import ReactionOptions
from registry import registry
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize("file, extensions, expected", [
    ("file.py", ["py"], True),
    ("file.py", ["txt"], False),
    ("file.txt", ["py"], False),
    ("file.txt", ["txt"], True),
    ("file.txt", ["py", "txt"], True),
    ("file.txt", ["txt", "py"], True),
])
async def test_file_has_extension(file, extensions, expected):
    """'_file_has_extension' should return True if the file has any of the given extensions"""
    assert monitors_loader._file_has_extension(file, extensions) == expected


async def test_get_monitors_files_from_path():
    """'_get_monitors_files_from_path' should return all the monitors files from a path"""
    monitors_files = list(monitors_loader._get_monitors_files_from_path("tests/sample_monitors"))

    assert len(monitors_files) == 3
    monitors_files = list(sorted(
        monitors_files, key=lambda monitor_files: monitor_files.monitor_name
    ))
    assert monitors_files == [
        monitors_loader.MonitorFiles(
            monitor_name="monitor_1",
            monitor_path=Path("tests/sample_monitors/others/monitor_1/monitor_1.py"),
            additional_files=[],
        ),
        monitors_loader.MonitorFiles(
            monitor_name="monitor_2",
            monitor_path=Path("tests/sample_monitors/internal/monitor_2/monitor_2.py"),
            additional_files=[],
        ),
        monitors_loader.MonitorFiles(
            monitor_name="monitor_3",
            monitor_path=Path("tests/sample_monitors/internal/monitor_3/monitor_3.py"),
            additional_files=[],
        ),
    ]


async def test_get_monitors_files_from_path_with_additional_files():
    """'_get_monitors_files_from_path' should return all the monitors files from a path including
    their additional files"""
    monitors_files = list(monitors_loader._get_monitors_files_from_path(
        "tests/sample_monitors/internal", additional_file_extensions=["sql"]
    ))

    assert len(monitors_files) == 2
    monitors_files = list(sorted(
        monitors_files, key=lambda monitor_files: monitor_files.monitor_name
    ))
    for monitor_files in monitors_files:
        monitor_files.additional_files = list(sorted(
            monitor_files.additional_files, key=lambda additional_file: additional_file.name
        ))
    assert monitors_files == [
        monitors_loader.MonitorFiles(
            monitor_name="monitor_2",
            monitor_path=Path("tests/sample_monitors/internal/monitor_2/monitor_2.py"),
            additional_files=[],
        ),
        monitors_loader.MonitorFiles(
            monitor_name="monitor_3",
            monitor_path=Path("tests/sample_monitors/internal/monitor_3/monitor_3.py"),
            additional_files=[
                monitors_loader.AdditionalFile(
                    name="other_file.sql",
                    path=Path("tests/sample_monitors/internal/monitor_3/other_file.sql")
                ),
                monitors_loader.AdditionalFile(
                    name="some_file.sql",
                    path=Path("tests/sample_monitors/internal/monitor_3/some_file.sql")
                ),
            ],
        ),
    ]


async def test_get_monitors_files_from_path_no_python_files():
    """'_get_monitors_files_from_path' should return an empty generator if there are no python
    files in the path"""
    monitors_files = list(monitors_loader._get_monitors_files_from_path("docs"))

    assert len(monitors_files) == 0


@pytest.mark.parametrize("additional_files", [
    None,
    {"file_1.sql": "SELECT * FROM table_1;"},
    {"file_1.sql": "SELECT * FROM table_1;", "file_2.sql": "SELECT * FROM table_2;"},
])
async def test_register_monitor(additional_files):
    """'register_monitor' function should register a monitor with the provided name and module
    code"""
    monitor_name = "test_register_monitor"

    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    monitor = await monitors_loader.register_monitor(
        monitor_name, monitor_code, additional_files=additional_files
    )

    assert monitor.name == monitor_name

    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)
    assert code_module is not None
    assert code_module.code == monitor_code
    assert code_module.additional_files == (additional_files or {})


@pytest.mark.parametrize("additional_files", [
    None,
    {"file_1.sql": "SELECT * FROM table_1;"},
    {"file_1.sql": "SELECT * FROM table_1;", "file_2.sql": "SELECT * FROM table_2;"},
])
async def test_register_monitor_monitor_already_exists(additional_files):
    """'register_monitor' should update an existing monitor's module code if the monitor already
    exists, without changing other fields"""
    monitor_name = "test_register_monitor_monitor_already_exists"
    timestamp = time_utils.now()

    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    monitor = await monitors_loader.register_monitor(
        monitor_name, monitor_code, additional_files=additional_files
    )
    monitor.search_executed_at = timestamp
    monitor.update_executed_at = timestamp
    await monitor.save()

    assert monitor.name == monitor_name

    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)
    assert code_module is not None
    assert code_module.code == monitor_code

    new_monitor_code = monitor_code.replace("b: str", "c: str")
    if additional_files is not None:
        new_additional_files = {
            file_name: file_content.replace("table", "tables")
            for file_name, file_content in additional_files.items()
        }
    else:
        new_additional_files = {"file_9.sql": "SELECT * FROM tables_9;"}

    monitor = await monitors_loader.register_monitor(
        monitor_name, new_monitor_code, additional_files=new_additional_files
    )

    await monitor.refresh()
    assert monitor.search_executed_at == timestamp
    assert monitor.update_executed_at == timestamp

    await code_module.refresh()
    assert code_module.code == monitor_code
    assert code_module.additional_files == new_additional_files


async def test_register_monitor_monitor_already_exists_error():
    """'register_monitor' should not update an existing monitor's module code if the monitor already
    exists and the new code has validation errors"""
    monitor_name = "test_register_monitor_monitor_already_exists_error"
    timestamp = time_utils.now()

    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    monitor = await monitors_loader.register_monitor(
        monitor_name, monitor_code, additional_files={"file_1.sql": "SELECT * FROM table_1;"}
    )
    monitor.search_executed_at = timestamp
    monitor.update_executed_at = timestamp
    await monitor.save()

    assert monitor.name == monitor_name

    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)
    assert code_module is not None
    assert code_module.code == monitor_code
    assert code_module.additional_files == {"file_1.sql": "SELECT * FROM table_1;"}

    new_monitor_code = monitor_code.replace("id: str", "not_id: str")
    new_monitor_code = new_monitor_code.replace("issues_data", "issue_data")
    new_additional_files = {
        "file_1.sql": "SELECT * FROM table_1;",
        "file_2.sql": "SELECT * FROM table_2;",
    }

    try:
        await monitors_loader.register_monitor(
            monitor_name, new_monitor_code, additional_files=new_additional_files
        )
    except monitors_loader.MonitorValidationError as exception:
        assert exception.monitor_name == monitor_name
        assert (
            "'IssueDataType' must have the 'id' field, as specified by 'issue_options.model_id_key'"
            in exception.errors_found
        )
        assert (
            "'update' function must have arguments 'issues_data: list[IssueDataType]'"
            in exception.errors_found
        )

    await monitor.refresh()
    assert monitor.search_executed_at == timestamp
    assert monitor.update_executed_at == timestamp

    await code_module.refresh()
    assert code_module.code == monitor_code
    assert code_module.additional_files == {"file_1.sql": "SELECT * FROM table_1;"}


async def test_register_monitor_validation_error():
    """'register_monitor' function should raise a 'MonitorValidationError' if the monitor module
    does not pass the validation"""
    monitor_name = "test_register_monitor"

    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    # Add errors that should be caught by the validation
    monitor_code = monitor_code.replace("id: str", "not_id: str")
    monitor_code = monitor_code.replace("issues_data", "issue_data")

    try:
        await monitors_loader.register_monitor(monitor_name, monitor_code)
    except monitors_loader.MonitorValidationError as exception:
        assert exception.monitor_name == monitor_name
        assert (
            "'IssueDataType' must have the 'id' field, as specified by 'issue_options.model_id_key'"
            in exception.errors_found
        )
        assert (
            "'update' function must have arguments 'issues_data: list[IssueDataType]'"
            in exception.errors_found
        )


async def test_register_monitors_from_path(clear_database):
    """'_register_monitors_from_path' should register all the monitors from a path"""
    registered_monitors = await Monitor.get_all()

    assert len(registered_monitors) == 0

    await monitors_loader._register_monitors_from_path("tests/sample_monitors")

    registered_monitors = await Monitor.get_all()
    monitors_ids = [monitor.id for monitor in registered_monitors]
    code_modules = await CodeModule.get_all(CodeModule.monitor_id.in_(monitors_ids))

    assert len(registered_monitors) == 3
    expected_monitors = {"monitor_1", "monitor_2", "monitor_3"}
    assert {monitor.name for monitor in registered_monitors} == expected_monitors
    assert all(code_module.additional_files == {} for code_module in code_modules)


async def test_register_monitors_from_path_additional_files(clear_database):
    """'_register_monitors_from_path' should register all the monitors from a path, including their
    additional files"""
    registered_monitors = await Monitor.get_all()

    assert len(registered_monitors) == 0

    await monitors_loader._register_monitors_from_path(
        "tests/sample_monitors", additional_file_extensions=["sql"]
    )

    registered_monitors = await Monitor.get_all()
    monitors_ids = [monitor.id for monitor in registered_monitors]
    code_modules = await CodeModule.get_all(CodeModule.monitor_id.in_(monitors_ids))
    code_modules_dict = {code_module.monitor_id: code_module for code_module in code_modules}

    assert len(registered_monitors) == 3
    expected_monitors = {"monitor_1", "monitor_2", "monitor_3"}
    assert {monitor.name for monitor in registered_monitors} == expected_monitors

    for monitor in registered_monitors:
        if monitor.name == "monitor_3":
            assert code_modules_dict[monitor.id].additional_files == {
                "some_file.sql": "select 1;\n",
                "other_file.sql": "select 2;\n",
            }
        else:
            assert code_modules_dict[monitor.id].additional_files == {}


async def test_register_monitors_from_path_internal(clear_database):
    """'_register_monitors_from_path' should register all the internal monitors from a path"""
    registered_monitors = await Monitor.get_all()

    assert len(registered_monitors) == 0

    await monitors_loader._register_monitors_from_path("tests/sample_monitors", internal=True)

    registered_monitors = await Monitor.get_all()

    assert len(registered_monitors) == 3
    expected_monitors = {"internal.monitor_1", "internal.monitor_2", "internal.monitor_3"}
    assert {monitor.name for monitor in registered_monitors} == expected_monitors


async def test_register_monitors_from_path_validation_error(caplog, monkeypatch, clear_database):
    """'_register_monitors_from_path' should log the errors if a monitor was not loaded and not
    register the monitor"""
    async def register_monitor_error_mock(monitor_name, monitor_code, additional_files):
        raise monitors_loader.MonitorValidationError(monitor_name="monitor", errors_found=[])

    monkeypatch.setattr(monitors_loader, "register_monitor", register_monitor_error_mock)

    registered_monitors = await Monitor.get_all()

    assert len(registered_monitors) == 0

    await monitors_loader._register_monitors_from_path("tests/sample_monitors")

    registered_monitors = await Monitor.get_all()
    assert len(registered_monitors) == 0

    assert_message_in_log(caplog, "Monitor 'monitor_1' not registered")
    assert_message_in_log(caplog, "Monitor 'monitor_2' not registered")
    assert_message_in_log(caplog, "Monitor 'monitor_3' not registered")


async def test_register_monitors_from_path_error(caplog, monkeypatch, clear_database):
    """'_register_monitors_from_path' should log the errors if a monitor was not loaded and not
    register the monitor"""
    async def register_monitor_error_mock(monitor_name, monitor_code, additional_files):
        raise ValueError("Some error")

    monkeypatch.setattr(monitors_loader, "register_monitor", register_monitor_error_mock)

    registered_monitors = await Monitor.get_all()

    assert len(registered_monitors) == 0

    await monitors_loader._register_monitors_from_path("tests/sample_monitors")

    registered_monitors = await Monitor.get_all()
    assert len(registered_monitors) == 0

    assert_message_in_log(caplog, "ValueError: Some error", count=3)


async def test_register_monitors(monkeypatch, clear_database):
    """'register_monitors' should register all the internal and sample monitors if enabled,
    including their additional files"""
    monkeypatch.setattr(configs, "load_sample_monitors", True)
    monkeypatch.setattr(configs, "internal_monitors_path", "tests/sample_monitors/internal")
    monkeypatch.setattr(configs, "sample_monitors_path", "tests/sample_monitors/others")

    registered_monitors = await Monitor.get_all()

    assert len(registered_monitors) == 0

    await monitors_loader._register_monitors()

    registered_monitors = await Monitor.get_all()
    monitors_ids = [monitor.id for monitor in registered_monitors]
    code_modules = await CodeModule.get_all(CodeModule.monitor_id.in_(monitors_ids))
    code_modules_dict = {code_module.monitor_id: code_module for code_module in code_modules}

    assert len(registered_monitors) == 3
    expected_monitors = {"monitor_1", "internal.monitor_2", "internal.monitor_3"}
    assert {monitor.name for monitor in registered_monitors} == expected_monitors

    for monitor in registered_monitors:
        if monitor.name == "internal.monitor_3":
            assert code_modules_dict[monitor.id].additional_files == {
                "some_file.sql": "select 1;\n",
                "other_file.sql": "select 2;\n",
            }
        else:
            assert code_modules_dict[monitor.id].additional_files == {}


async def test_register_monitors_no_sample_monitors(monkeypatch, clear_database):
    """'register_monitors' should register all the internal monitors but not the sample monitors if
    it's disabled"""
    monkeypatch.setattr(configs, "load_sample_monitors", False)
    monkeypatch.setattr(configs, "internal_monitors_path", "tests/sample_monitors/internal")
    monkeypatch.setattr(configs, "sample_monitors_path", "tests/sample_monitors/others")

    registered_monitors = await Monitor.get_all()

    assert len(registered_monitors) == 0

    await monitors_loader._register_monitors()

    registered_monitors = await Monitor.get_all()
    monitors_ids = [monitor.id for monitor in registered_monitors]
    code_modules = await CodeModule.get_all(CodeModule.monitor_id.in_(monitors_ids))
    code_modules_dict = {code_module.monitor_id: code_module for code_module in code_modules}

    assert len(registered_monitors) == 2
    expected_monitors = {"internal.monitor_2", "internal.monitor_3"}
    assert {monitor.name for monitor in registered_monitors} == expected_monitors

    for monitor in registered_monitors:
        if monitor.name == "internal.monitor_3":
            assert code_modules_dict[monitor.id].additional_files == {
                "some_file.sql": "select 1;\n",
                "other_file.sql": "select 2;\n",
            }
        else:
            assert code_modules_dict[monitor.id].additional_files == {}


async def test_configure_monitor(monkeypatch, sample_monitor: Monitor):
    """'_configure_monitor' should populate the 'reaction_options' and 'notification_options' with
    the default values"""
    monitor_module = sample_monitor.code
    monkeypatch.setattr(monitor_module, "reaction_options", None, raising=False)
    monkeypatch.setattr(monitor_module, "notification_options", None, raising=False)

    assert getattr(monitor_module, "reaction_options", None) is None
    assert getattr(monitor_module, "notification_options", None) is None

    monitors_loader._configure_monitor(monitor_module)

    assert isinstance(monitor_module.reaction_options, ReactionOptions)
    assert monitor_module.notification_options == []


async def test_configure_monitor_notifications_setup(monkeypatch, sample_monitor: Monitor):
    """'_configure_monitor' should extend the reactions in the 'reaction_options' fields with the
    reactions from the notifications from the 'notification_options'"""
    async def do_something(): ...
    async def do_nothing(): ...

    monitor_module = sample_monitor.code
    monkeypatch.setattr(
        monitor_module,
        "reaction_options",
        ReactionOptions(alert_updated=[do_something]),
        raising=False,
    )

    class MockNotification:
        min_priority_to_send = 5

        def reactions_list(self):
            return [
                ("alert_updated", [do_nothing]),
                ("alert_solved", [do_nothing, "do_nothing"]),
            ]

    monkeypatch.setattr(monitor_module, "notification_options", [MockNotification()], raising=False)

    monitors_loader._configure_monitor(monitor_module)

    assert monitor_module.reaction_options.alert_updated == [do_something, do_nothing]
    assert monitor_module.reaction_options.alert_solved == [do_nothing, "do_nothing"]


async def test_load_monitors(clear_database):
    """'_load_monitors' should load all enabled monitors from the database and add them to the
    registry"""
    await databases.execute_application(
        'insert into "Monitors"(id, name, enabled) values'
        "(9999123, 'monitor_1', true),"
        "(9999456, 'internal.monitor_2', true),"
        "(9999457, 'disabled_monitor', false);"
    )
    await databases.execute_application(
        'insert into "CodeModules"(monitor_id, code) values'
        "(9999123, 'def get_value(): return 10'),"
        "(9999456, 'def get_value(): return 11'),"
        "(9999457, 'def get_value(): return 12');"
    )

    await monitors_loader._load_monitors()

    assert len(registry._monitors) == 2
    assert isinstance(registry._monitors[9999123]["module"], ModuleType)
    assert isinstance(registry._monitors[9999456]["module"], ModuleType)


async def test_load_monitors_monitors_ready_flag(monkeypatch, clear_database):
    """'_load_monitors' should clear and set the registry's 'monitors_ready' while loading the
    monitors"""
    monitor_get_all = Monitor.get_all

    async def slow_get_all(self, *args, **kwargs):
        await asyncio.sleep(0.2)
        return await monitor_get_all(self, *args, **kwargs)

    monkeypatch.setattr(Monitor, "get_all", slow_get_all)

    await databases.execute_application(
        'insert into "Monitors"(id, name, enabled) values'
        "(9999123, 'monitor_1', true);"
    )
    await databases.execute_application(
        'insert into "CodeModules"(monitor_id, code) values'
        "(9999123, 'def get_value(): return 10');"
    )

    registry.monitors_ready.set()
    registry.monitors_pending.set()
    assert registry.monitors_ready.is_set()
    assert registry.monitors_pending.is_set()

    load_monitors_task = asyncio.create_task(monitors_loader._load_monitors())

    await asyncio.sleep(0.1)
    assert not registry.monitors_ready.is_set()

    await load_monitors_task

    assert registry.monitors_ready.is_set()
    assert not registry.monitors_pending.is_set()


async def test_load_monitors_monitor_without_code_module(caplog, monkeypatch, clear_database):
    """'_load_monitors' should disable the monitor if it doesn't have a code module"""
    monitor_get_all = Monitor.get_all

    async def slow_get_all(self, *args, **kwargs):
        await asyncio.sleep(0.2)
        return await monitor_get_all(self, *args, **kwargs)

    monkeypatch.setattr(Monitor, "get_all", slow_get_all)

    await databases.execute_application(
        'insert into "Monitors"(id, name, enabled) values'
        "(9999123, 'monitor_1', true);"
    )

    await monitors_loader._load_monitors()

    monitor = await Monitor.get_by_id(9999123)
    assert monitor is not None
    assert not monitor.enabled

    assert len(registry._monitors) == 0
    assert_message_in_log(caplog, "Monitor 'monitor_1' has no code module, it will be disabled")


async def test_load_monitors_error(caplog, clear_database):
    """'_load_monitors' should load all the monitors from the database and add them to the
    registry, even if an error occurs while loading any of them. Monitors with errors will not be
    added to the registry"""
    await databases.execute_application(
        'insert into "Monitors"(id, name, enabled) values'
        "(9999123, 'monitor_1', true),"
        "(9999456, 'internal.monitor_2', true);"
    )
    await databases.execute_application(
        'insert into "CodeModules"(monitor_id, code) values'
        "(9999123, 'invalid code'),"
        "(9999456, 'def get_value(): return 10');"
    )

    await monitors_loader._load_monitors()

    assert len(registry._monitors) == 1
    assert isinstance(registry._monitors[9999456]["module"], ModuleType)
    assert_message_in_log(caplog, "SyntaxError: invalid syntax")
    assert_message_in_log(caplog, "Exception caught successfully, going on")


async def test_run_as_controller(mocker, monkeypatch, clear_database):
    """Integration test of the 'monitors_loader' task running with the controller.
    It should update all internal monitors and sample monitors in the database at it's startup
    process.
    At each loop it should load all the monitors from the database and add them to the registry,
    while also checking for pending monitors, indicating that a reload is needed.
    When the app stops, the service's task should stop automatically"""
    # Disable the monitor loading schedule to control using the 'monitors_pending' event
    monkeypatch.setattr(configs, "monitors_load_schedule", "0 0 1 1 1")
    monkeypatch.setattr(configs, "load_sample_monitors", False)
    monkeypatch.setattr(configs, "internal_monitors_path", "tests/sample_monitors/internal")
    monkeypatch.setattr(configs, "sample_monitors_path", "tests/sample_monitors/others")
    monkeypatch.setattr(monitors_loader, "COOL_DOWN_TIME", 0)

    _load_monitors_spy: AsyncMock = mocker.spy(monitors_loader, "_load_monitors")

    # The monitors already exist in the database, so prevent from trying to reload them
    await monitors_loader.init(controller_enabled=True)

    for _ in range(3):
        await asyncio.sleep(0.1)
        registry.monitors_pending.set()

    await asyncio.sleep(0.1)
    app.stop()
    await monitors_loader.wait_stop()

    assert _load_monitors_spy.call_count == 4

    assert monitors_loader._task.done()

    assert len(registry._monitors) == 2


async def test_run_as_executor(mocker, monkeypatch, clear_database):
    """Integration test of the 'monitors_loader' task running with the executor.
    It should not update all internal monitors and sample monitors in the database.
    At each loop it should load all the monitors from the database and add them to the registry,
    while also checking for pending monitors, indicating that a reload is needed.
    When the app stops, the service's task should stop automatically"""
    # Disable the monitor loading schedule to control using the 'monitors_pending' event
    monkeypatch.setattr(configs, "monitors_load_schedule", "0 0 1 1 1")
    monkeypatch.setattr(monitors_loader, "COOL_DOWN_TIME", 0)

    _load_monitors_spy: AsyncMock = mocker.spy(monitors_loader, "_load_monitors")

    await databases.execute_application(
        'insert into "Monitors"(id, name, enabled) values'
        "(9999123, 'monitor_1', true),"
        "(9999456, 'internal.monitor_2', true),"
        "(9999457, 'disabled_monitor', false);"
    )
    await databases.execute_application(
        'insert into "CodeModules"(monitor_id, code) values'
        "(9999123, 'def get_value(): return 10'),"
        "(9999456, 'def get_value(): return 10'),"
        "(9999457, 'def get_value(): return 10');"
    )

    # The monitors already exist in the database, so prevent from trying to reload them
    await monitors_loader.init(controller_enabled=False)

    for _ in range(3):
        await asyncio.sleep(0.1)
        registry.monitors_pending.set()

    await asyncio.sleep(0.1)
    app.stop()
    await monitors_loader.wait_stop()

    assert _load_monitors_spy.call_count == 4

    assert monitors_loader._task.done()

    assert len(registry._monitors) == 2
    assert isinstance(registry._monitors[9999123]["module"], ModuleType)
    assert isinstance(registry._monitors[9999456]["module"], ModuleType)


async def test_run_cool_down(mocker, monkeypatch, clear_database):
    """Integration test of the 'monitors_loader' task.
    At each loop it should check for when the previous load was done, and if it was too recent,
    wait for the cool down time to pass before loading the monitors again.
    When the app stops, the service's task should stop automatically"""
    # Disable the monitor loading schedule to control using the 'monitors_pending' event
    monkeypatch.setattr(configs, "monitors_load_schedule", "0 0 1 1 1")
    monkeypatch.setattr(monitors_loader, "COOL_DOWN_TIME", 2)

    _load_monitors_spy: AsyncMock = mocker.spy(monitors_loader, "_load_monitors")

    await databases.execute_application(
        'insert into "Monitors"(id, name, enabled) values'
        "(9999123, 'monitor_1', true),"
        "(9999456, 'internal.monitor_2', true),"
        "(9999457, 'disabled_monitor', false);"
    )
    await databases.execute_application(
        'insert into "CodeModules"(monitor_id, code) values'
        "(9999123, 'def get_value(): return 10'),"
        "(9999456, 'def get_value(): return 10'),"
        "(9999457, 'def get_value(): return 10');"
    )

    # The monitors already exist in the database, so prevent from trying to reload them
    await monitors_loader.init(controller_enabled=False)

    for _ in range(3):
        await asyncio.sleep(0.1)
        registry.monitors_pending.set()

    await asyncio.sleep(0.1)
    app.stop()
    await monitors_loader.wait_stop()

    assert _load_monitors_spy.call_count == 1

    assert monitors_loader._task.done()

    assert len(registry._monitors) == 2
    assert isinstance(registry._monitors[9999123]["module"], ModuleType)
    assert isinstance(registry._monitors[9999456]["module"], ModuleType)

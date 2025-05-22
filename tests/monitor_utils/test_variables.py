import pytest

from models import Monitor, Variable
from monitor_utils.variables import _get_monitor_id, get_variable, set_variable

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize("monitor_id", [123, 456, 789])
async def test_get_monitor_id(monitor_id):
    """'_get_monitor_id' should return the monitor ID from the module if SENTINELA_MONITOR_ID is
    set"""

    class Module:
        SENTINELA_MONITOR_ID = monitor_id

    result = _get_monitor_id(Module())
    assert result == monitor_id


async def test_get_monitor_id_with_none():
    """'_get_monitor_id' should raise ValueError if SENTINELA_MONITOR_ID is None"""

    class Module:
        SENTINELA_MONITOR_ID = None

    expected_error_message = (
        "Function called outside a monitor or the monitor was not loaded properly"
    )
    with pytest.raises(ValueError, match=expected_error_message):
        _get_monitor_id(Module())


async def test_get_monitor_id_without_attribute():
    """'_get_monitor_id' should raise ValueError if SENTINELA_MONITOR_ID is not defined"""

    class Module:
        pass

    expected_error_message = (
        "Function called outside a monitor or the monitor was not loaded properly"
    )
    with pytest.raises(ValueError, match=expected_error_message):
        _get_monitor_id(Module())


@pytest.mark.parametrize(
    "variable_name, variable_value",
    [("test_var", "test_value"), ("another_var", "another_value"), ("empty_var", None)],
)
async def test_set_variable(sample_monitor: Monitor, variable_name, variable_value):
    """'set_variable' should set a variable for the monitor"""
    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        await call_function(set_variable, variable_name, variable_value)

    await f()

    variables = await Variable.get_all(Variable.monitor_id == sample_monitor.id)
    assert len(variables) == 1

    assert variables[0].monitor_id == sample_monitor.id
    assert variables[0].name == variable_name
    assert variables[0].value == variable_value


async def test_set_variable_multiple_variables(sample_monitor: Monitor):
    """'set_variable' should set multiple different variables for the same monitor"""
    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        await call_function(set_variable, "var1", "value1")
        await call_function(set_variable, "var2", "value2")
        await call_function(set_variable, "var3", None)

    await f()

    variables = await Variable.get_all(Variable.monitor_id == sample_monitor.id)
    assert len(variables) == 3

    variables_dict = {var.name: var.value for var in variables}
    expected_variables = {"var1": "value1", "var2": "value2", "var3": None}
    assert variables_dict == expected_variables


async def test_set_variable_update_existing(sample_monitor: Monitor):
    """'set_variable' should update an existing variable if it already exists"""
    await Variable.create(
        monitor_id=sample_monitor.id,
        name="test_var",
        value="initial_value",
    )

    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        await call_function(set_variable, "test_var", "updated_value")

    await f()

    variables = await Variable.get_all(Variable.monitor_id == sample_monitor.id)
    assert len(variables) == 1
    assert variables[0].name == "test_var"
    assert variables[0].value == "updated_value"


async def test_set_variable_monitor_id_none(monkeypatch, sample_monitor: Monitor):
    """'set_variable' should raise 'ValueError' if 'SENTINELA_MONITOR_ID' is None"""
    monkeypatch.setattr(sample_monitor.code, "SENTINELA_MONITOR_ID", None, raising=False)

    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        await call_function(set_variable, "test_var", "test_value")

    expected_error_message = (
        "Function called outside a monitor or the monitor was not loaded properly"
    )
    with pytest.raises(ValueError, match=expected_error_message):
        await f()


@pytest.mark.parametrize(
    "variable_name, variable_value",
    [("test_var", "test_value"), ("another_var", "another_value"), ("empty_var", None)],
)
async def test_get_variable(sample_monitor: Monitor, variable_name, variable_value):
    """'get_variable' should get a variable for the monitor"""
    await Variable.create(
        monitor_id=sample_monitor.id,
        name=variable_name,
        value=variable_value,
    )

    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        result = await call_function(get_variable, variable_name)
        assert result == variable_value

    await f()


async def test_get_variable_none_value(sample_monitor: Monitor):
    """'get_variable' should be able to get a variable with 'None' value"""
    await Variable.create(
        monitor_id=sample_monitor.id,
        name="test_var",
        value=None,
    )

    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        assert await call_function(get_variable, "test_var") is None

    await f()


async def test_get_variable_not_exists(sample_monitor: Monitor):
    """'get_variable' should not raise an error if the variable does not exist and return None"""
    variable = await Variable.get(
        Variable.monitor_id == sample_monitor.id,
        Variable.name == "non_existent_var",
    )
    assert variable is None

    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        assert await call_function(get_variable, "non_existent_var") is None

    await f()


async def test_get_variable_multiple_variables(sample_monitor: Monitor):
    """'get_variable' should correctly retrieve specific variables when multiple exist"""
    await Variable.create(
        monitor_id=sample_monitor.id,
        name="var1",
        value="value1",
    )
    await Variable.create(
        monitor_id=sample_monitor.id,
        name="var2",
        value="value2",
    )

    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        assert await call_function(get_variable, "var1") == "value1"
        assert await call_function(get_variable, "var2") == "value2"

    await f()


async def test_get_variable_monitor_id_none(monkeypatch, sample_monitor: Monitor):
    """'get_variable' should raise ValueError if SENTINELA_MONITOR_ID is None"""
    monkeypatch.setattr(sample_monitor.code, "SENTINELA_MONITOR_ID", None)

    call_function = sample_monitor.code.call_function  # type: ignore[attr-defined]

    async def f() -> None:
        await call_function(get_variable, "test_var")

    expected_error_message = (
        "Function called outside a monitor or the monitor was not loaded properly"
    )
    with pytest.raises(ValueError, match=expected_error_message):
        await f()

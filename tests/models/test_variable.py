from datetime import timedelta

import pytest

import utils.time as time_utils
from models import Variable

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_set(sample_monitor):
    """'Variable.set' should set the variable value and update the timestamp"""
    variable = await Variable.create(
        monitor_id=sample_monitor.id,
        name="test_variable",
        value="initial_value",
    )

    assert variable.value == "initial_value"
    assert variable.updated_at > time_utils.now() - timedelta(seconds=1)
    updated_at = variable.updated_at

    await variable.set("new_value")

    result_variable = await Variable.get_by_id(variable.id)

    assert result_variable is not None
    assert result_variable.value == "new_value"
    assert result_variable.updated_at > updated_at


async def test_set_none(sample_monitor):
    """'Variable.set' should set the variable value to None and update the timestamp"""
    variable = await Variable.create(
        monitor_id=sample_monitor.id,
        name="test_variable",
        value="initial_value",
    )

    assert variable.value == "initial_value"
    assert variable.updated_at > time_utils.now() - timedelta(seconds=1)
    updated_at = variable.updated_at

    await variable.set(None)

    result_variable = await Variable.get_by_id(variable.id)

    assert result_variable is not None
    assert result_variable.value is None
    assert result_variable.updated_at > updated_at

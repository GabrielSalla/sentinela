from datetime import datetime, timezone

import pytest
import pytest_asyncio

import databases
from models import CodeModule

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup(clear_database_module):
    """Clear the database and add some monitors and code modules that will be used in the tests"""
    await databases.execute_application(
        'insert into "Monitors"(id, name, enabled) values'
        "(9999123, 'monitor_1', true),"
        "(9999456, 'internal.monitor_2', true),"
        "(9999457, 'disabled_monitor', false);"
    )
    await databases.execute_application(
        'insert into "CodeModules"(monitor_id, code, registered_at) values'
        "(9999123, 'def get_value(): return 10', '2025-01-10 00:00'),"
        "(9999456, 'def get_value(): return 11', '2025-01-20 00:00'),"
        "(9999457, 'def get_value(): return 12', '2025-01-30 00:00');"
    )


@pytest.mark.parametrize(
    "monitors_ids, reference_timestamp, expected_result",
    [
        # No monitors provided
        ([], None, set()),
        ([], datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), set()),
        # No timestamp provided
        ([9999123], None, {9999123}),
        ([9999457], None, {9999457}),
        ([9999456, 9999457], None, {9999456, 9999457}),
        ([9999123, 9999456], None, {9999123, 9999456}),
        ([9999123, 9999456, 9999457], None, {9999123, 9999456, 9999457}),
        # Before first monitor
        ([9999123], datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), {9999123}),
        ([9999123, 9999456], datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), {9999123, 9999456}),
        (
            [9999123, 9999456, 9999457],
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            {9999123, 9999456, 9999457},
        ),
        ([9999456, 9999457], datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), {9999456, 9999457}),
        ([9999123, 9999456], datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), {9999123, 9999456}),
        # Before second monitor
        ([9999123, 9999456], datetime(2025, 1, 11, 0, 0, tzinfo=timezone.utc), {9999456}),
        ([9999456, 9999457], datetime(2025, 1, 11, 0, 0, tzinfo=timezone.utc), {9999456, 9999457}),
        ([9999123, 9999457], datetime(2025, 1, 11, 0, 0, tzinfo=timezone.utc), {9999457}),
        ([9999457], datetime(2025, 1, 11, 0, 0, tzinfo=timezone.utc), {9999457}),
        (
            [9999123, 9999456, 9999457],
            datetime(2025, 1, 11, 0, 0, tzinfo=timezone.utc),
            {9999456, 9999457},
        ),
        ([9999456, 9999457], datetime(2025, 1, 11, 0, 0, tzinfo=timezone.utc), {9999456, 9999457}),
        ([9999123, 9999457], datetime(2025, 1, 11, 0, 0, tzinfo=timezone.utc), {9999457}),
        ([9999457], datetime(2025, 1, 11, 0, 0, tzinfo=timezone.utc), {9999457}),
        # Before third monitor
        ([9999123, 9999456], datetime(2025, 1, 21, 0, 0, tzinfo=timezone.utc), set()),
        ([9999456, 9999457], datetime(2025, 1, 21, 0, 0, tzinfo=timezone.utc), {9999457}),
        ([9999123, 9999457], datetime(2025, 1, 21, 0, 0, tzinfo=timezone.utc), {9999457}),
        ([9999457], datetime(2025, 1, 21, 0, 0, tzinfo=timezone.utc), {9999457}),
        ([9999123, 9999456, 9999457], datetime(2025, 1, 21, 0, 0, tzinfo=timezone.utc), {9999457}),
        ([9999456, 9999457], datetime(2025, 1, 21, 0, 0, tzinfo=timezone.utc), {9999457}),
        ([9999123, 9999457], datetime(2025, 1, 21, 0, 0, tzinfo=timezone.utc), {9999457}),
        ([9999457], datetime(2025, 1, 21, 0, 0, tzinfo=timezone.utc), {9999457}),
        # After all monitors
        ([9999123, 9999456], datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc), set()),
        ([9999456, 9999457], datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc), set()),
        ([9999123, 9999457], datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc), set()),
        ([9999457], datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc), set()),
        ([9999123, 9999456, 9999457], datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc), set()),
        ([9999456, 9999457], datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc), set()),
        ([9999123, 9999457], datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc), set()),
        ([9999457], datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc), set()),
    ],
)
async def test_get_updated_code_modules_timestamp(
    monitors_ids, reference_timestamp, expected_result
):
    """'CodeModule.get_updated_code_modules' should return all the code modules that were updated
    after a given timestamp"""
    code_modules = await CodeModule.get_updated_code_modules(
        monitors_ids=monitors_ids, reference_timestamp=reference_timestamp
    )
    monitors_ids = {code_module.monitor_id for code_module in code_modules}

    assert monitors_ids == expected_result

from typing import Any, Callable

from monitor_utils import IssueOptions, MonitorOptions

monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
)


async def search() -> list[dict] | None: ...
async def update(issues_data: list[dict]) -> list[dict] | None: ...
def is_solved(issue_data: dict) -> bool: ...


async def call_function(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a function and return the result. This function is used in tests to mock calls that must
    come from inside the monitor"""
    return await function(*args, **kwargs)

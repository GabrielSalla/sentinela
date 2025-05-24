from typing import Any, Callable, TypedDict

from monitor_utils import IssueOptions, MonitorOptions

monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
)


class IssueDataType(TypedDict):
    id: int
    a: str
    b: int


async def search() -> list[IssueDataType] | None: ...
async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None: ...
def is_solved(issue_data: IssueDataType) -> bool: ...


async def call_function(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a function and return the result. This function is used in tests to mock calls that must
    come from inside the monitor"""
    return await function(*args, **kwargs)

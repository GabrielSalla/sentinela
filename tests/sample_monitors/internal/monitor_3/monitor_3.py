import random
from typing import TypedDict

from monitor_utils import IssueOptions, MonitorOptions

monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
)


class IssueDataType(TypedDict):
    id: str
    a: str
    b: int


async def search() -> list[IssueDataType] | None: ...


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None: ...


def is_solved(issue_data: IssueDataType) -> bool: ...


def test_1():
    return random.randrange(1, 1000)

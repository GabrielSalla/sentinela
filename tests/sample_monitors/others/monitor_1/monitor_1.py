import random

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


def test_1():
    return random.randrange(1, 1000)

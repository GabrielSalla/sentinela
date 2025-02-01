from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, reconstructor

import utils.time as time_utils
from data_models.monitor_options import AlertOptions, IssueOptions, MonitorOptions, ReactionOptions
from registry import get_monitor_module

from .alert import Alert, AlertStatus
from .base import Base
from .issue import Issue, IssueStatus

if TYPE_CHECKING:
    from components.monitors_loader.monitor_module_type import MonitorModule


class Monitor(Base):
    __tablename__ = "Monitors"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean(), insert_default=True)
    queued: Mapped[bool] = mapped_column(Boolean(), insert_default=False)
    running: Mapped[bool] = mapped_column(Boolean(), insert_default=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    running_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    search_executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    update_executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    active_alerts: list[Alert]
    active_issues: list[Issue]

    # Monitors won't trigger events when they are created, because they wouldn't be registered yet
    _enable_creation_event: bool = False

    def __repr__(self) -> str:
        return f"{self._class_name()}[{self.id}]({self.name})"

    @reconstructor  # type: ignore[misc]
    def init_on_load(self) -> None:
        """Init the monitor internal variables. This method is not called when the monitor is
        created for the first time, only when loaded from the database"""
        self.active_alerts: list[Alert] = []
        self.active_issues: list[Issue] = []

    async def _post_create(self) -> None:
        """Setup the internal variables and map itself automatically when created"""
        self.active_alerts: list[Alert] = []
        self.active_issues: list[Issue] = []

    @property
    def monitor_id(self) -> int:
        """Property to be compatible with all other models"""
        return self.id

    def _is_triggered(self, cron: str, last_execution: datetime | None) -> bool:
        """Check if the 'cron' and 'last_execution' is considered as triggered, if the monitor is
        not in a 'pending' state or disabled"""
        if not self.enabled or self.queued or self.running:
            return False
        if last_execution is None:
            return True
        if time_utils.is_triggered(cron, last_execution):
            return True
        return False

    @property
    def is_search_triggered(self) -> bool:
        """Return if the search is triggered for the monitor"""
        if self.options.search_cron is None:
            return False
        return self._is_triggered(self.options.search_cron, self.search_executed_at)

    @property
    def is_update_triggered(self) -> bool:
        """Return if the update is triggered for the monitor"""
        if self.options.update_cron is None:
            return False
        return self._is_triggered(self.options.update_cron, self.update_executed_at)

    @property
    def code(self) -> MonitorModule:
        """Return the monitor's code registered in the 'monitors' module"""
        return get_monitor_module(self.id)

    @property
    def options(self) -> MonitorOptions:
        """Return the 'monitor_options' attribute from the monitor's code"""
        return self.code.monitor_options

    @property
    def issue_options(self) -> IssueOptions:
        """Return the 'issue_options' attribute from the monitor's code"""
        return self.code.issue_options

    @property
    def alert_options(self) -> AlertOptions | None:
        """Return the 'alert_options' attribute from the monitor's code if it's defined,
        otherwise return 'None'"""
        try:
            return self.code.alert_options
        except AttributeError:
            return None

    @property
    def reaction_options(self) -> ReactionOptions:
        """Return the 'reaction_options' attribute from the monitor's code if it's defined,
        otherwise return an empty 'ReactionOptions()' object"""
        try:
            return self.code.reaction_options
        except AttributeError:
            return ReactionOptions()

    @property
    def search_function(self) -> Callable[[], Coroutine[Any, Any, list[Any] | None]]:
        """Return the 'search' attribute from the monitor's code"""
        return self.code.search

    @property
    def update_function(self) -> Callable[..., Coroutine[Any, Any, list[Any] | None]]:
        """Return the 'update' attribute from the monitor's code"""
        return self.code.update

    @property
    def is_solved_function(self) -> Callable[[Any], bool]:
        """Return the 'is_solved' attribute from the monitor's code if it's defined, otherwise
        return a lambda function that always return False. This condition exists because not
        solvable monitors don't have a 'is_solved' function"""
        try:
            return self.code.is_solved
        except AttributeError:
            return lambda issue_data: False

    async def load_active_issues(self) -> None:
        """Load all the monitor's active issues and store them in the 'active_issues' attribute"""
        self.active_issues: list[Issue] = list(
            await Issue.get_all(Issue.monitor_id == self.id, Issue.status == IssueStatus.active)
        )

    async def load_active_alerts(self) -> None:
        """Load all the monitor's active alerts and store them in the 'active_alerts' attribute"""
        self.active_alerts: list[Alert] = list(
            await Alert.get_all(Alert.monitor_id == self.id, Alert.status == AlertStatus.active)
        )

    async def load(self) -> None:
        """Load all the monitor's active issues and alerts"""
        await self.load_active_issues()
        await self.load_active_alerts()

    def set_search_executed_at(self) -> None:
        """Set the 'search_executed_at' to the current timestamp"""
        self.search_executed_at = time_utils.now()

    def set_update_executed_at(self) -> None:
        """Set the 'update_executed_at' to the current timestamp"""
        self.update_executed_at = time_utils.now()

    async def set_enabled(self, value: bool) -> None:
        """Set the 'enabled' to the provided value"""
        self.enabled = value
        await self.save()

    def set_queued(self, value: bool) -> None:
        """Set the 'queued' to the provided value"""
        self.queued = value
        if value:
            self.queued_at = time_utils.now()

    def set_running(self, value: bool) -> None:
        """Set the 'running' to the provided value"""
        self.running = value
        if value:
            self.running_at = time_utils.now()

    def add_issues(self, issues: Issue | list[Issue]) -> None:
        """Add the provided issues to the monitor's 'active_issues' attributes"""
        if not isinstance(issues, list):
            issues = [issues]
        self.active_issues.extend(issues)

    def add_alert(self, alert: Alert) -> None:
        """Add the provided alert to the monitor's 'active_alerts' attributes"""
        self.active_alerts.append(alert)

    def clear(self) -> None:
        """Clear the monitor's 'active_issues' and 'active_alerts' lists attributes"""
        self.active_issues.clear()
        self.active_alerts.clear()

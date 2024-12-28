import enum
from datetime import datetime
from typing import Sequence

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

import models.utils.priority as priority_utils
from options import AgeRule, AlertOptions, CountRule, IssueOptions, ValueRule
from registry import get_monitor_module
from utils.async_tools import do_concurrently
from utils.time import now

from .base import Base
from .issue import Issue, IssueStatus


class AlertStatus(enum.Enum):
    active = "active"
    solved = "solved"


class Alert(Base):
    __tablename__ = "Alerts"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("Monitors.id"))
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, native_enum=False), insert_default=AlertStatus.active
    )
    acknowledged: Mapped[bool] = mapped_column(Boolean(), insert_default=False)
    locked: Mapped[bool] = mapped_column(Boolean(), insert_default=False)
    priority: Mapped[int] = mapped_column(
        Integer(), insert_default=priority_utils.AlertPriority.low
    )
    acknowledge_priority: Mapped[int] = mapped_column(Integer(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=now)
    solved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def options(self) -> AlertOptions | None:
        """Get the 'alert_options' of the monitor"""
        try:
            return get_monitor_module(self.monitor_id).alert_options
        except AttributeError:
            return None

    @property
    def issue_options(self) -> IssueOptions:
        """Get the 'issue_options' of the monitor"""
        return get_monitor_module(self.monitor_id).issue_options

    @property
    async def active_issues(self) -> Sequence[Issue]:
        """Get all the active issues linked to the alert"""
        return await Issue.get_all(Issue.alert_id == self.id, Issue.status == IssueStatus.active)

    @property
    def is_priority_acknowledged(self) -> bool:
        """Check if the current alert priority is acknowledged"""
        if not self.acknowledged:
            return False
        if self.acknowledge_priority is None:
            return False
        return self.acknowledge_priority <= self.priority

    @staticmethod
    def calculate_priority(
        rule: AgeRule | CountRule | ValueRule, issues: list[Issue] | Sequence[Issue]
    ) -> int | None:
        """Calculate the alert priority for the provided rule and issues"""
        return priority_utils.calculate_priority(rule=rule, issues=issues)

    async def update_priority(self):
        """Update the alert priority from it's rule and active issues"""
        if self.options is None:
            self._logger.warning(
                "Updating alert priority is not possible without an 'AlertOptions' setting"
            )
            return

        previous_priority = self.priority

        new_priority = self.calculate_priority(
            rule=self.options.rule, issues=await self.active_issues
        )

        if new_priority is None:
            new_priority = priority_utils.AlertPriority.low

        if new_priority == previous_priority:
            return

        self.priority = new_priority
        await self.save()

        if new_priority < previous_priority:
            await self._create_event(
                "alert_priority_increased", extra_payload={"previous_priority": previous_priority}
            )
            self._logger.debug(
                f"Alert priority increased from {previous_priority} to {new_priority}"
            )
        else:
            await self._create_event(
                "alert_priority_decreased", extra_payload={"previous_priority": previous_priority}
            )
            self._logger.debug(
                f"Alert priority decreased from {previous_priority} to {new_priority}"
            )

    async def link_issues(self, issues: list[Issue]):
        """Link issues to the alert"""
        if self.status != AlertStatus.active:
            self._logger.info(f"Can't link issues, status is '{self.status.value}'")
            return

        if self.locked:
            self._logger.info("Can't link issues, alert is locked")
            return

        if len(issues) == 0:
            return

        await do_concurrently(*[issue.link_to_alert(self) for issue in issues])

        if self.options and self.options.dismiss_acknowledge_on_new_issues:
            await self.dismiss_acknowledge()

        linked_issues_ids = [issue.id for issue in issues]
        await self._create_event(
            "alert_issues_linked", extra_payload={"issues_ids": linked_issues_ids}
        )
        self._logger.debug(f"Issues linked: {linked_issues_ids}")

    async def acknowledge(self, send_event=True):
        """Acknowledge the alert at the current priority"""
        if self.status != AlertStatus.active:
            self._logger.info(f"Can't acknowledge, status is '{self.status.value}'")
            return

        if self.is_priority_acknowledged:
            return

        self.acknowledged = True
        self.acknowledge_priority = self.priority
        await self.save()

        if send_event:
            await self._create_event("alert_acknowledged")

        self._logger.debug("Acknowledged")

    async def dismiss_acknowledge(self):
        """Dismiss the alert's acknowledgement"""
        if self.status != AlertStatus.active:
            self._logger.info(f"Can't dismiss acknowledge, status is '{self.status.value}'")
            return

        if not self.acknowledged:
            return

        self.acknowledged = False
        await self.save()

        await self._create_event("alert_acknowledge_dismissed")

        self._logger.debug("Acknowledgement dismissed")

    async def lock(self):
        """Lock the alert to prevent linking new issues"""
        if self.status != AlertStatus.active:
            self._logger.info(f"Can't lock, status is '{self.status.value}'")
            return

        if self.locked:
            return

        self.locked = True
        await self.save()

        await self._create_event("alert_locked")

        self._logger.debug("Locked")

    async def unlock(self):
        """Unlock the alert to allow linking new issues"""
        if self.status != AlertStatus.active:
            self._logger.info(f"Can't unlock, status is '{self.status.value}'")
            return

        if not self.locked:
            return

        self.locked = False
        await self.save()

        await self._create_event("alert_unlocked")

        self._logger.debug("Unlocked")

    async def update(self):
        """Update the alert, checking if it's solved and queueing an 'alert_updated' event for the
        monitor's notifications"""
        if self.status != AlertStatus.active:
            self._logger.info(f"Can't update, status is '{self.status.value}'")
            return

        issues_count = await Issue.count(
            Issue.alert_id == self.id, Issue.status == IssueStatus.active
        )
        if issues_count == 0:
            await self.solve()
        else:
            await self._create_event("alert_updated")
            self._logger.debug("Updated")

    async def solve_issues(self):
        """Solve the alert's active issues if the issues are not 'solvable'"""
        if self.status != AlertStatus.active:
            self._logger.info(f"Can't solve issues, status is '{self.status.value}'")
            return

        if self.issue_options.solvable:
            self._logger.info("Tried to solve an alert with solvable issues, skipping")
            return

        await do_concurrently(*[issue.solve() for issue in await self.active_issues])

        await self.acknowledge(send_event=False)
        await self.update()

    async def solve(self):
        """Solve an alert, setting it's 'status' and 'solved_at' attributes"""
        if self.status != AlertStatus.active:
            self._logger.info(f"Can't solve, status is '{self.status.value}'")
            return

        self.status = AlertStatus.solved
        self.solved_at = now()
        await self.save()

        await self._create_event("alert_solved")

        self._logger.debug("Solved")

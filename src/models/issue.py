from __future__ import annotations

import enum
import json
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from src.data_types.issue_data_types import IssueDataType
from src.internal_database import CallbackSession
from src.models.base import Base
from src.options import IssueOptions
from src.registry import get_monitor_module
from src.utils.time import now

if TYPE_CHECKING:
    from src.models.alert import Alert


class IssueStatus(enum.Enum):
    active = "active"
    dropped = "dropped"
    solved = "solved"


class Issue(Base):
    __tablename__ = "Issues"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("Monitors.id"))
    alert_id: Mapped[int] = mapped_column(ForeignKey("Alerts.id"), nullable=True)
    model_id: Mapped[str] = mapped_column(String(255))
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, native_enum=False), insert_default=IssueStatus.active
    )
    data: Mapped[IssueDataType] = mapped_column(
        MutableDict.as_mutable(postgresql.JSON)  # type: ignore[arg-type]
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=now)
    solved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    dropped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    @staticmethod
    async def is_unique(monitor_id: int, model_id: str) -> bool:
        """Returns a boolean indicating if the provided monitor already has an issue with the
        provided 'model_id'"""
        issue = await Issue.get(Issue.monitor_id == monitor_id, Issue.model_id == model_id)
        return issue is None

    @property
    def options(self) -> IssueOptions:
        """Get the 'issue_options' object from the monitor's module code"""
        return get_monitor_module(self.monitor_id).issue_options

    @property
    def is_solved(self) -> bool:
        """Returns a boolean if the issue is solved using the monitor's 'is_solved' function. If
        the monitor's 'issue_options.solvable' is 'False', return 'False'"""
        if not get_monitor_module(self.monitor_id).issue_options.solvable:
            return False

        return get_monitor_module(self.monitor_id).is_solved(
            issue_data=self.data  # type: ignore[arg-type]
        )

    async def _link_to_alert_callback(self):
        """Callback of the 'link_to_alert' method that queues the event"""
        await self._create_event("issue_linked")
        self._logger.debug(f"Linked to alert '{self.alert_id}'")

    async def link_to_alert(self, alert: Alert, session: CallbackSession | None = None):
        """Link the issue to an alert if the issue's status is 'active'"""
        if self.status != IssueStatus.active:
            self._logger.info(f"Can't link to alert, status is '{self.status.value}'")
            return

        self.alert_id = alert.id
        await self.save(session=session, callback=self._link_to_alert_callback())

    async def check_solved(self, session: CallbackSession | None = None):
        """Check if the issue is solved if the issue's status is 'active' and solve it if
        positive"""
        if self.status != IssueStatus.active:
            self._logger.info(f"Can't check solved, status is '{self.status.value}'")
            return

        if self.is_solved:
            await self.solve(session=session)

    async def drop(self):
        """Set the issue as dropped if the issue's status is 'active'"""
        if self.status != IssueStatus.active:
            self._logger.info(f"Can't drop, status is '{self.status.value}'")
            return

        self.status = IssueStatus.dropped
        self.dropped_at = now()
        await self.save()

        await self._create_event("issue_dropped")
        self._logger.debug("Dropped")

    async def _solve_callback(self):
        """Callback of the 'solve' method that queues the event"""
        await self._create_event("issue_solved")
        self._logger.debug("Solved")

    async def solve(self, session: CallbackSession | None = None):
        """Set the issue as solved if the issue's status is 'active'"""
        if self.status != IssueStatus.active:
            self._logger.info(f"Can't solve, status is '{self.status.value}'")
            return

        self.status = IssueStatus.solved
        self.solved_at = now()
        await self.save(session=session, callback=self._solve_callback())

    async def _update_data_callback(self):
        """Callback of the 'update_data' method that queues the event"""
        # Use distinct events based on the current data, checking if it's solved or not, to allow
        # different reactions to each situation
        if self.is_solved:
            await self._create_event("issue_updated_solved")
        else:
            await self._create_event("issue_updated_not_solved")
        self._logger.debug(f"Data updated to '{json.dumps(self.data)}'")

    async def update_data(self, new_data: IssueDataType, session: CallbackSession | None = None):
        """Update the issue's data if the issue's status is 'active'"""
        if self.status != IssueStatus.active:
            self._logger.info(f"Can't update, status is '{self.status.value}'")
            return

        self.data = new_data
        await self.save(session=session, callback=self._update_data_callback())

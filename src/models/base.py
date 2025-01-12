import json
import logging
from asyncio import Semaphore
from datetime import datetime
from enum import Enum
from typing import Any, Coroutine, Optional, Sequence, Type, TypeVar, cast

from sqlalchemy import Row, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute
from sqlalchemy.sql.expression import ColumnElement

import message_queue as message_queue
from configs import configs
from internal_database import CallbackSession, get_session
from registry import get_monitor_module
from utils.async_tools import do_concurrently


def format_value(value: Any):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    else:
        return value


ClassType = TypeVar("ClassType")


class Base(AsyncAttrs, DeclarativeBase):
    __allow_unmapped__ = True

    _logger_obj: logging.Logger
    _semaphore_obj: Semaphore

    _enable_creation_event: bool = True

    @classmethod
    def _class_name(cls) -> str:
        return cls.__name__

    def __repr__(self) -> str:
        return f"{self._class_name()}[{self.id}]"  # type: ignore[attr-defined]

    async def _post_create(self):
        pass

    def _should_queue_event(self, event_name: str) -> bool:
        """Check if the event should be queued based on the monitor's 'reaction_options' settings"""
        monitor_code = get_monitor_module(self.monitor_id)  # type: ignore[attr-defined]
        try:
            reactions_list = monitor_code.reaction_options[event_name]
            return len(reactions_list) > 0
        except AttributeError:
            return False

    def _build_event_payload(
        self, event_name: str, extra_payload: dict[str, Any] | None
    ) -> dict[str, Any]:
        return {
            "event_source": self._class_name().lower(),
            "event_source_id": self.id,  # type: ignore[attr-defined]
            "event_source_monitor_id": self.monitor_id,  # type: ignore[attr-defined]
            "event_name": event_name,
            "event_data": {
                column.key: format_value(column.value) for column in inspect(self).attrs
            },
            "extra_payload": extra_payload,
        }

    async def _create_event(self, event_name: str, extra_payload: dict[str, Any] | None = None):
        """Check if the event has an reaction registered to it and, if does, queue the event"""
        event_payload = self._build_event_payload(event_name, extra_payload)

        if self._should_queue_event(event_name):
            self._logger.info(json.dumps(event_payload))
            await message_queue.send_message(type="event", payload=event_payload)
        elif configs.log_all_events:
            self._logger.info(json.dumps(event_payload))

    @property
    def _logger(self) -> logging.Logger:
        """Lazy load a Logger for the instance"""
        try:
            return self._logger_obj
        except AttributeError:
            self._logger_obj = logging.getLogger(str(self))
            return self._logger_obj

    @property
    def _semaphore(self) -> Semaphore:
        """Lazy load a Semaphore object to allow only 1 session accessing the object at a time, as
        multiple executors might be using the same object, even if not updating them.
        An example is one executor processing the object and another one processing an event that
        loads the same object to check for it's information"""
        try:
            return self._semaphore_obj
        except AttributeError:
            self._semaphore_obj = Semaphore()
            return self._semaphore_obj

    @classmethod
    async def count(cls: Type[ClassType], *column_filters: ColumnElement) -> int:
        async with get_session() as session:
            result = await session.execute(
                select(func.count(cls.id)).where(*column_filters)  # type: ignore[attr-defined]
            )
            return cast(int, result.scalars().first())

    @classmethod
    async def create_batch(cls: Type[ClassType], instances: list[ClassType]) -> list[ClassType]:
        """Create a list of instances in the database, calling their '_post_create' methods and
        queueing the creation events for them"""
        async with get_session() as session:
            session.add_all(instances)
            await session.commit()

        await do_concurrently(
            *[instance._post_create() for instance in instances]  # type: ignore[attr-defined]
        )

        await do_concurrently(
            *[
                instance._create_event(  # type: ignore[attr-defined]
                    event_name=f"{cls._class_name().lower()}_created"  # type: ignore[attr-defined]
                )
                for instance in instances
                if instance._enable_creation_event  # type: ignore[attr-defined]
            ]
        )

        return instances

    @classmethod
    async def create(cls: Type[ClassType], **attributes) -> ClassType:
        """Create an instance in the database with the provided attributes, calling it's
        '_post_create' methods and queueing the creation events for it"""
        async with get_session() as session:
            instance = cls(**attributes)
            session.add(instance)
            await session.commit()

        await instance._post_create()  # type: ignore[attr-defined]

        if instance._enable_creation_event:  # type: ignore[attr-defined]
            await instance._create_event(  # type: ignore[attr-defined]
                event_name=f"{cls._class_name().lower()}_created"  # type: ignore[attr-defined]
            )
        return instance

    @classmethod
    async def get(cls: Type[ClassType], *column_filters: ColumnElement) -> ClassType | None:
        """Return an instance of the model that matches the provided filters or 'None' if none was
        found"""
        async with get_session() as session:
            result = await session.execute(select(cls).where(*column_filters))
            instance = result.scalars().first()

        return instance

    @classmethod
    async def get_raw(
        cls: Type[ClassType],
        columns: list[InstrumentedAttribute],
        column_filters: list[ColumnElement] | None = None,
    ) -> Sequence[Row]:
        """Return a list of tuples with the provided columns for all instances that match the
        provided filters"""
        if column_filters is None:
            column_filters = []

        async with get_session() as session:
            result = await session.execute(select(*columns).where(*column_filters))
            return result.all()

    @classmethod
    async def get_by_id(cls: Type[ClassType], instance_id) -> ClassType | None:
        """Return an instance of the model that has the provided primary key or 'None' if none was
        found"""
        async with get_session() as session:
            return await session.get(cls, ident=instance_id)

    @classmethod
    async def get_all(
        cls: Type[ClassType],
        *column_filters: ColumnElement,
        order_by: list[InstrumentedAttribute] | None = None,
        limit: int | None = None,
    ) -> Sequence[ClassType]:
        """Return all instances that match the the provided filters, sorted by the optional list
        of fields and limited by number, if provided"""
        statement = select(cls).where(*column_filters)
        if order_by is not None:
            statement = statement.order_by(*order_by)
        if limit is not None:
            statement = statement.limit(limit)

        async with get_session() as session:
            result = await session.execute(statement)
            instances = result.scalars().all()

        return instances

    @classmethod
    async def get_or_create(
        cls: Type[ClassType], **attributes: str | int | float | bool | None
    ) -> ClassType:
        """Try to get an instance that matches the the provided filters and if none was found, try
        to create it"""
        # Transform the the attributes into class attributes filters to search for the object
        instance = await cls.get(  # type: ignore[attr-defined]
            *(getattr(cls, key) == value for key, value in attributes.items())
        )
        if instance:
            return cast(ClassType, instance)
        return cast(ClassType, await cls.create(**attributes))  # type: ignore[attr-defined]

    async def refresh(self, attribute_names: Optional[list[str] | None] = None):
        """Reload the instance's attributes from the database"""
        async with self._semaphore, get_session() as session:
            session.add(self)
            await session.refresh(self, attribute_names)

    async def save(self, session: CallbackSession | None = None, callback: Coroutine | None = None):
        """Save the instance to the database. If the session was not provided, create one. Add
        itself to the session and also add the provided callbacks"""
        if session is not None:
            session.add(self)
            session.add_callback(callback)
            return

        async with self._semaphore, get_session() as session:
            session.add(self)
            session.add_callback(callback)

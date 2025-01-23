import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Coroutine

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from configs import configs
from utils.async_tools import do_concurrently


class CallbackSession(AsyncSession):
    _callbacks: list[Coroutine[None, None, None]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._callbacks = []

    def add_callback(self, callback: Coroutine[None, None, None] | None) -> None:
        if callback is not None:
            self._callbacks.append(callback)

    async def execute_callbacks(self) -> None:
        await do_concurrently(*self._callbacks)

    def cancel_callbacks(self) -> None:
        for callback in self._callbacks:
            callback.close()


engine = create_async_engine(
    os.environ["DATABASE_APPLICATION"],
    echo=False,
    **configs.application_database_settings,
)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=CallbackSession)


@asynccontextmanager
async def get_session() -> AsyncGenerator[CallbackSession, None]:
    """Get a 'CallbackSession' session object that will execute all callbacks added if the commit
    is successful"""
    async with async_session() as session:
        async with session.begin():
            try:
                yield session
                # If the session is dirty, commit the changes and execute the callbacks
                if session.dirty:
                    await session.commit()
                await session.execute_callbacks()
            except Exception:
                # If there's any problem with the session, cancel all the callbacks
                session.cancel_callbacks()
                raise


async def close() -> None:
    await engine.dispose(close=True)

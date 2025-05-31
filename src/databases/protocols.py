from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Pool(Protocol):  # pragma: no cover
    PATTERNS: list[str]
    name: str

    def __init__(self, dsn: str, name: str, **configs: Any) -> None: ...

    async def init(self) -> None: ...

    async def execute(
        self, sql: str, *args: str | int | float | bool | list[str] | list[int] | list[float] | None
    ) -> None: ...

    async def fetch(
        self,
        sql: str,
        *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
        acquire_timeout: int,
        query_timeout: int,
    ) -> list[dict[str, Any]]: ...

    async def close(self) -> None: ...

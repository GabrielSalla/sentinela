from typing import Any, Protocol


class Message(Protocol):
    id: str

    @property
    def content(self) -> dict[str, Any]: ...


class Queue(Protocol):
    async def init(self) -> None: ...

    async def send_message(self, type: str, payload: dict[str, Any]) -> None: ...

    async def get_message(self) -> Message | None: ...

    async def change_visibility(self, message: Message) -> None: ...

    async def delete_message(self, message: Message) -> None: ...

from typing import Any

from pydantic.dataclasses import dataclass


@dataclass
class RequestPayload:
    action: str
    params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            field: value
            for field in self.__dataclass_fields__
            if (value := getattr(self, field)) is not None
        }

from typing import Any

from pydantic.dataclasses import dataclass


@dataclass
class EventPayload:
    """The event payload provided to each reaction function contains structured information about
    the event source, details, and any additional context.
    - `event_source`: Specifies the model that generated the event (e.g., `monitor`, `issue`,
    `alert`).
    - `event_source_id`: The unique identifier of the object that triggered the event (e.g.,
    `monitor_id`, `issue_id`).
    - `event_source_monitor_id`: The monitor ID associated with the object that generated the event.
    - `event_name`: Name of the event (e.g., `alert_created`, `issue_solved`).
    - `event_data`: Dictionary with detailed information about the event source.
    - `extra_payload`: Additional information that may be sent along with the event, providing
    further context.
    """

    event_source: str
    event_source_id: int
    event_source_monitor_id: int
    event_name: str
    event_data: dict[str, Any]
    extra_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            field: value
            for field in self.__dataclass_fields__
            if (value := getattr(self, field)) is not None
        }

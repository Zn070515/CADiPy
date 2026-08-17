"""In-process audit recorder; persistence/transport is deliberately separate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .events import AuditEvent


class AuditRecorder:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self._events.append(event)

    def to_list(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events]

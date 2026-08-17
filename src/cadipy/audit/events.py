"""Public audit event values with no backend object references."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditEvent:
    request_id: str
    operation: str
    executor_kind: str
    target: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    rebuild: str | None = None
    verification: str | None = None
    error_code: str | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

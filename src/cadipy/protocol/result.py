"""Serializable operation results shared by API, RPC, and MCP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cadipy.domain.errors import CadipyError


@dataclass(frozen=True, slots=True)
class OperationResult:
    ok: bool
    request_id: str
    operation: str
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": 1,
            "id": self.request_id,
            "operation": self.operation,
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
        }

    @classmethod
    def failure(cls, request_id: str, operation: str, error: Exception) -> OperationResult:
        if isinstance(error, CadipyError):
            payload = {
                "code": error.code,
                "message": str(error),
                "operation": error.operation or operation,
                "details": error.details,
            }
        else:
            payload = {
                "code": "internal_error",
                "message": str(error),
                "operation": operation,
                "details": {},
            }
        return cls(False, request_id, operation, error=payload)

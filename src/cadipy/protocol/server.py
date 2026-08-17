"""Transport-neutral RPC server adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cadipy.domain.errors import ProtocolError
from cadipy.operations.registry import operation_names

from .result import OperationResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cadipy.session import CadipySession


def exposed_rpc_operations() -> tuple[str, ...]:
    return operation_names()


class ProtocolServer:
    def __init__(self, session: CadipySession) -> None:
        self.session = session

    @classmethod
    def from_session(cls, session: CadipySession) -> ProtocolServer:
        return cls(session)

    def handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request_id = str(request.get("id", "request"))
        operation = str(request.get("operation", ""))
        if request.get("protocol", 1) != 1:
            return OperationResult.failure(
                request_id,
                operation,
                ProtocolError("unsupported protocol version"),
            ).to_dict()
        try:
            return self.session.dispatch_request(request).to_dict()
        except Exception as exc:
            return OperationResult.failure(request_id, operation, exc).to_dict()

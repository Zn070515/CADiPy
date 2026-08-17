"""Small protocol client usable with HTTP, named pipes, or an in-process server."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


class ProtocolClient:
    def __init__(self, transport: Callable[[Mapping[str, Any]], dict[str, Any]]) -> None:
        self.transport = transport

    def call(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return self.transport(request)

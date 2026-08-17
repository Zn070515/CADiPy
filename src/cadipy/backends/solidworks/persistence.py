"""SOLIDWORKS persistent-reference conversion and resolution."""

from __future__ import annotations

import base64
from typing import Any

from cadipy.domain.errors import EntityReferenceInvalidError


def encode_persist_reference(value: Any) -> str:
    """Encode a SOLIDWORKS byte-like persistent reference for the protocol."""

    try:
        raw = bytes(value)
    except (TypeError, ValueError) as exc:
        raise EntityReferenceInvalidError(
            "SOLIDWORKS returned an invalid persistent reference",
            operation="solidworks.persistent_reference.encode",
        ) from exc
    if not raw:
        raise EntityReferenceInvalidError(
            "SOLIDWORKS returned an empty persistent reference",
            operation="solidworks.persistent_reference.encode",
        )
    return base64.b64encode(raw).decode("ascii")


def decode_persist_reference(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise EntityReferenceInvalidError(
            "persistent reference must be non-empty base64 text",
            operation="solidworks.persistent_reference.decode",
        )
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise EntityReferenceInvalidError(
            "persistent reference is not valid base64 text",
            operation="solidworks.persistent_reference.decode",
        ) from exc
    if not raw:
        raise EntityReferenceInvalidError(
            "persistent reference must not decode to empty bytes",
            operation="solidworks.persistent_reference.decode",
        )
    return raw


class _ErrorCodeBox:
    def __init__(self) -> None:
        self.value = 0


def _error_code_box() -> Any:
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    except ImportError:
        return _ErrorCodeBox()


def _safe_array(raw: bytes) -> Any:
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, tuple(raw))
    except ImportError:
        return raw


def resolve_persist_reference(extension: Any, encoded_reference: str) -> Any:
    """Resolve exactly one persistent reference; never substitute another object."""

    raw = decode_persist_reference(encoded_reference)
    error_code = _error_code_box()
    try:
        resolved = extension.GetObjectByPersistReference3(
            _safe_array(raw),
            error_code,
        )
    except Exception as exc:
        raise EntityReferenceInvalidError(
            "SOLIDWORKS could not resolve the persistent reference",
            operation="solidworks.persistent_reference.resolve",
        ) from exc
    status = getattr(error_code, "value", 0)
    if resolved is None or status not in (0, None):
        raise EntityReferenceInvalidError(
            "the persistent reference is invalid or no longer resolves",
            operation="solidworks.persistent_reference.resolve",
            details={"status": status},
        )
    return resolved

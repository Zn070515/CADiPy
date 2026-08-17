"""Stable domain errors exposed by CADiPy."""

from __future__ import annotations

from typing import Any


class CadipyError(Exception):
    """Base class for readable, serializable CADiPy failures."""

    code = "cadipy_error"

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.details = details or {}


class InvalidArgumentError(CadipyError):
    code = "invalid_argument"


class UnsupportedPlatformError(CadipyError):
    code = "unsupported_platform"


class UnsupportedVersionError(CadipyError):
    code = "unsupported_version"


class CapabilityUnavailableError(CadipyError):
    code = "capability_unavailable"


class TargetNotFoundError(CadipyError):
    code = "target_not_found"


class TargetMismatchError(CadipyError):
    code = "target_mismatch"


class AmbiguousSelectionError(CadipyError):
    code = "ambiguous_selection"


class DocumentTypeError(CadipyError):
    code = "document_type"


class FileConflictError(CadipyError):
    code = "file_conflict"


class SolidWorksNotAvailableError(CadipyError):
    code = "solidworks_not_available"


class ComOperationError(CadipyError):
    code = "com_operation"


class RebuildError(CadipyError):
    code = "rebuild"


class VerificationError(CadipyError):
    code = "verification"


class TransactionError(CadipyError):
    code = "transaction"


class WorkerError(CadipyError):
    code = "worker"


class ProtocolError(CadipyError):
    code = "protocol"

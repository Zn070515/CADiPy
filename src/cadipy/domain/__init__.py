"""Platform-neutral CADiPy domain contracts."""

from .documents import DocumentType
from .errors import (
    AmbiguousSelectionError,
    CadipyError,
    InvalidArgumentError,
    SessionClosedError,
    TargetMismatchError,
    TargetNotFoundError,
)
from .identities import DocumentIdentity
from .targets import TargetBinding, resolve_target
from .units import deg_to_sw_rad, mm_to_sw_m, sw_m_to_mm, sw_rad_to_deg

__all__ = [
    "AmbiguousSelectionError",
    "CadipyError",
    "DocumentIdentity",
    "DocumentType",
    "InvalidArgumentError",
    "SessionClosedError",
    "TargetBinding",
    "TargetMismatchError",
    "TargetNotFoundError",
    "deg_to_sw_rad",
    "mm_to_sw_m",
    "resolve_target",
    "sw_m_to_mm",
    "sw_rad_to_deg",
]

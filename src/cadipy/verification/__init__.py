"""Engineering postcondition verification for CAD operations."""

from .postconditions import VerificationCheck, VerificationReport, verify_rectangular_extrusion
from .registry import register_postcondition, verify_postconditions

__all__ = [
    "VerificationCheck",
    "VerificationReport",
    "register_postcondition",
    "verify_postconditions",
    "verify_rectangular_extrusion",
]

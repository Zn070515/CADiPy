"""CAD document domain values."""

from enum import Enum


class DocumentType(str, Enum):
    PART = "part"
    ASSEMBLY = "assembly"
    DRAWING = "drawing"

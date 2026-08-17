from __future__ import annotations

import base64

import pytest

from cadipy.backends.solidworks.persistence import (
    decode_persist_reference,
    encode_persist_reference,
    resolve_persist_reference,
)
from cadipy.domain.errors import EntityReferenceInvalidError


def test_persist_reference_round_trips_as_url_safe_text() -> None:
    raw = bytes(range(48))

    encoded = encode_persist_reference(raw)

    assert encoded == base64.b64encode(raw).decode("ascii")
    assert decode_persist_reference(encoded) == raw


def test_persist_reference_rejects_malformed_text() -> None:
    with pytest.raises(EntityReferenceInvalidError):
        decode_persist_reference("not-base64!!!")


class FakeExtension:
    def __init__(self, result: object, error_code: int = 0) -> None:
        self.result = result
        self.error_code = error_code
        self.calls: list[tuple[object, object]] = []

    def GetObjectByPersistReference3(self, reference: object, error: object) -> object:
        self.calls.append((reference, error))
        error.value = self.error_code
        return self.result


def test_resolver_returns_only_the_object_reported_by_solidworks() -> None:
    extension = FakeExtension(result="resolved")

    assert resolve_persist_reference(extension, "AQID") == "resolved"
    assert len(extension.calls) == 1


@pytest.mark.parametrize(
    ("result", "error_code"),
    [(None, 0), ("resolved", 1)],
)
def test_resolver_fails_without_fallback_for_invalid_reference(
    result: object, error_code: int
) -> None:
    extension = FakeExtension(result=result, error_code=error_code)

    with pytest.raises(EntityReferenceInvalidError):
        resolve_persist_reference(extension, "AQID")

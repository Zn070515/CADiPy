from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cadipy.backends.solidworks.documents import close_document
from cadipy.domain.errors import DocumentDirtyError, InvalidArgumentError


@dataclass
class FakeDocument:
    dirty: bool
    save_calls: int = 0

    GetTitle = "Part1"

    def GetSaveFlag(self) -> int:
        return int(self.dirty)

    def Save3(self, options: int, errors: object, warnings: object) -> bool:
        self.save_calls += 1
        self.dirty = False
        return True


@dataclass
class FakeApplication:
    close_calls: list[str] = field(default_factory=list)

    def CloseDoc(self, title: str) -> None:
        self.close_calls.append(title)


def test_dirty_document_requires_explicit_close_policy() -> None:
    document = FakeDocument(dirty=True)

    with pytest.raises(DocumentDirtyError):
        close_document(FakeApplication(), document, require_clean=True)

    assert document.save_calls == 0


def test_dirty_document_can_be_saved_before_close() -> None:
    document = FakeDocument(dirty=True)
    application = FakeApplication()

    close_document(application, document, save=True)

    assert document.save_calls == 1
    assert application.close_calls == ["Part1"]


def test_close_rejects_ambiguous_save_discard_policy() -> None:
    with pytest.raises(InvalidArgumentError):
        close_document(FakeApplication(), FakeDocument(dirty=True), save=True, discard=True)

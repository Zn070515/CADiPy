"""Internal document operations; no objects in this module cross the port."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import (
    ComOperationError,
    DocumentDirtyError,
    DocumentTypeError,
    InvalidArgumentError,
)

SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_DOC_DRAWING = 3
SW_OPEN_SILENT = 1
SW_SAVE_CURRENT_VERSION = 0
SW_SAVE_SILENT = 1


def new_part(application: Any) -> Any:
    try:
        template = _part_template(application)
        document = application.NewDocument(template, 0, 0.0, 0.0)
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not create a Part document",
            operation="solidworks.create_part",
        ) from exc
    if document is None:
        raise ComOperationError(
            "SOLIDWORKS returned no Part document",
            operation="solidworks.create_part",
        )
    return document


def _part_template(application: Any) -> str:
    """Resolve the configured template without assuming an install directory."""

    try:
        configured = str(application.GetDocumentTemplate(SW_DOC_PART, "", 0, 0.0, 0.0))
        if configured and Path(configured).is_file():
            return configured
    except Exception:
        pass

    try:
        folder = Path(str(application.GetUserPreferenceStringValue(6)))
        candidates = tuple(folder.glob("*.prtdot"))
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS part template location could not be resolved",
            operation="solidworks.create_part",
        ) from exc

    preferred = next(
        (candidate for candidate in candidates if candidate.name.casefold() == "gb_part.prtdot"),
        None,
    )
    if preferred is not None:
        return str(preferred)
    if len(candidates) == 1:
        return str(candidates[0])
    raise ComOperationError(
        "SOLIDWORKS has no unambiguous Part template",
        operation="solidworks.create_part",
        details={"template_folder": str(folder)},
    )


def open_part(application: Any, path: Path) -> Any:
    errors = _int_out()
    warnings = _int_out()
    try:
        document = application.OpenDoc6(
            str(path),
            SW_DOC_PART,
            SW_OPEN_SILENT,
            "",
            errors,
            warnings,
        )
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not open the Part document",
            operation="solidworks.reopen",
            details={"path": str(path)},
        ) from exc
    if document is None:
        raise ComOperationError(
            "SOLIDWORKS returned no document while reopening",
            operation="solidworks.reopen",
            details={"path": str(path)},
        )
    return document


def open_document(application: Any, path: Path, document_type: DocumentType) -> Any:
    if document_type is not DocumentType.PART:
        raise DocumentTypeError(
            "document.open currently supports Part documents only",
            operation="solidworks.document.open",
            details={"document_type": document_type.value},
        )
    return open_part(application, path)


def list_open_documents(application: Any) -> tuple[Any, ...]:
    try:
        values = application.GetDocuments
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS open documents could not be enumerated",
            operation="solidworks.document.list",
        ) from exc
    if values is None:
        return ()
    return tuple(value for value in values if value is not None)


def active_document(application: Any) -> Any | None:
    try:
        return application.ActiveDoc
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS active document could not be read",
            operation="solidworks.document.active",
        ) from exc


def close_document(
    application: Any,
    document: Any,
    *,
    save: bool = False,
    discard: bool = False,
    require_clean: bool | None = None,
) -> None:
    if save and discard:
        raise InvalidArgumentError(
            "document.close cannot request both save and discard",
            operation="solidworks.close",
        )
    if require_clean and (save or discard):
        raise InvalidArgumentError(
            "document.close require_clean cannot be combined with save or discard",
            operation="solidworks.close",
        )
    if not save and not discard and require_clean is False:
        raise InvalidArgumentError(
            "document.close requires save, discard, or require_clean=True",
            operation="solidworks.close",
        )
    if not save and not discard and require_clean is None:
        require_clean = True
    try:
        title = str(document.GetTitle)
        dirty = bool(_com_value(document, "GetSaveFlag"))
        if dirty and require_clean:
            raise DocumentDirtyError(  # noqa: TRY301
                "document has unsaved changes; choose save or discard explicitly",
                operation="solidworks.close",
                details={"title": title},
            )
        if dirty and save:
            _save_current_document(document)
        if dirty and discard:
            application.QuitDoc(title)
        else:
            application.CloseDoc(title)
    except Exception as exc:
        if isinstance(exc, (DocumentDirtyError, InvalidArgumentError)):
            raise
        raise ComOperationError(
            "SOLIDWORKS could not close the owned document",
            operation="solidworks.close",
        ) from exc


def _save_current_document(document: Any) -> None:
    try:
        saved = bool(document.Save3(SW_SAVE_SILENT, None, None))
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not save the dirty document before close",
            operation="solidworks.close.save",
        ) from exc
    if not saved:
        raise ComOperationError(
            "SOLIDWORKS returned a failed save status before close",
            operation="solidworks.close.save",
        )


def _com_value(obj: Any, name: str) -> Any:
    value = getattr(obj, name)
    return value() if callable(value) else value


def document_type(document: Any) -> DocumentType:
    try:
        raw_type = int(document.GetType)
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS document type could not be read",
            operation="solidworks.inspect_document",
        ) from exc
    try:
        return {
            SW_DOC_PART: DocumentType.PART,
            SW_DOC_ASSEMBLY: DocumentType.ASSEMBLY,
            SW_DOC_DRAWING: DocumentType.DRAWING,
        }[raw_type]
    except KeyError as exc:
        raise DocumentTypeError(
            "unsupported SOLIDWORKS document type",
            operation="solidworks.inspect_document",
            details={"type": raw_type},
        ) from exc


def make_document_id() -> str:
    return f"sw-doc-{uuid4().hex}"


def _int_out() -> Any:
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

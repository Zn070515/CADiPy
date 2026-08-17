from __future__ import annotations

from cadipy.audit.events import AuditEvent
from cadipy.audit.recorder import AuditRecorder


def test_audit_recorder_keeps_machine_readable_public_evidence() -> None:
    recorder = AuditRecorder()
    recorder.record(
        AuditEvent(
            request_id="request-1",
            operation="part.rebuild",
            executor_kind="python-com",
            target={"document_id": "doc-1"},
            parameters={"depth_mm": 3.0},
            rebuild="ok",
            verification="passed",
        )
    )

    payload = recorder.to_list()
    assert payload[0]["operation"] == "part.rebuild"
    assert payload[0]["parameters"] == {"depth_mm": 3.0}
    assert "_oleobj_" not in str(payload)

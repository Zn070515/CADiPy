from __future__ import annotations

from cadipy.backends.executor import ApplicationInfo
from cadipy.diagnostics.environment import collect_environment


class _FakeExecutor:
    executor_kind = "fake"

    def connect(self) -> ApplicationInfo:
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)


def test_environment_probe_is_serializable_and_reports_backend_state() -> None:
    report = collect_environment(executor_factory=_FakeExecutor)

    payload = report.to_dict()
    assert payload["protocol_version"] == 1
    assert payload["com_reachable"] is True
    assert payload["solidworks_revision"] == "34.3.2"
    assert payload["executor"] == "fake"

from __future__ import annotations

from typing import Self

import pytest

from cadipy.backends.executor import ApplicationInfo
from cadipy.backends.solidworks import application
from cadipy.backends.solidworks.executor import PythonComSolidWorksExecutor
from cadipy.domain.errors import ApplicationOwnershipError


class FakeApartment:
    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None


class FakeApplication:
    RevisionNumber = "34.3.2"
    Visible = True

    def __init__(self, name: str) -> None:
        self.name = name
        self.exit_calls = 0

    def ExitApp(self) -> None:
        self.exit_calls += 1


def install_application_fakes(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[str], FakeApplication, FakeApplication]:
    acquired: list[str] = []
    attached = FakeApplication("attached")
    launched = FakeApplication("launched")
    monkeypatch.setattr(PythonComSolidWorksExecutor, "_info", application_info)
    monkeypatch.setattr(
        application,
        "attach_application",
        lambda: acquired.append("attach") or attached,
    )
    monkeypatch.setattr(
        application,
        "launch_application",
        lambda: acquired.append("launch") or launched,
    )
    return acquired, attached, launched


def application_info(executor: PythonComSolidWorksExecutor):
    app = executor._require_application()
    return ApplicationInfo(
        product="SOLIDWORKS",
        revision=str(app.RevisionNumber),
        executor=executor.executor_kind,
        connection_mode=executor._connection_mode,
        owned=executor._owns_application,
        visible=bool(app.Visible),
    )


def test_repeated_attach_is_idempotent_and_disconnect_does_not_exit_attached_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquired, attached, _ = install_application_fakes(monkeypatch)
    executor = PythonComSolidWorksExecutor()
    executor._apartment = FakeApartment()

    executor.attach()
    executor.attach()
    executor.disconnect()

    assert acquired == ["attach"]
    assert attached.exit_calls == 0


def test_conflicting_launch_after_attach_raises_stable_ownership_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquired, _, _ = install_application_fakes(monkeypatch)
    executor = PythonComSolidWorksExecutor()
    executor._apartment = FakeApartment()
    executor.attach()

    with pytest.raises(ApplicationOwnershipError) as caught:
        executor.launch()

    assert caught.value.code == "application_ownership_conflict"
    assert caught.value.details == {"current_mode": "attach", "requested_mode": "launch"}
    assert acquired == ["attach"]


def test_repeated_launch_is_idempotent_and_disconnect_exits_only_owned_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquired, _, launched = install_application_fakes(monkeypatch)
    executor = PythonComSolidWorksExecutor()
    executor._apartment = FakeApartment()

    executor.launch()
    executor.launch()
    executor.disconnect()

    assert acquired == ["launch"]
    assert launched.exit_calls == 1

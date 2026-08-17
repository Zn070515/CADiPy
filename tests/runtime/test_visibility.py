from __future__ import annotations

from cadipy import connect, launch
from cadipy.backends.executor import ApplicationInfo


class VisibilityExecutor:
    executor_kind = "visibility-fake"

    def __init__(self, *, visible: bool) -> None:
        self.visible = visible
        self.calls: list[tuple[str, bool | None]] = []

    def attach(self, *, visible: bool | None = None) -> ApplicationInfo:
        self.calls.append(("attach", visible))
        if visible is not None:
            self.visible = visible
        return self.application_info()

    def launch(self, *, visible: bool = True) -> ApplicationInfo:
        self.calls.append(("launch", visible))
        self.visible = visible
        return self.application_info()

    def set_visibility(self, visible: bool) -> ApplicationInfo:
        self.calls.append(("set_visibility", visible))
        self.visible = visible
        return self.application_info()

    def application_info(self) -> ApplicationInfo:
        return ApplicationInfo(
            product="SOLIDWORKS",
            revision="34.3.2",
            executor=self.executor_kind,
            connection_mode="attach",
            owned=False,
            visible=self.visible,
        )

    def disconnect(self) -> None:
        return None


def test_launch_defaults_to_visible_and_reports_visibility() -> None:
    executor = VisibilityExecutor(visible=False)

    with launch(executor=executor) as session:
        result = session.execute("application.info")

    assert executor.calls[0] == ("launch", True)
    assert result.data["visible"] is True


def test_connect_preserves_existing_visibility_by_default() -> None:
    executor = VisibilityExecutor(visible=False)

    with connect(executor=executor) as session:
        result = session.execute("application.info")

    assert executor.calls[0] == ("attach", None)
    assert result.data["visible"] is False


def test_connect_can_explicitly_set_visibility() -> None:
    executor = VisibilityExecutor(visible=False)

    with connect(executor=executor, visible=True) as session:
        result = session.execute("application.info")

    assert executor.calls[0] == ("attach", True)
    assert result.data["visible"] is True


def test_application_set_visibility_is_the_public_mutation() -> None:
    executor = VisibilityExecutor(visible=True)

    with connect(executor=executor) as session:
        result = session.execute(
            "application.set_visibility",
            params={"visible": False},
        )

    assert result.data["visible"] is False
    assert executor.calls[-1] == ("set_visibility", False)

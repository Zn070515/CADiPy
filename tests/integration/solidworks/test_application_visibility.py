from __future__ import annotations

import pytest


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_application_visibility_is_readable_and_mutable(
    solidworks_session,
) -> None:
    info = solidworks_session.execute("application.info")
    assert info.ok is True
    assert info.data is not None
    original = info.data["visible"]
    try:
        hidden = solidworks_session.set_visibility(False)
        assert hidden.ok is True
        assert hidden.data is not None
        assert hidden.data["visible"] is False
        assert solidworks_session.execute("application.info").data["visible"] is False

        shown = solidworks_session.set_visibility(True)
        assert shown.ok is True
        assert shown.data is not None
        assert shown.data["visible"] is True
        assert solidworks_session.execute("application.info").data["visible"] is True
    finally:
        solidworks_session.set_visibility(original)

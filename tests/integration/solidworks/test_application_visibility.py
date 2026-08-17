from __future__ import annotations

import pytest


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_application_visibility_is_readable_and_mutable(
    solidworks_executor,
) -> None:
    original = solidworks_executor.application_info().visible
    try:
        hidden = solidworks_executor.set_visibility(False)
        assert hidden.visible is False
        assert solidworks_executor.application_info().visible is False

        shown = solidworks_executor.set_visibility(True)
        assert shown.visible is True
        assert solidworks_executor.application_info().visible is True
    finally:
        solidworks_executor.set_visibility(original)

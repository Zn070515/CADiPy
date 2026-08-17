import math

import pytest

from cadipy.domain.errors import InvalidArgumentError
from cadipy.domain.units import (
    deg_to_sw_rad,
    mm_to_sw_m,
    sw_m_to_mm,
    sw_rad_to_deg,
)


def test_length_conversions_use_millimetres_at_public_boundary() -> None:
    assert mm_to_sw_m(100.0) == pytest.approx(0.1)
    assert sw_m_to_mm(0.003) == pytest.approx(3.0)


def test_angle_conversions_use_degrees_at_public_boundary() -> None:
    assert deg_to_sw_rad(180.0) == pytest.approx(math.pi)
    assert sw_rad_to_deg(math.pi / 4) == pytest.approx(45.0)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_unit_conversions_reject_non_finite_values(value: float) -> None:
    with pytest.raises(InvalidArgumentError):
        mm_to_sw_m(value)

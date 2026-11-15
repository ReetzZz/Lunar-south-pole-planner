# Last updated: 2026-11-14
import math

import pytest
from pyproj import CRS

from src.lunar_geometry import (
    MOON_GEOGRAPHIC_CRS,
    geographic_to_projected,
)


def test_moon_geographic_crs_uses_lunar_radius():
    assert MOON_GEOGRAPHIC_CRS.ellipsoid.semi_major_metre == pytest.approx(
        1_737_400.0
    )


def test_invalid_latitude_rejected():
    with pytest.raises(ValueError):
        geographic_to_projected(0, 91, MOON_GEOGRAPHIC_CRS)


def test_nonfinite_longitude_rejected():
    with pytest.raises(ValueError):
        geographic_to_projected(math.nan, -89, MOON_GEOGRAPHIC_CRS)


def test_identity_transform_returns_input():
    x, y = geographic_to_projected(12.5, -80.0, MOON_GEOGRAPHIC_CRS)
    assert x == pytest.approx(12.5)
    assert y == pytest.approx(-80.0)


def test_invalid_crs_rejected():
    with pytest.raises(Exception):
        geographic_to_projected(0, 0, "CRS_NON_VALIDO")

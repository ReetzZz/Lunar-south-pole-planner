# Last updated: 2026-11-14
import numpy as np
import pytest

from src.visibility import compare_with_horizon


AZ = np.arange(0.0, 360.0, 2.0)
FLAT = np.zeros_like(AZ)


def test_above_flat_horizon_is_preliminary_visible_by_default():
    result = compare_with_horizon(90, 10, AZ, FLAT)
    assert result.status == "preliminary_visible"
    assert result.clearance_deg == pytest.approx(10)
    assert result.georeference_validated is False


def test_below_terrain_horizon_is_preliminary_blocked():
    horizon = np.full_like(AZ, 15.0)
    result = compare_with_horizon(90, 10, AZ, horizon)
    assert result.status == "preliminary_blocked"
    assert result.clearance_deg == pytest.approx(-5)


def test_validated_profile_uses_unqualified_status():
    result = compare_with_horizon(
        90, 10, AZ, FLAT, georeference_validated=True
    )
    assert result.status == "visible"


def test_circular_interpolation_across_north():
    az = np.array([0.0, 90.0, 180.0, 270.0])
    el = np.array([10.0, 0.0, 0.0, 0.0])
    result = compare_with_horizon(315, 20, az, el)
    assert result.status == "indeterminate"  # 90-degree gap is too large


def test_near_horizon_is_indeterminate():
    result = compare_with_horizon(90, 0.02, AZ, FLAT, tolerance_deg=0.05)
    assert result.status == "indeterminate"


def test_nan_profile_samples_are_ignored():
    horizon = FLAT.copy()
    horizon[5] = np.nan
    result = compare_with_horizon(90, 5, AZ, horizon)
    assert result.status == "preliminary_visible"


def test_invalid_object_elevation_is_indeterminate():
    result = compare_with_horizon(90, 100, AZ, FLAT)
    assert result.status == "indeterminate"


def test_invalid_tolerance_raises():
    with pytest.raises(ValueError):
        compare_with_horizon(90, 5, AZ, FLAT, tolerance_deg=-1)


def test_missing_profile_is_indeterminate():
    result = compare_with_horizon(90, 5, [], [])
    assert result.status == "indeterminate"

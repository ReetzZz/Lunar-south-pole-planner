# Last updated: 2026-11-14
import numpy as np
import pytest

from src.rover_planning import plan_rover_path


def test_flat_dem_finds_path_and_estimates_distance():
    dem = np.zeros((10, 10), dtype=float)

    result = plan_rover_path(
        dem, (1, 1), (4, 5),
        pixel_size_m=5.0,
        energy_wh_per_m=0.02,
    )

    assert result.path_rc[0] == (1, 1)
    assert result.path_rc[-1] == (4, 5)
    assert result.distance_m == pytest.approx(3 * np.hypot(5.0, 5.0) + 5.0)
    assert result.estimated_energy_wh == pytest.approx(result.distance_m * 0.02)
    assert result.max_slope_deg == pytest.approx(0.0)


def test_diagonal_distance_uses_both_pixel_dimensions():
    dem = np.zeros((5, 5), dtype=float)

    result = plan_rover_path(
        dem, (1, 1), (2, 2),
        pixel_size_x_m=3.0,
        pixel_size_y_m=4.0,
    )

    assert result.distance_m == pytest.approx(5.0)


def test_steep_transition_is_rejected():
    dem = np.zeros((5, 5), dtype=float)
    dem[2, 2] = 100.0

    with pytest.raises(ValueError, match="Nessun percorso"):
        plan_rover_path(
            dem, (1, 2), (3, 2),
            pixel_size_m=1.0,
            max_slope_deg=10.0,
            allow_diagonal=False,
        )


def test_nodata_cells_are_not_used():
    dem = np.zeros((5, 5), dtype=float)
    dem[1:4, 2] = np.nan

    result = plan_rover_path(
        dem, (2, 1), (2, 3),
        pixel_size_m=1.0,
        allow_diagonal=False,
    )

    assert all(np.isfinite(dem[r, c]) for r, c in result.path_rc)
    assert not any(
        not np.isfinite(dem[r, c])
        for r, c in result.path_rc
    )


def test_energy_budget_is_enforced():
    dem = np.zeros((5, 5), dtype=float)

    with pytest.raises(ValueError, match="oltre il budget"):
        plan_rover_path(
            dem, (1, 1), (1, 3),
            pixel_size_m=5.0,
            energy_wh_per_m=1.0,
            energy_budget_wh=9.0,
            allow_diagonal=False,
        )


def test_invalid_start_is_rejected():
    dem = np.zeros((5, 5), dtype=float)
    dem[0, 0] = np.nan

    with pytest.raises(ValueError, match="NoData"):
        plan_rover_path(dem, (0, 0), (4, 4))

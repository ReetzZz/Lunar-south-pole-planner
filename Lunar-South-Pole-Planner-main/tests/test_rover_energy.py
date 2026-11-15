# Last updated: 2026-11-14
import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from src.rover_energy import estimate_route_energy


@pytest.fixture
def flat_dem_and_plan(tmp_path):
    """Create a tiny flat DEM and a route plan for isolated energy tests."""
    dem_path = tmp_path / "flat_dem.tif"
    plan_path = tmp_path / "rover_plan.json"

    dem = np.zeros((3, 3), dtype=np.float32)

    with rasterio.open(
        dem_path,
        "w",
        driver="GTiff",
        height=3,
        width=3,
        count=1,
        dtype=dem.dtype,
        crs="EPSG:3857",
        transform=from_origin(0, 15, 5, 5),
    ) as dst:
        dst.write(dem, 1)

    plan = {
        "path_rc": [[1, 0], [1, 1], [1, 2]],
        "dem_path": str(dem_path),
    }
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    return plan_path, dem_path


def estimate(plan_path, output_path, **overrides):
    params = {
        "mass_kg": 100.0,
        "rolling_resistance_coefficient": 0.1,
        "drivetrain_efficiency": 0.8,
        "auxiliary_power_w": 10.0,
        "mission_duration_hours": 2.0,
        "battery_capacity_wh": 1000.0,
        "reserve_percent": 20.0,
    }
    params.update(overrides)

    return estimate_route_energy(
        plan_path,
        output_path=output_path,
        **params,
    )


def test_flat_route_distance_and_energy_are_calculated(
    flat_dem_and_plan, tmp_path
):
    plan_path, _ = flat_dem_and_plan
    output_path = tmp_path / "energy.json"

    result = estimate(plan_path, output_path)

    # Two 5 m segments on flat terrain.
    assert result["distance_m"] == pytest.approx(10.0)
    assert result["positive_ascent_m"] == pytest.approx(0.0)
    assert result["negative_descent_m"] == pytest.approx(0.0)

    expected_rolling_wh = (
        0.1 * 100.0 * 1.62 * 10.0 / 3600.0 / 0.8
    )
    assert result["energy_wh"]["traction_after_drivetrain"] == pytest.approx(
        expected_rolling_wh, abs=0.0001
    )
    assert result["energy_wh"]["auxiliary_load"] == pytest.approx(20.0)
    assert output_path.is_file()


def test_auxiliary_energy_scales_with_duration(flat_dem_and_plan, tmp_path):
    plan_path, _ = flat_dem_and_plan

    result = estimate(
        plan_path,
        tmp_path / "energy.json",
        auxiliary_power_w=15.0,
        mission_duration_hours=4.0,
    )

    assert result["energy_wh"]["auxiliary_load"] == pytest.approx(60.0)


def test_insufficient_battery_is_reported(flat_dem_and_plan, tmp_path):
    plan_path, _ = flat_dem_and_plan

    result = estimate(
        plan_path,
        tmp_path / "energy.json",
        auxiliary_power_w=100.0,
        mission_duration_hours=10.0,
        battery_capacity_wh=500.0,
        reserve_percent=20.0,
    )

    assert result["energy_wh"]["within_budget"] is False
    assert result["energy_wh"]["remaining_after_estimate"] < 0


def test_route_with_nodata_is_rejected(flat_dem_and_plan, tmp_path):
    plan_path, dem_path = flat_dem_and_plan

    with rasterio.open(dem_path, "r+") as ds:
        dem = ds.read(1)
        dem[1, 1] = np.nan
        ds.write(dem, 1)

    with pytest.raises(ValueError, match="NoData"):
        estimate(plan_path, tmp_path / "energy.json")


def test_non_adjacent_route_cells_are_rejected(flat_dem_and_plan, tmp_path):
    plan_path, _ = flat_dem_and_plan
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["path_rc"] = [[0, 0], [2, 2]]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="salti"):
        estimate(plan_path, tmp_path / "energy.json")


def test_invalid_drivetrain_efficiency_is_rejected(
    flat_dem_and_plan, tmp_path
):
    plan_path, _ = flat_dem_and_plan

    with pytest.raises(ValueError, match="efficienza"):
        estimate(
            plan_path,
            tmp_path / "energy.json",
            drivetrain_efficiency=1.5,
        )

# Last updated: 2026-11-14
import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.terrain_horizon import calculate_horizon


def make_dem(tmp_path, wall=None, density_wall=False):
    dem_path = tmp_path / "dem.tif"
    density_path = tmp_path / "density.tif"

    dem = np.zeros((101, 101), dtype=np.float32)
    density = np.ones_like(dem)

    if wall == "north":
        dem[45, 40:61] = 10.0
        if density_wall:
            density[45, 40:61] = 0.0
    elif wall == "south":
        dem[55, 40:61] = 10.0
        if density_wall:
            density[55, 40:61] = 0.0

    transform = from_origin(-252.5, 252.5, 5, 5)

    for path, array in ((dem_path, dem), (density_path, density)):
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=101,
            width=101,
            count=1,
            dtype="float32",
            transform=transform,
            nodata=np.nan,
        ) as ds:
            ds.write(array, 1)

    return dem_path, density_path


def run_profile(dem_path, density_path=None):
    return calculate_horizon(
        dem_path,
        0.0,
        0.0,
        density_path=density_path,
        azimuth_step_deg=2.0,
        max_distance_m=200.0,
    )


def angle_at(profile, azimuth):
    idx = int(np.argmin(np.abs(profile.azimuth_deg - azimuth)))
    return profile.elevation_deg[idx]


def test_flat_terrain_has_zero_horizon(tmp_path):
    dem_path, _ = make_dem(tmp_path)
    profile = run_profile(dem_path)
    assert np.allclose(profile.elevation_deg, 0.0)


def test_north_wall_is_detected_at_north(tmp_path):
    dem_path, _ = make_dem(tmp_path, wall="north")
    profile = run_profile(dem_path)
    expected = np.degrees(np.arctan2(10.0, 25.0))
    assert np.isclose(angle_at(profile, 0), expected)
    assert np.isclose(angle_at(profile, 180), 0.0)
    assert profile.azimuth_deg[np.nanargmax(profile.elevation_deg)] == 0.0


def test_south_wall_is_detected_at_south(tmp_path):
    dem_path, _ = make_dem(tmp_path, wall="south")
    profile = run_profile(dem_path)
    expected = np.degrees(np.arctan2(10.0, 25.0))
    assert np.isclose(angle_at(profile, 180), expected)
    assert np.isclose(angle_at(profile, 0), 0.0)
    assert angle_at(profile, 180) > angle_at(profile, 0)


def test_zero_density_is_reported_for_wall(tmp_path):
    dem_path, density_path = make_dem(
        tmp_path, wall="north", density_wall=True
    )
    profile = run_profile(dem_path, density_path)
    assert profile.zero_density_fraction[0] > 0.0


def test_georeference_remains_unvalidated(tmp_path):
    dem_path, _ = make_dem(tmp_path)
    profile = run_profile(dem_path)
    assert profile.georeference_validated is False


def test_invalid_azimuth_step_raises(tmp_path):
    import pytest

    dem_path, _ = make_dem(tmp_path)
    with pytest.raises(ValueError, match="azimuth_step_deg"):
        calculate_horizon(dem_path, 0.0, 0.0, azimuth_step_deg=0)


def test_nonpositive_max_distance_raises(tmp_path):
    import pytest

    dem_path, _ = make_dem(tmp_path)
    with pytest.raises(ValueError, match="max_distance_m"):
        calculate_horizon(dem_path, 0.0, 0.0, max_distance_m=-5)


def test_observer_outside_dem_raises(tmp_path):
    import pytest

    dem_path, _ = make_dem(tmp_path)
    with pytest.raises(ValueError, match="fuori dal raster"):
        calculate_horizon(dem_path, 10000.0, 10000.0)


def test_observer_on_nodata_raises(tmp_path):
    import pytest

    dem_path, _ = make_dem(tmp_path)
    with rasterio.open(dem_path, "r+") as ds:
        ds.write(np.array([[np.nan]], dtype=np.float32), 1, window=((50, 51), (50, 51)))

    with pytest.raises(ValueError, match="Quota osservatore non valida"):
        calculate_horizon(dem_path, 0.0, 0.0)

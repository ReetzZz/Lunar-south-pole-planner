# Last updated: 2026-11-14
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from src.local_site_analysis import analyze_local_site


def make_raster(path, data, transform=None, crs="EPSG:3857"):
    if transform is None:
        transform = from_origin(-252.5, 252.5, 5, 5)
    with rasterio.open(
        path, "w", driver="GTiff",
        height=data.shape[0], width=data.shape[1],
        count=1, dtype="float32", crs=crs,
        transform=transform, nodata=np.nan,
    ) as ds:
        ds.write(data.astype("float32"), 1)


def test_local_report_for_flat_dem(tmp_path):
    dem = tmp_path / "dem.tif"
    make_raster(dem, np.zeros((101, 101), dtype=np.float32))

    report = analyze_local_site(
        "test", dem, 0.0, 0.0, max_distance_m=200
    )

    assert report.site_name == "test"
    assert report.elevation_m == pytest.approx(0.0)
    assert report.valid_azimuth_fraction == pytest.approx(1.0)
    assert report.mean_horizon_deg == pytest.approx(0.0)
    assert report.georeference_validated is False
    assert report.warnings


def test_misaligned_auxiliary_rejected(tmp_path):
    dem = tmp_path / "dem.tif"
    aux = tmp_path / "aux.tif"
    array = np.zeros((101, 101), dtype=np.float32)
    make_raster(dem, array)
    make_raster(aux, array, transform=from_origin(-250, 250, 5, 5))

    with pytest.raises(ValueError, match="non allineato"):
        analyze_local_site(
            "test", dem, 0.0, 0.0,
            density_path=aux, max_distance_m=200
        )


def test_nonfinite_observer_rejected(tmp_path):
    dem = tmp_path / "dem.tif"
    make_raster(dem, np.zeros((101, 101), dtype=np.float32))

    with pytest.raises(ValueError, match="observer_x_m"):
        analyze_local_site(
            "test", dem, float("nan"), 0.0, max_distance_m=200
        )

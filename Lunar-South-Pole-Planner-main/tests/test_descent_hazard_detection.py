# Last updated: 2026-11-14
import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from src.descent_hazard_detection import analyze_descent_patch


def make_dem(path, data):
    with rasterio.open(
        path, "w", driver="GTiff",
        width=data.shape[1], height=data.shape[0],
        count=1, dtype="float32", crs="EPSG:3857",
        transform=from_origin(0, data.shape[0], 1, 1), nodata=-9999.0,
    ) as ds:
        ds.write(data.astype("float32"), 1)


def test_flat_terrain_is_potentially_acceptable(tmp_path):
    path = tmp_path / "flat.tif"
    make_dem(path, np.full((21, 21), 100.0))
    result = analyze_descent_patch(path, (10, 10), radius_cells=3)
    assert result["decision"] == "POTENZIALMENTE_ACCETTABILE"
    assert result["metrics"]["max_local_slope_deg"] == pytest.approx(0)
    assert result["metrics"]["mae_scan_vs_dem_m"] == pytest.approx(0)


def test_synthetic_obstacle_is_detected(tmp_path):
    path = tmp_path / "flat.tif"
    make_dem(path, np.full((21, 21), 100.0))
    result = analyze_descent_patch(
        path, (10, 10), radius_cells=3,
        synthetic_obstacle_height_m=8.0, max_discrepancy_m=1.5,
    )
    assert result["decision"] == "EVITARE"
    assert result["metrics"]["max_absolute_discrepancy_m"] == pytest.approx(8.0)
    assert any("Discrepanza" in reason for reason in result["decision_reasons"])


def test_insufficient_scan_coverage_is_rejected(tmp_path):
    path = tmp_path / "flat.tif"
    make_dem(path, np.full((21, 21), 100.0))
    scan = np.full((7, 7), np.nan)
    scan[0, 0] = 100.0
    result = analyze_descent_patch(
        path, (10, 10), radius_cells=3,
        scan_elevation_m=scan, min_coverage=0.9,
    )
    assert result["decision"] == "DATI_INSUFFICIENTI"
    assert result["coverage"]["fraction"] < 0.9


def test_json_report_and_scan_shape_validation(tmp_path):
    path = tmp_path / "flat.tif"
    report_path = tmp_path / "report.json"
    make_dem(path, np.full((21, 21), 100.0))
    result = analyze_descent_patch(
        path, (10, 10), radius_cells=2, output_path=report_path,
    )
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["schema"] == "lunar-descent-hazard-report/1.0"
    assert saved["decision"] == result["decision"]
    assert len(saved["warnings"]) >= 4
    with pytest.raises(ValueError, match="forma"):
        analyze_descent_patch(
            path, (10, 10), radius_cells=2,
            scan_elevation_m=np.zeros((2, 2)),
        )

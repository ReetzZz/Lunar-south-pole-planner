# Last updated: 2026-11-14
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.confidence_validation import validate_confidence_raster


def make_raster(path: Path, data: np.ndarray) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[1],
        height=data.shape[0],
        count=1,
        dtype="uint8",
        transform=from_origin(0, data.shape[0], 1, 1),
    ) as ds:
        ds.write(data, 1)


def test_reports_documented_and_undocumented_classes(tmp_path):
    path = tmp_path / "confidence.tif"
    make_raster(path, np.array([[0, 1, 2], [4, 14, 255]], dtype=np.uint8))

    result = validate_confidence_raster(path)

    assert result.exists
    assert result.total_pixels == 6
    assert result.class_counts == {0: 1, 1: 1, 2: 1, 4: 1, 14: 1, 255: 1}
    assert result.nodata_pixels == 1
    assert result.shadow_pixels == 1
    assert result.interpolated_extrapolated_pixels == 1
    assert result.image_matching_pixels == 1
    assert result.undocumented_classes == (2, 255)
    assert any("senza significato verificato" in warning for warning in result.warnings)


def test_missing_file_is_reported(tmp_path):
    result = validate_confidence_raster(tmp_path / "missing.tif")

    assert not result.exists
    assert result.total_pixels == 0
    assert result.warnings


def test_real_pds3_reconstruction_preserves_expected_classes():
    path = Path(
        "data/terrain/processed/"
        "NAC_DTM_ESALL_SR12_CONF_PDS3_exact_20261025-131507.tif"
    )
    if not path.is_file():
        return

    result = validate_confidence_raster(path)

    assert result.exists
    assert result.total_pixels == 2500 * 2500
    assert result.class_counts == {
        0: 520525,
        1: 1417451,
        2: 611,
        4: 130067,
        5: 255,
        6: 341,
        12: 1,
        14: 4180749,
    }
    assert result.undocumented_classes == (2, 5, 6, 12)

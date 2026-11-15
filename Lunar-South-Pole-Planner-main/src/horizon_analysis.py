# Last updated: 2026-11-14
"""Esportazione del profilo dell'orizzonte locale da una cella DEM.

Il profilo è espresso nell'orientamento della griglia raster. Non deve essere
confrontato direttamente con gli azimut astronomici di Horizons finché la
trasformazione tra assi della griglia e nord locale non sia stata validata.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import rasterio

from src.terrain_horizon import calculate_horizon


def calculate_and_write_horizon(
    dem_path: str | Path,
    row: int,
    col: int,
    *,
    observer_height_m: float = 1.0,
    azimuth_step_deg: float = 2.0,
    max_distance_m: float = 5000.0,
    output_path: str | Path = "reports/local_horizon_profile.json",
) -> Path:
    """Calculate a grid-frame horizon profile and save it as JSON.

    The selected observer is the center of a DEM pixel, specified by zero-based
    row/column. No coordinate transform, DEM, or source metadata is modified.
    """
    raster = Path(dem_path)
    if not raster.is_file():
        raise FileNotFoundError(f"DEM non trovato: {raster}")
    if observer_height_m < 0:
        raise ValueError("L'altezza dell'osservatore non può essere negativa.")

    with rasterio.open(raster) as ds:
        row, col = int(row), int(col)
        if not (0 <= row < ds.height and 0 <= col < ds.width):
            raise ValueError(
                f"Cella fuori raster: riga 0..{ds.height - 1}, "
                f"colonna 0..{ds.width - 1}."
            )
        x, y = rasterio.transform.xy(ds.transform, row, col, offset="center")
        crs = str(ds.crs) if ds.crs else None
        pixel_x = abs(float(ds.transform.a))
        pixel_y = abs(float(ds.transform.e))

    profile = calculate_horizon(
        raster,
        float(x),
        float(y),
        azimuth_step_deg=azimuth_step_deg,
        max_distance_m=max_distance_m,
        observer_height_m=observer_height_m,
    )

    samples = []
    for i, azimuth in enumerate(profile.azimuth_deg):
        elevation = float(profile.elevation_deg[i])
        samples.append({
            "grid_azimuth_deg": float(azimuth),
            "horizon_elevation_deg": elevation if elevation == elevation else None,
            "max_obstacle_distance_m": float(profile.max_distance_m[i]),
            "valid_samples": int(profile.valid_samples[i]),
        })

    result = {
        "schema": "lunar-local-horizon-profile/1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_dem": str(raster),
        "crs_wkt": crs,
        "observer": {
            "grid_row": row,
            "grid_col": col,
            "x_map_units": float(x),
            "y_map_units": float(y),
            "height_above_dem_m": float(observer_height_m),
            "ground_elevation_m": float(profile.observer_elevation_m - observer_height_m),
        },
        "sampling": {
            "azimuth_step_deg": float(azimuth_step_deg),
            "max_distance_m": float(max_distance_m),
            "pixel_size_x_map_units": pixel_x,
            "pixel_size_y_map_units": pixel_y,
            "azimuth_frame": "raster grid axes; not certified true-north azimuth",
        },
        "georeference_validated": False,
        "warnings": [
            "Profilo diagnostico calcolato dal DEM selezionato.",
            "Azimut riferiti agli assi della griglia raster; non confrontare direttamente con Horizons senza validare la rotazione verso il nord locale.",
            "La georeferenziazione fisica del sito lunare non è validata indipendentemente.",
            "Il profilo non costituisce da solo una previsione di illuminazione, energia solare o disponibilità radio.",
        ],
        "samples": samples,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return out

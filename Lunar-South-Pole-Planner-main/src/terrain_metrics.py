# Last updated: 2026-11-14
"""Local terrain metrics sampled by DEM row/column, without geographic assumptions.

These metrics describe a raster neighborhood only. They do not validate CRS alignment
or claim that the selected pixel corresponds to a named lunar site.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import numpy as np
import rasterio

@dataclass(frozen=True)
class LocalTerrainMetrics:
    raster_path: str
    center_row: int
    center_col: int
    radius_pixels: int
    window_shape: tuple[int, int]
    valid_pixels: int
    total_pixels: int
    valid_fraction: float
    pixel_size_x_m: float
    pixel_size_y_m: float
    center_elevation_m: float | None
    slope_at_center_deg: float | None
    slope_median_deg: float | None
    slope_p95_deg: float | None
    roughness_plane_residual_std_m: float | None
    warning: str = ("Metriche locali in coordinate di griglia; CRS e corrispondenza fisica "
                   "del sito non sono validati. La rugosità è la deviazione standard "
                   "dei residui rispetto a un piano locale.")
    generated_utc: str = ""
    def to_dict(self):
        return asdict(self)

def analyze_local_terrain(raster_path, center_row: int, center_col: int, radius_pixels: int = 10) -> LocalTerrainMetrics:
    path = Path(raster_path)
    if radius_pixels < 2 or radius_pixels > 250:
        raise ValueError("radius_pixels deve essere compreso tra 2 e 250.")
    with rasterio.open(path) as ds:
        row, col = int(center_row), int(center_col)
        if not (0 <= row < ds.height and 0 <= col < ds.width):
            raise ValueError(f"Centro fuori raster: riga 0..{ds.height-1}, colonna 0..{ds.width-1}.")
        r0, r1 = max(0, row-radius_pixels), min(ds.height, row+radius_pixels+1)
        c0, c1 = max(0, col-radius_pixels), min(ds.width, col+radius_pixels+1)
        arr = ds.read(1, window=((r0,r1),(c0,c1)), masked=True).astype(np.float64)
        z = np.asarray(arr.filled(np.nan), dtype=float)
        if ds.nodata is not None:
            z[np.isclose(z, ds.nodata, equal_nan=True)] = np.nan
        z[~np.isfinite(z)] = np.nan
        valid = np.isfinite(z)
        count = int(valid.sum()); total = int(z.size)
        px, py = abs(float(ds.transform.a)), abs(float(ds.transform.e))
        cr, cc = row-r0, col-c0
        center = float(z[cr,cc]) if np.isfinite(z[cr,cc]) else None
        if count < 9:
            raise ValueError(f"Copertura valida insufficiente nella finestra: {count}/{total} pixel.")
        # Derivatives use local metric pixel spacing. Fill holes only for gradient calculation;
        # valid-only gradient cells are then retained for statistics.
        filled = z.copy()
        med = float(np.nanmedian(filled))
        filled[~np.isfinite(filled)] = med
        dz_drow, dz_dcol = np.gradient(filled, py, px)
        slope = np.degrees(np.arctan(np.hypot(dz_dcol, dz_drow)))
        # Least-squares plane residuals provide a scale-aware local roughness measure.
        rr, cc_grid = np.indices(z.shape)
        x = (cc_grid-(cc-0))*px
        y = -(rr-(cr-0))*py
        good = valid
        design = np.column_stack([x[good], y[good], np.ones(count)])
        coeff, *_ = np.linalg.lstsq(design, z[good], rcond=None)
        residual = z[good] - design @ coeff
        local_slopes = slope[good]
        center_slope = float(slope[cr,cc]) if valid[cr,cc] else None
        return LocalTerrainMetrics(
            raster_path=str(path), center_row=row, center_col=col, radius_pixels=radius_pixels,
            window_shape=tuple(map(int,z.shape)), valid_pixels=count, total_pixels=total,
            valid_fraction=count/total, pixel_size_x_m=px, pixel_size_y_m=py,
            center_elevation_m=center, slope_at_center_deg=center_slope,
            slope_median_deg=float(np.median(local_slopes)),
            slope_p95_deg=float(np.percentile(local_slopes,95)),
            roughness_plane_residual_std_m=float(np.std(residual)),
            generated_utc=datetime.now(timezone.utc).isoformat(),
        )

def write_metrics(metrics: LocalTerrainMetrics, output_path="reports/local_terrain_metrics.json") -> Path:
    out=Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out

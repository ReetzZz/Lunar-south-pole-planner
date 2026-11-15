# Last updated: 2026-11-14
"""Audit di qualità per DEM lunari senza modificare i raster originali.

I controlli descrivono metadati e copertura; non certificano da soli il frame
geodetico o la co-registrazione fisica dei prodotti.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
import math
import numpy as np
import rasterio

@dataclass(frozen=True)
class RasterAudit:
    path: str
    exists: bool
    width: int | None = None
    height: int | None = None
    resolution_x_m: float | None = None
    resolution_y_m: float | None = None
    crs_wkt: str | None = None
    bounds: tuple[float, float, float, float] | None = None
    nodata: float | str | None = None
    valid_pixels: int | None = None
    total_pixels: int | None = None
    valid_percent: float | None = None
    elevation_min_m: float | None = None
    elevation_median_m: float | None = None
    elevation_max_m: float | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self):
        return asdict(self)


def audit_raster(path: str | Path) -> RasterAudit:
    p = Path(path)
    if not p.is_file():
        return RasterAudit(path=str(p), exists=False, warnings=("File non trovato.",))
    warnings = []
    with rasterio.open(p) as ds:
        arr = ds.read(1, masked=True).astype(np.float64)
        vals = arr.compressed()
        vals = vals[np.isfinite(vals)]
        total = int(ds.width * ds.height)
        valid = int(vals.size)
        if ds.crs is None:
            warnings.append("CRS assente.")
        else:
            crs_text = ds.crs.to_wkt().lower()
            if "unknown" in crs_text or 'datum["unknown"' in crs_text:
                warnings.append("Datum dichiarato sconosciuto: frame lunare da validare.")
        if ds.units[0] is None:
            warnings.append("Unità della banda non dichiarate; verificare che le quote siano in metri.")
        if valid == 0:
            warnings.append("Nessun pixel valido.")
        return RasterAudit(
            path=str(p), exists=True, width=ds.width, height=ds.height,
            resolution_x_m=float(abs(ds.transform.a)),
            resolution_y_m=float(abs(ds.transform.e)),
            crs_wkt=ds.crs.to_wkt() if ds.crs else None,
            bounds=(float(ds.bounds.left), float(ds.bounds.bottom), float(ds.bounds.right), float(ds.bounds.top)),
            nodata=(float(ds.nodata) if ds.nodata is not None and math.isfinite(ds.nodata) else str(ds.nodata)),
            valid_pixels=valid, total_pixels=total,
            valid_percent=(100.0 * valid / total if total else 0.0),
            elevation_min_m=(float(np.min(vals)) if valid else None),
            elevation_median_m=(float(np.median(vals)) if valid else None),
            elevation_max_m=(float(np.max(vals)) if valid else None),
            warnings=tuple(warnings),
        )


def compare_grid_metadata(reference_path: str | Path, candidate_path: str | Path) -> dict:
    """Report metadata compatibility only; never asserts physical alignment."""
    a, b = audit_raster(reference_path), audit_raster(candidate_path)
    if not a.exists or not b.exists:
        return {"compatible_grid": False, "reason": "Uno o entrambi i raster non esistono.", "reference": a.to_dict(), "candidate": b.to_dict()}
    with rasterio.open(reference_path) as ra, rasterio.open(candidate_path) as rb:
        same_crs = ra.crs == rb.crs
        same_shape = (ra.width, ra.height) == (rb.width, rb.height)
        same_transform = ra.transform == rb.transform
    return {
        "compatible_grid": bool(same_crs and same_shape and same_transform),
        "same_crs": bool(same_crs), "same_shape": bool(same_shape),
        "same_transform": bool(same_transform),
        "physical_georeference_validated": False,
        "warning": "Compatibilità dei metadati non equivale a co-registrazione geodetica validata.",
        "reference": a.to_dict(), "candidate": b.to_dict(),
    }

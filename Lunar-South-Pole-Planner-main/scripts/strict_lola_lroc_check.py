# Last updated: 2026-11-14
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

ROOT = Path.cwd()
LOLA = ROOT / "data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif"
LROC = ROOT / "data/terrain/reference-lroc/NAC_DTM_ESALL_SR12.TIF"
OUT = ROOT / "reports/strict_lola_lroc_summary.json"

# Finestre di controllo in coordinate proiettate, metri.
CENTERS = [
    {"name": "zona_1", "x": -580.0, "y": -9090.0},
    {"name": "zona_2", "x": -4900.0, "y": -5380.0},
    {"name": "zona_3", "x": -4020.0, "y": -6170.0},
]
RADIUS_PIXELS = 40

def window_stats(a, b, strict, row, col, radius):
    r0, r1 = max(0, row-radius), min(a.shape[0], row+radius+1)
    c0, c1 = max(0, col-radius), min(a.shape[1], col+radius+1)
    aa = a[r0:r1, c0:c1]
    bb = b[r0:r1, c0:c1]
    ss = strict[r0:r1, c0:c1]
    valid = np.isfinite(aa) & np.isfinite(bb) & ss
    d = aa[valid].astype(np.float64) - bb[valid].astype(np.float64)

    result = {
        "window_pixels": int(aa.size),
        "strict_common_pixels": int(valid.sum()),
        "strict_coverage_percent": round(float(valid.mean()*100), 4),
    }
    if d.size:
        result.update({
            "median_difference_m": round(float(np.median(d)), 4),
            "mae_m": round(float(np.mean(np.abs(d))), 4),
            "rmse_m": round(float(np.sqrt(np.mean(d*d))), 4),
            "p95_abs_difference_m": round(float(np.percentile(np.abs(d), 95)), 4),
            "count_abs_diff_gt_10m": int((np.abs(d) > 10).sum()),
            "count_abs_diff_gt_100m": int((np.abs(d) > 100).sum()),
        })
    else:
        result["note"] = "Nessun campione valido dopo il filtro rigoroso."
    return result

with rasterio.open(LOLA) as ref, rasterio.open(LROC) as src:
    lola = ref.read(1, masked=True).filled(np.nan).astype(np.float32)
    src_data = src.read(1, masked=True).filled(np.nan).astype(np.float32)
    src_valid = src.read_masks(1) > 0
    src_valid &= np.isfinite(src_data)

    # Ricampionamento bilineare delle quote.
    lroc = np.full(lola.shape, np.nan, dtype=np.float32)
    reproject(
        source=src_data,
        destination=lroc,
        src_transform=src.transform,
        src_crs=src.crs,
        src_nodata=np.nan,
        dst_transform=ref.transform,
        dst_crs=ref.crs,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )

    # Ricampiona la maschera con nearest-neighbor.
    mask_nn = np.zeros(lola.shape, dtype=np.uint8)
    reproject(
        source=src_valid.astype(np.uint8),
        destination=mask_nn,
        src_transform=src.transform,
        src_crs=src.crs,
        dst_transform=ref.transform,
        dst_crs=ref.crs,
        resampling=Resampling.nearest,
    )

    # Per il filtro rigoroso: tutte le celle sorgente valide in una
    # finestra 2x2 devono contribuire alla bilineare.
    # Usiamo un ricampionamento conservativo della maschera:
    # se la bilineare della maschera non è praticamente 1, scartiamo.
    mask_fraction = np.zeros(lola.shape, dtype=np.float32)
    reproject(
        source=src_valid.astype(np.float32),
        destination=mask_fraction,
        src_transform=src.transform,
        src_crs=src.crs,
        dst_transform=ref.transform,
        dst_crs=ref.crs,
        resampling=Resampling.bilinear,
    )

    strict = (
        (mask_nn == 1)
        & (mask_fraction >= 0.999)
        & np.isfinite(lola)
        & np.isfinite(lroc)
    )

    valid_all = np.isfinite(lola) & np.isfinite(lroc)
    result = {
        "method": "LOLA-LROC preliminary strict-mask comparison",
        "strict_rule": "nearest valid plus bilinear-resampled source mask >= 0.999",
        "warning": (
            "CRS/geodetic alignment is not independently validated. "
            "This mask test is diagnostic, not a geodetic correction."
        ),
        "global": {
            "lola_pixels": int(lola.size),
            "common_pixels_before_strict_filter": int(valid_all.sum()),
            "common_pixels_after_strict_filter": int(strict.sum()),
            "strict_coverage_percent_of_lola": round(float(strict.mean()*100), 4),
        },
        "zones": [],
    }

    for center in CENTERS:
        row, col = ref.index(center["x"], center["y"])
        zone = {
            **center,
            "lola_row": int(row),
            "lola_col": int(col),
            "stats": window_stats(
                lola, lroc, strict, row, col, RADIUS_PIXELS
            ),
        }
        result["zones"].append(zone)

OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
print("\nRapporto salvato:", OUT)
print("Nessun raster originale modificato.")

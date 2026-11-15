# Last updated: 2026-11-14
"""Confronto diagnostico LOLA-LROC con filtro per confidenza PDS3.

Non modifica i raster e non certifica l'allineamento geodetico.
Le statistiche per codice descrivono il confronto, non la sicurezza del rover.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling


DOCUMENTED_CLASSES = {
    0: "NoDATA / fuori dal perimetro valido",
    1: "Ombra",
    4: "Interpolato o estrapolato",
    14: "Basato sui risultati dell'image matching",
}


def compare_lola_lroc_quality(
    lola_path: str | Path,
    lroc_path: str | Path,
    confidence_path: str | Path,
    output_path: str | Path,
) -> dict:
    """Produce statistiche per classe e residui del solo codice originale 14."""
    for path in (lola_path, lroc_path, confidence_path):
        if not Path(path).is_file():
            raise FileNotFoundError(f"File raster non trovato: {path}")

    with rasterio.open(lola_path) as lo, \
         rasterio.open(lroc_path) as lr, \
         rasterio.open(confidence_path) as cf:

        if lo.count != 1 or lr.count != 1 or cf.count != 1:
            raise ValueError("I tre raster devono avere una sola banda.")
        if lo.crs is None or lr.crs is None or cf.crs is None:
            raise ValueError("CRS assente: confronto interrotto per sicurezza.")
        if cf.dtypes[0] != "uint8":
            raise ValueError("La confidenza originale deve essere uint8.")

        lola = lo.read(1, masked=True).astype(np.float64).filled(np.nan)
        lroc = np.full(lola.shape, np.nan, dtype=np.float32)
        codes = np.zeros(lola.shape, dtype=np.uint8)

        reproject(
            source=rasterio.band(lr, 1),
            destination=lroc,
            src_transform=lr.transform,
            src_crs=lr.crs,
            src_nodata=lr.nodata,
            dst_transform=lo.transform,
            dst_crs=lo.crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        reproject(
            source=rasterio.band(cf, 1),
            destination=codes,
            src_transform=cf.transform,
            src_crs=cf.crs,
            src_nodata=cf.nodata,
            dst_transform=lo.transform,
            dst_crs=lo.crs,
            dst_nodata=0,
            resampling=Resampling.nearest,
        )

    valid = np.isfinite(lola) & np.isfinite(lroc) & (codes > 0)
    delta = lroc.astype(np.float64) - lola
    abs_delta = np.abs(delta)

    def stats(mask: np.ndarray) -> dict:
        d = delta[mask]
        ad = np.abs(d)
        if d.size == 0:
            return {
                "pixel_count": 0,
                "median_difference_m": None,
                "mean_difference_m": None,
                "mae_m": None,
                "rmse_m": None,
                "p95_absolute_difference_m": None,
                "max_absolute_difference_m": None,
                "absolute_difference_over_10m": 0,
                "absolute_difference_over_50m": 0,
                "absolute_difference_over_100m": 0,
            }
        return {
            "pixel_count": int(d.size),
            "median_difference_m": float(np.median(d)),
            "mean_difference_m": float(np.mean(d)),
            "mae_m": float(np.mean(ad)),
            "rmse_m": float(np.sqrt(np.mean(d * d))),
            "p95_absolute_difference_m": float(np.percentile(ad, 95)),
            "max_absolute_difference_m": float(np.max(ad)),
            "absolute_difference_over_10m": int(np.sum(ad > 10)),
            "absolute_difference_over_50m": int(np.sum(ad > 50)),
            "absolute_difference_over_100m": int(np.sum(ad > 100)),
        }

    per_class = {}
    class_counts = {}
    for code in sorted(int(x) for x in np.unique(codes[valid])):
        mask = valid & (codes == code)
        per_class[str(code)] = {
            "description": DOCUMENTED_CLASSES.get(
                code, "Classe non documentata nell'etichetta consultata"
            ),
            **stats(mask),
        }
        class_counts[str(code)] = int(mask.sum())

    output = {
        "schema": "lola-lroc-quality-report/1.0",
        "method": "LROC bilinear resampling on LOLA grid; confidence nearest",
        "sources": {
            "lola_dem": str(lola_path),
            "lroc_dem": str(lroc_path),
            "lroc_original_confidence": str(confidence_path),
        },
        "valid_overlap_pixels": int(valid.sum()),
        "confidence_class_counts_on_overlap": class_counts,
        "by_confidence_class": per_class,
        "code_14_reference_comparison": stats(valid & (codes == 14)),
        "warnings": [
            "Confronto diagnostico, non validazione geodetica.",
            "Il codice 14 indica image matching riuscito, non certifica l'accuratezza assoluta.",
            "Le differenze non sono correzioni da applicare automaticamente alle quote.",
            "La confidenza LROC non è una maschera di percorribilità del rover.",
            "Il confronto non certifica frame fisico lunare o datum verticale equivalenti.",
        ],
    }

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "output_path": str(target),
        "valid_overlap_pixels": output["valid_overlap_pixels"],
        "code_14_mae_m": output["code_14_reference_comparison"]["mae_m"],
        "code_14_rmse_m": output["code_14_reference_comparison"]["rmse_m"],
        "class_counts": class_counts,
    }

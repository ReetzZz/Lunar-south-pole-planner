#!/usr/bin/env python3
# Last updated: 2026-11-14
"""Confronto diagnostico delle quote LOLA e LROC sulla griglia LOLA."""

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

ROOT = Path(__file__).resolve().parents[1]
LOLA_PATH = ROOT / "data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif"
LROC_PATH = ROOT / "data/terrain/reference-lroc/NAC_DTM_ESALL_SR12.TIF"
OUT = ROOT / "reports"
OUT.mkdir(exist_ok=True)


def main():
    print("Caricamento dei DEM...", flush=True)

    with rasterio.open(LOLA_PATH) as ref, rasterio.open(LROC_PATH) as src:
        lola = ref.read(1, masked=True).filled(np.nan).astype(np.float32)
        lroc_src = src.read(1, masked=True).filled(np.nan).astype(np.float32)
        lroc = np.full((ref.height, ref.width), np.nan, dtype=np.float32)

        reproject(
            source=lroc_src,
            destination=lroc,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

        transform = ref.transform
        crs_equal = ref.crs == src.crs
        resolution = ref.res

    valid = np.isfinite(lola) & np.isfinite(lroc)
    count = int(valid.sum())
    if count == 0:
        raise RuntimeError("Nessuna cella valida in comune.")

    diff = np.full(lola.shape, np.nan, dtype=np.float32)
    diff[valid] = lola[valid] - lroc[valid]
    values = diff[valid].astype(np.float64)

    stats = {
        "comparison": "LOLA minus LROC resampled to LOLA grid",
        "lola_file": str(LOLA_PATH.relative_to(ROOT)),
        "lroc_file": str(LROC_PATH.relative_to(ROOT)),
        "resampling": "bilinear",
        "crs_definitions_identical": crs_equal,
        "geodetic_alignment_validated": False,
        "valid_common_pixels": count,
        "bias_m": float(np.mean(values)),
        "mae_m": float(np.mean(np.abs(values))),
        "rmse_m": float(np.sqrt(np.mean(values**2))),
        "p95_absolute_difference_m": float(np.percentile(np.abs(values), 95)),
        "min_difference_m": float(np.min(values)),
        "max_difference_m": float(np.max(values)),
        "correlation": float(np.corrcoef(lola[valid], lroc[valid])[0, 1]),
        "warnings": [
            "Confronto diagnostico: il CRS LOLA e quello LROC non sono identici.",
            "La riproiezione usa le definizioni CRS dichiarate nei file.",
            "Somiglianza delle quote e correlazione non dimostrano allineamento geodetico.",
            "Le differenze comprendono anche risoluzione, interpolazione e caratteristiche dei dataset.",
        ],
    }

    # Mappa delle differenze. Percentili simmetrici per non lasciare
    # che pochi valori estremi rendano il resto illeggibile.
    limit = float(np.percentile(np.abs(values), 98))
    limit = max(limit, 0.1)

    fig, ax = plt.subplots(figsize=(11, 8))
    im = ax.imshow(
        np.ma.masked_invalid(diff),
        extent=(
            transform.c,
            transform.c + transform.a * diff.shape[1],
            transform.f + transform.e * diff.shape[0],
            transform.f,
        ),
        cmap="coolwarm",
        vmin=-limit,
        vmax=limit,
        interpolation="nearest",
        aspect="equal",
    )
    fig.colorbar(im, ax=ax, label="LOLA − LROC (m)")
    ax.set_xlabel("X del raster LOLA (m)")
    ax.set_ylabel("Y del raster LOLA (m)")
    ax.set_title(
        "Differenze di quota LOLA − LROC\n"
        "LROC riproiettato sulla griglia LOLA — confronto diagnostico"
    )
    fig.text(
        0.5, 0.015,
        "CRS/georeferenziazione non validati; scala colore limitata al 98° percentile",
        ha="center", fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    map_path = OUT / "lola_lroc_difference_map.png"
    fig.savefig(map_path, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(values, bins=120)
    ax.axvline(0, linestyle="--", linewidth=1)
    ax.axvline(stats["bias_m"], linestyle=":", linewidth=1.5,
               label=f"Bias = {stats['bias_m']:.3f} m")
    ax.set_xlabel("LOLA − LROC (m)")
    ax.set_ylabel("Numero di pixel")
    ax.set_title("Distribuzione delle differenze di quota")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    hist_path = OUT / "lola_lroc_difference_histogram.png"
    fig.savefig(hist_path, dpi=160)
    plt.close(fig)

    stats["outputs"] = [
        str(map_path.relative_to(ROOT)),
        str(hist_path.relative_to(ROOT)),
    ]
    json_path = OUT / "lola_lroc_comparison_summary.json"
    json_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n========== STATISTICHE ==========")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("\nFile creati:")
    print(map_path)
    print(hist_path)
    print(json_path)


if __name__ == "__main__":
    main()

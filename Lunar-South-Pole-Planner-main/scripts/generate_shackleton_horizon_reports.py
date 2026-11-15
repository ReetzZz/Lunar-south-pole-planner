#!/usr/bin/env python3
# Last updated: 2026-11-14
"""Genera grafici e report diagnostici dell'orizzonte del sito candidato."""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.local_site_analysis import analyze_local_site

DEM = ROOT / "data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif"
DENSITY = ROOT / "data/terrain/shackleton_site04_lola_density.tif"
ERROR = ROOT / "data/terrain/shackleton_site04_terrain_error.tif"
OUT = ROOT / "reports"

OBSERVER_X_M = -1000.037
OBSERVER_Y_M = -7000.346
AZIMUTH_STEP_DEG = 2.0
MAX_DISTANCE_M = 7000.0
OBSERVER_HEIGHT_M = 0.0


def main():
    if not DEM.is_file():
        raise FileNotFoundError(f"DEM non trovato: {DEM}")

    OUT.mkdir(parents=True, exist_ok=True)
    print("Calcolo profilo dell'orizzonte...", flush=True)
    print(f"DEM: {DEM}", flush=True)
    print(f"Passo azimutale: {AZIMUTH_STEP_DEG} gradi", flush=True)
    print(f"Distanza massima: {MAX_DISTANCE_M:.0f} m", flush=True)

    report = analyze_local_site(
        site_name="Shackleton — candidato provvisorio",
        dem_path=DEM,
        observer_x_m=OBSERVER_X_M,
        observer_y_m=OBSERVER_Y_M,
        density_path=DENSITY if DENSITY.is_file() else None,
        error_path=ERROR if ERROR.is_file() else None,
        azimuth_step_deg=AZIMUTH_STEP_DEG,
        max_distance_m=MAX_DISTANCE_M,
        observer_height_m=OBSERVER_HEIGHT_M,
    )

    h = report.horizon
    valid = np.isfinite(h.elevation_deg)
    if not np.any(valid):
        raise RuntimeError("Nessun azimut valido: impossibile generare i grafici.")

    # Grafico polare: 0° in alto e azimut in senso orario.
    polar_path = OUT / "shackleton_horizon_polar.png"
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="polar")
    theta = np.deg2rad(h.azimuth_deg)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.plot(theta[valid], h.elevation_deg[valid], linewidth=1.4)
    ax.set_title(
        "Orizzonte topografico preliminare — Shackleton\n"
        f"Passo {AZIMUTH_STEP_DEG:g}° | raggio {MAX_DISTANCE_M/1000:g} km",
        pad=22,
    )
    ax.set_ylabel("Elevazione apparente del terreno (°)", labelpad=24)
    ax.grid(True, alpha=0.35)
    fig.text(
        0.5, 0.015,
        "DIAGNOSTICO — georeferenziazione lunare non validata",
        ha="center", fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(polar_path, dpi=150)
    plt.close(fig)
    print(f"Creato: {polar_path}", flush=True)

    # Profilo lineare azimut-elevazione.
    distance_path = OUT / "shackleton_horizon_distance.png"
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(h.azimuth_deg[valid], h.elevation_deg[valid], linewidth=1.4)
    ax.set_xlabel("Azimut nella griglia raster (°)")
    ax.set_ylabel("Angolo massimo del terreno (°)")
    ax.set_title("Profilo dell'orizzonte per azimut — Shackleton")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 360)
    fig.text(
        0.5, 0.015,
        "DIAGNOSTICO — non rappresenta direttamente l'illuminazione solare",
        ha="center", fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(distance_path, dpi=150)
    plt.close(fig)
    print(f"Creato: {distance_path}", flush=True)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "site_name": report.site_name,
        "dem_path": str(DEM.relative_to(ROOT)),
        "observer": {
            "x_m": report.observer_x_m,
            "y_m": report.observer_y_m,
            "elevation_m": report.elevation_m,
            "height_above_dem_m": OBSERVER_HEIGHT_M,
            "row": int(h.observer_row),
            "col": int(h.observer_col),
        },
        "parameters": {
            "azimuth_step_deg": AZIMUTH_STEP_DEG,
            "max_distance_m": MAX_DISTANCE_M,
            "dem_pixel_size_m": 5.0,
        },
        "results": {
            "azimuth_count": int(len(h.azimuth_deg)),
            "valid_azimuth_fraction": report.valid_azimuth_fraction,
            "mean_horizon_deg": report.mean_horizon_deg,
            "max_horizon_deg": report.max_horizon_deg,
            "mean_zero_density_fraction": report.mean_zero_density_fraction,
            "mean_dem_error_m": report.mean_dem_error_m,
            "maximum_angle_azimuth_deg": (
                float(h.azimuth_deg[np.nanargmax(h.elevation_deg)])
            ),
            "maximum_angle_distance_m": (
                float(h.max_distance_m[np.nanargmax(h.elevation_deg)])
            ),
        },
        "georeference_validated": False,
        "warnings": list(report.warnings),
        "interpretation_note": (
            "Il profilo è un risultato diagnostico del DEM. "
            "Non costituisce una previsione certificata dell'illuminazione "
            "o una validazione della posizione lunare."
        ),
        "outputs": [
            str(polar_path.relative_to(ROOT)),
            str(distance_path.relative_to(ROOT)),
        ],
    }

    json_path = OUT / "shackleton_horizon_summary.json"
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Creato: {json_path}", flush=True)
    print("\n========== RISULTATI ==========")
    print(json.dumps(summary["results"], indent=2, ensure_ascii=False))
    print("\nGeoreferenziazione validata:", report.georeference_validated)
    print("Avvertenze:")
    for warning in report.warnings:
        print(f"- {warning}")


if __name__ == "__main__":
    main()

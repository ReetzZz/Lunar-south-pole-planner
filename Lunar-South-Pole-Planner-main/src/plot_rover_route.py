# Last updated: 2026-11-14
"""Esporta una visualizzazione diagnostica della rotta rover su DEM."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Visualizza la rotta rover e la pendenza locale sul DEM."
    )
    parser.add_argument(
        "--plan", default="reports/mission/rover_plan.json"
    )
    parser.add_argument(
        "--output", default="reports/mission/rover_route_map.png"
    )
    args = parser.parse_args()

    plan_path = Path(args.plan)
    output_path = Path(args.output)

    if not plan_path.is_file():
        parser.error(f"Piano rotta non trovato: {plan_path}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema") != "lunar-rover-route-plan/1.0":
        parser.error("Schema del piano rover non riconosciuto.")

    dem_path = Path(plan["dem_path"])
    if not dem_path.is_file():
        parser.error(f"DEM non trovato: {dem_path}")

    path_rc = plan.get("path_rc")
    if not isinstance(path_rc, list) or not path_rc:
        parser.error("Il piano non contiene una rotta valida.")

    path = np.asarray(path_rc, dtype=int)
    if path.ndim != 2 or path.shape[1] != 2:
        parser.error("Formato path_rc non valido.")

    with rasterio.open(dem_path) as ds:
        dem = ds.read(1, masked=True).astype("float64").filled(np.nan)
        px = abs(float(ds.transform.a))
        py = abs(float(ds.transform.e))
        crs = str(ds.crs) if ds.crs else "non dichiarato"

    if (
        np.any(path[:, 0] < 0) or np.any(path[:, 0] >= dem.shape[0])
        or np.any(path[:, 1] < 0) or np.any(path[:, 1] >= dem.shape[1])
    ):
        parser.error("La rotta contiene coordinate fuori dal DEM.")

    elevations = dem[path[:, 0], path[:, 1]]
    if not np.isfinite(elevations).all():
        parser.error("La rotta attraversa celle NoData del DEM.")

    margin = 12
    r0 = max(0, int(path[:, 0].min()) - margin)
    r1 = min(dem.shape[0], int(path[:, 0].max()) + margin + 1)
    c0 = max(0, int(path[:, 1].min()) - margin)
    c1 = min(dem.shape[1], int(path[:, 1].max()) + margin + 1)
    terrain = dem[r0:r1, c0:c1]

    valid = np.isfinite(terrain)
    if valid.sum() < 4:
        parser.error("Dati validi insufficienti nella finestra del terreno.")

    filled = terrain.copy()
    filled[~valid] = float(np.nanmedian(terrain))
    dz_dr, dz_dc = np.gradient(filled, py, px)
    slope = np.degrees(np.arctan(np.hypot(dz_dc, dz_dr)))
    slope[~valid] = np.nan

    local_rows = path[:, 0] - r0
    local_cols = path[:, 1] - c0
    route_distance = float(plan.get("distance_m", 0.0))
    max_slope = float(plan.get("max_slope_deg", 0.0))
    start_z = float(elevations[0])
    end_z = float(elevations[-1])

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)

    image1 = axes[0].imshow(
        terrain, origin="upper", cmap="terrain", interpolation="nearest"
    )
    axes[0].plot(local_cols, local_rows, color="red", linewidth=2.2,
                 label="Rotta A*")
    axes[0].scatter(local_cols[0], local_rows[0], color="lime",
                    edgecolors="black", s=85, zorder=5, label="Partenza")
    axes[0].scatter(local_cols[-1], local_rows[-1], color="cyan",
                    edgecolors="black", marker="*", s=150,
                    zorder=5, label="Destinazione")
    axes[0].set_title("Quota del terreno e rotta")
    axes[0].set_xlabel("Colonna DEM")
    axes[0].set_ylabel("Riga DEM")
    axes[0].legend(loc="best")
    fig.colorbar(image1, ax=axes[0], label="Quota DEM (unità originali)")

    image2 = axes[1].imshow(
        slope, origin="upper", cmap="magma", vmin=0, vmax=30,
        interpolation="nearest"
    )
    axes[1].plot(local_cols, local_rows, color="cyan", linewidth=2.2,
                 label="Rotta A*")
    axes[1].scatter(local_cols[0], local_rows[0], color="lime",
                    edgecolors="black", s=85, zorder=5, label="Partenza")
    axes[1].scatter(local_cols[-1], local_rows[-1], color="white",
                    edgecolors="black", marker="*", s=150,
                    zorder=5, label="Destinazione")
    axes[1].set_title("Pendenza locale stimata")
    axes[1].set_xlabel("Colonna DEM")
    axes[1].set_ylabel("Riga DEM")
    axes[1].legend(loc="best")
    fig.colorbar(image2, ax=axes[1], label="Pendenza (gradi)")

    fig.suptitle(
        f"ROVER ROUTE — {route_distance:.2f} m | "
        f"pendenza massima del piano: {max_slope:.2f}°\n"
        f"Quota iniziale: {start_z:.2f} | finale: {end_z:.2f} | "
        f"CRS: {crs}\n"
        "ANALISI PRELIMINARE — non certificata per operazioni di volo",
        fontsize=11,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print("Mappa salvata:", output_path)
    print("Dimensioni:", f"{terrain.shape[1]} x {terrain.shape[0]} celle")
    print("Risoluzione pixel:", f"x={px:g} m, y={py:g} m")
    print("Celle della rotta:", len(path))
    print("Distanza piano:", f"{route_distance:.2f} m")
    print("Pendenza massima registrata nel piano:", f"{max_slope:.2f}°")
    print("CRS:", crs)
    print("Nota: la pendenza mostrata è una stima derivata dal DEM.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

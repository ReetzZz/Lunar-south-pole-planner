# Last updated: 2026-11-14
"""Prototipo preliminare di rilevamento ostacoli durante la discesa lunare."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rasterio

SCHEMA = "lunar-descent-hazard-report/1.0"


def analyze_descent_patch(
    dem_path,
    center_rc,
    *,
    radius_cells=5,
    scan_elevation_m=None,
    noise_sigma_m=0.0,
    synthetic_obstacle_height_m=0.0,
    max_slope_deg=15.0,
    max_roughness_m=1.0,
    max_discrepancy_m=1.5,
    min_coverage=0.90,
    output_path=None,
    random_seed=0,
):
    """Analizza una finestra DEM confrontandola con una scansione laser simulata o fornita."""
    if not Path(dem_path).is_file():
        raise FileNotFoundError(f"DEM non trovato: {dem_path}")
    if isinstance(radius_cells, bool) or not isinstance(radius_cells, int) or radius_cells < 1:
        raise ValueError("radius_cells deve essere un intero >= 1.")

    params = {
        "noise_sigma_m": noise_sigma_m,
        "synthetic_obstacle_height_m": synthetic_obstacle_height_m,
        "max_slope_deg": max_slope_deg,
        "max_roughness_m": max_roughness_m,
        "max_discrepancy_m": max_discrepancy_m,
        "min_coverage": min_coverage,
    }
    for name, value in params.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} deve essere numerico.")
        if not math.isfinite(value):
            raise ValueError(f"{name} deve essere finito.")
    if noise_sigma_m < 0:
        raise ValueError("noise_sigma_m non può essere negativo.")
    if not 0 < max_slope_deg < 90:
        raise ValueError("max_slope_deg deve essere tra 0 e 90.")
    if max_roughness_m < 0 or max_discrepancy_m < 0:
        raise ValueError("Le soglie di rugosità e discrepanza devono essere >= 0.")
    if not 0 < min_coverage <= 1:
        raise ValueError("min_coverage deve essere in (0, 1].")

    try:
        row, col = center_rc
        if isinstance(row, bool) or isinstance(col, bool):
            raise ValueError
        row, col = int(row), int(col)
    except (TypeError, ValueError):
        raise ValueError("center_rc deve contenere riga e colonna intere.") from None

    with rasterio.open(dem_path) as ds:
        if ds.count != 1:
            raise ValueError("Il DEM deve avere una sola banda.")
        if ds.crs is None:
            raise ValueError("CRS assente: analisi interrotta per sicurezza.")
        if not (0 <= row < ds.height and 0 <= col < ds.width):
            raise ValueError("center_rc è fuori dal DEM.")

        r0, r1 = max(0, row - radius_cells), min(ds.height, row + radius_cells + 1)
        c0, c1 = max(0, col - radius_cells), min(ds.width, col + radius_cells + 1)
        dem = ds.read(1, window=((r0, r1), (c0, c1)), masked=True)
        dem = dem.astype("float64").filled(np.nan)
        px, py = abs(float(ds.transform.a)), abs(float(ds.transform.e))

    if not all(math.isfinite(v) and v > 0 for v in (px, py)):
        raise ValueError("Risoluzione del DEM non valida.")
    if min(dem.shape) < 2:
        raise ValueError("La finestra DEM è troppo piccola.")

    if scan_elevation_m is None:
        scan = dem.copy()
        rng = np.random.default_rng(random_seed)
        valid_dem = np.isfinite(scan)
        if noise_sigma_m:
            scan[valid_dem] += rng.normal(0, noise_sigma_m, int(valid_dem.sum()))
        if synthetic_obstacle_height_m:
            local_center = (row - r0, col - c0)
            if np.isfinite(scan[local_center]):
                scan[local_center] += synthetic_obstacle_height_m
        scan_source = "simulated_from_dem"
    else:
        scan = np.asarray(scan_elevation_m, dtype=float)
        if scan.shape != dem.shape:
            raise ValueError(f"La scansione deve avere forma {dem.shape}, ricevuta {scan.shape}.")
        scan_source = "provided_scan"

    total_cells = int(dem.size)
    valid = np.isfinite(dem) & np.isfinite(scan)
    valid_count = int(valid.sum())
    coverage = valid_count / total_cells if total_cells else 0.0
    warnings = [
        "Prototipo software preliminare: non certificato per un atterraggio reale.",
        "La scansione sintetica non riproduce geometria, dinamica o limiti reali del lidar.",
        "Il confronto presuppone DEM e scansione allineati nello stesso riferimento orizzontale e verticale.",
        "La classificazione non costituisce una garanzia di sicurezza.",
    ]

    reasons = []
    if valid_count:
        values = scan[valid]
        roughness = float(np.percentile(values, 95) - np.percentile(values, 5))
        filled = scan.copy()
        filled[~np.isfinite(filled)] = float(np.median(values))
        dz_row, dz_col = np.gradient(filled, py, px)
        slope = np.degrees(np.arctan(np.hypot(dz_col, dz_row)))
        max_slope = float(np.max(slope[valid]))
        delta = scan[valid] - dem[valid]
        abs_delta = np.abs(delta)
        mae = float(np.mean(abs_delta))
        p95_delta = float(np.percentile(abs_delta, 95))
        max_delta = float(np.max(abs_delta))
    else:
        roughness = max_slope = mae = p95_delta = max_delta = None

    if coverage < min_coverage or valid_count == 0:
        decision = "DATI_INSUFFICIENTI"
        reasons.append(f"Copertura {coverage:.3f}; richiesta almeno {min_coverage:.3f}.")
    else:
        if max_slope > max_slope_deg:
            reasons.append(f"Pendenza {max_slope:.3f}° oltre soglia {max_slope_deg:.3f}°.")
        if roughness > max_roughness_m:
            reasons.append(f"Rugosità proxy {roughness:.3f} m oltre soglia {max_roughness_m:.3f} m.")
        if p95_delta > max_discrepancy_m:
            reasons.append(
                f"Discrepanza P95 {p95_delta:.3f} m oltre soglia "
                f"{max_discrepancy_m:.3f} m."
            )
        # Il percentile può nascondere ostacoli piccoli ma molto alti.
        # Controlliamo anche la discrepanza massima per non ignorarli.
        if max_delta > max_discrepancy_m:
            reasons.append(
                f"Discrepanza massima {max_delta:.3f} m oltre soglia "
                f"{max_discrepancy_m:.3f} m."
            )
        decision = "EVITARE" if reasons else "POTENZIALMENTE_ACCETTABILE"
        if not reasons:
            reasons.append("Nessuna soglia configurata è stata superata.")

    # Mappa preliminare per cella: non equivale a una certificazione di sicurezza.
    cell_map = np.full(dem.shape, "DATI_INSUFFICIENTI", dtype=object)
    cell_valid = np.isfinite(dem) & np.isfinite(scan)

    if valid_count:
        scan_filled = scan.copy()
        scan_filled[~np.isfinite(scan_filled)] = float(np.median(scan[valid]))
        grad_row, grad_col = np.gradient(scan_filled, py, px)
        cell_slope = np.degrees(np.arctan(np.hypot(grad_col, grad_row)))
        cell_delta = np.abs(scan - dem)

        cell_map[cell_valid] = "ENTRO_SOGLIE"
        cell_risk = cell_valid & (
            (cell_slope > max_slope_deg)
            | (cell_delta > max_discrepancy_m)
        )
        cell_map[cell_risk] = "RISCHIO"

    cell_map_counts = {
        label: int(np.count_nonzero(cell_map == label))
        for label in ("ENTRO_SOGLIE", "RISCHIO", "DATI_INSUFFICIENTI")
    }

    report = {
        "schema": SCHEMA,
        "status": "preliminary",
        "decision": decision,
        "decision_reasons": reasons,
        "input": {
            "dem_path": str(dem_path),
            "center_rc": [row, col],
            "radius_cells": radius_cells,
            "scan_source": scan_source,
            "pixel_size_x_m": px,
            "pixel_size_y_m": py,
        },
        "coverage": {
            "valid_cells": valid_count,
            "total_cells": total_cells,
            "fraction": coverage,
            "required_fraction": min_coverage,
        },
        "metrics": {
            "max_local_slope_deg": max_slope,
            "roughness_p95_minus_p5_m": roughness,
            "mae_scan_vs_dem_m": mae,
            "p95_absolute_discrepancy_m": p95_delta,
            "max_absolute_discrepancy_m": max_delta,
        },
        "cell_risk_map": {
            "classification": cell_map.tolist(),
            "counts": cell_map_counts,
            "legend": {
                "ENTRO_SOGLIE": "Nessuna soglia locale superata; non certifica la sicurezza.",
                "RISCHIO": "Pendenza o discrepanza locale oltre soglia.",
                "DATI_INSUFFICIENTI": "DEM o scansione non validi in questa cella.",
            },
        },
        "thresholds": {
            "max_slope_deg": max_slope_deg,
            "max_roughness_m": max_roughness_m,
            "max_discrepancy_m": max_discrepancy_m,
        },
        "warnings": warnings,
    }

    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        report["output_path"] = str(target)
    return report

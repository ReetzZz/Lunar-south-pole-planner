# Last updated: 2026-11-14
"""Metriche diagnostiche della qualità geometrica di una rotta rover.

Opera esclusivamente in memoria e non modifica DEM o percorso.
Le metriche non costituiscono una certificazione di percorribilità.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math

import numpy as np


def analyze_route_quality(
    elevation_m,
    path_rc,
    pixel_size_x_m: float,
    pixel_size_y_m: float,
) -> dict:
    """Calcola dislivelli e pendenze lungo una rotta esistente."""
    dem = np.asarray(elevation_m, dtype=float)

    if dem.ndim != 2 or min(dem.shape) < 2:
        raise ValueError("Il DEM deve essere una matrice 2D almeno 2x2.")
    for name, value in (
        ("pixel_size_x_m", pixel_size_x_m),
        ("pixel_size_y_m", pixel_size_y_m),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} deve essere finito e positivo.")

    path = [tuple(map(int, point)) for point in path_rc]
    if not path:
        raise ValueError("Il percorso è vuoto.")

    for row, col in path:
        if not (0 <= row < dem.shape[0] and 0 <= col < dem.shape[1]):
            raise ValueError(f"Cella del percorso fuori DEM: {(row, col)}.")
        if not math.isfinite(float(dem[row, col])):
            raise ValueError(f"Cella NoData nel percorso: {(row, col)}.")

    if len(set(path)) != len(path):
        raise ValueError("Il percorso contiene celle duplicate.")

    valid = np.isfinite(dem)
    filled = dem.copy()
    if not valid.all():
        filled[~valid] = float(np.nanmedian(dem[valid]))

    dz_drow, dz_dcol = np.gradient(
        filled, float(pixel_size_y_m), float(pixel_size_x_m)
    )
    slope_field = np.degrees(
        np.arctan(np.hypot(dz_dcol, dz_drow))
    )
    slope_field[~valid] = np.nan

    distances = []
    edge_slopes = []
    gains = []
    losses = []

    for (r0, c0), (r1, c1) in zip(path, path[1:]):
        dr, dc = r1 - r0, c1 - c0
        if max(abs(dr), abs(dc)) != 1:
            raise ValueError(
                f"Passaggio non contiguo nella rotta: {(r0, c0)} -> {(r1, c1)}."
            )

        distance = math.hypot(
            dr * float(pixel_size_y_m),
            dc * float(pixel_size_x_m),
        )
        dz = float(dem[r1, c1] - dem[r0, c0])
        distances.append(distance)
        edge_slopes.append(math.degrees(math.atan2(abs(dz), distance)))
        gains.append(max(dz, 0.0))
        losses.append(max(-dz, 0.0))

    route_slopes = np.asarray(
        [slope_field[r, c] for r, c in path], dtype=float
    )
    route_slopes = route_slopes[np.isfinite(route_slopes)]
    elevations = np.asarray([dem[r, c] for r, c in path], dtype=float)
    total_distance = float(sum(distances))
    total_gain = float(sum(gains))
    total_loss = float(sum(losses))
    net_change = float(elevations[-1] - elevations[0])

    warnings = [
        "Metriche diagnostiche: non certificano la sicurezza o la percorribilità.",
        "La pendenza è stimata dal DEM; non include incertezza altimetrica.",
        "Le stime non modellano slittamento, ostacoli, dinamica o limiti meccanici.",
    ]
    if len(path) < 2:
        warnings.append("Percorso composto da una sola cella: nessun tratto valutabile.")
    if not valid.all():
        warnings.append("Il DEM contiene NoData; le celle non valide restano escluse dal percorso.")

    return {
        "schema": "lunar-rover-route-quality/1.0",
        "status": "diagnostic_only",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "path_cells": len(path),
        "path_segments": len(distances),
        "pixel_size_x_m": float(pixel_size_x_m),
        "pixel_size_y_m": float(pixel_size_y_m),
        "distance_m": total_distance,
        "start_elevation_m": float(elevations[0]),
        "end_elevation_m": float(elevations[-1]),
        "net_elevation_change_m": net_change,
        "cumulative_ascent_m": total_gain,
        "cumulative_descent_m": total_loss,
        "slope_median_deg": float(np.median(route_slopes)) if route_slopes.size else None,
        "slope_p95_deg": float(np.percentile(route_slopes, 95)) if route_slopes.size else None,
        "slope_max_deg": float(np.max(route_slopes)) if route_slopes.size else None,
        "max_edge_grade_deg": float(max(edge_slopes, default=0.0)),
        "valid_path_cell_fraction": float(
            sum(math.isfinite(float(dem[r, c])) for r, c in path) / len(path)
        ),
        "warnings": warnings,
    }

# Last updated: 2026-11-14
"""Preliminary physics-based rover route energy estimate.

This is an engineering estimate, not a validated vehicle model. It accounts for
rolling resistance, positive gravitational work while climbing, drivetrain
losses, and auxiliary load. It deliberately does not credit downhill regeneration
or solar generation unless those are modeled separately with validated inputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
import rasterio

LUNAR_GRAVITY_M_S2 = 1.62
JOULES_PER_WH = 3600.0


def estimate_route_energy(
    plan_json: str | Path = "reports/rover_plan.json",
    *,
    mass_kg: float,
    rolling_resistance_coefficient: float,
    drivetrain_efficiency: float,
    auxiliary_power_w: float,
    mission_duration_hours: float,
    battery_capacity_wh: float,
    reserve_percent: float = 20.0,
    output_path: str | Path = "reports/rover_energy_assessment.json",
) -> dict:
    """Estimate route energy from a saved row/column route and its source DEM."""
    params = {
        "mass_kg": mass_kg,
        "rolling_resistance_coefficient": rolling_resistance_coefficient,
        "drivetrain_efficiency": drivetrain_efficiency,
        "auxiliary_power_w": auxiliary_power_w,
        "mission_duration_hours": mission_duration_hours,
        "battery_capacity_wh": battery_capacity_wh,
        "reserve_percent": reserve_percent,
    }
    for name, value in params.items():
        if not math.isfinite(float(value)):
            raise ValueError(f"Parametro non finito: {name}")
    if mass_kg <= 0:
        raise ValueError("La massa deve essere maggiore di zero.")
    if rolling_resistance_coefficient < 0:
        raise ValueError("Il coefficiente di resistenza al rotolamento non può essere negativo.")
    if not 0 < drivetrain_efficiency <= 1:
        raise ValueError("L'efficienza della trasmissione deve essere in (0, 1].")
    if auxiliary_power_w < 0 or mission_duration_hours < 0 or battery_capacity_wh <= 0:
        raise ValueError("Potenza ausiliaria/durata non valide o capacità batteria non positiva.")
    if not 0 <= reserve_percent < 100:
        raise ValueError("La riserva deve essere compresa tra 0% incluso e 100% escluso.")

    plan_path = Path(plan_json)
    if not plan_path.is_file():
        raise FileNotFoundError(f"Piano rover non trovato: {plan_path}. Calcola prima un percorso.")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    route = plan.get("path_rc")
    dem_path = plan.get("dem_path")
    if not isinstance(route, list) or len(route) < 1:
        raise ValueError("Il piano non contiene una sequenza path_rc valida.")
    if not dem_path or not Path(dem_path).is_file():
        raise FileNotFoundError(f"DEM sorgente del piano non trovato: {dem_path!r}")

    cells = []
    for item in route:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("Una cella del percorso non ha formato [riga, colonna].")
        cells.append((int(item[0]), int(item[1])))

    with rasterio.open(dem_path) as ds:
        dem = ds.read(1, masked=True).astype(np.float64).filled(np.nan)
        px = abs(float(ds.transform.a))
        py = abs(float(ds.transform.e))
        if not math.isfinite(px) or not math.isfinite(py) or px <= 0 or py <= 0:
            raise ValueError("Risoluzione del DEM non valida.")
        for row, col in cells:
            if not (0 <= row < ds.height and 0 <= col < ds.width):
                raise ValueError(f"Cella del percorso fuori dal DEM: {(row, col)}")
            if not math.isfinite(float(dem[row, col])):
                raise ValueError(f"Il percorso attraversa una cella NoData: {(row, col)}")
        dem_name = str(dem_path)

    distance_m = 0.0
    positive_ascent_m = 0.0
    negative_descent_m = 0.0
    segment_count = 0
    for (r0, c0), (r1, c1) in zip(cells, cells[1:]):
        dr, dc = r1 - r0, c1 - c0
        if max(abs(dr), abs(dc)) > 1:
            raise ValueError("Il percorso contiene salti tra celle adiacenti; non è possibile stimare l'energia in sicurezza.")
        ds_m = math.hypot(dr * py, dc * px)
        dz = float(dem[r1, c1] - dem[r0, c0])
        distance_m += ds_m
        positive_ascent_m += max(0.0, dz)
        negative_descent_m += max(0.0, -dz)
        segment_count += 1

    rolling_j = rolling_resistance_coefficient * mass_kg * LUNAR_GRAVITY_M_S2 * distance_m
    climb_j = mass_kg * LUNAR_GRAVITY_M_S2 * positive_ascent_m
    traction_wh = (rolling_j + climb_j) / drivetrain_efficiency / JOULES_PER_WH
    auxiliary_wh = auxiliary_power_w * mission_duration_hours
    total_wh = traction_wh + auxiliary_wh
    usable_wh = battery_capacity_wh * (1.0 - reserve_percent / 100.0)
    result = {
        "schema": "lunar-rover-energy-assessment/1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "preliminary_estimate",
        "route_plan": str(plan_path),
        "dem_path": dem_name,
        "route_cells": len(cells),
        "segments": segment_count,
        "distance_m": round(distance_m, 3),
        "positive_ascent_m": round(positive_ascent_m, 3),
        "negative_descent_m": round(negative_descent_m, 3),
        "lunar_gravity_m_s2": LUNAR_GRAVITY_M_S2,
        "inputs": params,
        "energy_wh": {
            "rolling_resistance_before_drivetrain": round(rolling_j / JOULES_PER_WH, 4),
            "positive_climb_before_drivetrain": round(climb_j / JOULES_PER_WH, 4),
            "traction_after_drivetrain": round(traction_wh, 4),
            "auxiliary_load": round(auxiliary_wh, 4),
            "total_estimated": round(total_wh, 4),
            "usable_battery_after_reserve": round(usable_wh, 4),
            "remaining_after_estimate": round(usable_wh - total_wh, 4),
            "within_budget": bool(total_wh <= usable_wh),
        },
        "assumptions": [
            "La resistenza al rotolamento usa coefficiente costante e carico normale pari a massa x gravità lunare.",
            "Il lavoro contro gravità include solo dislivello positivo; nessun recupero in discesa è accreditato.",
            "La potenza ausiliaria è costante per tutta la durata indicata.",
            "Non sono modellati accelerazione, sterzata, slittamento, sinkage, deformazione del suolo, temperatura, degradazione batteria o margini di incertezza DEM.",
            "Nessun contributo solare è sottratto: la visibilità solare diagnostica non è una stima validata della potenza generata.",
            "Il risultato non è un modello qualificato per operazioni reali; parametri e percorso devono essere validati.",
        ],
        "warnings": [
            "Frame geodetico del DEM non validato indipendentemente.",
            "Stima di progetto preliminare; non usare come certificazione di autonomia o sicurezza del rover.",
        ],
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    result["output_path"] = str(out)
    return result

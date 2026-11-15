# Last updated: 2026-11-14
"""Coordinamento locale multi-rover con assegnazione deterministica dei task.

Il modello è un pianificatore di alto livello: posizioni e distanze devono essere
espresse nello stesso sistema metrico locale. Non calcola percorsi DEM, link radio,
finestre di illuminazione o sincronizzazione remota P-System.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any


def _finite_number(value: Any, name: str, *, minimum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: valore numerico richiesto") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name}: il valore deve essere finito")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name}: il valore minimo è {minimum}")
    return number


def _xy(value: Any, name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} deve essere [x, y] nel medesimo frame metrico locale")
    return (_finite_number(value[0], f"{name}[0]"), _finite_number(value[1], f"{name}[1]"))


def allocate_tasks(rovers: list[dict], tasks: list[dict], *, output_path: str | Path | None = None) -> dict:
    """Assegna task ai rover con capacità, budget energetico e bilanciamento carico.

    Rover schema: id, position_xy, capabilities, available_energy_wh,
    energy_wh_per_m (optional, default 0).
    Task schema: id, position_xy, required_capabilities (optional), priority,
    estimated_energy_wh (optional, default 0).
    """
    if not isinstance(rovers, list) or not rovers:
        raise ValueError("Specificare almeno un rover")
    if not isinstance(tasks, list):
        raise ValueError("tasks deve essere una lista")
    rover_state = {}
    for i, rover in enumerate(rovers):
        if not isinstance(rover, dict):
            raise ValueError(f"Rover #{i+1} non valido")
        rid = str(rover.get("id", "")).strip()
        if not rid or rid in rover_state:
            raise ValueError(f"ID rover mancante o duplicato: {rid!r}")
        caps = rover.get("capabilities", [])
        if not isinstance(caps, list) or not all(isinstance(c, str) for c in caps):
            raise ValueError(f"{rid}.capabilities deve essere una lista di stringhe")
        rover_state[rid] = {
            "id": rid,
            "position": _xy(rover.get("position_xy", [0, 0]), f"{rid}.position_xy"),
            "capabilities": set(caps),
            "initial_energy_wh": _finite_number(rover.get("available_energy_wh", 0), f"{rid}.available_energy_wh", minimum=0),
            "remaining_energy_wh": _finite_number(rover.get("available_energy_wh", 0), f"{rid}.available_energy_wh", minimum=0),
            "energy_wh_per_m": _finite_number(rover.get("energy_wh_per_m", 0), f"{rid}.energy_wh_per_m", minimum=0),
            "assigned_task_ids": [],
            "distance_m": 0.0,
            "energy_reserved_wh": 0.0,
        }

    normalized_tasks = []
    seen_task_ids = set()
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"Task #{i+1} non valido")
        tid = str(task.get("id", "")).strip()
        if not tid or tid in seen_task_ids:
            raise ValueError(f"ID task mancante o duplicato: {tid!r}")
        seen_task_ids.add(tid)
        required = task.get("required_capabilities", [])
        if not isinstance(required, list) or not all(isinstance(c, str) for c in required):
            raise ValueError(f"{tid}.required_capabilities deve essere una lista di stringhe")
        normalized_tasks.append({
            "id": tid,
            "position": _xy(task.get("position_xy", [0, 0]), f"{tid}.position_xy"),
            "required_capabilities": set(required),
            "priority": _finite_number(task.get("priority", 1), f"{tid}.priority", minimum=0),
            "task_energy_wh": _finite_number(task.get("estimated_energy_wh", 0), f"{tid}.estimated_energy_wh", minimum=0),
            "description": str(task.get("description", "")),
        })

    # Priorità più alta prima; gli ID rendono i pareggi ripetibili.
    normalized_tasks.sort(key=lambda t: (-t["priority"], t["id"]))
    assignments, unassigned = [], []
    for task in normalized_tasks:
        candidates = []
        capability_candidates = []
        for rover in rover_state.values():
            if not task["required_capabilities"].issubset(rover["capabilities"]):
                continue
            capability_candidates.append(rover)
            x0, y0 = rover["position"]
            x1, y1 = task["position"]
            distance = math.hypot(x1 - x0, y1 - y0)
            travel_energy = distance * rover["energy_wh_per_m"]
            total_energy = task["task_energy_wh"] + travel_energy
            if total_energy > rover["remaining_energy_wh"]:
                continue
            # Favorisce la distanza breve e il rover meno carico; energia è un vincolo.
            load_ratio = (rover["initial_energy_wh"] - rover["remaining_energy_wh"]) / max(rover["initial_energy_wh"], 1.0)
            cost = distance * (1.0 + load_ratio) + total_energy * 0.01
            candidates.append((cost, rover["id"], distance, travel_energy, total_energy))
        if not candidates:
            if not capability_candidates:
                reason = "no_rover_with_required_capabilities"
            else:
                reason = "insufficient_energy_budget"
            unassigned.append({"task_id": task["id"], "reason": reason})
            continue
        _, rid, distance, travel_energy, total_energy = min(candidates, key=lambda c: (c[0], c[1]))
        rover = rover_state[rid]
        rover["remaining_energy_wh"] -= total_energy
        rover["energy_reserved_wh"] += total_energy
        rover["distance_m"] += distance
        rover["position"] = task["position"]
        rover["assigned_task_ids"].append(task["id"])
        assignments.append({
            "task_id": task["id"], "rover_id": rid,
            "distance_from_previous_position_m": round(distance, 3),
            "travel_energy_estimate_wh": round(travel_energy, 3),
            "task_energy_estimate_wh": round(task["task_energy_wh"], 3),
            "total_energy_reserved_wh": round(total_energy, 3),
            "priority": task["priority"], "status": "assigned",
            "description": task["description"],
        })

    rover_summary = []
    for rover in sorted(rover_state.values(), key=lambda r: r["id"]):
        rover_summary.append({
            "rover_id": rover["id"],
            "assigned_task_ids": rover["assigned_task_ids"],
            "distance_sum_m": round(rover["distance_m"], 3),
            "energy_reserved_wh": round(rover["energy_reserved_wh"], 3),
            "remaining_energy_wh": round(rover["remaining_energy_wh"], 3),
            "capabilities": sorted(rover["capabilities"]),
            "final_position_xy": [round(rover["position"][0], 3), round(rover["position"][1], 3)],
        })
    result = {
        "schema": "lunar-multi-rover-allocation/1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "local_high_level_plan",
        "rover_count": len(rover_state), "task_count": len(normalized_tasks),
        "assigned_count": len(assignments), "unassigned_count": len(unassigned),
        "assignments": assignments, "unassigned_tasks": unassigned,
        "rovers": rover_summary,
        "limitations": [
            "Posizioni espresse in un frame metrico locale comune; non vengono trasformate da coordinate geografiche lunari.",
            "La distanza è euclidea in linea d'aria, non un percorso calcolato sul DEM.",
            "I consumi sono stime basate su energy_wh_per_m e sui consumi task forniti dall'utente.",
            "Non vengono pianificati link radio, finestre di illuminazione, collision avoidance o sincronizzazione distribuita.",
            "Gli eventi possono essere registrati nel journal locale; nessun nodo P-System remoto è collegato.",
        ],
    }
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        result["output_path"] = str(path)
    return result

# Last updated: 2026-11-14
"""Terrain-aware preliminary A* planner over a DEM grid.

Uses anisotropic pixel spacing, local DEM gradients, NoData barriers and a simple
energy-per-distance estimate. This is not a validated rover dynamics/power model.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import heapq
import math
import numpy as np

@dataclass(frozen=True)
class RoverPlan:
    path_rc: tuple[tuple[int, int], ...]
    distance_m: float
    estimated_energy_wh: float
    max_slope_deg: float
    cells_expanded: int
    status: str = "preliminary"
    warning: str = (
        "Pianificazione preliminare su DEM. Energia = distanza x consumo costante; "
        "non include massa, pendenza energetica, slittamento, ruote, temperatura, "
        "incertezza DEM o dinamica del rover. Frame geodetico non validato."
    )
    def to_dict(self):
        return asdict(self)


def plan_rover_path(
    elevation_m,
    start_rc,
    goal_rc,
    *,
    pixel_size_m=5.0,
    pixel_size_x_m=None,
    pixel_size_y_m=None,
    max_slope_deg=20.0,
    energy_wh_per_m=0.02,
    energy_budget_wh=float("inf"),
    allow_diagonal=True,
) -> RoverPlan:
    """Find a path whose local terrain slope does not exceed the configured limit.

    Pixel sizes are metres per column (x) and row (y). ``pixel_size_m`` remains
    as a backward-compatible fallback. The DEM is interpreted only in grid space.
    """
    dem = np.asarray(elevation_m, dtype=float)
    if dem.ndim != 2 or min(dem.shape) < 2:
        raise ValueError("Il DEM deve essere una matrice 2D almeno 2x2.")
    px = float(pixel_size_x_m if pixel_size_x_m is not None else pixel_size_m)
    py = float(pixel_size_y_m if pixel_size_y_m is not None else pixel_size_m)
    if not math.isfinite(px) or px <= 0 or not math.isfinite(py) or py <= 0:
        raise ValueError("Le dimensioni dei pixel devono essere finite e positive.")
    if not math.isfinite(max_slope_deg) or not 0 < max_slope_deg < 90:
        raise ValueError("max_slope_deg deve essere tra 0 e 90.")
    if not math.isfinite(energy_wh_per_m) or energy_wh_per_m < 0:
        raise ValueError("energy_wh_per_m non valido.")
    if math.isnan(energy_budget_wh) or energy_budget_wh < 0:
        raise ValueError("energy_budget_wh non valido.")

    start, goal = tuple(map(int, start_rc)), tuple(map(int, goal_rc))
    for label, point in (("start", start), ("goal", goal)):
        if len(point) != 2 or not (0 <= point[0] < dem.shape[0] and 0 <= point[1] < dem.shape[1]):
            raise ValueError(f"{label} fuori dal DEM.")
        if not math.isfinite(dem[point]):
            raise ValueError(f"{label} ricade su una cella NoData.")

    valid = np.isfinite(dem)
    # Fill invalid cells only to make gradient computation possible; those cells
    # remain impassable and never become part of the returned route.
    filled = dem.copy()
    if not valid.all():
        filled[~valid] = float(np.nanmedian(dem[valid]))
    dz_drow, dz_dcol = np.gradient(filled, py, px)
    slope_field = np.degrees(np.arctan(np.hypot(dz_dcol, dz_drow)))
    slope_field[~valid] = np.inf

    if start == goal:
        return RoverPlan((start,), 0.0, 0.0, float(slope_field[start]), 0)

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if allow_diagonal:
        directions += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

    def distance_between(a, b):
        dr, dc = b[0] - a[0], b[1] - a[1]
        return math.hypot(dr * py, dc * px)

    def heuristic(point):
        return math.hypot((goal[0] - point[0]) * py, (goal[1] - point[1]) * px)

    queue = [(heuristic(start), 0.0, start)]
    came_from = {}
    best_cost = {start: 0.0}
    edge_slope = {}
    expanded = 0
    while queue:
        _, queued_cost, current = heapq.heappop(queue)
        if queued_cost != best_cost.get(current):
            continue
        expanded += 1
        if current == goal:
            break
        for dr, dc in directions:
            nxt = (current[0] + dr, current[1] + dc)
            if not (0 <= nxt[0] < dem.shape[0] and 0 <= nxt[1] < dem.shape[1]):
                continue
            if not valid[nxt]:
                continue
            step_m = distance_between(current, nxt)
            edge_grade = math.degrees(math.atan2(abs(dem[nxt] - dem[current]), step_m))
            local_slope = max(float(slope_field[current]), float(slope_field[nxt]), edge_grade)
            if local_slope > max_slope_deg:
                continue
            # Terrain gradient is a routing penalty, not a physical energy model.
            penalty = 1.0 + (local_slope / max_slope_deg) ** 2
            new_cost = queued_cost + step_m * penalty
            if new_cost < best_cost.get(nxt, float("inf")):
                best_cost[nxt] = new_cost
                came_from[nxt] = current
                edge_slope[nxt] = local_slope
                heapq.heappush(queue, (new_cost + heuristic(nxt), new_cost, nxt))

    if goal not in best_cost:
        raise ValueError("Nessun percorso trovato con le soglie di pendenza e le celle valide impostate.")
    path = [goal]
    while path[-1] != start:
        path.append(came_from[path[-1]])
    path.reverse()
    distance = sum(distance_between(path[i - 1], path[i]) for i in range(1, len(path)))
    energy = distance * energy_wh_per_m
    if energy > energy_budget_wh:
        raise ValueError(f"Energia preliminare {energy:.2f} Wh oltre il budget {energy_budget_wh:.2f} Wh.")
    max_slope = max((edge_slope.get(point, float(slope_field[point])) for point in path[1:]), default=0.0)
    return RoverPlan(tuple(path), float(distance), float(energy), float(max_slope), expanded)

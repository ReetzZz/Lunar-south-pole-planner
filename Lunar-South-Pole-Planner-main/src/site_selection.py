# Last updated: 2026-11-14
"""Selezione preliminare e riproducibile di siti candidati lunari."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import math

import rasterio

from src.mission_planning import SiteMetrics, SiteWeights, score_site
from src.terrain_metrics import analyze_local_terrain


SCHEMA = "lunar-site-selection/1.0"


def select_candidate_sites(
    dem_path: str | Path,
    *,
    output_path: str | Path = "reports/mission/site_ranking.json",
    radius_pixels: int = 10,
    target_candidates: int = 400,
    max_slope_deg: float = 15.0,
    max_roughness_m: float = 5.0,
    min_valid_fraction: float = 0.95,
    top_n: int = 20,
) -> dict:
    """Campiona il DEM e ordina candidati in base alle sole metriche disponibili.

    Il punteggio è limitato a pendenza e rugosità. Illuminazione,
    comunicazioni e confidenza non vengono inventate né incluse.
    """
    dem = Path(dem_path)
    if not dem.is_file():
        raise FileNotFoundError(f"DEM non trovato: {dem}")
    if radius_pixels < 2:
        raise ValueError("radius_pixels deve essere >= 2.")
    if target_candidates < 1 or top_n < 1:
        raise ValueError("target_candidates e top_n devono essere positivi.")
    if not math.isfinite(max_slope_deg) or max_slope_deg <= 0:
        raise ValueError("max_slope_deg deve essere positivo e finito.")
    if not math.isfinite(max_roughness_m) or max_roughness_m <= 0:
        raise ValueError("max_roughness_m deve essere positivo e finito.")
    if not 0 < min_valid_fraction <= 1:
        raise ValueError("min_valid_fraction deve essere in (0, 1].")

    with rasterio.open(dem) as ds:
        width, height = ds.width, ds.height
        transform = ds.transform
        crs = str(ds.crs) if ds.crs else None
        bounds = {
            "left": float(ds.bounds.left),
            "bottom": float(ds.bounds.bottom),
            "right": float(ds.bounds.right),
            "top": float(ds.bounds.top),
        }

    usable_rows = max(0, height - 2 * radius_pixels)
    usable_cols = max(0, width - 2 * radius_pixels)
    if usable_rows == 0 or usable_cols == 0:
        raise ValueError("DEM troppo piccolo per il raggio richiesto.")

    # Passo adattivo: limita il costo senza pretendere di analizzare ogni pixel.
    area = usable_rows * usable_cols
    step = max(
        1,
        int(math.sqrt(area / target_candidates)),
    )
    row_start = radius_pixels
    col_start = radius_pixels
    row_stop = height - radius_pixels
    col_stop = width - radius_pixels

    weights = SiteWeights(
        illumination=0.0,
        communications=0.0,
        slope=0.60,
        roughness=0.40,
        confidence=0.0,
    )

    ranked = []
    rejected = []
    evaluated = 0

    for row in range(row_start, row_stop, step):
        for col in range(col_start, col_stop, step):
            evaluated += 1
            try:
                terrain = analyze_local_terrain(
                    dem, row, col, radius_pixels
                )
                slope = float(terrain.slope_p95_deg)
                roughness = float(terrain.roughness_plane_residual_std_m)
                valid_fraction = float(terrain.valid_fraction)

                if not all(map(math.isfinite, (slope, roughness, valid_fraction))):
                    raise ValueError("Metriche del terreno non finite.")

                metrics = {
                    "slope_p95_deg": slope,
                    "roughness_plane_residual_std_m": roughness,
                    "valid_fraction": valid_fraction,
                }

                reasons = []
                if valid_fraction < min_valid_fraction:
                    reasons.append("COPERTURA_DATI_INSUFFICIENTE")
                if slope > max_slope_deg:
                    reasons.append("PENDENZA_OLTRE_SOGLIA")
                if roughness > max_roughness_m:
                    reasons.append("RUGOSITA_OLTRE_SOGLIA")

                slope_utilization = 100.0 * slope / max_slope_deg
                roughness_utilization = 100.0 * roughness / max_roughness_m

                if reasons:
                    terrain_class = "EXCLUDED_BY_CONFIGURED_THRESHOLDS"
                elif slope_utilization >= 80.0 or roughness_utilization >= 80.0:
                    terrain_class = "ELIGIBLE_NEAR_THRESHOLD"
                else:
                    terrain_class = "ELIGIBLE_WITHIN_CONFIGURED_THRESHOLDS"

                candidate = {
                    "name": f"candidate_r{row}_c{col}",
                    "grid_row": row,
                    "grid_col": col,
                    "map_x": float((transform * (col + 0.5, row + 0.5))[0]),
                    "map_y": float((transform * (col + 0.5, row + 0.5))[1]),
                    "terrain_metrics": metrics,
                    "terrain_threshold_utilization_pct": {
                        "slope": slope_utilization,
                        "roughness": roughness_utilization,
                    },
                    "terrain_class": terrain_class,
                    "eligible_by_terrain_thresholds": not reasons,
                    "exclusion_reasons": reasons,
                }

                if reasons:
                    rejected.append(candidate)
                    continue

                score = score_site(
                    SiteMetrics(
                        name=candidate["name"],
                        slope_deg=slope,
                        roughness_m=roughness,
                    ),
                    weights=weights,
                    max_slope_deg=max_slope_deg,
                    max_roughness_m=max_roughness_m,
                )
                candidate["score"] = score.to_dict()
                candidate["score_coverage_fraction"] = score.coverage_fraction
                candidate["missing_metrics"] = list(score.missing_metrics)
                candidate["score_scope"] = [
                    "slope",
                    "roughness",
                ]
                ranked.append(candidate)

            except Exception as exc:
                rejected.append({
                    "name": f"candidate_r{row}_c{col}",
                    "grid_row": row,
                    "grid_col": col,
                    "eligible_by_terrain_thresholds": False,
                    "exclusion_reasons": ["ANALISI_NON_DISPONIBILE"],
                    "error": str(exc),
                })

    ranked.sort(
        key=lambda item: (
            -(item["score"]["score_0_100"] or 0.0),
            item["terrain_metrics"]["slope_p95_deg"],
            item["terrain_metrics"]["roughness_plane_residual_std_m"],
        )
    )

    class_counts = {
        "EXCLUDED_BY_CONFIGURED_THRESHOLDS": len(rejected),
        "ELIGIBLE_NEAR_THRESHOLD": sum(
            item.get("terrain_class") == "ELIGIBLE_NEAR_THRESHOLD"
            for item in ranked
        ),
        "ELIGIBLE_WITHIN_CONFIGURED_THRESHOLDS": sum(
            item.get("terrain_class") == "ELIGIBLE_WITHIN_CONFIGURED_THRESHOLDS"
            for item in ranked
        ),
    }

    result = {
        "schema": SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "terrain_class_summary": {
            "counts": class_counts,
            "interpretation": (
                "Classificazione basata solo su pendenza, rugosità e copertura "
                "dei dati rispetto alle soglie configurate; non certifica "
                "la sicurezza del sito."
            ),
        },
        "status": "preliminary",
        "dem_path": str(dem),
        "dem_grid": {"width": width, "height": height, "crs": crs, "bounds": bounds},
        "sampling": {
            "method": "regular_grid_with_adaptive_step",
            "step_pixels": step,
            "radius_pixels": radius_pixels,
            "target_candidates": target_candidates,
            "evaluated_candidates": evaluated,
        },
        "thresholds": {
            "max_slope_deg": max_slope_deg,
            "max_roughness_m": max_roughness_m,
            "min_valid_fraction": min_valid_fraction,
        },
        "ranking_method": (
            "Score 0-100 based only on slope and roughness, "
            "with weights 0.60 and 0.40."
        ),
        "eligible_count": len(ranked),
        "rejected_count": len(rejected),
        "top_candidates": ranked[:top_n],
        "rejected_candidates": rejected,
        "warnings": [
            "Classifica preliminare: non certifica la sicurezza dell'atterraggio.",
            "Il campionamento non analizza ogni pixel del DEM.",
            "Il punteggio usa soltanto pendenza e rugosità.",
            "Illuminazione, comunicazioni e confidenza non sono incluse nel punteggio.",
            "Coordinate e CRS non attestano da soli un frame lunare fisicamente validato.",
        ],
    }

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    result["output_path"] = str(target)
    return result

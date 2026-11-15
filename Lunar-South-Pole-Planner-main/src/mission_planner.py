# Last updated: 2026-11-14
"""Mission planning utilities for the Lunar South Pole Planner.

Generated plans are preliminary engineering artifacts, not flight-qualified
mission plans. Geometry and communication constraints must be validated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json


@dataclass
class MissionConfig:
    site: str
    start_date_utc: str
    duration_hours: int = 48
    science_priority: int = 5
    engineering_priority: int = 5
    min_sun_elevation_deg: float = 5.0
    min_earth_elevation_deg: float = 5.0


def validate_config(config: MissionConfig, valid_sites: list[str]) -> None:
    if config.site not in valid_sites:
        raise ValueError(f"Sito non riconosciuto: {config.site}")

    try:
        datetime.strptime(config.start_date_utc, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("La data deve avere formato YYYY-MM-DD.") from exc

    if not 1 <= config.duration_hours <= 720:
        raise ValueError("La durata deve essere compresa tra 1 e 720 ore.")

    if not 1 <= config.science_priority <= 5:
        raise ValueError("La priorità scientifica deve essere tra 1 e 5.")

    if not 1 <= config.engineering_priority <= 5:
        raise ValueError("La priorità ingegneristica deve essere tra 1 e 5.")

    if not -90 <= config.min_sun_elevation_deg <= 90:
        raise ValueError("Soglia di elevazione solare non valida.")

    if not -90 <= config.min_earth_elevation_deg <= 90:
        raise ValueError("Soglia di elevazione terrestre non valida.")


def build_mission_plan(
    config: MissionConfig,
    valid_sites: list[str],
    observations_status: str = "not_run",
    operational_windows: list[dict] | None = None,
) -> dict:
    """Create a JSON-serializable preliminary plan from supplied evidence."""
    validate_config(config, valid_sites)

    windows = operational_windows or []
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mission": asdict(config),
        "astronomy": {
            "status": observations_status,
            "operational_windows": windows,
            "window_count": len(windows),
            "window_constraints": {
                "min_sun_elevation_deg": config.min_sun_elevation_deg,
                "min_earth_elevation_deg": config.min_earth_elevation_deg,
            },
        },
        "validation": {
            "terrain_occlusion": "not_verified",
            "radio_line_of_sight": "not_verified",
            "landing_safety": "not_verified",
            "flight_qualification": "not_qualified",
        },
        "notice": (
            "Piano preliminare. Le finestre sono utilizzabili solo se "
            "provengono da osservazioni astronomiche valide per questo sito, "
            "intervallo temporale e soglie. Nessuna certificazione di sicurezza."
        ),
    }


def save_mission_plan(plan: dict, output_path: str | Path) -> Path:
    """Save a plan as UTF-8 JSON, creating parent directories if necessary."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def rank_operational_windows(
    windows,
    sun_elevations,
    earth_elevations,
    config,
):
    """Classifica finestre preliminari; il punteggio non certifica la sicurezza."""
    def mean_valid(values):
        valid = [
            float(v) for v in values
            if v is not None and -90.0 <= float(v) <= 90.0
        ]
        return sum(valid) / len(valid) if valid else None

    def elevation_score(value):
        if value is None:
            return 0.0
        return max(0.0, min(100.0, value / 90.0 * 100.0))

    candidates = []
    for window in windows:
        start = int(window.start_index)
        end = int(window.end_index)
        if start < 0 or end < start:
            continue

        sun_mean = mean_valid(sun_elevations[start:end + 1])
        earth_mean = mean_valid(earth_elevations[start:end + 1])
        samples = max(1, int(window.duration_samples))

        candidates.append({
            "start_index": start,
            "end_index": end,
            "duration_samples": samples,
            "sun_mean_elevation_deg": (
                round(sun_mean, 3) if sun_mean is not None else None
            ),
            "earth_mean_elevation_deg": (
                round(earth_mean, 3) if earth_mean is not None else None
            ),
            "science_score": elevation_score(sun_mean),
            "engineering_score": elevation_score(earth_mean),
        })

    max_samples = max(
        (candidate["duration_samples"] for candidate in candidates),
        default=1,
    )
    science_weight = config.science_priority
    engineering_weight = config.engineering_priority
    duration_weight = (science_weight + engineering_weight) / 2.0
    total_weight = science_weight + engineering_weight + duration_weight

    for candidate in candidates:
        duration_score = (
            candidate["duration_samples"] / max_samples * 100.0
        )
        candidate["duration_score"] = round(duration_score, 2)
        candidate["score"] = round(
            (
                science_weight * candidate["science_score"]
                + engineering_weight * candidate["engineering_score"]
                + duration_weight * duration_score
            ) / total_weight,
            2,
        )
        candidate["score_method"] = (
            "Heuristic: mean Sun elevation, mean Earth elevation, "
            "and relative duration; not flight-qualified."
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank

    return candidates


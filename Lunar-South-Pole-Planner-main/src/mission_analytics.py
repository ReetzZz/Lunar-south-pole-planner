# Last updated: 2026-11-14
"""Statistics for paired lunar Sun/Earth ephemeris samples.

This module describes geometric elevation constraints only. It does not infer
terrain visibility, RF link availability, solar power, or mission safety.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Iterable, Mapping, Any


def _stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "max": None, "mean": None, "samples": 0}
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "samples": len(values),
    }


def summarize_ephemerides(
    observations: Iterable[Mapping[str, Any]],
    *,
    min_sun_elevation_deg: float,
    min_earth_elevation_deg: float,
    windows: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Summarize paired observations without filling missing samples."""
    for name, value in (("min_sun_elevation_deg", min_sun_elevation_deg),
                        ("min_earth_elevation_deg", min_earth_elevation_deg)):
        if not math.isfinite(float(value)) or not -90 <= float(value) <= 90:
            raise ValueError(f"{name} must be finite and between -90 and 90 degrees")

    rows = list(observations)
    valid: list[tuple[float, float]] = []
    invalid = 0
    for row in rows:
        try:
            sun = float(row["sun_elevation_deg"])
            earth = float(row["earth_elevation_deg"])
            if not (math.isfinite(sun) and math.isfinite(earth)
                    and -90 <= sun <= 90 and -90 <= earth <= 90):
                raise ValueError
            valid.append((sun, earth))
        except (KeyError, TypeError, ValueError):
            invalid += 1

    sun_values = [p[0] for p in valid]
    earth_values = [p[1] for p in valid]
    sun_pass = sum(v >= min_sun_elevation_deg for v in sun_values)
    earth_pass = sum(v >= min_earth_elevation_deg for v in earth_values)
    both_pass = sum(s >= min_sun_elevation_deg and e >= min_earth_elevation_deg
                    for s, e in valid)
    n = len(valid)

    def pct(count: int) -> float | None:
        return round(100.0 * count / n, 3) if n else None

    window_rows = list(windows)
    spans: list[float] = []
    for win in window_rows:
        span = win.get("sampled_span_hours")
        if span is None:
            try:
                span = max(0.0, (int(win["duration_samples"]) - 1)
                           * float(win.get("sample_step_hours", 1)))
            except (KeyError, TypeError, ValueError):
                continue
        span = float(span)
        if math.isfinite(span) and span >= 0:
            spans.append(span)

    if n == 0:
        diagnosis = "Insufficient valid paired samples; no geometric conclusion."
    elif both_pass:
        diagnosis = "At least one sample satisfies both elevation constraints."
    elif sun_pass == 0 and earth_pass == 0:
        diagnosis = "Neither Sun nor Earth elevation reaches its configured threshold."
    elif sun_pass == 0:
        diagnosis = "Sun elevation is the limiting geometric constraint."
    elif earth_pass == 0:
        diagnosis = "Earth elevation is the limiting geometric constraint."
    else:
        diagnosis = "Each constraint is met separately, but not at the same samples."

    return {
        "schema": "lunar-ephemeris-analytics/1.0",
        "sample_count": len(rows),
        "valid_sample_count": n,
        "invalid_sample_count": invalid,
        "thresholds_deg": {
            "sun": float(min_sun_elevation_deg),
            "earth": float(min_earth_elevation_deg),
        },
        "sun": {**_stats(sun_values), "passing_samples": sun_pass,
                "passing_percent": pct(sun_pass)},
        "earth": {**_stats(earth_values), "passing_samples": earth_pass,
                  "passing_percent": pct(earth_pass)},
        "simultaneous": {"passing_samples": both_pass,
                         "passing_percent": pct(both_pass)},
        "operational_windows": {
            "count": len(window_rows),
            "total_sampled_span_hours": round(sum(spans), 6),
            "spans_hours": spans,
            "earliest_start_utc": window_rows[0].get("start_utc") if window_rows else None,
        },
        "diagnosis": diagnosis,
        "interpretation_scope": "geometric_elevation_only",
        "not_evaluated": ["terrain_occlusion", "RF_link_budget", "solar_power",
                           "thermal_limits", "landing_safety"],
    }

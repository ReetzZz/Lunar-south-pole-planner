# Last updated: 2026-11-14
"""Confronto geometrico dei siti lunari tramite NASA/JPL Horizons."""
from datetime import datetime, timezone
from pathlib import Path
import json

from src.astronomy import query_observations
from src.mission_planning import find_operational_windows


def compare_candidate_sites(sites, start_utc, *, hours=48, step="1h"):
    if start_utc.tzinfo is None:
        raise ValueError("La data deve includere il fuso orario.")
    if not 1 <= int(hours) <= 168:
        raise ValueError("La durata deve essere compresa tra 1 e 168 ore.")

    start = start_utc.astimezone(timezone.utc)
    report = {
        "schema": "lunar-south-pole-site-comparison/1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "start_utc": start.isoformat(),
        "hours": int(hours),
        "step": step,
        "source": "NASA/JPL Horizons",
        "thresholds_deg": {"sun_minimum": 5.0, "earth_minimum": 5.0},
        "interpretation": (
            "Screening geometrico preliminare; non costituisce una stima "
            "di potenza solare né una verifica del collegamento radio."
        ),
        "sites": [],
    }

    for name, coordinates in sites.items():
        lat, lon = coordinates[:2]
        entry = {
            "site": name,
            "latitude_deg": float(lat),
            "longitude_deg": float(lon),
            "coordinate_frame_validated": False,
            "matched_samples": 0,
            "sun_max_elevation_deg": None,
            "earth_max_elevation_deg": None,
            "geometric_windows": [],
            "observations": [],
            "error": None,
        }

        try:
            sun_rows = query_observations(
                "10", lat, lon, start, hours=hours, step=step
            )
            earth_rows = query_observations(
                "399", lat, lon, start, hours=hours, step=step
            )

            sun = {r.time_utc: r for r in sun_rows}
            earth = {r.time_utc: r for r in earth_rows}
            times = sorted(sun.keys() & earth.keys())

            if not times:
                raise RuntimeError("Nessun timestamp comune tra Sole e Terra.")

            sun_elev = []
            earth_elev = []

            for timestamp in times:
                s, e = sun[timestamp], earth[timestamp]
                sun_elev.append(float(s.elevation_deg))
                earth_elev.append(float(e.elevation_deg))
                entry["observations"].append({
                    "time_utc": timestamp,
                    "sun_azimuth_deg": float(s.azimuth_deg),
                    "sun_elevation_deg": float(s.elevation_deg),
                    "earth_azimuth_deg": float(e.azimuth_deg),
                    "earth_elevation_deg": float(e.elevation_deg),
                })

            entry["matched_samples"] = len(times)
            entry["sun_max_elevation_deg"] = max(sun_elev)
            entry["earth_max_elevation_deg"] = max(earth_elev)

            windows = find_operational_windows(
                sun_elev,
                earth_elev,
                min_sun_elevation_deg=5.0,
                min_earth_elevation_deg=5.0,
            )

            for w in windows:
                first, last = w.start_index, w.end_index
                t0 = datetime.fromisoformat(times[first].replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(times[last].replace("Z", "+00:00"))
                entry["geometric_windows"].append({
                    "start_utc": times[first],
                    "end_utc": times[last],
                    "sample_count": int(w.duration_samples),
                    "approx_duration_hours": max(
                        0.0, (t1 - t0).total_seconds() / 3600
                    ),
                    "minimum_sun_elevation_deg": 5.0,
                    "minimum_earth_elevation_deg": 5.0,
                })

        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"

        report["sites"].append(entry)

    return report


def write_comparison_report(report, output_dir="reports/site_comparison"):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"site-comparison-{stamp}.json"
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path

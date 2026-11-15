# Last updated: 2026-11-14
"""Orchestratore preliminare per missioni lunari multi-rover."""
from __future__ import annotations
import re

from datetime import datetime, timedelta, timezone
import json
import math
import uuid
from pathlib import Path

import rasterio

from src.rover_planning import plan_rover_path
from src.route_quality import analyze_route_quality
from src.rover_energy import estimate_route_energy
from src.multi_rover import allocate_tasks
from src.psystem_adapter import MissionJournal
from src.lola_lroc_quality import compare_lola_lroc_quality
from src.descent_hazard_detection import analyze_descent_patch
from src.export_descent_risk_raster import export_descent_risk_raster
from src.site_selection import select_candidate_sites
from src.astronomy import SITES, query_observations
from src.mission_planning import find_operational_windows
from src.illumination_analysis import estimate_direct_solar_visibility
from src.visibility import compare_with_horizon
from src.horizon_analysis import calculate_and_write_horizon
from src.local_site_analysis import analyze_local_site
from src.confidence_validation import validate_confidence_raster
from src.data_quality import audit_raster, compare_grid_metadata
from src.site_assessment import assess_candidate, write_assessment
from src.lunar_geometry import locate_observer, sample_elevation
from src.mission_report import build_mission_report, write_mission_report


SCHEMA = "lunar-mission-orchestration/1.0"


def _read_json(path):
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Configurazione non trovata: {source}")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("La configurazione deve essere un oggetto JSON.")
    return data


def _write_json(data, path):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return target


def _finite(value, name, minimum=None):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: valore numerico non valido.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name}: valore non finito.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name}: deve essere >= {minimum}.")
    return number



def _diagnose_temporal_continuity(sun_rows, earth_rows, expected_step_seconds):
    """Diagnostica la continuità temporale senza modificare le osservazioni."""
    warnings = []
    gap_count = 0
    series_diagnostics = {}

    for name, rows in (("Sun", sun_rows), ("Earth", earth_rows)):
        parsed = []
        invalid_timestamps = []

        for row in rows:
            value = row.get("time_utc")
            try:
                timestamp = datetime.fromisoformat(
                    str(value).replace("Z", "+00:00")
                )
                if timestamp.tzinfo is None:
                    raise ValueError("timestamp senza fuso orario")
                parsed.append((timestamp, str(value)))
            except (TypeError, ValueError):
                invalid_timestamps.append(value)

        duplicate_count = len(parsed) - len(
            {timestamp for timestamp, _ in parsed}
        )
        out_of_order = any(
            parsed[i][0] < parsed[i - 1][0]
            for i in range(1, len(parsed))
        )
        intervals = [
            (parsed[i][0] - parsed[i - 1][0]).total_seconds()
            for i in range(1, len(parsed))
        ]
        gaps = [
            seconds for seconds in intervals
            if seconds > expected_step_seconds * 1.01
        ]
        gap_count += len(gaps)

        series_diagnostics[name] = {
            "observations": len(rows),
            "invalid_timestamp_count": len(invalid_timestamps),
            "duplicate_timestamp_count": duplicate_count,
            "out_of_order": out_of_order,
            "gap_count": len(gaps),
            "largest_interval_seconds": max(intervals, default=None),
        }

        if invalid_timestamps:
            warnings.append(
                f"{name}: {len(invalid_timestamps)} timestamp non validi."
            )
        if duplicate_count:
            warnings.append(
                f"{name}: rilevati {duplicate_count} timestamp duplicati."
            )
        if out_of_order:
            warnings.append(f"{name}: timestamp fuori ordine.")
        if gaps:
            warnings.append(
                f"{name}: rilevati {len(gaps)} intervalli superiori "
                "al passo temporale atteso."
            )

    sun_times = {
        row.get("time_utc") for row in sun_rows
        if row.get("time_utc") is not None
    }
    earth_times = {
        row.get("time_utc") for row in earth_rows
        if row.get("time_utc") is not None
    }
    unmatched_sun = len(sun_times - earth_times)
    unmatched_earth = len(earth_times - sun_times)

    if unmatched_sun or unmatched_earth:
        warnings.append(
            "Le serie Sole/Terra non hanno gli stessi timestamp: "
            f"{unmatched_sun} esclusivi del Sole, "
            f"{unmatched_earth} esclusivi della Terra."
        )

    continuity_verified = (
        bool(sun_rows)
        and bool(earth_rows)
        and not warnings
    )

    return {
        "expected_step_seconds": expected_step_seconds,
        "continuity_verified": continuity_verified,
        "gap_count": gap_count,
        "unmatched_sun_timestamp_count": unmatched_sun,
        "unmatched_earth_timestamp_count": unmatched_earth,
        "series": series_diagnostics,
        "warnings": warnings,
    }


def run_mission_workflow(config_path):
    config = _read_json(config_path)
    output_dir = Path(config.get("output_dir", "reports/mission"))
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    report = {
        "schema": SCHEMA,
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed_with_warnings",
        "configuration": str(Path(config_path)),
        "steps": {},
        "artifacts": {},
        "warnings": [
            "Risultati preliminari, non certificati per operazioni reali.",
            "Georeferenziazione e frame fisico lunare non validati indipendentemente.",
            "L'allocazione multi-rover usa distanze euclidee, non percorsi DEM.",
            "Il journal è locale e non si connette a nodi P-System remoti.",
        ],
    }

    def step(name, operation):
        try:
            result = operation()
            report["steps"][name] = {"status": "success", "result": result}
            return result
        except Exception as exc:
            report["steps"][name] = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            return None

    astronomy_cfg = config.get("astronomy")
    if astronomy_cfg is not None and astronomy_cfg.get("enabled", False):
        def collect_astronomy():
            site_name = astronomy_cfg.get("site", "Connecting Ridge")
            if site_name not in SITES:
                raise ValueError(
                    f"Sito astronomico non riconosciuto: {site_name}. "
                    f"Siti disponibili: {', '.join(SITES)}"
                )

            latitude, longitude = SITES[site_name]
            start_text = astronomy_cfg.get("start_utc")
            if start_text:
                start_utc = datetime.fromisoformat(
                    start_text.replace("Z", "+00:00")
                )
                if start_utc.tzinfo is None:
                    raise ValueError("start_utc deve includere il fuso orario.")
            else:
                start_utc = datetime.now(timezone.utc)

            hours = int(astronomy_cfg.get("hours", 48))
            step_size = astronomy_cfg.get("step", "1h")
            targets = astronomy_cfg.get("targets", ["10", "399"])
            names = {"10": "Sun", "399": "Earth"}
            observations = {}

            for target in targets:
                target = str(target)
                if target not in names:
                    raise ValueError(
                        f"Target Horizons non supportato da questo step: {target}"
                    )
                rows = query_observations(
                    target, latitude, longitude, start_utc,
                    hours=hours, step=step_size,
                )
                observations[names[target]] = [
                    {
                        "time_utc": row.time_utc,
                        "azimuth_deg": row.azimuth_deg,
                        "elevation_deg": row.elevation_deg,
                        "distance_au": row.distance_au,
                        "range_rate_km_s": row.range_rate_km_s,
                    }
                    for row in rows
                ]

            windows = []
            window_summary = {
                "status": "unavailable",
                "reason": "Sono necessarie osservazioni sia del Sole sia della Terra.",
                "windows": [],
            }

            if "Sun" in observations and "Earth" in observations:
                sun_rows = observations["Sun"]
                earth_rows = observations["Earth"]
                earth_by_time = {row["time_utc"]: row for row in earth_rows}
                common_times = [
                    row["time_utc"] for row in sun_rows
                    if row["time_utc"] in earth_by_time
                ]
                sun_aligned = [
                    next(row for row in sun_rows if row["time_utc"] == timestamp)
                    for timestamp in common_times
                ]
                earth_aligned = [earth_by_time[timestamp] for timestamp in common_times]

                sun_threshold = float(
                    astronomy_cfg.get("min_sun_elevation_deg", 5.0)
                )
                earth_threshold = float(
                    astronomy_cfg.get("min_earth_elevation_deg", 5.0)
                )

                if common_times:
                    found = find_operational_windows(
                        [row["elevation_deg"] for row in sun_aligned],
                        [row["elevation_deg"] for row in earth_aligned],
                        min_sun_elevation_deg=sun_threshold,
                        min_earth_elevation_deg=earth_threshold,
                    )
                    for window in found:
                        window_start = datetime.fromisoformat(
                            common_times[window.start_index].replace("Z", "+00:00")
                        )
                        window_end = datetime.fromisoformat(
                            common_times[window.end_index].replace("Z", "+00:00")
                        )
                        duration_seconds = (
                            window_end - window_start
                        ).total_seconds()

                        windows.append({
                            "start_utc": common_times[window.start_index],
                            "end_utc": common_times[window.end_index],
                            "duration_samples": window.duration_samples,
                            "duration_seconds": duration_seconds,
                            "duration_minutes": duration_seconds / 60.0,
                        })

                    window_summary = {
                        "status": "preliminary",
                        "method": "simultaneous geometric elevation thresholds",
                        "min_sun_elevation_deg": sun_threshold,
                        "min_earth_elevation_deg": earth_threshold,
                        "matched_samples": len(common_times),
                        "windows": windows,
                    }
                else:
                    window_summary["reason"] = (
                        "Nessun timestamp comune tra le serie del Sole e della Terra."
                    )

            step_match = re.fullmatch(
                r"\s*(\d+(?:\.\d+)?)\s*([smhd])\s*",
                str(step_size).lower(),
            )
            if not step_match:
                raise ValueError(
                    f"Passo astronomico non supportato per la diagnostica: {step_size!r}. "
                    "Usare un valore come 30m, 1h o 1d."
                )

            step_value = float(step_match.group(1))
            step_unit = step_match.group(2)
            step_seconds = step_value * {
                "s": 1, "m": 60, "h": 3600, "d": 86400
            }[step_unit]

            temporal_diagnostics = {
                "continuity_verified": False,
                "gap_count": 0,
                "unmatched_sun_timestamp_count": 0,
                "unmatched_earth_timestamp_count": 0,
                "series": {},
                "warnings": [
                    "Diagnostica non eseguita: mancano osservazioni del Sole o della Terra."
                ],
            }
            if "Sun" in observations and "Earth" in observations:
                temporal_diagnostics = _diagnose_temporal_continuity(
                    observations["Sun"],
                    observations["Earth"],
                    step_seconds,
                )

            window_summary["temporal_diagnostics"] = temporal_diagnostics

            artifact = output_dir / astronomy_cfg.get(
                "report_name", "astronomy_observations.json"
            )
            payload = {
                "schema": "lunar-astronomy-observations/1.0",
                "status": "preliminary",
                "site": site_name,
                "latitude_deg": latitude,
                "longitude_east_deg": longitude,
                "start_utc": start_utc.astimezone(timezone.utc).isoformat(),
                "hours": hours,
                "step": step_size,
                "observations": observations,
                "temporal_diagnostics": temporal_diagnostics,
                "operational_windows": window_summary,
                "limitations": [
                    "Osservazioni geometriche apparenti da NASA/JPL Horizons.",
                    "Non includono ombreggiamento del terreno.",
                    "Non costituiscono un bilancio energetico o radio.",
                    "Frame e coordinate del sito non validati indipendentemente.",
                ],
            }
            artifact.parent.mkdir(parents=True, exist_ok=True)
            _write_json(payload, artifact)
            if not artifact.is_file():
                raise OSError(f"Report astronomico non creato: {artifact}")
            report["artifacts"]["astronomy"] = str(artifact)
            return {
                "status": "preliminary",
                "site": site_name,
                "targets": list(observations),
                "observation_counts": {
                    name: len(rows) for name, rows in observations.items()
                },
                "report_file": str(artifact),
            }

        step("astronomy", collect_astronomy)

    horizon_cfg = config.get("horizon_analysis")
    if horizon_cfg is not None and horizon_cfg.get("enabled", False):
        def generate_horizon_profile():
            dem_path = horizon_cfg.get("dem_path")
            row = horizon_cfg.get("observer_row")
            col = horizon_cfg.get("observer_col")

            if not dem_path:
                raise ValueError("horizon_analysis.dem_path è obbligatorio.")
            if row is None or col is None:
                raise ValueError(
                    "Specificare observer_row e observer_col; "
                    "le coordinate dell'osservatore non vengono inventate."
                )

            artifact = output_dir / horizon_cfg.get(
                "report_name", "horizon_profile.json"
            )
            result_path = calculate_and_write_horizon(
                dem_path=dem_path,
                row=int(row),
                col=int(col),
                observer_height_m=float(
                    horizon_cfg.get("observer_height_m", 1.0)
                ),
                azimuth_step_deg=float(
                    horizon_cfg.get("azimuth_step_deg", 2.0)
                ),
                max_distance_m=float(
                    horizon_cfg.get("max_distance_m", 5000.0)
                ),
                output_path=artifact,
            )
            report["artifacts"]["horizon_analysis"] = str(result_path)
            return {
                "status": "preliminary",
                "report_file": str(result_path),
                "azimuth_frame": "raster grid; north orientation not certified",
                "georeference_validated": False,
            }

        step("horizon_analysis", generate_horizon_profile)

    illumination_cfg = config.get("illumination")
    if illumination_cfg is not None and illumination_cfg.get("enabled", False):
        def analyze_illumination():
            horizon_step = report["steps"].get("horizon_analysis", {})
            horizon_result = horizon_step.get("result", {})
            generated_horizon = horizon_result.get("report_file")

            if horizon_step.get("status") == "success" and generated_horizon:
                horizon_json = generated_horizon
                horizon_source = "generated_by_horizon_analysis"
            else:
                horizon_json = illumination_cfg.get("horizon_json")
                horizon_source = "configured_path"

            if not horizon_json:
                raise ValueError(
                    "Profilo dell'orizzonte non disponibile: abilitare "
                    "horizon_analysis con observer_row/observer_col validi "
                    "oppure configurare illumination.horizon_json."
                )
            if "grid_azimuth_offset_deg" not in illumination_cfg:
                raise ValueError(
                    "Configurare esplicitamente grid_azimuth_offset_deg; "
                    "l'orientamento non viene dedotto automaticamente."
                )

            astronomy_result = report["steps"].get("astronomy", {})
            astronomy_data = astronomy_result.get("result", {})
            astronomy_file = astronomy_data.get("report_file")
            if astronomy_result.get("status") != "success" or not astronomy_file:
                raise ValueError(
                    "L'illuminazione richiede uno step astronomy completato "
                    "con osservazioni del Sole."
                )

            astronomy_path = Path(astronomy_file)
            if not astronomy_path.is_file():
                raise FileNotFoundError(
                    f"Report astronomico non trovato: {astronomy_path}"
                )

            astronomy_payload = json.loads(
                astronomy_path.read_text(encoding="utf-8")
            )
            solar_rows = astronomy_payload.get("observations", {}).get("Sun")
            if not solar_rows:
                raise ValueError(
                    "Il report astronomico non contiene osservazioni del Sole."
                )

            artifact = output_dir / illumination_cfg.get(
                "report_name", "solar_illumination_diagnostic.json"
            )
            result_path = estimate_direct_solar_visibility(
                horizon_json=horizon_json,
                solar_observations=solar_rows,
                grid_azimuth_offset_deg=float(
                    illumination_cfg["grid_azimuth_offset_deg"]
                ),
                output_path=artifact,
            )
            report["artifacts"]["illumination"] = str(result_path)
            return {
                "status": "preliminary",
                "observation_count": len(solar_rows),
                "report_file": str(result_path),
                "horizon_profile_source": horizon_source,
                "horizon_profile_file": str(horizon_json),
                "azimuth_offset_independently_validated": False,
            }

        step("illumination", analyze_illumination)

    visibility_cfg = config.get("visibility_analysis")
    if visibility_cfg is not None and visibility_cfg.get("enabled", False):
        def analyze_astronomical_visibility():
            if visibility_cfg.get("grid_azimuth_offset_deg") is None:
                raise ValueError(
                    "Specificare visibility_analysis.grid_azimuth_offset_deg."
                )
            offset = _finite(
                visibility_cfg["grid_azimuth_offset_deg"],
                "visibility_analysis.grid_azimuth_offset_deg",
            )

            horizon_step = report["steps"].get("horizon_analysis", {})
            horizon_result = horizon_step.get("result", {})
            horizon_file = horizon_result.get("report_file")
            if horizon_step.get("status") != "success" or not horizon_file:
                horizon_file = visibility_cfg.get("horizon_json")
            if not horizon_file:
                raise ValueError("Profilo dell'orizzonte non configurato.")

            horizon_path = Path(horizon_file)
            if not horizon_path.is_file():
                raise FileNotFoundError(f"Profilo orizzonte non trovato: {horizon_path}")
            horizon = json.loads(horizon_path.read_text(encoding="utf-8"))
            samples = horizon.get("samples", [])
            horizon_az = [s.get("grid_azimuth_deg") for s in samples]
            horizon_el = [s.get("horizon_elevation_deg") for s in samples]

            astronomy_step = report["steps"].get("astronomy", {})
            astronomy_result = astronomy_step.get("result", {})
            astronomy_file = astronomy_result.get("report_file")
            if astronomy_step.get("status") != "success" or not astronomy_file:
                raise ValueError("Lo step astronomy deve produrre un report.")
            astronomy_path = Path(astronomy_file)
            if not astronomy_path.is_file():
                raise FileNotFoundError(
                    f"Report astronomico non trovato: {astronomy_path}"
                )
            astronomy = json.loads(astronomy_path.read_text(encoding="utf-8"))
            observations = astronomy.get("observations", {})

            results = []
            for target in ("Sun", "Earth"):
                for obs in observations.get(target, []):
                    try:
                        az = float(obs["azimuth_deg"])
                        el = float(obs["elevation_deg"])
                        timestamp = str(obs["time_utc"])
                    except (KeyError, TypeError, ValueError):
                        results.append({
                            "target": target,
                            "status": "indeterminate",
                            "message": "Osservazione incompleta o non numerica.",
                            "georeference_validated": False,
                        })
                        continue

                    grid_az = (az + offset) % 360.0
                    result = compare_with_horizon(
                        azimuth_deg=grid_az,
                        elevation_deg=el,
                        horizon_azimuth_deg=horizon_az,
                        horizon_elevation_deg=horizon_el,
                        georeference_validated=False,
                    )

                    def finite_or_none(value):
                        if value is None:
                            return None
                        number = float(value)
                        return number if math.isfinite(number) else None

                    results.append({
                        "target": target,
                        "time_utc": timestamp,
                        "horizons_azimuth_deg": az,
                        "grid_azimuth_deg": grid_az,
                        "object_elevation_deg": el,
                        "terrain_elevation_deg": finite_or_none(
                            result.terrain_elevation_deg
                        ),
                        "clearance_deg": finite_or_none(result.clearance_deg),
                        "status": result.status,
                        "message": result.message,
                        "georeference_validated": False,
                    })

            artifact = output_dir / visibility_cfg.get(
                "report_name", "astronomical_visibility_diagnostic.json"
            )
            payload = {
                "schema": "lunar-astronomical-visibility-diagnostic/1.0",
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "horizon_profile": str(horizon_path),
                "astronomy_report": str(astronomy_path),
                "azimuth_mapping": {
                    "convention": "grid_azimuth=(Horizons azimuth + offset) mod 360",
                    "offset_deg": offset,
                    "independently_validated": False,
                },
                "georeference_validated": False,
                "observation_count": len(results),
                "observations": results,
                "warnings": [
                    "Risultati diagnostici: orientamento e georeferenziazione non validati.",
                    "Le classificazioni non costituiscono certificazione operativa.",
                    "La qualità del profilo dipende dal DEM e dal suo campionamento.",
                ],
            }
            result_path = _write_json(payload, artifact)
            report["artifacts"]["visibility_analysis"] = str(result_path)
            return {
                "status": "preliminary",
                "report_file": str(result_path),
                "observation_count": len(results),
                "targets": ["Sun", "Earth"],
                "azimuth_offset_independently_validated": False,
                "georeference_validated": False,
            }

        step("visibility_analysis", analyze_astronomical_visibility)

    local_cfg = config.get("local_site_analysis")
    if local_cfg is not None and local_cfg.get("enabled", False):
        def analyze_configured_local_site():
            required = ("site_name", "dem_path", "observer_x_m", "observer_y_m")
            missing = [key for key in required if key not in local_cfg]
            if missing:
                raise ValueError(
                    "Configurazione local_site_analysis incompleta: "
                    + ", ".join(missing)
                )

            result = analyze_local_site(
                site_name=local_cfg["site_name"],
                dem_path=local_cfg["dem_path"],
                observer_x_m=float(local_cfg["observer_x_m"]),
                observer_y_m=float(local_cfg["observer_y_m"]),
                density_path=local_cfg.get("density_path"),
                error_path=local_cfg.get("error_path"),
                azimuth_step_deg=float(
                    local_cfg.get("azimuth_step_deg", 2.0)
                ),
                max_distance_m=float(
                    local_cfg.get("max_distance_m", 7000.0)
                ),
                observer_height_m=float(
                    local_cfg.get("observer_height_m", 0.0)
                ),
            )

            horizon = result.horizon
            artifact = output_dir / local_cfg.get(
                "report_name", "local_site_analysis.json"
            )
            payload = {
                "schema": "lunar-local-site-analysis/1.0",
                "status": "preliminary",
                "site_name": result.site_name,
                "dem_path": result.dem_path,
                "observer": {
                    "x_m": result.observer_x_m,
                    "y_m": result.observer_y_m,
                    "elevation_m": result.elevation_m,
                    "row": int(horizon.observer_row),
                    "col": int(horizon.observer_col),
                },
                "horizon": {
                    "azimuth_deg": horizon.azimuth_deg.tolist(),
                    "elevation_deg": horizon.elevation_deg.tolist(),
                    "max_distance_m": horizon.max_distance_m.tolist(),
                    "valid_samples": horizon.valid_samples.tolist(),
                    "zero_density_fraction": horizon.zero_density_fraction.tolist(),
                    "mean_dem_error_m": horizon.mean_dem_error_m.tolist(),
                    "valid_azimuth_fraction": result.valid_azimuth_fraction,
                    "mean_horizon_deg": result.mean_horizon_deg,
                    "max_horizon_deg": result.max_horizon_deg,
                    "mean_zero_density_fraction": result.mean_zero_density_fraction,
                    "mean_dem_error_m": result.mean_dem_error_m,
                },
                "georeference_validated": result.georeference_validated,
                "warnings": list(result.warnings),
            }
            _write_json(payload, artifact)
            report["artifacts"]["local_site_analysis"] = str(artifact)
            return {
                "status": "preliminary",
                "site_name": result.site_name,
                "valid_azimuth_fraction": result.valid_azimuth_fraction,
                "report_file": str(artifact),
                "georeference_validated": result.georeference_validated,
            }

        step("local_site_analysis", analyze_configured_local_site)

    geometry_cfg = config.get("lunar_geometry")
    if geometry_cfg is not None and geometry_cfg.get("enabled", False):
        def diagnose_lunar_geometry():
            required = ("dem_path", "longitude_east_deg", "latitude_deg")
            missing = [
                key for key in required
                if key not in geometry_cfg or geometry_cfg[key] is None
            ]
            if missing:
                raise ValueError(
                    "Configurazione lunar_geometry incompleta: "
                    + ", ".join(missing)
                )

            location = locate_observer(
                geometry_cfg["dem_path"],
                float(geometry_cfg["longitude_east_deg"]),
                float(geometry_cfg["latitude_deg"]),
            )
            elevation = sample_elevation(
                geometry_cfg["dem_path"], location
            )
            result = {
                "schema": "lunar-geometry-diagnostic/1.0",
                "longitude_east_deg": location.longitude_east_deg,
                "latitude_deg": location.latitude_deg,
                "x_m": location.x_m,
                "y_m": location.y_m,
                "row": location.row,
                "col": location.col,
                "inside_raster": location.inside_raster,
                "elevation_m": elevation,
                "georeference_validated": False,
                "status": location.status,
                "message": location.message,
                "warning": (
                    "Trasformazione diagnostica basata su un CRS lunare "
                    "ipotizzato; non usare come convalida del frame fisico."
                ),
            }
            output_path = output_dir / geometry_cfg.get(
                "report_name", "lunar_geometry_diagnostic.json"
            )
            _write_json(result, output_path)
            report["artifacts"]["lunar_geometry"] = str(output_path)
            return result

        step("lunar_geometry", diagnose_lunar_geometry)

    assessment_cfg = config.get("site_assessment")
    if assessment_cfg is not None and assessment_cfg.get("enabled", False):
        def assess_configured_site():
            required = ("candidate_name", "dem_path", "row", "col")
            missing = [
                key for key in required
                if key not in assessment_cfg or assessment_cfg[key] is None
            ]
            if missing:
                raise ValueError(
                    "Configurazione site_assessment incompleta: "
                    + ", ".join(missing)
                )

            astronomy_step = report["steps"].get("astronomy", {})
            astronomy_result = astronomy_step.get("result", {})
            astronomy_file = astronomy_result.get("report_file")
            if astronomy_step.get("status") != "success" or not astronomy_file:
                raise ValueError(
                    "site_assessment richiede osservazioni astronomiche "
                    "già generate dallo step astronomy."
                )

            astronomy_path = Path(astronomy_file)
            if not astronomy_path.is_file():
                raise FileNotFoundError(
                    f"Report astronomico non trovato: {astronomy_path}"
                )

            astronomy_payload = json.loads(
                astronomy_path.read_text(encoding="utf-8")
            )
            observations = astronomy_payload.get("observations", {})
            sun_rows = observations.get("Sun", [])
            earth_rows = observations.get("Earth", [])
            earth_by_time = {
                row.get("time_utc"): row
                for row in earth_rows if row.get("time_utc") is not None
            }
            common = [
                (row, earth_by_time[row["time_utc"]])
                for row in sun_rows
                if row.get("time_utc") in earth_by_time
            ]
            if not common:
                raise ValueError(
                    "Nessun timestamp comune tra le osservazioni del Sole e della Terra."
                )

            assessment = assess_candidate(
                candidate_name=str(assessment_cfg["candidate_name"]),
                dem_path=assessment_cfg["dem_path"],
                row=int(assessment_cfg["row"]),
                col=int(assessment_cfg["col"]),
                radius_pixels=int(assessment_cfg.get("radius_pixels", 10)),
                sun_elevations_deg=[
                    float(pair[0]["elevation_deg"]) for pair in common
                ],
                earth_elevations_deg=[
                    float(pair[1]["elevation_deg"]) for pair in common
                ],
                confidence_path=assessment_cfg.get("confidence_path"),
            )
            artifact = output_dir / assessment_cfg.get(
                "report_name", "site_assessment.json"
            )
            saved = write_assessment(assessment, artifact)
            report["artifacts"]["site_assessment"] = str(saved)
            return {
                "status": "preliminary",
                "candidate_name": assessment.candidate_name,
                "score": assessment.score,
                "matched_observation_count": len(common),
                "report_file": str(saved),
                "warnings": list(assessment.warnings),
            }

        step("site_assessment", assess_configured_site)

    confidence_cfg = config.get("confidence_validation")
    if confidence_cfg is not None and confidence_cfg.get("enabled", False):
        def validate_configured_confidence():
            raster_path = confidence_cfg.get("raster_path")
            if not raster_path:
                raise ValueError(
                    "confidence_validation.raster_path è obbligatorio."
                )

            result = validate_confidence_raster(raster_path)
            artifact = output_dir / confidence_cfg.get(
                "report_name", "confidence_validation.json"
            )
            _write_json(result.to_dict(), artifact)
            report["artifacts"]["confidence_validation"] = str(artifact)

            if not result.exists:
                raise FileNotFoundError(
                    f"Mappa di confidenza non trovata: {raster_path}"
                )

            return {
                "status": "preliminary",
                "total_pixels": result.total_pixels,
                "undocumented_classes": list(result.undocumented_classes),
                "report_file": str(artifact),
                "warnings": list(result.warnings),
            }

        step("confidence_validation", validate_configured_confidence)

    quality_audit_cfg = config.get("data_quality")
    if quality_audit_cfg is not None and quality_audit_cfg.get("enabled", False):
        def audit_configured_rasters():
            dem_path = quality_audit_cfg.get("dem_path")
            if not dem_path:
                raise ValueError("data_quality.dem_path è obbligatorio.")

            result = {
                "schema": "lunar-raster-quality-audit/1.0",
                "status": "preliminary",
                "dem_audit": audit_raster(dem_path).to_dict(),
                "grid_comparison": None,
                "warnings": [
                    "Audit dei metadati e della copertura; non certifica il frame lunare."
                ],
            }

            candidate_path = quality_audit_cfg.get("comparison_path")
            if candidate_path:
                result["grid_comparison"] = compare_grid_metadata(
                    dem_path, candidate_path
                )
                result["warnings"].append(
                    "Compatibilità della griglia non equivale a co-registrazione fisica."
                )

            artifact = output_dir / quality_audit_cfg.get(
                "report_name", "data_quality_audit.json"
            )
            _write_json(result, artifact)
            report["artifacts"]["data_quality"] = str(artifact)

            if not result["dem_audit"]["exists"]:
                raise FileNotFoundError(f"DEM non trovato: {dem_path}")

            return {
                "status": "preliminary",
                "dem_exists": result["dem_audit"]["exists"],
                "valid_percent": result["dem_audit"]["valid_percent"],
                "comparison_performed": candidate_path is not None,
                "report_file": str(artifact),
            }

        step("data_quality", audit_configured_rasters)

    descent_cfg = config.get("descent_hazard_detection")
    if descent_cfg is not None:
        def assess_descent_hazards():
            dem_path = Path(descent_cfg["dem_path"])
            result = analyze_descent_patch(
                dem_path=dem_path,
                center_rc=descent_cfg["center_rc"],
                radius_cells=descent_cfg.get("radius_cells", 5),
                noise_sigma_m=descent_cfg.get("noise_sigma_m", 0.0),
                synthetic_obstacle_height_m=descent_cfg.get(
                    "synthetic_obstacle_height_m", 0.0
                ),
                max_slope_deg=descent_cfg.get("max_slope_deg", 15.0),
                max_roughness_m=descent_cfg.get("max_roughness_m", 1.0),
                max_discrepancy_m=descent_cfg.get("max_discrepancy_m", 1.5),
                min_coverage=descent_cfg.get("min_coverage", 0.90),
                output_path=output_dir / descent_cfg.get(
                    "report_name", "descent_hazard_report.json"
                ),
                random_seed=descent_cfg.get("random_seed", 0),
            )
            report["artifacts"]["descent_hazard_detection"] = result["output_path"]
            return {
                "decision": result["decision"],
                "decision_reasons": result["decision_reasons"],
                "coverage_fraction": result["coverage"]["fraction"],
                "report_file": result["output_path"],
                "status": "preliminary",
            }

        step("descent_hazard_detection", assess_descent_hazards)


    risk_map_cfg = config.get("descent_risk_map", {})
    if risk_map_cfg.get("enabled", False):
        def export_descent_risk_map():
            hazard_step = report["steps"].get("descent_hazard_detection", {})
            hazard_result = hazard_step.get("result", {})

            if hazard_step.get("status") != "success":
                raise RuntimeError(
                    "Lo step descent_hazard_detection non è terminato correttamente."
                )

            hazard_report = hazard_result.get("report_file")
            if not hazard_report:
                hazard_report = report["artifacts"].get("descent_hazard_detection")
            if not hazard_report:
                raise ValueError("Percorso del report dei rischi non disponibile.")

            dem_path = Path(descent_cfg["dem_path"])
            output_path = output_dir / risk_map_cfg.get(
                "report_name", "descent_risk_map.tif"
            )

            exported = export_descent_risk_raster(
                report_path=hazard_report,
                dem_path=dem_path,
                output_path=output_path,
            )
            report["artifacts"]["descent_risk_map"] = str(exported)

            return {
                "status": "preliminary",
                "raster_file": str(exported),
                "source_report": str(hazard_report),
                "source_dem": str(dem_path),
                "flight_certified": False,
            }

        step("descent_risk_map", export_descent_risk_map)

    selection_cfg = config.get("site_selection")
    if selection_cfg is not None:
        def select_sites():
            result = select_candidate_sites(
                dem_path=selection_cfg["dem_path"],
                output_path=output_dir / selection_cfg.get(
                    "report_name", "site_ranking.json"
                ),
                radius_pixels=selection_cfg.get("radius_pixels", 10),
                target_candidates=selection_cfg.get("target_candidates", 400),
                max_slope_deg=selection_cfg.get("max_slope_deg", 15.0),
                max_roughness_m=selection_cfg.get("max_roughness_m", 5.0),
                min_valid_fraction=selection_cfg.get("min_valid_fraction", 0.95),
                top_n=selection_cfg.get("top_n", 20),
            )
            report["artifacts"]["site_selection"] = result["output_path"]

            top_candidates = result.get("top_candidates", [])
            terrain_summary = result.get("terrain_class_summary", {})

            return {
                "status": "preliminary",
                "candidates_ranked": len(top_candidates),
                "terrain_class_summary": terrain_summary,
                "top_candidate": top_candidates[0] if top_candidates else None,
                "report_file": result["output_path"],
                "warnings": result.get("warnings", []),
            }

        step("site_selection", select_sites)

    quality_cfg = config.get("lola_lroc_quality")
    if quality_cfg is not None:
        def assess_lola_lroc_quality():
            result = compare_lola_lroc_quality(
                lola_path=quality_cfg["lola_path"],
                lroc_path=quality_cfg["lroc_path"],
                confidence_path=quality_cfg["confidence_path"],
                output_path=output_dir / quality_cfg.get(
                    "report_name", "lola_lroc_quality.json"
                ),
            )
            report["artifacts"]["lola_lroc_quality"] = result["output_path"]
            return result

        step("lola_lroc_quality", assess_lola_lroc_quality)

    rover_cfg = config.get("rover_path")
    if rover_cfg is not None:
        def plan_route():
            dem_path = Path(rover_cfg["dem_path"])
            if not dem_path.is_file():
                raise FileNotFoundError(f"DEM non trovato: {dem_path}")

            with rasterio.open(dem_path) as ds:
                dem = ds.read(1, masked=True).astype("float64").filled(float("nan"))
                px = abs(float(ds.transform.a))
                py = abs(float(ds.transform.e))
                if ds.crs is None:
                    report["warnings"].append(
                        "DEM senza CRS dichiarato: le dimensioni pixel sono interpretate in metri."
                    )

            plan = plan_rover_path(
                dem,
                rover_cfg["start_rc"],
                rover_cfg["goal_rc"],
                pixel_size_x_m=px,
                pixel_size_y_m=py,
                max_slope_deg=_finite(
                    rover_cfg.get("max_slope_deg", 20),
                    "max_slope_deg", 0.001,
                ),
                energy_wh_per_m=_finite(
                    rover_cfg.get("energy_wh_per_m", 0.02),
                    "energy_wh_per_m", 0,
                ),
                energy_budget_wh=_finite(
                    rover_cfg.get("energy_budget_wh", 1e30),
                    "energy_budget_wh", 0,
                ),
                allow_diagonal=bool(rover_cfg.get("allow_diagonal", True)),
            )
            plan_data = plan.to_dict()
            plan_data.update({
                "schema": "lunar-rover-route-plan/1.0",
                "dem_path": str(dem_path),
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "pixel_size_x_m": px,
                "pixel_size_y_m": py,
            })
            saved = _write_json(plan_data, output_dir / "rover_plan.json")
            report["artifacts"]["rover_plan"] = str(saved)

            quality_data = analyze_route_quality(
                dem,
                plan.path_rc,
                pixel_size_x_m=px,
                pixel_size_y_m=py,
            )
            quality_data["dem_path"] = str(dem_path)
            quality_data["route_plan_path"] = str(saved)
            quality_path = _write_json(
                quality_data, output_dir / "route_quality.json"
            )
            report["artifacts"]["route_quality"] = str(quality_path)

            # Esporta la visualizzazione diagnostica della rotta pianificata.
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np

            path_rc = np.asarray(plan.path_rc, dtype=int)
            r0 = max(0, int(path_rc[:, 0].min()) - 12)
            r1 = min(dem.shape[0], int(path_rc[:, 0].max()) + 13)
            c0 = max(0, int(path_rc[:, 1].min()) - 12)
            c1 = min(dem.shape[1], int(path_rc[:, 1].max()) + 13)
            terrain = dem[r0:r1, c0:c1]
            valid = np.isfinite(terrain)
            filled = terrain.copy()
            filled[~valid] = float(np.nanmedian(terrain[valid]))
            dz_dr, dz_dc = np.gradient(filled, py, px)
            slope = np.degrees(np.arctan(np.hypot(dz_dc, dz_dr)))
            slope[~valid] = np.nan
            local_rows = path_rc[:, 0] - r0
            local_cols = path_rc[:, 1] - c0

            fig, axes = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)
            image1 = axes[0].imshow(terrain, origin="upper", cmap="terrain")
            axes[0].plot(local_cols, local_rows, color="red", linewidth=2, label="Rotta A*")
            axes[0].scatter(local_cols[0], local_rows[0], color="lime",
                            edgecolors="black", s=85, label="Partenza", zorder=5)
            axes[0].scatter(local_cols[-1], local_rows[-1], color="cyan",
                            edgecolors="black", marker="*", s=150,
                            label="Destinazione", zorder=5)
            axes[0].set_title("Quota del terreno e rotta")
            axes[0].set_xlabel("Colonna DEM")
            axes[0].set_ylabel("Riga DEM")
            axes[0].legend()
            fig.colorbar(image1, ax=axes[0], label="Quota DEM (unità originali)")

            image2 = axes[1].imshow(
                slope, origin="upper", cmap="magma", vmin=0, vmax=30
            )
            axes[1].plot(local_cols, local_rows, color="cyan", linewidth=2, label="Rotta A*")
            axes[1].scatter(local_cols[0], local_rows[0], color="lime",
                            edgecolors="black", s=85, label="Partenza", zorder=5)
            axes[1].scatter(local_cols[-1], local_rows[-1], color="white",
                            edgecolors="black", marker="*", s=150,
                            label="Destinazione", zorder=5)
            axes[1].set_title("Pendenza locale stimata")
            axes[1].set_xlabel("Colonna DEM")
            axes[1].set_ylabel("Riga DEM")
            axes[1].legend()
            fig.colorbar(image2, ax=axes[1], label="Pendenza (gradi)")
            fig.suptitle(
                f"ROVER ROUTE — {plan.distance_m:.2f} m | "
                f"pendenza massima: {plan.max_slope_deg:.2f}°\\n"
                "ANALISI PRELIMINARE — non certificata per operazioni di volo"
            )
            route_map_path = output_dir / "rover_route_map.png"
            fig.savefig(route_map_path, dpi=180, bbox_inches="tight")
            plt.close(fig)
            report["artifacts"]["rover_route_map"] = str(route_map_path)


            return {
                "distance_m": plan.distance_m,
                "estimated_energy_wh": plan.estimated_energy_wh,
                "max_slope_deg": plan.max_slope_deg,
                "cells_in_path": len(plan.path_rc),
                "cells_expanded": plan.cells_expanded,
                "plan_file": str(saved),
                "status": plan.status,
            }

        step("rover_path", plan_route)

    energy_cfg = config.get("energy", {})
    if energy_cfg.get("enabled", False):
        def energy_assessment():
            plan_file = energy_cfg.get(
                "plan_json",
                report["artifacts"].get("rover_plan", "reports/rover_plan.json"),
            )
            required = (
                "mass_kg", "rolling_resistance_coefficient",
                "drivetrain_efficiency", "auxiliary_power_w",
                "mission_duration_hours", "battery_capacity_wh",
            )
            missing = [key for key in required if key not in energy_cfg]
            if missing:
                raise ValueError("Parametri energetici mancanti: " + ", ".join(missing))
            result = estimate_route_energy(
                plan_file,
                **{key: energy_cfg[key] for key in required},
                reserve_percent=energy_cfg.get("reserve_percent", 20.0),
                output_path=output_dir / "rover_energy_assessment.json",
            )
            report["artifacts"]["rover_energy"] = result["output_path"]
            return result
        step("rover_energy", energy_assessment)

    fleet_cfg = config.get("fleet", {})
    if fleet_cfg.get("enabled", False):
        def allocate_fleet():
            result = allocate_tasks(
                fleet_cfg.get("rovers", []),
                fleet_cfg.get("tasks", []),
                output_path=output_dir / "multi_rover_allocation.json",
            )
            report["artifacts"]["fleet_allocation"] = result["output_path"]
            return result
        step("multi_rover", allocate_fleet)

    journal_cfg = config.get("journal", {})
    if journal_cfg.get("enabled", False):
        def record_journal():
            journal = MissionJournal(
                journal_cfg.get("path", output_dir / "mission_events.jsonl"),
                str(journal_cfg["node_id"]),
            )
            events = []
            for name, item in report["steps"].items():
                event = journal.append(
                    entity_id=f"mission-step:{name}",
                    event_type=f"step_{item['status']}",
                    payload={
                        "run_id": run_id,
                        "step": name,
                        "status": item["status"],
                        "error": item.get("error"),
                    },
                )
                events.append(event.to_dict())
            report["artifacts"]["journal"] = str(journal.path)
            return {"events_appended": len(events), "events": events}
        step("local_journal", record_journal)

    # Verifica di coerenza degli artefatti effettivamente registrati.
    missing_artifacts = []
    for artifact_name, artifact_value in report.get("artifacts", {}).items():
        if artifact_name == "journal":
            continue
        if not artifact_value:
            missing_artifacts.append(artifact_name)
            continue

        artifact_path = Path(artifact_value)
        if not artifact_path.is_absolute():
            artifact_path = Path.cwd() / artifact_path

        if not artifact_path.exists():
            missing_artifacts.append(artifact_name)

    if missing_artifacts:
        warning = (
            "Artefatti registrati ma mancanti: "
            + ", ".join(sorted(missing_artifacts))
        )
        if warning not in report["warnings"]:
            report["warnings"].append(warning)

    # Classificazione coerente degli esiti dei moduli.
    step_results = list(report.get("steps", {}).values())
    statuses = [
        item.get("status", "unknown")
        if isinstance(item, dict)
        else "unknown"
        for item in step_results
    ]

    failed_statuses = {"failed", "error", "failure"}
    incomplete_statuses = {
        "unknown", "skipped", "not_configured", "unavailable",
        "disabled", "pending",
    }
    preliminary_statuses = {"preliminary", "completed_preliminary"}
    preliminary_caveats = {
        "Risultati preliminari, non certificati per operazioni reali.",
        "Georeferenziazione e frame fisico lunare non validati indipendentemente.",
        "L'allocazione multi-rover usa distanze euclidee, non percorsi DEM.",
        "Il journal è locale e non si connette a nodi P-System remoti.",
    }


    if any(status in failed_statuses for status in statuses):
        report["status"] = "completed_with_errors"
    elif missing_artifacts:
        report["status"] = "completed_with_errors"
        report["warnings"].append(
            "Artefatti registrati ma mancanti: "
            + ", ".join(sorted(missing_artifacts))
        )
    elif any(status in incomplete_statuses for status in statuses) or any(
        status not in {"success", "completed"} | preliminary_statuses
        for status in statuses
    ):
        report["status"] = "completed_with_warnings"
    elif any(status in preliminary_statuses for status in statuses):
        report["status"] = "completed_preliminary"
    elif any(
        warning not in preliminary_caveats
        and not warning.startswith("Risultati preliminari")
        and not warning.startswith("Georeferenziazione e frame fisico lunare")
        and not warning.startswith("L'allocazione multi-rover")
        and not warning.startswith("Il journal è locale")
        for warning in report.get("warnings", [])
    ):
        report["status"] = "completed_with_warnings"
    else:
        report["status"] = "completed"


    mission_report_cfg = config.get("mission_report", {})
    if mission_report_cfg.get("enabled", True):
        try:
            astronomy_step = report["steps"].get("astronomy", {})
            astronomy_result = astronomy_step.get("result", {})
            astronomy_file = astronomy_result.get("report_file")
            observations = []

            if astronomy_step.get("status") == "success" and astronomy_file:
                astronomy_path = Path(astronomy_file)
                if astronomy_path.is_file():
                    astronomy_payload = json.loads(
                        astronomy_path.read_text(encoding="utf-8")
                    )
                    for label, target in (("Sun", "Sole"), ("Earth", "Terra")):
                        for row in astronomy_payload.get("observations", {}).get(label, []):
                            observations.append((
                                target,
                                type("Observation", (), {
                                    "time_utc": row.get("time_utc"),
                                    "elevation_deg": row.get("elevation_deg"),
                                    "azimuth_deg": row.get("azimuth_deg"),
                                })(),
                            ))

            # Assicura che il journal esista prima di leggerlo nel report.
            if journal_cfg.get("enabled", False):
                journal_path_for_report = Path(
                    journal_cfg.get("path", output_dir / "mission_events.jsonl")
                )
                journal_path_for_report.parent.mkdir(parents=True, exist_ok=True)
                journal_path_for_report.touch(exist_ok=True)


            status_report = build_mission_report(
                site_name=mission_report_cfg.get(
                    "site_name",
                    astronomy_result.get("site", "non specificato"),
                ),
                planning_date=mission_report_cfg.get(
                    "planning_date", datetime.now(timezone.utc).date().isoformat()
                ),
                horizon_hours=int(mission_report_cfg.get("horizon_hours", 48)),
                horizons_observations=observations,
                project_root=Path.cwd(),
                rover_plan_path=report["artifacts"].get(
                    "rover_plan", output_dir / "rover_plan.json"
                ),
                energy_assessment_path=report["artifacts"].get("rover_energy"),
                journal_path=journal_cfg.get(
                    "path",
                    report["artifacts"].get(
                        "journal", output_dir / "mission_events.jsonl"
                    ),
                ),
                journal_enabled=journal_cfg.get("enabled", False),
                run_id=run_id,
            )
            selection_step = report["steps"].get("site_selection", {})
            selection_result = selection_step.get("result", {})
            selection_summary = {
                "status": selection_step.get("status", "not_configured"),
                "candidates_ranked": selection_result.get("candidates_ranked", 0),
                "terrain_class_summary": selection_result.get(
                    "terrain_class_summary", {}
                ),
                "top_candidate": selection_result.get("top_candidate"),
                "report_file": selection_result.get("report_file")
                or report["artifacts"].get("site_selection"),
                "warnings": selection_result.get("warnings", []),
                "safety_note": (
                    "La selezione è preliminare e basata sulle metriche e "
                    "soglie configurate; non certifica l'idoneità operativa "
                    "del sito."
                ),
            }

            status_report["site_selection"] = selection_summary
            status_report["orchestration"] = {
                "status": report["status"],
                "steps": report["steps"],
                "artifacts": report["artifacts"],
                "warnings": report["warnings"],
                "execution_summary": {
                    "step_count": len(report.get("steps", {})),
                    "status_counts": {
                        status: sum(
                            1 for item in report.get("steps", {}).values()
                            if (
                                item.get("status", "unknown")
                                if isinstance(item, dict)
                                else "unknown"
                            ) == status
                        )
                        for status in sorted({
                            (
                                item.get("status", "unknown")
                                if isinstance(item, dict)
                                else "unknown"
                            )
                            for item in report.get("steps", {}).values()
                        })
                    },
                    "artifact_count": len(report.get("artifacts", {})),
                    "warning_count": len(report.get("warnings", [])),
                    "preliminary_steps": [
                        name for name, item in report.get("steps", {}).items()
                        if isinstance(item, dict)
                        and item.get("status") in {
                            "preliminary", "completed_preliminary"
                        }
                    ],
                    "failed_steps": [
                        name for name, item in report.get("steps", {}).items()
                        if isinstance(item, dict)
                        and item.get("status") in {
                            "failed", "error", "failure"
                        }
                    ],
                },
            }
            json_report, markdown_report = write_mission_report(
                status_report, output_dir=output_dir
            )
            report["artifacts"]["mission_status_json"] = str(json_report)
            report["artifacts"]["mission_status_markdown"] = str(markdown_report)
            # Sincronizza il Markdown con lo stato definitivo dell'orchestratore.
            markdown_text = markdown_report.read_text(encoding="utf-8")
            marker = "## Coerenza finale dell'esecuzione"
            if marker in markdown_text:
                markdown_text = markdown_text.split(marker, 1)[0].rstrip()

            final_section = [
                "",
                marker,
                "",
                f"- Stato finale: {report['status']}",
                f"- Moduli registrati: {len(report.get('steps', {}))}",
                f"- Artefatti registrati: {len(report.get('artifacts', {}))}",
                f"- Avvisi: {len(report.get('warnings', []))}",
                "- Risultati preliminari non certificati per operazioni reali.",
            ]
            if report.get("warnings"):
                final_section.extend(["", "### Avvisi", ""])
                final_section.extend(
                    f"- {warning}" for warning in report["warnings"]
                )

            markdown_report.write_text(
                markdown_text.rstrip() + "\n"
                + "\n".join(final_section) + "\n",
                encoding="utf-8",
            )


            # Ricalcola lo stato dopo aver prodotto tutti gli artefatti.
            final_statuses = [
                item.get("status", "unknown")
                if isinstance(item, dict) else "unknown"
                for item in report.get("steps", {}).values()
            ]
            failed = {"failed", "error", "failure"}
            incomplete = {
                "unknown", "skipped", "not_configured", "unavailable",
                "disabled", "pending",
            }
            preliminary = {"preliminary", "completed_preliminary"}

            missing_artifacts = []
            for name, value in report.get("artifacts", {}).items():
                # Il journal può essere aggiornato durante la finalizzazione.
                if name == "journal":
                    continue
                path = Path(value) if value else None
                if path is not None and not path.is_absolute():
                    path = Path.cwd() / path
                if path is None or not path.exists():
                    missing_artifacts.append(name)

            final_statuses = [
                item.get("status", "unknown")
                if isinstance(item, dict)
                else "unknown"
                for item in report.get("steps", {}).values()
            ]

            if any(status in failed for status in final_statuses):
                report["status"] = "completed_with_errors"
            elif missing_artifacts:
                report["status"] = "completed_with_errors"
                warning = (
                    "Artefatti finali mancanti: "
                    + ", ".join(sorted(missing_artifacts))
                )
                if warning not in report["warnings"]:
                    report["warnings"].append(warning)
            elif any(status in incomplete for status in final_statuses):
                report["status"] = "completed_with_warnings"
            elif any(
                status not in {"success", "completed"} | preliminary
                for status in final_statuses
            ):
                report["status"] = "completed_with_warnings"
            elif any(status in preliminary for status in final_statuses):
                report["status"] = "completed_preliminary"
            else:
                # Questo pianificatore produce risultati preliminari per progetto.
                report["status"] = "completed_preliminary"

            orchestration = status_report.setdefault("orchestration", {})
            orchestration["status"] = report["status"]
            orchestration["steps"] = report.get("steps", {})
            orchestration["artifacts"] = dict(report.get("artifacts", {}))
            orchestration["warnings"] = list(report.get("warnings", []))
            summary = orchestration.setdefault("execution_summary", {})
            summary["step_count"] = len(report.get("steps", {}))
            summary["artifact_count"] = len(report.get("artifacts", {}))
            summary["warning_count"] = len(report.get("warnings", []))

            json_report.write_text(
                __import__("json").dumps(
                    status_report, indent=2, ensure_ascii=False
                ) + "\n",
                encoding="utf-8",
            )

            # Allinea il riepilogo dell'esecuzione dopo la generazione dei report.
            orchestration = status_report.setdefault("orchestration", {})
            orchestration["status"] = report["status"]
            orchestration["steps"] = report.get("steps", {})
            orchestration["artifacts"] = dict(report.get("artifacts", {}))
            orchestration["warnings"] = list(report.get("warnings", []))

            summary = orchestration.setdefault("execution_summary", {})
            summary["step_count"] = len(report.get("steps", {}))
            summary["artifact_count"] = len(report.get("artifacts", {}))
            summary["warning_count"] = len(report.get("warnings", []))

            json_report.write_text(
                __import__("json").dumps(
                    status_report, indent=2, ensure_ascii=False
                ) + "\n",
                encoding="utf-8",
            )

            # Aggiorna il report JSON finale con gli artefatti dei report stessi.
            status_report["orchestration"]["artifacts"] = dict(report["artifacts"])
            status_report["orchestration"]["status"] = report["status"]
            status_report["orchestration"]["warnings"] = list(report["warnings"])
            json_report.write_text(
                __import__("json").dumps(
                    status_report, indent=2, ensure_ascii=False
                ) + "\n",
                encoding="utf-8",
            )

            # Allinea il Markdown agli artefatti e allo stato finali.
            markdown_text = markdown_report.read_text(encoding="utf-8")
            consistency_section = [
                "",
                "## Coerenza finale dell'esecuzione",
                "",
                f"- Stato orchestratore: {report['status']}",
                f"- Moduli eseguiti: {len(report.get('steps', {}))}",
                f"- Artefatti registrati: {len(report.get('artifacts', {}))}",
                f"- Avvisi: {len(report.get('warnings', []))}",
                "- Gli esiti preliminary indicano analisi non certificate.",
            ]
            if report.get("warnings"):
                consistency_section.extend(["", "### Avvisi", ""])
                consistency_section.extend(
                    f"- {warning}" for warning in report["warnings"]
                )

            marker = "## Coerenza finale dell'esecuzione"
            if marker in markdown_text:
                markdown_text = markdown_text.split(marker, 1)[0].rstrip()
            markdown_report.write_text(
                markdown_text.rstrip() + "\n"
                + "\n".join(consistency_section) + "\n",
                encoding="utf-8",
            )

            # Registra nel report JSON anche gli artefatti finali aggiornati.
            status_report["orchestration"]["artifacts"] = dict(report["artifacts"])
            status_report["orchestration"]["status"] = report["status"]
            status_report["orchestration"]["warnings"] = list(report["warnings"])
            status_report["orchestration"]["execution_summary"]["artifact_count"] = (
                len(report["artifacts"])
            )
            status_report["orchestration"]["execution_summary"]["warning_count"] = (
                len(report["warnings"])
            )
            json_report.write_text(
                __import__("json").dumps(
                    status_report, indent=2, ensure_ascii=False
                ) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            report["status"] = "completed_with_errors"
            report["warnings"].append(
                f"Generazione report riepilogativo non riuscita: "
                f"{type(exc).__name__}: {exc}"
            )
            report["steps"]["mission_report"] = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

            # Registra la correzione dello stato se il report ha fallito.
            if journal_cfg.get("enabled", False):
                try:
                    correction_journal = MissionJournal(
                        journal_cfg.get("path", output_dir / "mission_events.jsonl"),
                        str(journal_cfg["node_id"]),
                    )
                    correction_event = correction_journal.append(
                        entity_id=f"mission-run:{run_id}",
                        event_type="mission_completed_with_errors",
                        payload={
                            "run_id": run_id,
                            "status": report["status"],
                            "reason": "mission_report_failed",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "generated_utc": report["generated_utc"],
                        },
                    )
                    report["final_journal_event"] = correction_event.to_dict()
                    report["artifacts"]["journal"] = str(correction_journal.path)
                except Exception as journal_exc:
                    report["warnings"].append(
                        "Registrazione della correzione nel journal non riuscita: "
                        f"{type(journal_exc).__name__}: {journal_exc}"
                    )

# Registra l'evento finale dopo la classificazione definitiva.
        if journal_cfg.get("enabled", False):
            final_journal = MissionJournal(
                journal_cfg.get("path", output_dir / "mission_events.jsonl"),
                str(journal_cfg["node_id"]),
            )
            final_event = final_journal.append(
                entity_id=f"mission-run:{run_id}",
                event_type=(
                "mission_completed_preliminary"
                if report["status"] == "completed_preliminary"
                else f"mission_{report['status']}"
            ),
                payload={
                    "run_id": run_id,
                    "status": report["status"],
                    "generated_utc": report["generated_utc"],
                    "steps_count": len(report["steps"]),
                    "warnings_count": len(report["warnings"]),
                },
            )
            report["artifacts"]["journal"] = str(final_journal.path)
            report["final_journal_event"] = final_event.to_dict()


    # Sincronizza il report di stato con l'evento finale appena scritto.
    if journal_cfg.get("enabled", False):
        try:
            status_json_path = output_dir / "mission_status_report.json"
            if status_json_path.is_file():
                status_data = json.loads(status_json_path.read_text(encoding="utf-8"))
                journal_data = build_mission_report(
                    site_name=config.get("mission_report", {}).get("site_name", "non specificato"),
                    planning_date=config.get("mission_report", {}).get(
                        "planning_date", datetime.now(timezone.utc).date().isoformat()
                    ),
                    horizon_hours=int(config.get("mission_report", {}).get("horizon_hours", 48)),
                    project_root=Path.cwd(),
                    journal_path=journal_cfg.get("path", output_dir / "mission_events.jsonl"),
                    journal_enabled=True,
                    run_id=run_id,
                )["psystem_journal"]
                status_data["psystem_journal"] = journal_data
                status_json_path.write_text(
                    json.dumps(status_data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                markdown_path = output_dir / "mission_status_report.md"
                if markdown_path.is_file():
                    markdown_text = markdown_path.read_text(encoding="utf-8")
                    event_count_line = (
                        f"Eventi dell'esecuzione corrente: "
                        f"{journal_data['current_run_event_lines']}"
                    )
                    if re.search(
                        r"Eventi dell'esecuzione corrente:\\s*\\d+",
                        markdown_text,
                    ):
                        markdown_text = re.sub(
                            r"Eventi dell'esecuzione corrente:\\s*\\d+",
                            event_count_line,
                            markdown_text,
                        )
                    else:
                        markdown_text = markdown_text.rstrip() + (
                            "\\n\\n## Journal P-System\\n\\n- "
                            + event_count_line
                            + "\\n"
                        )
                    markdown_path.write_text(markdown_text, encoding="utf-8")
        except Exception as exc:
            report.setdefault("warnings", []).append(
                f"Aggiornamento conteggio journal nel report non riuscito: {type(exc).__name__}: {exc}"
            )


    report_path = _write_json(report, output_dir / "mission_report.json")
    report["report_path"] = str(report_path)
    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Orchestratore preliminare di missioni lunari multi-rover."
    )
    parser.add_argument("config", help="File JSON di configurazione della missione.")
    args = parser.parse_args()

    try:
        result = run_mission_workflow(args.config)
    except Exception as exc:
        print(f"Errore di configurazione: {type(exc).__name__}: {exc}")
        return 2

    print(json.dumps({
        "status": result["status"],
        "steps": result["steps"],
        "artifacts": result["artifacts"],
        "report_path": result.get("report_path"),
        "warnings": result["warnings"],
    }, indent=2, ensure_ascii=False))
    return 1 if result["status"] == "completed_with_errors" else 0


if __name__ == "__main__":
    raise SystemExit(main())

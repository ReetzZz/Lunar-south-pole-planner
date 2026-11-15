# Last updated: 2026-11-14
"""Generazione di un rapporto missione riproducibile dai dati disponibili.

Il rapporto distingue osservazioni e artefatti presenti da metriche mancanti;
non trasforma input dimostrativi in risultati scientifici.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    if not path.is_file():
        return None, "file non presente"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"lettura non riuscita: {exc}"


def build_mission_report(
    *,
    site_name: str,
    planning_date: str,
    horizon_hours: int,
    horizons_observations: list | None = None,
    project_root: str | Path = ".",
    rover_plan_path: str | Path | None = None,
    energy_assessment_path: str | Path | None = None,
    journal_path: str | Path | None = None,
    journal_enabled: bool | None = None,
    run_id: str | None = None,
) -> dict:
    """Create a status report without performing network calls or modifying DEMs."""
    root = Path(project_root).resolve()
    observations = horizons_observations or []
    obs_by_object: dict[str, list[dict]] = {"Sole": [], "Terra": []}
    for label, row in observations:
        if label not in obs_by_object:
            continue
        obs_by_object[label].append({
            "time_utc": getattr(row, "time_utc", None),
            "elevation_deg": getattr(row, "elevation_deg", None),
            "azimuth_deg": getattr(row, "azimuth_deg", None),
        })

    raster_paths = {
        "LOLA": Path("data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif"),
        "LROC": Path("data/terrain/reference-lroc/NAC_DTM_ESALL_SR12.TIF"),
    }
    rasters = {}
    for name, relative in raster_paths.items():
        path = root / relative
        rasters[name] = {
            "path": str(relative),
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "metadata_audit": "available via GUI audit" if path.is_file() else "not available",
            "physical_georeference_validated": False,
        }

    rover_source = Path(rover_plan_path) if rover_plan_path is not None else Path("reports/rover_plan.json")
    if not rover_source.is_absolute():
        rover_source = root / rover_source
    rover, rover_error = _read_json(rover_source)
    rover_summary = None
    if isinstance(rover, dict):
        rover_summary = {
            key: rover.get(key)
            for key in ("distance_m", "estimated_energy_wh", "max_slope_deg", "cells_expanded", "status", "warning", "dem_path", "dem_shape", "pixel_size_m", "coordinates")
            if key in rover
        }

    energy_source = (
        Path(energy_assessment_path)
        if energy_assessment_path is not None
        else None
    )
    if energy_source is not None and not energy_source.is_absolute():
        energy_source = root / energy_source
    energy_payload, energy_error = (
        _read_json(energy_source)
        if energy_source is not None
        else (None, "valutazione energetica non configurata")
    )
    energy_summary = None
    if isinstance(energy_payload, dict):
        energy_values = energy_payload.get("energy_wh", {})
        inputs = energy_payload.get("inputs", {})
        if isinstance(energy_values, dict):
            energy_summary = {
                "status": energy_payload.get("status", "unknown"),
                "distance_m": energy_payload.get("distance_m"),
                "total_estimated_wh": energy_values.get("total_estimated"),
                "usable_battery_after_reserve_wh": energy_values.get("usable_battery_after_reserve"),
                "remaining_after_estimate_wh": energy_values.get("remaining_after_estimate"),
                "within_budget": energy_values.get("within_budget"),
                "reserve_percent": inputs.get("reserve_percent") if isinstance(inputs, dict) else None,
                "warnings": energy_payload.get("warnings", []),
                "assumptions": energy_payload.get("assumptions", []),
            }

    journal_source = Path(journal_path) if journal_path is not None else Path("reports/mission_events.jsonl")
    if not journal_source.is_absolute():
        journal_source = root / journal_source
    journal_count = 0
    journal_run_event_count = 0
    journal_error = None
    if journal_enabled is False:
        journal_status = "disabled"
        journal_display_path = None
    else:
        journal_display_path = str(journal_source)
        if journal_source.is_file():
            journal_status = "available"
            try:
                journal_lines = [
                    line for line in
                    journal_source.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                journal_count = len(journal_lines)
                for number, line in enumerate(journal_lines, 1):
                    try:
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError("l'evento JSON non è un oggetto")
                        required = {
                            "event_id", "node_id", "entity_id", "event_type",
                            "logical_clock", "payload", "created_unix",
                        }
                        missing = required - event.keys()
                        if missing:
                            raise ValueError(
                                "campi mancanti: " + ", ".join(sorted(missing))
                            )
                        if not isinstance(event["payload"], dict):
                            raise ValueError("payload non è un oggetto")
                    except (json.JSONDecodeError, ValueError, TypeError) as exc:
                        journal_status = "invalid"
                        journal_error = f"Evento non valido alla riga {number}: {exc}"
                        break

                    if (
                        run_id is not None
                        and event["payload"].get("run_id") == run_id
                    ):
                        journal_run_event_count += 1
            except OSError as exc:
                journal_error = str(exc)
                journal_status = "unreadable"
        else:
            journal_status = "missing" if journal_enabled is True else "not_configured"

    return {
        "report_schema": "lunar-south-pole-mission-report/1.0",
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mission": {
            "site_name": site_name,
            "planning_date": planning_date,
            "horizon_hours": int(horizon_hours),
        },
        "astronomy": {
            "source": "observations already loaded in the application; no network request performed",
            "site_matches_current_selection": bool(observations),
            "sun_observations": obs_by_object["Sole"],
            "earth_observations": obs_by_object["Terra"],
            "warning": "Geometric observations do not alone establish solar power or RF link availability.",
        },
        "terrain": {
            "rasters": rasters,
            "physical_georeference_validated": False,
            "warning": "CRS metadata and grid compatibility do not independently validate the physical lunar frame.",
        },
        "rover_plan": {
            "available": rover_summary is not None,
            "summary": rover_summary,
            "read_error": rover_error,
        },
        "energy_assessment": {
            "available": energy_summary is not None,
            "summary": energy_summary,
            "path": str(energy_source) if energy_source is not None else None,
            "read_error": energy_error,
        },
        "psystem_journal": {
            "status": journal_status,
            "path": journal_display_path,
            "event_lines": journal_count,
            "current_run_event_lines": journal_run_event_count,
            "read_error": journal_error,
            "remote_node_connected": False,
        },
        "limitations": [
            "Geodetic alignment of LOLA/LROC and candidate coordinates is not independently validated.",
            "No power-system model, RF link budget, rover dynamics, or multi-rover coordination is certified by this report.",
            "Missing measurements remain missing; no placeholder scientific values are inferred.",
            "The P-System journal is local unless a real remote protocol integration is configured separately.",
        ],
    }


def write_mission_report(report: dict, output_dir: str | Path = "reports") -> tuple[Path, Path]:
    """Write JSON and human-readable Markdown copies of a mission report."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "mission_status_report.json"
    md_path = out / "mission_status_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    mission = report.get("mission", {})
    astro = report.get("astronomy", {})
    terrain = report.get("terrain", {})
    rover = report.get("rover_plan", {})
    energy = report.get("energy_assessment", {})
    journal = report.get("psystem_journal", {})
    selection = report.get("site_selection", {})
    lines = [
        "# Lunar South Pole — rapporto di stato missione", "",
        f"- Generato UTC: {report.get('generated_utc', 'non disponibile')}",
        f"- Run ID: {report.get('run_id') or 'non disponibile'}",
        f"- Sito candidato: {mission.get('site_name', 'non specificato')}",
        f"- Data pianificazione: {mission.get('planning_date', 'non specificata')}",
        f"- Orizzonte: {mission.get('horizon_hours', 'n/d')} ore", "",
        "## Osservazioni astronomiche caricate", "",
        f"- Sole: {len(astro.get('sun_observations', []))} campioni",
        f"- Terra: {len(astro.get('earth_observations', []))} campioni",
        f"- Fonte: {astro.get('source', 'non specificata')}",
        f"- Nota: {astro.get('warning', '')}", "",
        "## Dati del terreno", "",
    ]
    for name, raster in terrain.get("rasters", {}).items():
        lines.append(f"- {name}: {'presente' if raster.get('exists') else 'assente'} — `{raster.get('path')}`")
    lines += [
        f"- Georeferenziazione fisica validata: {terrain.get('physical_georeference_validated', False)}",
        "",
        "## Selezione del sito lunare", "",
    ]

    lines.append(f"- Stato della selezione: {selection.get('status', 'non disponibile')}")
    lines.append(
        f"- Candidati classificati nel ranking: "
        f"{selection.get('candidates_ranked', 'n/d')}"
    )

    terrain_summary = selection.get("terrain_class_summary", {})
    class_counts = terrain_summary.get("counts", {}) if isinstance(
        terrain_summary, dict
    ) else {}
    if class_counts:
        lines.append("- Classificazione topografica:")
        for class_name, count in class_counts.items():
            lines.append(f"  - {class_name}: {count}")

    candidate = selection.get("top_candidate")
    if isinstance(candidate, dict):
        lines.append("- Candidato migliore del ranking:")
        for key in (
            "name", "candidate_id", "grid_row", "grid_col",
            "score", "terrain_class", "slope_deg", "roughness_m",
            "valid_fraction",
        ):
            if key in candidate:
                lines.append(f"  - {key}: {candidate[key]}")
    else:
        lines.append("- Candidato migliore: non disponibile.")

    selection_file = selection.get("report_file")
    if selection_file:
        lines.append(f"- Report dettagliato: `{selection_file}`")

    for warning in selection.get("warnings", []):
        lines.append(f"- Avviso selezione: {warning}")

    lines.append(
        "- Nota: la classificazione topografica è preliminare e non "
        "certifica la sicurezza o l'idoneità operativa del sito."
    )

    lines += ["", "## Pianificazione rover", ""]
    if rover.get("summary"):
        for key, value in rover["summary"].items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- Nessun piano rover salvato disponibile.")
    lines += ["", "## Valutazione energetica rover", ""]
    energy_summary = energy.get("summary")
    if energy.get("available") and isinstance(energy_summary, dict):
        lines.append(f"- Stato: {energy_summary.get('status', 'non disponibile')}")
        lines.append(f"- Distanza valutata: {energy_summary.get('distance_m', 'n/d')} m")
        lines.append(f"- Consumo stimato totale: {energy_summary.get('total_estimated_wh', 'n/d')} Wh")
        lines.append(f"- Batteria utilizzabile dopo riserva: {energy_summary.get('usable_battery_after_reserve_wh', 'n/d')} Wh")
        lines.append(f"- Energia residua stimata: {energy_summary.get('remaining_after_estimate_wh', 'n/d')} Wh")
        lines.append(f"- Entro il budget energetico: {energy_summary.get('within_budget', 'n/d')}")
        lines.append(f"- Riserva batteria: {energy_summary.get('reserve_percent', 'n/d')}%")
        lines.append("- Avvertenza: stima preliminare, non certificata per operazioni reali.")
        for warning in energy_summary.get("warnings", []):
            lines.append(f"- Avviso: {warning}")
    else:
        lines.append("- Valutazione energetica non disponibile.")
        if energy.get("read_error"):
            lines.append(f"- Motivo: {energy['read_error']}")

    journal_status_labels = {
        "disabled": "Disabilitato dalla configurazione",
        "available": "Disponibile",
        "missing": "File journal mancante",
        "not_configured": "Non configurato",
        "unreadable": "File journal non leggibile",
        "invalid": "Contenuto del journal non valido",
    }
    journal_status = journal.get("status", "not_configured")
    journal_label = journal_status_labels.get(journal_status, journal_status)

    lines += [
        "", "## P-System", "",
        f"- Stato journal locale: {journal_label}",
        f"- Eventi nel journal locale: {journal.get('event_lines', 0)}",
        f"- Eventi dell'esecuzione corrente: {journal.get('current_run_event_lines', 0)}",
        f"- Percorso journal: {journal.get('path') or 'non applicabile'}",
        f"- Nodo remoto collegato: {journal.get('remote_node_connected', False)}", "",
        "## Limiti e avvertenze", "",
    ]
    lines.extend(f"- {item}" for item in report.get("limitations", []))
    orchestration = report.get("orchestration")
    if isinstance(orchestration, dict):
        lines += ["", "## Esecuzione orchestratore", ""]
        lines.append(f"- Stato: {orchestration.get('status', 'non disponibile')}")
        lines += ["", "### Step", ""]
        steps = orchestration.get("steps", {})
        if steps:
            for name, item in steps.items():
                if not isinstance(item, dict):
                    lines.append(f"- **{name}**: formato risultato inatteso")
                    continue
                lines.append(f"- **{name}**: {item.get('status', 'sconosciuto')}")
                if item.get("error"):
                    lines.append(f"  - Errore: {item['error']}")
        else:
            lines.append("- Nessuno step registrato.")

        lines += ["", "### Artefatti", ""]
        artifacts = orchestration.get("artifacts", {})
        if artifacts:
            for name, value in artifacts.items():
                lines.append(f"- **{name}**: `{value}`")
        else:
            lines.append("- Nessun artefatto registrato.")

        lines += ["", "### Avvisi dell'orchestratore", ""]
        warnings = orchestration.get("warnings", [])
        if warnings:
            lines.extend(f"- {warning}" for warning in warnings)
        else:
            lines.append("- Nessun avviso registrato.")

    lines.append("")
    lines += ["", "## Sintesi integrata della missione", ""]
    selection = report.get("site_selection", {})
    orchestration = report.get("orchestration", {})
    candidate = selection.get("top_candidate")

    lines.append(
        f"- Stato selezione siti: {selection.get('status', 'non disponibile')}"
    )
    lines.append(
        f"- Candidati nel ranking: {selection.get('candidates_ranked', 'n/d')}"
    )

    if isinstance(candidate, dict):
        for key in (
            "name", "candidate_id", "id", "terrain_class",
            "score", "slope_deg", "roughness_m", "valid_fraction",
        ):
            if candidate.get(key) is not None:
                lines.append(f"- Candidato migliore — {key}: {candidate[key]}")
    else:
        lines.append("- Candidato migliore: non disponibile.")

    if isinstance(energy_summary, dict):
        lines.append(
            f"- Budget energetico rispettato: "
            f"{energy_summary.get('within_budget', 'non determinato')}"
        )
        lines.append(
            f"- Energia residua stimata: "
            f"{energy_summary.get('remaining_after_estimate_wh', 'n/d')} Wh"
        )
    else:
        lines.append("- Budget energetico: valutazione non disponibile.")

    steps = orchestration.get("steps", {})
    for name in ("descent_hazard_detection", "descent_risk_map"):
        result = steps.get(name)
        status = result.get("status", "stato sconosciuto") if isinstance(result, dict) else "non disponibile"
        lines.append(f"- {name}: {status}")

    lines += ["", "## Limiti e avvertenze", ""]
    limitations = report.get("limitations", [])
    lines.extend(f"- {item}" for item in limitations)
    for warning in orchestration.get("warnings", []):
        lines.append(f"- Avviso orchestratore: {warning}")

    # Quadro operativo derivato esclusivamente dai risultati registrati.
    lines += ["", "## Quadro complessivo dello stato della missione", ""]

    orchestration = report.get("orchestration", {})
    steps = orchestration.get("steps", {})
    artifacts = orchestration.get("artifacts", {})
    warnings = orchestration.get("warnings", [])

    status_counts = {}
    for step_name, step_data in steps.items():
        status = (
            step_data.get("status", "unknown")
            if isinstance(step_data, dict)
            else "unknown"
        )
        status_counts[status] = status_counts.get(status, 0) + 1

    lines.append(f"- Stato complessivo: {orchestration.get('status', 'non disponibile')}")
    lines.append(f"- Moduli registrati: {len(steps)}")
    for status, count in sorted(status_counts.items()):
        lines.append(f"- Moduli con stato '{status}': {count}")

    lines += ["", "### Dettaglio dei moduli", ""]
    if steps:
        for step_name, step_data in steps.items():
            if isinstance(step_data, dict):
                status = step_data.get("status", "unknown")
                detail = step_data.get("error") or step_data.get("message")
            else:
                status = "unknown"
                detail = None

            line = f"- **{step_name}**: {status}"
            if detail:
                line += f" — {detail}"
            lines.append(line)
    else:
        lines.append("- Nessun dettaglio dei moduli disponibile.")

    lines += ["", "### Artefatti generati", ""]
    if artifacts:
        for artifact_name, artifact_path in sorted(artifacts.items()):
            lines.append(f"- {artifact_name}: `{artifact_path}`")
    else:
        lines.append("- Nessun artefatto registrato nell'orchestratore.")

    lines += ["", "### Avvisi e limitazioni aperte", ""]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- Nessun avviso registrato dall'orchestratore.")

    lines.append(
        "- I moduli non presenti nel registro non sono considerati completati. "
        "L'assenza di avvisi non costituisce una certificazione di sicurezza."
    )

    # Sintesi degli artefatti tecnici: mostra solo dati realmente disponibili.
    lines += ["", "## Dettaglio delle analisi tecniche", ""]

    technical_artifacts = {
        "Qualità LOLA/LROC": "lola_lroc_quality",
        "Qualità del percorso rover": "route_quality",
        "Rilevamento dei rischi di discesa": "descent_hazard_detection",
        "Mappa dei rischi": "descent_risk_map",
    }

    for label, artifact_key in technical_artifacts.items():
        artifact_path = artifacts.get(artifact_key)
        if not artifact_path:
            lines.append(f"- {label}: artefatto non registrato.")
            continue

        lines.append(f"- **{label}**: `{artifact_path}`")
        try:
            artifact_file = Path(artifact_path)
            if not artifact_file.is_absolute():
                artifact_file = Path.cwd() / artifact_file

            if artifact_file.suffix.lower() != ".json":
                lines.append(
                    "  - Dettagli: consultare il file indicato."
                )
                continue

            payload, read_error = _read_json(artifact_file)
            if read_error or not isinstance(payload, dict):
                lines.append(
                    f"  - Dettagli JSON non disponibili: "
                    f"{read_error or 'formato inatteso'}."
                )
                continue

            for key in (
                "status", "overall_status", "quality_status",
                "distance_m", "max_slope_deg", "valid_fraction",
                "warnings", "limitations",
            ):
                value = payload.get(key)
                if value is not None:
                    lines.append(f"  - {key}: {value}")

            if not any(
                key in payload
                for key in (
                    "status", "overall_status", "quality_status",
                    "distance_m", "max_slope_deg", "valid_fraction",
                    "warnings", "limitations",
                )
            ):
                lines.append(
                    "  - Il file esiste, ma non espone campi sintetici "
                    "riconosciuti da questa sezione."
                )
        except (OSError, ValueError, TypeError) as exc:
            lines.append(
                f"  - Lettura dei dettagli non riuscita: "
                f"{type(exc).__name__}: {exc}"
            )

    lines.append(
        "- La presenza di un artefatto non equivale a una validazione "
        "scientifica o a una certificazione operativa."
    )

    # Quadro decisionale: riepiloga evidenze disponibili e lacune,
    # senza trasformare la presenza di un file in una validazione.
    lines += ["", "## Quadro decisionale della missione", ""]

    orchestration_data = report.get("orchestration", {})
    step_data = orchestration_data.get("steps", {})
    artifact_data = orchestration_data.get("artifacts", {})

    decision_gates = [
        (
            "Selezione del sito",
            "site_selection",
            "site_selection",
        ),
        (
            "Confronto qualitativo LOLA/LROC",
            "lola_lroc_quality",
            "lola_lroc_quality",
        ),
        (
            "Analisi dei rischi di discesa",
            "descent_hazard_detection",
            "descent_hazard_detection",
        ),
        (
            "Mappa dei rischi",
            "descent_risk_map",
            "descent_risk_map",
        ),
        (
            "Pianificazione del rover",
            "rover_path",
            "rover_plan",
        ),
        (
            "Valutazione energetica",
            "rover_energy",
            "rover_energy",
        ),
    ]

    for label, step_name, artifact_name in decision_gates:
        step_info = step_data.get(step_name)
        artifact_path = artifact_data.get(artifact_name)

        if isinstance(step_info, dict):
            step_status = step_info.get("status", "stato non specificato")
        else:
            step_status = "fase non registrata"

        if artifact_path:
            artifact_note = f"; artefatto: `{artifact_path}`"
        else:
            artifact_note = "; artefatto non registrato"

        lines.append(
            f"- **{label}** — {step_status}{artifact_note}"
        )

    lines += ["", "### Criteri per interpretare il risultato", ""]
    lines.extend([
        "- Un modulo riuscito indica che la fase software ha prodotto un risultato; "
        "non dimostra da solo la validità scientifica del risultato.",
        "- Una fase non configurata o non registrata non deve essere interpretata "
        "come superata.",
        "- La selezione topografica non sostituisce le verifiche di georeferenziazione, "
        "illuminazione, comunicazione, dinamica del rover e condizioni operative.",
        "- La stima energetica deve essere interpretata secondo le ipotesi e "
        "le riserve riportate nel relativo artefatto.",
        "- Decisione operativa finale: non determinabile dal solo riepilogo software; "
        "richiede validazione dei dati, dei modelli e dei requisiti della missione.",
    ])

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path

# Last updated: 2026-11-14
import json

from src.mission_report import build_mission_report, write_mission_report


def build_report(tmp_path, **overrides):
    args = {
        "site_name": "Shackleton",
        "planning_date": "2026-10-25",
        "horizon_hours": 48,
        "project_root": tmp_path,
        "journal_enabled": False,
    }
    args.update(overrides)
    return build_mission_report(**args)


def make_event(run_id, event_id="event-1"):
    return {
        "event_id": event_id,
        "node_id": "lunar-planner-local",
        "entity_id": "mission-run:example",
        "event_type": "mission_completed",
        "logical_clock": 1,
        "payload": {"run_id": run_id, "status": "completed"},
        "created_unix": 1792950000.0,
    }


def test_disabled_journal_is_reported_as_disabled(tmp_path):
    report = build_report(
        tmp_path,
        journal_path="reports/events.jsonl",
        journal_enabled=False,
        run_id="run-1",
    )

    journal = report["psystem_journal"]
    assert journal["status"] == "disabled"
    assert journal["path"] is None
    assert journal["event_lines"] == 0
    assert journal["current_run_event_lines"] == 0
    assert journal["remote_node_connected"] is False


def test_missing_enabled_journal_is_reported_as_missing(tmp_path):
    report = build_report(
        tmp_path,
        journal_path="reports/missing.jsonl",
        journal_enabled=True,
    )

    assert report["psystem_journal"]["status"] == "missing"


def test_valid_journal_counts_only_current_run_events(tmp_path):
    path = tmp_path / "events.jsonl"
    events = [
        make_event("run-1", "event-1"),
        make_event("run-2", "event-2"),
        make_event("run-1", "event-3"),
    ]
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    report = build_report(
        tmp_path,
        journal_path=path,
        journal_enabled=True,
        run_id="run-1",
    )

    journal = report["psystem_journal"]
    assert journal["status"] == "available"
    assert journal["event_lines"] == 3
    assert journal["current_run_event_lines"] == 2
    assert journal["read_error"] is None


def test_invalid_journal_event_is_reported(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"event_id":"incomplete"}\n', encoding="utf-8")

    report = build_report(
        tmp_path,
        journal_path=path,
        journal_enabled=True,
    )

    journal = report["psystem_journal"]
    assert journal["status"] == "invalid"
    assert journal["read_error"] is not None
    assert "riga 1" in journal["read_error"]


def test_invalid_json_is_reported(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("{invalid json}\n", encoding="utf-8")

    report = build_report(
        tmp_path,
        journal_path=path,
        journal_enabled=True,
    )

    assert report["psystem_journal"]["status"] == "invalid"


def test_report_writer_includes_journal_status_and_run_count(tmp_path):
    report = build_report(
        tmp_path,
        journal_enabled=False,
        run_id="run-42",
    )
    report["psystem_journal"]["current_run_event_lines"] = 4

    json_path, markdown_path = write_mission_report(
        report,
        output_dir=tmp_path / "output",
    )

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert saved["run_id"] == "run-42"
    assert saved["psystem_journal"]["current_run_event_lines"] == 4
    assert "Eventi dell'esecuzione corrente: 4" in markdown

def test_energy_assessment_is_included_in_report_and_markdown(tmp_path):
    energy_path = tmp_path / "rover_energy_assessment.json"
    energy_path.write_text(
        json.dumps({
            "status": "preliminary_estimate",
            "distance_m": 133.994,
            "inputs": {"reserve_percent": 20.0},
            "energy_wh": {
                "total_estimated": 42.5,
                "usable_battery_after_reserve": 800.0,
                "remaining_after_estimate": 757.5,
                "within_budget": True,
            },
            "warnings": ["Stima preliminare non certificata."],
            "assumptions": ["Potenza ausiliaria costante."],
        }),
        encoding="utf-8",
    )

    report = build_report(
        tmp_path,
        energy_assessment_path=energy_path,
    )

    energy = report["energy_assessment"]
    assert energy["available"] is True
    assert energy["summary"]["total_estimated_wh"] == 42.5
    assert energy["summary"]["usable_battery_after_reserve_wh"] == 800.0
    assert energy["summary"]["remaining_after_estimate_wh"] == 757.5
    assert energy["summary"]["within_budget"] is True

    _, markdown_path = write_mission_report(
        report,
        output_dir=tmp_path / "output",
    )
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Valutazione energetica rover" in markdown
    assert "Consumo stimato totale: 42.5 Wh" in markdown
    assert "Entro il budget energetico: True" in markdown
    assert "Stima preliminare non certificata." in markdown


def test_energy_assessment_missing_file_is_reported(tmp_path):
    report = build_report(
        tmp_path,
        energy_assessment_path=tmp_path / "missing_energy.json",
    )

    energy = report["energy_assessment"]
    assert energy["available"] is False
    assert energy["summary"] is None
    assert energy["read_error"] == "file non presente"

    _, markdown_path = write_mission_report(
        report,
        output_dir=tmp_path / "output",
    )
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Valutazione energetica non disponibile." in markdown
    assert "file non presente" in markdown


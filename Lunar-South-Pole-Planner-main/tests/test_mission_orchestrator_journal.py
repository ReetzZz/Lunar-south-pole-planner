# Last updated: 2026-11-14
import json

from src.mission_orchestrator import run_mission_workflow


def test_orchestrator_records_final_journal_event_and_reports(tmp_path):
    output_dir = tmp_path / "output"
    journal_path = output_dir / "mission_events.jsonl"
    config_path = tmp_path / "mission_config.json"

    config = {
        "output_dir": str(output_dir),
        "journal": {
            "enabled": True,
            "node_id": "test-node",
            "path": str(journal_path),
        },
        "mission_report": {
            "enabled": True,
            "site_name": "Shackleton",
            "planning_date": "2026-10-25",
            "horizon_hours": 48,
        },
    }
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = run_mission_workflow(config_path)

    assert result["status"] == "completed_preliminary"
    assert result["run_id"]
    assert result["artifacts"]["journal"] == str(journal_path)
    assert result["report_path"]

    events = [
        json.loads(line)
        for line in journal_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    final_events = [
        event for event in events
        if event["entity_id"] == f"mission-run:{result['run_id']}"
    ]

    assert len(final_events) == 1
    assert final_events[0]["event_type"] == "mission_completed_preliminary"
    assert final_events[0]["payload"]["run_id"] == result["run_id"]

    main_report = json.loads(
        (output_dir / "mission_report.json").read_text(encoding="utf-8")
    )
    status_report = json.loads(
        (output_dir / "mission_status_report.json").read_text(encoding="utf-8")
    )
    markdown = (
        output_dir / "mission_status_report.md"
    ).read_text(encoding="utf-8")

    assert main_report["run_id"] == result["run_id"]
    assert main_report["final_journal_event"]["event_id"] == final_events[0]["event_id"]
    assert status_report["run_id"] == result["run_id"]
    assert status_report["psystem_journal"]["status"] == "available"
    assert status_report["psystem_journal"]["current_run_event_lines"] == 1
    assert status_report["psystem_journal"]["remote_node_connected"] is False
    assert "Eventi dell'esecuzione corrente: 1" in markdown

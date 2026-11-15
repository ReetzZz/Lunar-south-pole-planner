# Last updated: 2026-11-14
import json
from datetime import datetime, timedelta, timezone

from src.astronomy import Observation
import src.mission_orchestrator as orchestrator


def make_observations(start, elevations, azimuth=180.0):
    rows = []
    for index, elevation in enumerate(elevations):
        timestamp = (start + timedelta(hours=index)).isoformat()
        rows.append(
            Observation(
                time_utc=timestamp,
                azimuth_deg=azimuth,
                elevation_deg=elevation,
                distance_au=1.0,
                range_rate_km_s=0.0,
            )
        )
    return rows


def run_astronomy(tmp_path, monkeypatch, sun_rows, earth_rows, **overrides):
    start = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    rows_by_target = {"10": sun_rows, "399": earth_rows}
    calls = []

    def fake_query(target, latitude, longitude, start_utc, hours=48, step="1h"):
        calls.append(target)
        return rows_by_target[target]

    monkeypatch.setattr(orchestrator, "query_observations", fake_query)

    output_dir = tmp_path / "output"
    config = {
        "output_dir": str(output_dir),
        "astronomy": {
            "enabled": True,
            "site": "Shackleton",
            "start_utc": start.isoformat(),
            "hours": 4,
            "step": "1h",
            **overrides,
        },
    }
    config_path = tmp_path / "mission_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = orchestrator.run_mission_workflow(config_path)
    artifact = output_dir / "astronomy_observations.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    return result, payload, calls


def test_astronomy_workflow_records_simultaneous_windows(
    tmp_path, monkeypatch
):
    start = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    sun = make_observations(start, [-1, 6, 12, 3])
    earth = make_observations(start, [8, 7, 9, 10])

    result, payload, calls = run_astronomy(
        tmp_path, monkeypatch, sun, earth
    )

    summary = payload["operational_windows"]
    assert result["steps"]["astronomy"]["status"] == "success"
    assert calls == ["10", "399"]
    assert summary["status"] == "preliminary"
    assert summary["matched_samples"] == 4
    assert summary["windows"] == [{
        "start_utc": sun[1].time_utc,
        "end_utc": sun[2].time_utc,
        "duration_samples": 2,
        "duration_seconds": 3600.0,
        "duration_minutes": 60.0,
    }]


def test_astronomy_workflow_matches_only_common_timestamps(
    tmp_path, monkeypatch
):
    start = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    sun = make_observations(start, [8, 9, 10])
    earth = [
        sun[0],
        Observation(
            time_utc=(start + timedelta(hours=2)).isoformat(),
            azimuth_deg=180.0,
            elevation_deg=9.0,
            distance_au=1.0,
            range_rate_km_s=0.0,
        ),
    ]

    _, payload, _ = run_astronomy(
        tmp_path, monkeypatch, sun, earth
    )

    summary = payload["operational_windows"]
    assert summary["matched_samples"] == 2
    assert summary["windows"] == [{
        "start_utc": sun[0].time_utc,
        "end_utc": sun[2].time_utc,
        "duration_samples": 2,
        "duration_seconds": 7200.0,
        "duration_minutes": 120.0,
    }]


def test_astronomy_workflow_reports_no_common_timestamps(
    tmp_path, monkeypatch
):
    start = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    sun = make_observations(start, [8, 9])
    earth = make_observations(start + timedelta(hours=5), [8, 9])

    _, payload, _ = run_astronomy(
        tmp_path, monkeypatch, sun, earth
    )

    summary = payload["operational_windows"]
    assert summary["status"] == "unavailable"
    assert summary["windows"] == []
    assert "Nessun timestamp comune" in summary["reason"]


def test_astronomy_window_duration_exposes_missing_time_samples(
    tmp_path, monkeypatch
):
    start = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    sun = [
        make_observations(start, [8])[0],
        make_observations(start + timedelta(hours=2), [9])[0],
    ]
    earth = [
        make_observations(start, [8])[0],
        make_observations(start + timedelta(hours=2), [9])[0],
    ]

    _, payload, _ = run_astronomy(tmp_path, monkeypatch, sun, earth)

    window = payload["operational_windows"]["windows"][0]
    assert window["duration_samples"] == 2
    assert window["duration_seconds"] == 7200.0
    assert window["duration_minutes"] == 120.0


def test_astronomy_reports_temporal_gap_warning(
    tmp_path, monkeypatch
):
    start = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    sun = [
        make_observations(start, [8])[0],
        make_observations(start + timedelta(hours=2), [9])[0],
    ]
    earth = [
        make_observations(start, [8])[0],
        make_observations(start + timedelta(hours=2), [9])[0],
    ]

    _, payload, _ = run_astronomy(
        tmp_path, monkeypatch, sun, earth
    )

    summary = payload["operational_windows"]
    diagnostics = summary["temporal_diagnostics"]

    assert diagnostics["continuity_verified"] is False
    assert diagnostics["gap_count"] >= 1
    assert diagnostics["warnings"]

# Last updated: 2026-11-14
import json

import pytest

from src.psystem_adapter import MissionEvent, MissionJournal


def test_append_and_read_event(tmp_path):
    path = tmp_path / "mission_events.jsonl"
    journal = MissionJournal(path, "node-a")

    event = journal.append(
        entity_id="mission-step:astronomy",
        event_type="step_success",
        payload={"run_id": "run-1", "status": "success"},
    )

    events = journal.read_events()

    assert len(events) == 1
    assert events[0] == event
    assert events[0].logical_clock == 1
    assert events[0].node_id == "node-a"
    assert json.loads(path.read_text(encoding="utf-8"))["event_id"] == event.event_id


def test_logical_clock_continues_after_reopening(tmp_path):
    path = tmp_path / "mission_events.jsonl"

    first = MissionJournal(path, "node-a")
    event1 = first.append("mission-run:1", "mission_running", {})

    second = MissionJournal(path, "node-a")
    event2 = second.append("mission-run:1", "mission_completed", {})

    assert event2.logical_clock == event1.logical_clock + 1


@pytest.mark.parametrize(
    ("entity_id", "event_type", "payload"),
    [
        ("", "step_success", {}),
        ("mission-step:1", "", {}),
        ("mission-step:1", "step_success", []),
    ],
)
def test_append_rejects_invalid_arguments(tmp_path, entity_id, event_type, payload):
    journal = MissionJournal(tmp_path / "events.jsonl", "node-a")

    with pytest.raises(ValueError):
        journal.append(entity_id, event_type, payload)


def test_empty_node_id_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="node_id obbligatorio"):
        MissionJournal(tmp_path / "events.jsonl", " ")


def test_invalid_json_line_is_reported(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"event_id":\n', encoding="utf-8")

    with pytest.raises(ValueError, match="riga 1"):
        MissionJournal(path, "node-a")


def test_reconcile_deduplicates_and_sorts_events():
    event1 = MissionEvent(
        event_id="event-1",
        node_id="node-a",
        entity_id="mission-step:1",
        event_type="step_running",
        logical_clock=1,
        payload={"status": "running"},
        created_unix=1.0,
    )
    event2 = MissionEvent(
        event_id="event-2",
        node_id="node-a",
        entity_id="mission-step:1",
        event_type="step_success",
        logical_clock=2,
        payload={"status": "success"},
        created_unix=2.0,
    )

    result = MissionJournal.reconcile([[event2, event1], [event1]])

    assert [event["event_id"] for event in result["events"]] == [
        "event-1",
        "event-2",
    ]
    assert result["latest_by_entity"]["mission-step:1"]["event_id"] == "event-2"
    assert result["conflicts"] == []
    assert result["connected_to_remote_psystem"] is False


def test_reconcile_flags_same_clock_payload_conflict():
    event1 = MissionEvent(
        event_id="event-a",
        node_id="node-a",
        entity_id="mission-run:1",
        event_type="mission_completed",
        logical_clock=3,
        payload={"status": "completed"},
        created_unix=1.0,
    )
    event2 = MissionEvent(
        event_id="event-b",
        node_id="node-b",
        entity_id="mission-run:1",
        event_type="mission_failed",
        logical_clock=3,
        payload={"status": "failed"},
        created_unix=2.0,
    )

    result = MissionJournal.reconcile([[event1], [event2]])

    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["entity_id"] == "mission-run:1"
    assert result["conflicts"][0]["status"] == "manual_resolution_required"

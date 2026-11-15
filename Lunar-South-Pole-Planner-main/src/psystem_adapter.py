# Last updated: 2026-11-14
"""Adattatore dimostrativo P-System: journal locale e riconciliazione deterministica.

Non apre connessioni con P-System e non pretende compatibilità con un protocollo
remoto. Gli eventi sono identificati da event_id e versione logica.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, time, uuid

@dataclass(frozen=True)
class MissionEvent:
    event_id: str
    node_id: str
    entity_id: str
    event_type: str
    logical_clock: int
    payload: dict
    created_unix: float
    def to_dict(self): return asdict(self)

class MissionJournal:
    def __init__(self, path: str | Path, node_id: str):
        if not node_id.strip(): raise ValueError("node_id obbligatorio")
        self.path, self.node_id = Path(path), node_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = 0
        for e in self.read_events(): self.clock=max(self.clock,e.logical_clock)

    def read_events(self):
        if not self.path.exists(): return []
        events=[]
        for number,line in enumerate(self.path.read_text(encoding="utf-8").splitlines(),1):
            if not line.strip(): continue
            try: events.append(MissionEvent(**json.loads(line)))
            except (ValueError, TypeError, KeyError) as exc: raise ValueError(f"Evento journal non valido alla riga {number}: {exc}") from exc
        return events

    def append(self, entity_id: str, event_type: str, payload: dict) -> MissionEvent:
        if not entity_id.strip() or not event_type.strip(): raise ValueError("entity_id ed event_type obbligatori")
        if not isinstance(payload,dict): raise ValueError("payload deve essere un oggetto")
        self.clock += 1
        event=MissionEvent(str(uuid.uuid4()),self.node_id,entity_id,event_type,self.clock,payload,time.time())
        with self.path.open("a",encoding="utf-8") as f: f.write(json.dumps(event.to_dict(),sort_keys=True,ensure_ascii=False)+"\n")
        return event

    @staticmethod
    def reconcile(event_lists):
        """Deduplica per event_id e ordina in modo ripetibile; non fonde conflitti."""
        unique={}
        for events in event_lists:
            for e in events:
                item=e if isinstance(e,MissionEvent) else MissionEvent(**e)
                unique.setdefault(item.event_id,item)
        ordered=sorted(unique.values(),key=lambda e:(e.logical_clock,e.node_id,e.event_id))
        latest={}
        conflicts=[]
        for e in ordered:
            prior=latest.get(e.entity_id)
            if prior and prior.logical_clock == e.logical_clock and prior.payload != e.payload:
                conflicts.append({"entity_id":e.entity_id,"event_ids":[prior.event_id,e.event_id],"status":"manual_resolution_required"})
            if prior is None or (e.logical_clock,e.node_id,e.event_id) > (prior.logical_clock,prior.node_id,prior.event_id): latest[e.entity_id]=e
        return {"events": [e.to_dict() for e in ordered], "latest_by_entity": {k:v.to_dict() for k,v in latest.items()}, "conflicts": conflicts, "connected_to_remote_psystem": False, "warning": "Prototipo locale; nessuna integrazione con un nodo P-System remoto."}

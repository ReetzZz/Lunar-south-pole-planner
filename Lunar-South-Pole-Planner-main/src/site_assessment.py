# Last updated: 2026-11-14
"""Assessment integrata di un candidato su griglia DEM e osservazioni Horizons.

Il candidato è identificato da indici riga/colonna del raster. Non viene assunto
che tali indici corrispondano al sito geografico nominale, finché il frame lunare
non sia validato indipendentemente.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import math

from src.mission_planning import SiteMetrics, SiteWeights, score_site
from src.terrain_metrics import analyze_local_terrain
from src.confidence_validation import validate_confidence_raster


@dataclass(frozen=True)
class CandidateAssessment:
    schema: str
    generated_utc: str
    candidate_name: str
    dem_path: str
    grid_row: int
    grid_col: int
    terrain_metrics: dict
    astronomy_metrics: dict
    confidence_metrics: dict | None
    score: dict
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def assess_candidate(
    *, candidate_name: str, dem_path: str | Path, row: int, col: int,
    radius_pixels: int, sun_elevations_deg: list[float],
    earth_elevations_deg: list[float], weights: SiteWeights = SiteWeights(),
    confidence_path: str | Path | None = None,
) -> CandidateAssessment:
    """Create a transparent score using only supplied/derived measurements.

    Astronomical fractions are geometric sample fractions (elevation > 0°), not
    terrain-shadow-corrected illumination or a radio link budget. Terrain uses
    P95 local slope and plane-residual roughness from the selected DEM window.
    Data confidence is intentionally missing until a defensible quality model is
    provided; it is not fabricated from valid-pixel fraction.
    """
    if len(sun_elevations_deg) != len(earth_elevations_deg):
        raise ValueError("Le serie di elevazione Sole/Terra devono avere la stessa lunghezza.")
    if not sun_elevations_deg:
        raise ValueError("Servono osservazioni Horizons già caricate per il sito selezionato.")
    for label, values in (("Sole", sun_elevations_deg), ("Terra", earth_elevations_deg)):
        if any(not math.isfinite(float(v)) for v in values):
            raise ValueError(f"La serie {label} contiene valori non finiti.")

    terrain = analyze_local_terrain(dem_path, row, col, radius_pixels)
    confidence = (validate_confidence_raster(confidence_path).to_dict()
                  if confidence_path is not None else None)
    sun_fraction = sum(float(v) > 0.0 for v in sun_elevations_deg) / len(sun_elevations_deg)
    earth_fraction = sum(float(v) > 0.0 for v in earth_elevations_deg) / len(earth_elevations_deg)
    metrics = SiteMetrics(
        name=candidate_name,
        illumination_fraction=sun_fraction,
        earth_visibility_fraction=earth_fraction,
        slope_deg=terrain.slope_p95_deg,
        roughness_m=terrain.roughness_plane_residual_std_m,
        data_confidence=None,
        notes=("Illuminazione e visibilità sono frazioni geometriche campionate da Horizons; "
               "non includono ombre DEM, potenza solare o link budget RF."),
    )
    score = score_site(metrics, weights)
    warnings = [
        "La posizione DEM è specificata in riga/colonna; il collegamento al sito geografico nominale non è validato.",
        "La frazione di elevazione solare positiva non equivale a illuminazione diretta dopo gli ostacoli topografici.",
        "La visibilità geometrica della Terra non equivale a disponibilità del collegamento radio.",
        "La confidenza LROC è riepilogata separatamente e resta esclusa dal punteggio.",
        "Il riepilogo della confidenza è globale: non certifica la cella del candidato.",
        "La georeferenziazione fisica e la co-registrazione LOLA-LROC non sono validate.",
    ]
    if terrain.valid_fraction < 0.95:
        warnings.append("Copertura valida della finestra DEM inferiore al 95%; interpretare le metriche con cautela.")
    return CandidateAssessment(
        schema="lunar-candidate-assessment/1.0",
        generated_utc=datetime.now(timezone.utc).isoformat(),
        candidate_name=candidate_name,
        dem_path=str(dem_path), grid_row=int(row), grid_col=int(col),
        terrain_metrics=terrain.to_dict(),
        astronomy_metrics={
            "source": "Horizons observations already loaded in application",
            "sample_count": len(sun_elevations_deg),
            "sun_elevation_positive_fraction": sun_fraction,
            "earth_elevation_positive_fraction": earth_fraction,
        },
        confidence_metrics=confidence,
        score=score.to_dict(), warnings=tuple(warnings),
    )


def write_assessment(assessment: CandidateAssessment, path: str | Path = "reports/site_assessment.json") -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(assessment.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out

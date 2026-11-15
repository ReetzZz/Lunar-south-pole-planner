# Last updated: 2026-11-14
"""Stima diagnostica dell'illuminazione diretta usando un profilo d'orizzonte DEM.

L'azimut di Horizons deve essere trasformato nel sistema di azimut della griglia
con un offset esplicito e validato dall'utente. Il modulo non deduce tale offset.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np


def estimate_direct_solar_visibility(
    horizon_json: str | Path,
    solar_observations: list[dict],
    *,
    grid_azimuth_offset_deg: float,
    output_path: str | Path = "reports/solar_illumination_diagnostic.json",
) -> Path:
    """Compare solar elevation to DEM horizon after explicit azimuth rotation.

    Convention: grid_azimuth = (Horizons azimuth + offset) % 360.
    solar_observations items require time_utc, azimuth_deg, elevation_deg.
    """
    src=Path(horizon_json)
    if not src.is_file():
        raise FileNotFoundError(f"Profilo orizzonte non trovato: {src}")
    profile=json.loads(src.read_text(encoding="utf-8"))
    samples=profile.get("samples", [])
    az=[]; elev=[]
    for s in samples:
        a=s.get("grid_azimuth_deg")
        h=s.get("horizon_elevation_deg")
        if a is not None and h is not None and np.isfinite(a) and np.isfinite(h):
            az.append(float(a)%360); elev.append(float(h))
    if len(az)<3:
        raise ValueError("Il profilo orizzonte non contiene campioni validi sufficienti.")
    order=np.argsort(az)
    az=np.asarray(az)[order]; elev=np.asarray(elev)[order]
    if not np.isfinite(grid_azimuth_offset_deg):
        raise ValueError("Offset azimutale non valido.")
    rows=[]
    for obs in solar_observations:
        try:
            h_az=float(obs["azimuth_deg"])%360
            sun_el=float(obs["elevation_deg"])
            time=str(obs["time_utc"])
        except (KeyError, TypeError, ValueError):
            continue
        grid_az=(h_az+float(grid_azimuth_offset_deg))%360
        # Interpolazione circolare aggiungendo un campione ai due lati.
        az_ext=np.concatenate(([az[-1]-360],az,[az[0]+360]))
        el_ext=np.concatenate(([elev[-1]],elev,[elev[0]]))
        horizon=float(np.interp(grid_az,az_ext,el_ext))
        rows.append({
            "time_utc":time,"horizons_azimuth_deg":h_az,
            "grid_azimuth_deg":grid_az,"solar_elevation_deg":sun_el,
            "terrain_horizon_elevation_deg":horizon,
            "estimated_direct_sun_visible":bool(sun_el>horizon),
            "clearance_deg":sun_el-horizon,
        })
    result={
        "schema":"lunar-solar-illumination-diagnostic/1.0",
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "horizon_profile":str(src),
        "azimuth_mapping":{"convention":"grid_azimuth=(Horizons azimuth + offset) mod 360",
                            "offset_deg":float(grid_azimuth_offset_deg),
                            "independently_validated":False},
        "observation_count":len(rows),
        "estimated_sun_visible_count":sum(r["estimated_direct_sun_visible"] for r in rows),
        "observations":rows,
        "warnings":[
            "Risultato diagnostico: l'offset azimutale deve essere validato indipendentemente.",
            "Il riferimento geodetico del sito e l'orientamento del raster non sono certificati.",
            "Il modello considera solo il profilo d'orizzonte DEM e l'elevazione solare; non modella ombre penumbrali, rilievo oltre la distanza campionata, occultazioni locali sub-pixel, efficienza dei pannelli o energia disponibile.",
            "La visibilità geometrica diretta del Sole non equivale a una stima energetica della missione."
        ]
    }
    dst=Path(output_path); dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return dst

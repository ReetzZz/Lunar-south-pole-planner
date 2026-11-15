# Last updated: 2026-11-14
"""Confronto preliminare tra osservazioni astronomiche e orizzonte LOLA.

Questo modulo non calcola effemeridi e non valida la georeferenziazione.
Le classificazioni basate su profili non validati sono sempre diagnostiche.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class VisibilityResult:
    status: str
    object_azimuth_deg: float
    object_elevation_deg: float
    terrain_elevation_deg: float | None
    clearance_deg: float | None
    georeference_validated: bool
    message: str


def compare_with_horizon(
    azimuth_deg: float,
    elevation_deg: float,
    horizon_azimuth_deg,
    horizon_elevation_deg,
    *,
    georeference_validated: bool = False,
    tolerance_deg: float = 0.05,
) -> VisibilityResult:
    """Confronta una direzione astronomica con il profilo locale.

    L'azimut è in gradi, in senso orario dal nord.
    L'elevazione è in gradi rispetto all'orizzonte geometrico.

    Gli stati possibili sono:
      visible / blocked: classificazione su georeferenziazione validata;
      preliminary_visible / preliminary_blocked: risultato diagnostico;
      indeterminate: input non utilizzabili o margine entro la tolleranza.
    """
    def indeterminate(message: str) -> VisibilityResult:
        return VisibilityResult(
            "indeterminate",
            float(azimuth_deg) if math.isfinite(azimuth_deg) else math.nan,
            float(elevation_deg) if math.isfinite(elevation_deg) else math.nan,
            None, None, georeference_validated, message,
        )

    if not math.isfinite(azimuth_deg) or not math.isfinite(elevation_deg):
        return indeterminate("Azimut o elevazione dell'oggetto non validi.")

    if not -90.0 <= elevation_deg <= 90.0:
        return indeterminate("Elevazione dell'oggetto fuori intervallo.")

    if not math.isfinite(tolerance_deg) or tolerance_deg < 0:
        raise ValueError("tolerance_deg deve essere finita e non negativa")

    az = np.asarray(horizon_azimuth_deg, dtype=float)
    el = np.asarray(horizon_elevation_deg, dtype=float)

    if az.ndim != 1 or el.ndim != 1 or az.size != el.size or az.size < 2:
        return indeterminate("Profilo dell'orizzonte mancante o non valido.")

    valid = np.isfinite(az) & np.isfinite(el)
    az, el = az[valid], el[valid]

    if az.size < 2 or np.any((el < -90.0) | (el > 90.0)):
        return indeterminate("Campioni validi insufficienti nel profilo.")

    # Ordina e normalizza gli azimut; per valori duplicati conserva il massimo
    # ostacolo angolare, scelta conservativa per un controllo preliminare.
    az = np.mod(az, 360.0)
    order = np.argsort(az)
    az, el = az[order], el[order]
    unique_az = np.unique(az)
    unique_el = np.array([np.max(el[az == a]) for a in unique_az])

    if unique_az.size < 2:
        return indeterminate("Il profilo non contiene azimut distinti.")

    target = float(azimuth_deg % 360.0)

    # Interpolazione circolare solo entro il passo massimo osservato.
    # Non si colmano automaticamente grandi lacune nel profilo.
    gaps = np.diff(np.r_[unique_az, unique_az[0] + 360.0])
    max_gap = float(np.max(gaps))
    right = int(np.searchsorted(unique_az, target, side="right"))
    left_i = (right - 1) % unique_az.size
    right_i = right % unique_az.size

    left_az = float(unique_az[left_i])
    right_az = float(unique_az[right_i])
    if right_i == 0:
        right_az += 360.0
    query_az = target
    if query_az < left_az:
        query_az += 360.0

    gap = right_az - left_az
    if gap <= 0 or gap > max_gap + 1e-9:
        return indeterminate("Impossibile interpolare il profilo in questo azimut.")

    # Se il campionamento è troppo rado rispetto alla sua stessa distribuzione,
    # non si pretende di ricostruire ostacoli stretti non campionati.
    if gap > 10.0:
        return indeterminate(
            f"Campionamento angolare insufficiente: intervallo di {gap:.2f}°."
        )

    fraction = (query_az - left_az) / gap
    terrain = float(
        unique_el[left_i] + fraction * (unique_el[right_i] - unique_el[left_i])
    )
    clearance = float(elevation_deg - terrain)

    if abs(clearance) <= tolerance_deg:
        return VisibilityResult(
            "indeterminate", target, float(elevation_deg), terrain, clearance,
            georeference_validated,
            "Oggetto vicino al profilo del terreno: esito incerto entro la tolleranza.",
        )

    visible = clearance > 0
    if georeference_validated:
        status = "visible" if visible else "blocked"
        prefix = "Classificazione basata sul profilo dichiarato validato."
    else:
        status = "preliminary_visible" if visible else "preliminary_blocked"
        prefix = "Classificazione soltanto diagnostica: georeferenziazione non validata."

    return VisibilityResult(
        status, target, float(elevation_deg), terrain, clearance,
        georeference_validated,
        f"{prefix} Margine rispetto al terreno: {clearance:.3f}°.",
    )

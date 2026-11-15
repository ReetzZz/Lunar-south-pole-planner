# Last updated: 2026-11-14
"""Scoring trasparente dei siti e finestre operative basate su input espliciti."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math

@dataclass(frozen=True)
class SiteMetrics:
    name: str
    illumination_fraction: float | None = None
    earth_visibility_fraction: float | None = None
    slope_deg: float | None = None
    roughness_m: float | None = None
    data_confidence: float | None = None
    notes: str = ""

@dataclass(frozen=True)
class SiteWeights:
    illumination: float = 0.30
    communications: float = 0.25
    slope: float = 0.15
    roughness: float = 0.10
    confidence: float = 0.20

@dataclass(frozen=True)
class SiteScore:
    name: str
    score_0_100: float | None
    coverage_fraction: float
    components_0_100: dict
    missing_metrics: tuple[str, ...]
    notes: str
    def to_dict(self): return asdict(self)


def score_site(metrics: SiteMetrics, weights: SiteWeights = SiteWeights(), max_slope_deg: float = 15.0, max_roughness_m: float = 5.0) -> SiteScore:
    """Scores only measured/supplied metrics; missing values are not fabricated."""
    pairs = {
        "illumination": (metrics.illumination_fraction, weights.illumination),
        "communications": (metrics.earth_visibility_fraction, weights.communications),
        "slope": (None if metrics.slope_deg is None else 1.0 - min(max(metrics.slope_deg, 0.0) / max_slope_deg, 1.0), weights.slope),
        "roughness": (None if metrics.roughness_m is None else 1.0 - min(max(metrics.roughness_m, 0.0) / max_roughness_m, 1.0), weights.roughness),
        "confidence": (metrics.data_confidence, weights.confidence),
    }
    if max_slope_deg <= 0 or max_roughness_m <= 0:
        raise ValueError("Soglie di pendenza e rugosità devono essere positive.")
    if any(not math.isfinite(w) or w < 0 for _, w in pairs.values()) or sum(w for _, w in pairs.values()) <= 0:
        raise ValueError("I pesi devono essere finiti, non negativi e con somma positiva.")
    components, missing, numerator, denominator = {}, [], 0.0, 0.0
    for name, (value, weight) in pairs.items():
        if value is None:
            missing.append(name); continue
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"La metrica {name} deve essere compresa tra 0 e 1.")
        components[name] = round(value * 100, 2)
        numerator += value * weight; denominator += weight
    score = round(100 * numerator / denominator, 2) if denominator else None
    return SiteScore(metrics.name, score, denominator / sum(w for _, w in pairs.values()), components, tuple(missing), metrics.notes)

@dataclass(frozen=True)
class OperationalWindow:
    start_index: int
    end_index: int
    duration_samples: int


def find_operational_windows(sun_elevation_deg, earth_elevation_deg, *, min_sun_elevation_deg=5.0, min_earth_elevation_deg=5.0) -> list[OperationalWindow]:
    """Contiguous sample windows meeting both geometric elevation thresholds.

    Inputs must be equally sampled; returned indices refer to caller's time array.
    This is geometry only, not a power or RF-link budget.
    """
    sun, earth = list(sun_elevation_deg), list(earth_elevation_deg)
    if len(sun) != len(earth): raise ValueError("Le serie devono avere la stessa lunghezza.")
    good = [a is not None and b is not None and math.isfinite(a) and math.isfinite(b) and a >= min_sun_elevation_deg and b >= min_earth_elevation_deg for a,b in zip(sun,earth)]
    out, start = [], None
    for i, ok in enumerate(good + [False]):
        if ok and start is None: start = i
        elif not ok and start is not None:
            out.append(OperationalWindow(start, i - 1, i - start)); start = None
    return out

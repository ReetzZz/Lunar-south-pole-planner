# Last updated: 2026-11-14
"""Analisi locale preliminare di un sito lunare.

I risultati sono diagnostici: non certificano il frame lunare,
la georeferenziazione o l'illuminazione astronomica.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np
import rasterio

from src.terrain_horizon import HorizonProfile, calculate_horizon


@dataclass(frozen=True)
class LocalSiteReport:
    site_name: str
    dem_path: str
    observer_x_m: float
    observer_y_m: float
    elevation_m: float
    horizon: HorizonProfile
    valid_azimuth_fraction: float
    mean_horizon_deg: float | None
    max_horizon_deg: float | None
    mean_zero_density_fraction: float | None
    mean_dem_error_m: float | None
    georeference_validated: bool
    warnings: tuple[str, ...]


def _aligned(reference_path: Path, auxiliary_path: Path) -> bool:
    """Controlla dimensioni, CRS e trasformazione del raster ausiliario."""
    with rasterio.open(reference_path) as ref, rasterio.open(auxiliary_path) as aux:
        return (
            ref.width == aux.width
            and ref.height == aux.height
            and ref.crs == aux.crs
            and ref.transform == aux.transform
        )


def analyze_local_site(
    site_name: str,
    dem_path: str | Path,
    observer_x_m: float,
    observer_y_m: float,
    *,
    density_path: str | Path | None = None,
    error_path: str | Path | None = None,
    azimuth_step_deg: float = 2.0,
    max_distance_m: float = 7000.0,
    observer_height_m: float = 0.0,
) -> LocalSiteReport:
    """Calcola un profilo locale e un rapporto con avvertenze esplicite."""
    dem = Path(dem_path)
    if not dem.is_file():
        raise FileNotFoundError(f"DEM non trovato: {dem}")

    for name, value in (
        ("observer_x_m", observer_x_m),
        ("observer_y_m", observer_y_m),
        ("observer_height_m", observer_height_m),
    ):
        if not math.isfinite(value):
            raise ValueError(f"{name} deve essere finito")

    warnings = [
        "Analisi diagnostica: georeferenziazione lunare non validata.",
        "Il campionamento del profilo può non rilevare ostacoli più stretti del passo.",
        "L'orizzonte geometrico non include rifrazione, libratione o occultazioni astronomiche.",
    ]

    checked_aux: dict[str, str | None] = {
        "density": str(density_path) if density_path else None,
        "error": str(error_path) if error_path else None,
    }

    for label, value in checked_aux.items():
        if value is None:
            continue
        aux = Path(value)
        if not aux.is_file():
            warnings.append(f"Raster {label} non trovato; metrica non disponibile.")
            checked_aux[label] = None
        elif not _aligned(dem, aux):
            raise ValueError(
                f"Raster {label} non allineato: CRS, trasformazione e dimensioni "
                "devono coincidere con il DEM."
            )

    horizon = calculate_horizon(
        dem,
        observer_x_m,
        observer_y_m,
        density_path=checked_aux["density"],
        error_path=checked_aux["error"],
        azimuth_step_deg=azimuth_step_deg,
        max_distance_m=max_distance_m,
        observer_height_m=observer_height_m,
    )

    valid = np.isfinite(horizon.elevation_deg)
    fraction = float(np.mean(valid)) if valid.size else 0.0

    mean_horizon = (
        float(np.mean(horizon.elevation_deg[valid])) if np.any(valid) else None
    )
    max_horizon = (
        float(np.max(horizon.elevation_deg[valid])) if np.any(valid) else None
    )

    zero_density = horizon.zero_density_fraction
    zero_valid = np.isfinite(zero_density)
    mean_zero_density = (
        float(np.mean(zero_density[zero_valid]))
        if np.any(zero_valid) else None
    )

    errors = horizon.mean_dem_error_m
    error_valid = np.isfinite(errors)
    mean_error = float(np.mean(errors[error_valid])) if np.any(error_valid) else None

    if fraction < 1.0:
        warnings.append("Uno o più azimut non hanno campioni validi.")

    return LocalSiteReport(
        site_name=site_name,
        dem_path=str(dem),
        observer_x_m=float(observer_x_m),
        observer_y_m=float(observer_y_m),
        elevation_m=float(horizon.observer_elevation_m),
        horizon=horizon,
        valid_azimuth_fraction=fraction,
        mean_horizon_deg=mean_horizon,
        max_horizon_deg=max_horizon,
        mean_zero_density_fraction=mean_zero_density,
        mean_dem_error_m=mean_error,
        georeference_validated=False,
        warnings=tuple(warnings),
    )

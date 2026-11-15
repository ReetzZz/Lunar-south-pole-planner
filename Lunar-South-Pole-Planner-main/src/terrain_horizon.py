# Last updated: 2026-11-14
"""Profilo preliminare dell'orizzonte da raster LOLA.

Il risultato resta diagnostico finché la posizione dell'osservatore,
la proiezione e la geometria lunare non sono validate.
"""

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np
import rasterio


@dataclass
class HorizonProfile:
    azimuth_deg: np.ndarray
    elevation_deg: np.ndarray
    max_distance_m: np.ndarray
    valid_samples: np.ndarray
    zero_density_fraction: np.ndarray
    mean_dem_error_m: np.ndarray
    observer_elevation_m: float
    observer_row: int
    observer_col: int
    georeference_validated: bool = False


def calculate_horizon(
    dem_path,
    observer_x,
    observer_y,
    density_path=None,
    error_path=None,
    azimuth_step_deg=2.0,
    max_distance_m=7000.0,
    observer_height_m=0.0,
):
    if not 0 < azimuth_step_deg <= 45:
        raise ValueError("azimuth_step_deg deve essere tra 0 e 45")
    if max_distance_m <= 0:
        raise ValueError("max_distance_m deve essere positivo")

    with rasterio.open(dem_path) as ds:
        dem = ds.read(1, masked=True).filled(np.nan).astype(np.float32)
        transform = ds.transform
        row, col = ds.index(observer_x, observer_y)

        if not (0 <= row < ds.height and 0 <= col < ds.width):
            raise ValueError("Punto osservatore fuori dal raster")

        z0 = float(dem[row, col])
        if not math.isfinite(z0):
            raise ValueError("Quota osservatore non valida")

        pixel_size = min(abs(transform.a), abs(transform.e))
        if pixel_size <= 0:
            raise ValueError("Risoluzione raster non valida")

        height, width = dem.shape

    density = None
    error = None

    if density_path and Path(density_path).is_file():
        with rasterio.open(density_path) as ds:
            density = ds.read(1, masked=True).filled(np.nan).astype(np.float32)

    if error_path and Path(error_path).is_file():
        with rasterio.open(error_path) as ds:
            error = ds.read(1, masked=True).filled(np.nan).astype(np.float32)

    for name, arr in (("densità", density), ("errore", error)):
        if arr is not None and arr.shape != dem.shape:
            raise ValueError(f"Raster {name} non allineato al DEM")

    observer_z = z0 + observer_height_m
    azimuths = np.arange(0.0, 360.0, azimuth_step_deg)

    elevations = np.full(azimuths.shape, np.nan)
    max_distances = np.zeros(azimuths.shape)
    valid_counts = np.zeros(azimuths.shape, dtype=int)
    zero_density = np.full(azimuths.shape, np.nan)
    mean_errors = np.full(azimuths.shape, np.nan)

    # Il campionamento avviene in memoria: nessuna lettura raster nel ciclo.
    distances = np.arange(
        pixel_size, max_distance_m + pixel_size, pixel_size
    )

    for i, azimuth in enumerate(azimuths):
        rad = math.radians(float(azimuth))
        dx, dy = math.sin(rad), math.cos(rad)

        best_angle = -90.0
        best_distance = 0.0
        valid = 0
        zero_count = 0
        errors = []

        for distance in distances:
            x = observer_x + dx * distance
            y = observer_y + dy * distance
            rr, cc = rasterio.transform.rowcol(transform, x, y)

            if not (0 <= rr < height and 0 <= cc < width):
                break

            z = float(dem[rr, cc])
            if not math.isfinite(z):
                continue

            angle = math.degrees(
                math.atan2(z - observer_z, float(distance))
            )
            if angle > best_angle:
                best_angle = angle
                best_distance = float(distance)

            valid += 1

            if density is not None:
                d = float(density[rr, cc])
                if not math.isfinite(d) or d <= 0:
                    zero_count += 1

            if error is not None:
                e = float(error[rr, cc])
                if math.isfinite(e):
                    errors.append(e)

        if valid:
            elevations[i] = best_angle
            max_distances[i] = best_distance
            valid_counts[i] = valid

            if density is not None:
                zero_density[i] = zero_count / valid
            if errors:
                mean_errors[i] = float(np.mean(errors))

    return HorizonProfile(
        azimuth_deg=azimuths,
        elevation_deg=elevations,
        max_distance_m=max_distances,
        valid_samples=valid_counts,
        zero_density_fraction=zero_density,
        mean_dem_error_m=mean_errors,
        observer_elevation_m=observer_z,
        observer_row=row,
        observer_col=col,
    )

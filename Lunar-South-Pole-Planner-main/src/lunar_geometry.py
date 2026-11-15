# Last updated: 2026-11-14
"""Geometria cartografica lunare: trasformazioni diagnostiche.

ATTENZIONE:
- La trasformazione matematica non convalida il datum o il frame lunare.
- La longitudine di ingresso deve essere esplicitamente est positiva.
- georeference_validated rimane False finché non esiste una verifica esterna.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import rasterio
from pyproj import CRS, Transformer


MOON_RADIUS_M = 1_737_400.0

# Ipotesi di lavoro: longitudine est positiva e sfera lunare.
# La compatibilità con MOON_ME / DE421 deve ancora essere verificata.
MOON_GEOGRAPHIC_CRS = CRS.from_proj4(
    f"+proj=longlat +R={MOON_RADIUS_M} +no_defs +type=crs"
)


@dataclass(frozen=True)
class ObserverLocation:
    longitude_east_deg: float
    latitude_deg: float
    x_m: float
    y_m: float
    row: int
    col: int
    inside_raster: bool
    georeference_validated: bool
    status: str
    message: str


def geographic_to_projected(
    longitude_east_deg: float,
    latitude_deg: float,
    target_crs,
) -> tuple[float, float]:
    """Trasforma lon/lat lunari in coordinate del CRS indicato.

    La longitudine deve essere est positiva. Il risultato non certifica
    che il CRS di destinazione condivida il frame fisico delle coordinate.
    """
    if not math.isfinite(longitude_east_deg):
        raise ValueError("La longitudine deve essere finita.")
    if not math.isfinite(latitude_deg) or not -90 <= latitude_deg <= 90:
        raise ValueError("La latitudine deve essere finita e compresa tra -90 e 90.")
    if not -360 <= longitude_east_deg <= 360:
        raise ValueError("La longitudine deve essere compresa tra -360 e 360.")

    target = CRS.from_user_input(target_crs)
    transformer = Transformer.from_crs(
        MOON_GEOGRAPHIC_CRS, target, always_xy=True
    )
    x, y = transformer.transform(longitude_east_deg, latitude_deg)

    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("La trasformazione ha prodotto coordinate non finite.")

    return float(x), float(y)


def locate_observer(
    dem_path: str | Path,
    longitude_east_deg: float,
    latitude_deg: float,
) -> ObserverLocation:
    """Localizza un candidato nel raster senza dichiararlo validato."""
    path = Path(dem_path)
    if not path.is_file():
        raise FileNotFoundError(f"DEM non trovato: {path}")

    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise ValueError("Il DEM non dichiara un CRS.")

        x, y = geographic_to_projected(
            longitude_east_deg, latitude_deg, ds.crs
        )

        row, col = ds.index(x, y)
        inside = 0 <= row < ds.height and 0 <= col < ds.width

        status = "candidate_inside" if inside else "outside_raster"
        message = (
            "Punto candidato dentro i limiti raster; frame e posizione "
            "geografica non ancora convalidati."
            if inside else
            "Il punto candidato è fuori dal raster secondo la trasformazione "
            "ipotizzata; verificare convenzione della longitudine e frame."
        )

        return ObserverLocation(
            longitude_east_deg=float(longitude_east_deg),
            latitude_deg=float(latitude_deg),
            x_m=x,
            y_m=y,
            row=int(row),
            col=int(col),
            inside_raster=inside,
            georeference_validated=False,
            status=status,
            message=message,
        )


def sample_elevation(
    dem_path: str | Path,
    location: ObserverLocation,
) -> float | None:
    """Legge la quota del pixel candidato; restituisce None se non valida."""
    if not location.inside_raster:
        return None

    with rasterio.open(dem_path) as ds:
        value = next(ds.sample([(location.x_m, location.y_m)], masked=True))[0]
        if bool(getattr(value, "mask", False)):
            return None

        elevation = float(value)
        if not math.isfinite(elevation):
            return None
        return elevation

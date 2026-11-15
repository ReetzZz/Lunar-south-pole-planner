# Last updated: 2026-11-14
"""Astronomical observations from NASA/JPL Horizons.

Azimuth is measured clockwise from north.
Elevation is relative to the local geometric horizon.

Terrain obstruction, solar power and radio-link availability
are not calculated by this module.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
TIMEOUT = 30

SITES = {
    # NASA Lunar Surface Data Book, Rev. baseline, 2025-03-18,
    # Table A2.1-1; coordinates derived from PGDA south-pole LOLA DEMs.
    "Shackleton": (-89.7668, -171.87),
    "Connecting Ridge": (-89.4632, -137.49),
    "Nobile": (-85.4381, 37.36667),
}


class AstronomyError(RuntimeError):
    """Horizons request or parsing error."""


@dataclass
class Observation:
    time_utc: str
    azimuth_deg: float
    elevation_deg: float
    distance_au: float | None
    range_rate_km_s: float | None


def query_observations(
    target: str,
    latitude: float,
    longitude: float,
    start_utc: datetime,
    hours: int = 48,
    step: str = "1h",
) -> list[Observation]:
    """Retrieve topocentric apparent azimuth/elevation from Horizons.

    target='10' means Sun; target='399' means Earth.
    Coordinates are east longitude, latitude, altitude in km.
    """
    if start_utc.tzinfo is None:
        raise ValueError("start_utc must include a timezone.")
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    if not -360 <= longitude <= 360:
        raise ValueError("Longitude is outside the accepted range.")
    if hours < 1 or hours > 720:
        raise ValueError("hours must be between 1 and 720.")

    start = start_utc.astimezone(timezone.utc).replace(
        second=0, microsecond=0
    )
    stop = start + timedelta(hours=hours)

    params = {
        "format": "json",
        "COMMAND": f"'{target}'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": "'coord@301'",
        "COORD_TYPE": "GEODETIC",
        "SITE_COORD": f"'{longitude},{latitude},0'",
        "START_TIME": f"'{start:%Y-%m-%d %H:%M}'",
        "STOP_TIME": f"'{stop:%Y-%m-%d %H:%M}'",
        "STEP_SIZE": f"'{step}'",
        "QUANTITIES": "'4,20'",
        "CSV_FORMAT": "YES",
    }

    try:
        response = requests.get(
            HORIZONS_URL, params=params, timeout=TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise AstronomyError(f"Horizons request failed: {exc}") from exc

    if payload.get("error"):
        raise AstronomyError(str(payload["error"]))

    result = payload.get("result", "")
    if "$$SOE" not in result or "$$EOE" not in result:
        raise AstronomyError(
            "Horizons did not return an ephemeris data block."
        )

    data = result.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    observations = []

    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue

        # CSV fields: date, solar-presence flag, interfering-body flag,
        # azimuth, elevation, distance (AU), range rate (km/s).
        fields = next(csv.reader(io.StringIO(line), skipinitialspace=True))
        if len(fields) < 5:
            continue

        try:
            # Horizons restituisce i mesi in inglese (Jan, Feb, Oct...).
            # Non dipendere dalla locale configurata sul sistema operativo.
            match = re.fullmatch(
                r"(\d{4})-([A-Za-z]{3})-(\d{2})\s+(\d{2}):(\d{2})",
                fields[0].strip(),
            )
            if not match:
                raise ValueError(
                    f"Formato data Horizons non riconosciuto: {fields[0]!r}"
                )

            year, month_name, day, hour, minute = match.groups()
            months = {
                "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
                "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
                "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
            }
            month = months.get(month_name.title())
            if month is None:
                raise ValueError(f"Mese Horizons non riconosciuto: {month_name}")

            timestamp = datetime(
                int(year), month, int(day), int(hour), int(minute),
                tzinfo=timezone.utc,
            )

            azimuth = float(fields[3])
            elevation = float(fields[4])

            distance = None
            range_rate = None

            if len(fields) > 5 and fields[5].strip() not in ("", "n.a."):
                distance = float(fields[5])
            if len(fields) > 6 and fields[6].strip() not in ("", "n.a."):
                range_rate = float(fields[6])

            observations.append(Observation(
                time_utc=timestamp.isoformat(),
                azimuth_deg=azimuth,
                elevation_deg=elevation,
                distance_au=distance,
                range_rate_km_s=range_rate,
            ))
        except (ValueError, IndexError):
            # Ignore headers or malformed rows; never fabricate data.
            continue

    if not observations:
        raise AstronomyError(
            "Horizons returned no usable numeric observations."
        )

    return observations


def main():
    site_name = "Connecting Ridge"
    latitude, longitude = SITES[site_name]
    start = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )

    print("NASA/JPL HORIZONS — LOCAL OBSERVATION TEST")
    print(f"Site: {site_name} ({latitude}, {longitude})")
    print(f"Start UTC: {start.isoformat()}")

    for target, name in (("10", "SUN"), ("399", "EARTH")):
        print(f"\n{name}")
        try:
            rows = query_observations(
                target, latitude, longitude, start, hours=6
            )
            print("UTC                      AZIMUTH    ELEVATION")
            for row in rows:
                print(
                    f"{row.time_utc:25s} "
                    f"{row.azimuth_deg:8.3f}° "
                    f"{row.elevation_deg:9.3f}°"
                )
        except AstronomyError as exc:
            print(f"ERROR: {exc}")

    print(
        "\nLIMITATION: geometric apparent positions only. "
        "Local terrain and radio-link validation are not included."
    )


if __name__ == "__main__":
    main()

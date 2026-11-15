# Last updated: 2026-11-14
"""Esporta la classificazione del rischio di discesa in un GeoTIFF diagnostico."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, transform as window_transform


CLASS_VALUES = {
    "DATI_INSUFFICIENTI": 0,
    "ENTRO_SOGLIE": 1,
    "RISCHIO": 2,
}


def export_descent_risk_raster(
    report_path: str | Path,
    dem_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Esporta le classi del report sulla finestra corrispondente del DEM.

    I valori sono: 0=dati insufficienti, 1=entro soglie, 2=rischio.
    Il raster eredita CRS e trasformazione dal DEM originale.
    """
    report_file = Path(report_path)
    dem_file = Path(dem_path)
    destination = Path(output_path)

    if not report_file.is_file():
        raise FileNotFoundError(f"Report rischi non trovato: {report_file}")
    if not dem_file.is_file():
        raise FileNotFoundError(f"DEM non trovato: {dem_file}")

    payload = json.loads(report_file.read_text(encoding="utf-8"))
    if payload.get("schema") != "lunar-descent-hazard-report/1.0":
        raise ValueError("Schema del report rischi non riconosciuto.")

    input_data = payload.get("input", {})
    center = input_data.get("center_rc")
    radius = input_data.get("radius_cells")
    classification = payload.get("cell_risk_map", {}).get("classification")

    if not isinstance(center, list) or len(center) != 2:
        raise ValueError("Il report non contiene center_rc valido.")
    if isinstance(radius, bool) or not isinstance(radius, int) or radius < 1:
        raise ValueError("Il report non contiene radius_cells valido.")
    if not isinstance(classification, list) or not classification:
        raise ValueError("La matrice di classificazione è assente.")

    try:
        row, col = int(center[0]), int(center[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("center_rc non valido.") from exc

    with rasterio.open(dem_file) as dem:
        if dem.count != 1:
            raise ValueError("Il DEM deve contenere una sola banda.")
        if dem.crs is None:
            raise ValueError("Il DEM non ha un CRS: esportazione interrotta.")

        if not (0 <= row < dem.height and 0 <= col < dem.width):
            raise ValueError("Il centro indicato è fuori dal DEM.")

        row_start = max(0, row - radius)
        col_start = max(0, col - radius)
        row_stop = min(dem.height, row + radius + 1)
        col_stop = min(dem.width, col + radius + 1)

        expected_shape = (row_stop - row_start, col_stop - col_start)
        if len(classification) != expected_shape[0]:
            raise ValueError(
                f"Altezza matrice {len(classification)}; attesa {expected_shape[0]}."
            )

        if any(
            not isinstance(line, list) or len(line) != expected_shape[1]
            for line in classification
        ):
            raise ValueError(f"Forma matrice non coerente: attesa {expected_shape}.")

        numeric = np.full(expected_shape, 0, dtype=np.uint8)
        for label, value in CLASS_VALUES.items():
            mask = np.array(
                [[cell == label for cell in line] for line in classification],
                dtype=bool,
            )
            numeric[mask] = value

        recognized = np.isin(numeric, list(CLASS_VALUES.values()))
        for line in classification:
            for cell in line:
                if cell not in CLASS_VALUES:
                    raise ValueError(f"Classe di rischio sconosciuta: {cell!r}")

        profile = dem.profile.copy()
        profile.update(
            driver="GTiff",
            height=expected_shape[0],
            width=expected_shape[1],
            count=1,
            dtype="uint8",
            transform=window_transform(
                Window(
                    col_start,
                    row_start,
                    expected_shape[1],
                    expected_shape[0],
                ),
                dem.transform,
            ),
            nodata=None,
            compress="deflate",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(destination, "w", **profile) as output:
        output.write(numeric, 1)
        output.set_band_description(1, "Classificazione diagnostica rischio discesa")
        output.update_tags(
            CLASS_0="DATI_INSUFFICIENTI",
            CLASS_1="ENTRO_SOGLIE",
            CLASS_2="RISCHIO",
            SOURCE_REPORT=str(report_file),
            SOURCE_DEM=str(dem_file),
            STATUS="PRELIMINARY_NOT_FLIGHT_CERTIFIED",
        )

    return destination

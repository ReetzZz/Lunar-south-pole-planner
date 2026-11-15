# Last updated: 2026-11-14
"""Validazione prudente delle classi della mappa di confidenza PDS3 LROC.

Non modifica raster, non corregge elevazioni e non assegna significati
non documentati alle classi.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rasterio


DOCUMENTED_CLASSES = {
    0: "NoDATA / fuori dal perimetro valido",
    1: "Ombra",
    4: "Interpolato o estrapolato",
    14: "Basato sui risultati dell'image matching",
}


@dataclass(frozen=True)
class ConfidenceValidation:
    raster_path: str
    exists: bool
    total_pixels: int = 0
    class_counts: dict | None = None
    nodata_pixels: int = 0
    shadow_pixels: int = 0
    interpolated_extrapolated_pixels: int = 0
    image_matching_pixels: int = 0
    undocumented_classes: tuple[int, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def validate_confidence_raster(path: str | Path) -> ConfidenceValidation:
    """Legge e riepiloga una mappa PDS3 senza attribuire classi ignote."""
    raster_path = Path(path)
    if not raster_path.is_file():
        return ConfidenceValidation(
            raster_path=str(raster_path),
            exists=False,
            warnings=("File della mappa di confidenza non trovato.",),
        )

    with rasterio.open(raster_path) as ds:
        if ds.count != 1:
            raise ValueError("La mappa di confidenza deve avere una sola banda.")
        if ds.dtypes[0] != "uint8":
            raise ValueError(
                f"Tipo dati inatteso: {ds.dtypes[0]}; atteso uint8 PDS3."
            )
        values = ds.read(1)

    unique, counts = np.unique(values, return_counts=True)
    class_counts = {int(k): int(v) for k, v in zip(unique, counts)}
    known = set(DOCUMENTED_CLASSES)
    unknown = tuple(sorted(set(class_counts) - known))
    warnings = [
        "Le classi documentate sono interpretate secondo l'etichetta PDS3 disponibile.",
        "La classe 0 è NoDATA per questa mappa, non una quota del DEM.",
        "La mappa di confidenza non dimostra da sola la co-registrazione fisica dei DEM.",
    ]
    if unknown:
        warnings.append(
            "Classi senza significato verificato nell'etichetta consultata: "
            + ", ".join(map(str, unknown))
            + ". Non assegnare loro un significato senza documentazione."
        )

    return ConfidenceValidation(
        raster_path=str(raster_path),
        exists=True,
        total_pixels=int(values.size),
        class_counts=class_counts,
        nodata_pixels=class_counts.get(0, 0),
        shadow_pixels=class_counts.get(1, 0),
        interpolated_extrapolated_pixels=class_counts.get(4, 0),
        image_matching_pixels=class_counts.get(14, 0),
        undocumented_classes=unknown,
        warnings=tuple(warnings),
    )

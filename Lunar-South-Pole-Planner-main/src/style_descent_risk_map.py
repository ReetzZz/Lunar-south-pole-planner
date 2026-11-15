# Last updated: 2026-11-14
"""Applica lo stile QGIS alla mappa diagnostica dei rischi lunari."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsRasterLayer,
    QgsSingleBandPseudoColorRenderer,
    QgsColorRampShader,
    QgsRasterShader,
    QgsCoordinateReferenceSystem,
    QgsReferencedRectangle,
)
from qgis.PyQt.QtGui import QColor


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crea un progetto QGIS per la mappa diagnostica dei rischi."
    )
    parser.add_argument(
        "raster",
        nargs="?",
        default="reports/mission/descent_risk_map.tif",
        help="Percorso del GeoTIFF di classificazione.",
    )
    parser.add_argument(
        "--output",
        default="reports/mission/descent_risk_map.qgz",
        help="Percorso del progetto QGIS da salvare.",
    )
    parser.add_argument(
        "--crs",
        default=None,
        help=(
            "CRS esplicito da assegnare solo dopo averne verificato "
            "la compatibilità con il DEM. Per impostazione predefinita "
            "viene mantenuto il CRS incorporato nel GeoTIFF."
        ),
    )
    args = parser.parse_args()

    raster_path = Path(args.raster).expanduser().resolve()
    project_path = Path(args.output).expanduser().resolve()

    if not raster_path.is_file():
        print(f"ERRORE: GeoTIFF non trovato: {raster_path}", file=sys.stderr)
        return 2

    project_path.parent.mkdir(parents=True, exist_ok=True)
    print("GeoTIFF:", raster_path)
    print("Progetto destinazione:", project_path)
    print("CRS esplicito richiesto:", args.crs or "nessuno; usa quello del GeoTIFF")

    app = QgsApplication([], False)
    app.initQgis()
    try:
        project = QgsProject.instance()
        layer = QgsRasterLayer(str(raster_path), "Mappa rischi atterraggio lunare")
        if not layer.isValid():
            print("ERRORE: QGIS non riesce a leggere il GeoTIFF.", file=sys.stderr)
            return 2

        if args.crs:
            selected_crs = QgsCoordinateReferenceSystem(args.crs)
            if not selected_crs.isValid():
                print(f"ERRORE: CRS non disponibile: {args.crs}", file=sys.stderr)
                return 2
            print(
                "ATTENZIONE: viene assegnato un CRS esplicito senza "
                "riproiettare il raster. Usarlo solo dopo verifica indipendente.",
                file=sys.stderr,
            )
            layer.setCrs(selected_crs)
        else:
            selected_crs = layer.crs()
            if not selected_crs.isValid():
                print(
                    "ERRORE: il GeoTIFF non espone un CRS valido. "
                    "Verificare il riferimento originale prima di procedere.",
                    file=sys.stderr,
                )
                return 2

        project.setCrs(selected_crs)

        shader = QgsColorRampShader()
        shader.setColorRampType(QgsColorRampShader.Discrete)
        shader.setClassificationMode(QgsColorRampShader.EqualInterval)
        shader.setColorRampItemList([
            QgsColorRampShader.ColorRampItem(
                0, QColor("#929292"), "Dati insufficienti"
            ),
            QgsColorRampShader.ColorRampItem(
                1, QColor("#299764"), "Entro soglie"
            ),
            QgsColorRampShader.ColorRampItem(
                2, QColor("#D94B4B"), "Rischio"
            ),
        ])

        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(shader)
        renderer = QgsSingleBandPseudoColorRenderer(
            layer.dataProvider(), 1, raster_shader
        )
        layer.setRenderer(renderer)

        project.addMapLayer(layer)
        project.viewSettings().setDefaultViewExtent(
            QgsReferencedRectangle(layer.extent(), selected_crs)
        )
        project.setFileName(str(project_path))

        if not project.write():
            print("ERRORE: impossibile salvare il progetto QGIS.", file=sys.stderr)
            return 1

        print("Progetto QGIS salvato:", project.fileName())
        print("Stile: grigio=0, verde=1, rosso=2")
        print("CRS del progetto:", selected_crs.authid() or "CRS personalizzato")
        print("ATTENZIONE: la georeferenziazione MOON_ME/DE421 non è stata validata.")
        print("ATTENZIONE: mappa diagnostica preliminare, non certificata per il volo.")
        return 0
    finally:
        app.exitQgis()


if __name__ == "__main__":
    raise SystemExit(main())

# Last updated: 2026-11-14
from pathlib import Path
import sys

def main():
    try:
        import trimesh
    except ImportError:
        print("Dipendenze mancanti. Esegui:")
        print('.venv/bin/python -m pip install trimesh "pyglet<2"')
        raise SystemExit(1)

    root = Path(__file__).resolve().parent.parent
    model_path = (
        root / "data/terrain/global/Moon_NASA_LRO_8k_Topo_Small.glb"
    )

    if not model_path.is_file():
        print(f"Modello NASA non trovato: {model_path}")
        raise SystemExit(1)

    print("Caricamento del modello NASA LRO...")
    print(f"File: {model_path}")
    print(f"Dimensione: {model_path.stat().st_size / 1024**2:.1f} MB")

    try:
        scene = trimesh.load(model_path, force="scene")
    except Exception as exc:
        print(f"Errore nel caricamento GLB: {exc}")
        raise SystemExit(2) from exc

    if not isinstance(scene, trimesh.Scene) or not scene.geometry:
        print("Il file non contiene geometrie 3D visualizzabili.")
        raise SystemExit(3)

    print(f"Geometrie caricate: {len(scene.geometry)}")
    print("Apertura finestra 3D...")
    print("Mouse: ruota e ispeziona la Luna; chiudi la finestra per uscire.")

    try:
        scene.show(viewer="gl", resolution=(1280, 800))
    except Exception as exc:
        print(f"Errore del visualizzatore OpenGL: {exc}")
        print("Verifica che Kali abbia una sessione grafica attiva.")
        raise SystemExit(4) from exc


if __name__ == "__main__":
    main()

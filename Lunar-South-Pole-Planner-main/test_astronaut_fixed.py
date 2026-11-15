# Last updated: 2026-11-14
from pathlib import Path
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Filename, loadPrcFileData

loadPrcFileData("", "window-type off")
loadPrcFileData("", "audio-library-name null")

ASSET_DIR = Path(__file__).resolve().parent / "data/models/nasa"

class ModelTest(ShowBase):
    def __init__(self):
        super().__init__()
        self.disableMouse()

        print("\n===== TEST MODELLI NASA GLB =====")
        for path in sorted(ASSET_DIR.glob("*.glb")):
            try:
                model = self.loader.loadModel(
                    Filename.fromOsSpecific(str(path.resolve())),
                    noCache=True
                )
                if model is None or model.isEmpty():
                    print(f"ERRORE: {path.name} — modello vuoto")
                    continue

                model.reparentTo(self.render)
                bounds = model.getTightBounds()

                if bounds:
                    lo, hi = bounds
                    size = hi - lo
                    print(
                        f"OK: {path.name} | "
                        f"dimensioni: {size.x:.3f}, "
                        f"{size.y:.3f}, {size.z:.3f}"
                    )
                else:
                    print(f"CARICATO: {path.name} | limiti non disponibili")

                model.removeNode()

            except Exception as exc:
                print(f"ERRORE: {path.name} | {exc}")

        print("===== FINE TEST =====")
        self.userExit()

app = ModelTest()
app.run()

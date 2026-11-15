# Last updated: 2026-11-14
from pathlib import Path
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Filename, loadPrcFileData

loadPrcFileData("", "window-type off")
loadPrcFileData("", "audio-library-name null")

assets = Path(__file__).resolve().parent / "data/models/nasa"
names = [
    "Astronaut_compatible.glb",
    "Apollo_Lunar_Module_fixed.glb",
    "LRO_A_fixed.glb",
    "LRO_B_fixed.glb",
    "Gateway_Core.glb",
]

class TestModels(ShowBase):
    def __init__(self):
        super().__init__()
        print("\n===== MODELLI CONVERTITI =====")
        for name in names:
            path = assets / name
            if not path.exists():
                print(f"MANCANTE: {name}")
                continue
            try:
                model = self.loader.loadModel(
                    Filename.fromOsSpecific(str(path.resolve())),
                    noCache=True
                )
                if model and not model.isEmpty():
                    print(f"OK: {name}")
                    model.removeNode()
                else:
                    print(f"NON CARICATO: {name}")
            except Exception as exc:
                print(f"ERRORE: {name}: {exc}")
        self.userExit()

TestModels().run()

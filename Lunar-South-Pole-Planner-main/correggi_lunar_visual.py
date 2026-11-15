#!/usr/bin/env python3
# Last updated: 2026-11-14
"""Correzione layout Lunar Mission Control: globo, leggibilità, grafici e pulsanti."""
from pathlib import Path
from datetime import datetime
import ast, py_compile, shutil, re

target = Path("src/lunar_mission_3d.py")
if not target.is_file():
    raise SystemExit("Esegui dalla root ~/Lunar-South-Pole-Planner: file src/lunar_mission_3d.py non trovato.")
src = target.read_text(encoding="utf-8")
ast.parse(src)
backup_dir = Path("backups")
backup_dir.mkdir(exist_ok=True)
backup = backup_dir / f"lunar_mission_3d.pre-visual-fix-{datetime.now():%Y%m%d-%H%M%S}.py"
shutil.copy2(target, backup)

original = src

def replace_once(old, new, label):
    global src
    if old not in src:
        print(f"[SKIP] pattern non trovato: {label}")
        return
    src = src.replace(old, new, 1)
    print(f"[OK] {label}")

# Globo più contenuto, con raggio coerente per marker e asset di superficie.
replace_once("scale = 5.8 / extent\n        self.moon_radius = 2.9",
             "scale = 4.65 / extent\n        self.moon_radius = 2.325",
             "ridimensionamento modello lunare")

# Camera più distante e inquadratura neutra: niente spostamento artificiale laterale.
replace_once("self.camera_distance = 12.8\n        self.camera.setPos(self.moon_center.x + 0.15, -self.camera_distance,\n                           self.moon_center.z + 0.35)\n        self.camera.lookAt(self.moon_center)",
             "self.camera_distance = 14.6\n        self.camera.setPos(self.moon_center.x, -self.camera_distance,\n                           self.moon_center.z + 0.20)\n        self.camera.lookAt(self.moon_center)",
             "camera iniziale")
replace_once("self.camera_distance = 12.8\n        self.camera.setPos(self.moon_center.x + 0.15, -self.camera_distance,\n                           self.moon_center.z + 0.35)\n        self.camera.lookAt(self.moon_center)",
             "self.camera_distance = 14.6\n        self.camera.setPos(self.moon_center.x, -self.camera_distance,\n                           self.moon_center.z + 0.20)\n        self.camera.lookAt(self.moon_center)",
             "reset camera")

# Rendere i grafici più alti e spostarli in una fascia inferiore più leggibile.
replace_once('"sun": (-0.73,-0.02,-0.735,-0.565),\n                             "earth": (0.10,0.81,-0.735,-0.565)',
             '"sun": (-0.70,-0.015,-0.735,-0.535),\n                             "earth": (0.095,0.78,-0.735,-0.535)',
             "dimensioni grafici")

# Leggibilità dei pulsanti: evitare che la scala del widget rimpicciolisca anche il testo.
src = re.sub(r'text_scale=0\.038, scale=0\.48,', 'text_scale=0.034, scale=0.78,', src)
src = re.sub(r'text_scale=0\.036, scale=0\.46,', 'text_scale=0.032, scale=0.78,', src)
src = re.sub(r'text_scale=0\.022,\s*\n\s*scale=0\.42,', 'text_scale=0.028,\n                scale=0.72,', src)
# I grafici e le loro etichette sono leggibili anche su schermi 1600x900.
src = src.replace('text_scale=0.024,\n                frameColor=(0,0,0,0), pos=(x0,0,z1+0.026)',
                  'text_scale=0.030,\n                frameColor=(0,0,0,0), pos=(x0,0,z1+0.032)')
src = src.replace('text_scale=0.017, frameColor=(0,0,0,0), pos=(x,0,z0-0.018)',
                  'text_scale=0.022, frameColor=(0,0,0,0), pos=(x,0,z0-0.024)')
# Pannello destro: aumentare i caratteri e ridurre il wordwrap eccessivo.
src = src.replace('text_scale=0.023, frameColor=(0,0,0,0), pos=(-0.29,0,0.21)',
                  'text_scale=0.027, frameColor=(0,0,0,0), pos=(-0.29,0,0.21)')
src = src.replace('text_scale=0.027, text_wordwrap=23,',
                  'text_scale=0.031, text_wordwrap=21,')
src = src.replace('text_scale=0.023,\n            frameColor=(0,0,0,0), pos=(-0.29,0,0.25)',
                  'text_scale=0.027,\n            frameColor=(0,0,0,0), pos=(-0.29,0,0.25)')
src = src.replace('text_scale=0.020, text_wordwrap=29,',
                  'text_scale=0.024, text_wordwrap=24,')

# Barra inferiore più leggibile e leggermente più alta.
src = src.replace('pos=(x,0,-0.89), command=action)',
                  'pos=(x,0,-0.875), command=action)')

if src == original:
    raise SystemExit("Nessuna modifica applicata: il file non corrisponde alla versione attesa. Backup: " + str(backup))
ast.parse(src)
tmp = target.with_suffix(".visual-fix.tmp")
tmp.write_text(src, encoding="utf-8")
py_compile.compile(str(tmp), doraise=True)
tmp.replace(target)
print(f"\nCORREZIONE APPLICATA. Backup: {backup}")
print("Sintassi Python: OK")
print("Avvia con: python -m src.lunar_mission_3d")

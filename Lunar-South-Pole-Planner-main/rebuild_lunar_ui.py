#!/usr/bin/env python3
# Last updated: 2026-11-14
# Ridisegna l'interfaccia Panda3D preservando la logica scientifica.
from pathlib import Path
import ast
import py_compile
import shutil
from datetime import datetime

ROOT = Path.cwd()
TARGET = ROOT / "src" / "lunar_mission_3d.py"
if not TARGET.is_file():
    raise SystemExit(f"Non trovo {TARGET}. Esegui lo script dalla root del progetto.")

source = TARGET.read_text(encoding="utf-8")
tree = ast.parse(source)
cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LunarMission3D"), None)
if cls is None:
    raise SystemExit("Classe LunarMission3D non trovata; file lasciato invariato.")

backup_dir = ROOT / "backups"
backup_dir.mkdir(exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = backup_dir / f"lunar_mission_3d.pre-ui-redesign-{stamp}.py"
shutil.copy2(TARGET, backup)

replacements = {
"_setup_camera": r"""    def _setup_camera(self):
        self.camera_distance = 12.8
        self.camera.setPos(self.moon_center.x + 0.15, -self.camera_distance,
                           self.moon_center.z + 0.35)
        self.camera.lookAt(self.moon_center)
""",
"_setup_controls": r"""    def _setup_controls(self):
        panel_color = (0.012, 0.035, 0.060, 0.97)
        cyan = (0.22, 0.88, 1.0, 1)
        white = (0.82, 0.91, 0.97, 1)
        muted = (0.48, 0.67, 0.77, 1)
        self.panel = DirectFrame(parent=self.aspect2d, frameColor=panel_color,
            frameSize=(-0.34, 0.34, -0.61, 0.67), pos=(-1.28, 0, 0.10))
        DirectLabel(parent=self.panel, text="MISSION SETUP", text_align=TextNode.ALeft,
            text_fg=cyan, text_scale=0.042, frameColor=(0,0,0,0), pos=(-0.29,0,0.57))
        DirectLabel(parent=self.panel, text="LUNAR SOUTH POLE / LRO", text_align=TextNode.ALeft,
            text_fg=muted, text_scale=0.021, frameColor=(0,0,0,0), pos=(-0.29,0,0.51))
        DirectLabel(parent=self.panel, text="01  TARGET SITE", text_align=TextNode.ALeft,
            text_fg=white, text_scale=0.027, frameColor=(0,0,0,0), pos=(-0.29,0,0.41))
        self.site_menu = DirectOptionMenu(parent=self.panel, items=self.site_names,
            initialitem=0, command=self.on_site_changed, scale=0.035, pos=(-0.28,0,0.33),
            text_fg=white, frameColor=(0.025,0.095,0.135,1),
            item_frameColor=(0.025,0.095,0.135,1))
        DirectLabel(parent=self.panel, text="02  START DATE / UTC", text_align=TextNode.ALeft,
            text_fg=white, text_scale=0.025, frameColor=(0,0,0,0), pos=(-0.29,0,0.21))
        self.date_entry = DirectEntry(parent=self.panel,
            initialText=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            scale=0.034, width=12, pos=(-0.28,0,0.13),
            frameColor=(0.018,0.065,0.095,1), text_fg=(1,1,1,1), numLines=1)
        DirectLabel(parent=self.panel, text="03  ANALYSIS HORIZON", text_align=TextNode.ALeft,
            text_fg=white, text_scale=0.025, frameColor=(0,0,0,0), pos=(-0.29,0,0.015))
        DirectLabel(parent=self.panel, text="48 HOURS / 1 H SAMPLE", text_align=TextNode.ALeft,
            text_fg=cyan, text_scale=0.022, frameColor=(0,0,0,0), pos=(-0.29,0,-0.055))
        DirectButton(parent=self.panel, text="RUN HORIZONS", text_scale=0.038, scale=0.48,
            textMayChange=False, frameColor=(0.02,0.34,0.46,1), text_fg=(1,1,1,1),
            pos=(0,0,-0.19), command=self.refresh_astronomy)
        DirectButton(parent=self.panel, text="RESET 3D VIEW", text_scale=0.036, scale=0.46,
            textMayChange=False, frameColor=(0.025,0.09,0.13,1), text_fg=cyan,
            pos=(0,0,-0.31), command=self.reset_camera)
        DirectLabel(parent=self.panel, text="SYSTEM STATUS", text_align=TextNode.ALeft,
            text_fg=muted, text_scale=0.022, frameColor=(0,0,0,0), pos=(-0.29,0,-0.43))
        self.status_label = DirectLabel(parent=self.panel, text="Initialising mission systems…",
            text_align=TextNode.ALeft, text_wordwrap=25, text_fg=white, text_scale=0.023,
            frameColor=(0,0,0,0), pos=(-0.29,0,-0.49))
        self.site_label = self.render.attachNewNode("site-coordinate-label")
        self.site_label.setPos(-5.0, 0.0, 3.0)
        self._set_site_label()
""",
"_setup_top_bar": r"""    def _setup_top_bar(self):
        self.top_bar = DirectFrame(parent=self.aspect2d, frameColor=(0.004,0.016,0.029,0.99),
            frameSize=(-1.66,1.66,-0.075,0.075), pos=(0,0,0.91))
        DirectLabel(parent=self.top_bar, text="LUNAR", text_align=TextNode.ALeft,
            text_fg=(0.20,0.88,1,1), text_scale=0.048, frameColor=(0,0,0,0),
            pos=(-1.58,0,-0.015))
        DirectLabel(parent=self.top_bar, text="MISSION CONTROL", text_align=TextNode.ALeft,
            text_fg=(0.88,0.94,1,1), text_scale=0.034, frameColor=(0,0,0,0),
            pos=(-1.18,0,-0.012))
        DirectLabel(parent=self.top_bar, text="NASA LRO / JPL HORIZONS / SOUTH POLE",
            text_align=TextNode.ARight, text_fg=(0.35,0.75,0.85,1), text_scale=0.024,
            frameColor=(0,0,0,0), pos=(1.57,0,-0.01))
""",
"_setup_scene_labels": r"""    def _setup_scene_labels(self):
        cyan = (0.18,0.86,1.0,1)
        white = (0.82,0.92,0.98,1)
        self.site_info_frame = DirectFrame(parent=self.aspect2d,
            frameColor=(0.008,0.027,0.046,0.96), frameSize=(-0.33,0.33,-0.24,0.27),
            pos=(1.27,0,0.52))
        self.site_info_title = DirectLabel(parent=self.site_info_frame,
            text="TARGET / SITE TELEMETRY", text_align=TextNode.ALeft, text_fg=cyan,
            text_scale=0.023, frameColor=(0,0,0,0), pos=(-0.29,0,0.21))
        self.site_info_label = DirectLabel(parent=self.site_info_frame, text="SELECT SITE",
            text_align=TextNode.ALeft, text_fg=white, text_scale=0.027, text_wordwrap=23,
            frameColor=(0,0,0,0), pos=(-0.29,0,0.10))
        self.mission_window_frame = DirectFrame(parent=self.aspect2d,
            frameColor=(0.008,0.027,0.046,0.96), frameSize=(-0.33,0.33,-0.31,0.31),
            pos=(1.27,0,-0.13))
        DirectLabel(parent=self.mission_window_frame, text="OPERATIONAL WINDOWS",
            text_align=TextNode.ALeft, text_fg=cyan, text_scale=0.023,
            frameColor=(0,0,0,0), pos=(-0.29,0,0.25))
        self.mission_window_label = DirectLabel(parent=self.mission_window_frame,
            text="Awaiting Horizons data…", text_align=TextNode.ALeft, text_fg=white,
            text_scale=0.020, text_wordwrap=29, frameColor=(0,0,0,0), pos=(-0.29,0,0.15))
        self.graph_panel = DirectFrame(parent=self.aspect2d,
            frameColor=(0.006,0.020,0.036,0.96), frameSize=(-0.80,0.80,-0.205,0.205),
            pos=(0.02,0,-0.625))
        self.graph_root = self.aspect2d.attachNewNode("astronomy-2d-curves")
        self.graph_axes_root = self.aspect2d.attachNewNode("astronomy-2d-axes")
        self.graph_labels = []
        self.graph_bounds = {"sun": (-0.73,-0.02,-0.735,-0.565),
                             "earth": (0.10,0.81,-0.735,-0.565)}
        self.site_annotation_line = None
        self._set_site_label()
        separator = LineSegs("hud-separator")
        separator.setThickness(1.2)
        separator.setColor(0.08,0.40,0.52,0.85)
        separator.moveTo(-1.65,0,0.805)
        separator.drawTo(1.65,0,0.805)
        self.aspect2d.attachNewNode(separator.create())
        # Etichette di asse e titolo dei grafici sono create dal metodo seguente.
        self._draw_graph_axes()
""",
"_setup_holographic_hubs": r"""    def _setup_holographic_hubs(self):
        items = [("SITE TRACKING", self._hub_site_tracking),
                 ("HORIZONS REFRESH", self._hub_horizons),
                 ("DTM STATUS", self._hub_dtm),
                 ("MISSION WINDOWS", self._hub_windows),
                 ("RESET CAMERA", self._hub_view)]
        self.hologram_nodes = []
        xs = [-1.20,-0.60,0.0,0.60,1.20]
        for (label, action), x in zip(items, xs):
            button = DirectButton(parent=self.aspect2d, text=label, text_scale=0.022,
                scale=0.42, textMayChange=False, frameColor=(0.012,0.065,0.090,0.98),
                text_fg=(0.30,0.88,1.0,1), frameSize=(-0.60,0.60,-0.065,0.065),
                pos=(x,0,-0.89), command=action)
            self.hologram_nodes.append(button)
""",
"_draw_graph_axes": r"""    def _draw_graph_axes(self):
        for key, (x0,x1,z0,z1) in self.graph_bounds.items():
            color = (1.0,0.69,0.20,1) if key == "sun" else (0.18,0.82,1.0,1)
            lines = LineSegs(f"{key}-grid")
            lines.setThickness(0.8)
            lines.setColor(0.12,0.29,0.38,0.85)
            for elevation in (0,2,4,6,8,10):
                z = z0 + elevation/10.0*(z1-z0)
                lines.moveTo(x0,0,z); lines.drawTo(x1,0,z)
            for hour in (0,12,24,36,48):
                x = x0 + hour/48.0*(x1-x0)
                lines.moveTo(x,0,z0); lines.drawTo(x,0,z1)
            self.graph_axes_root.attachNewNode(lines.create())
            title = DirectLabel(parent=self.aspect2d,
                text="SUN ELEVATION / 0–10°" if key == "sun" else "EARTH ELEVATION / 0–10°",
                text_align=TextNode.ALeft, text_fg=color, text_scale=0.024,
                frameColor=(0,0,0,0), pos=(x0,0,z1+0.026))
            self.graph_labels.append(title)
            for hour in (0,12,24,36,48):
                x = x0 + hour/48.0*(x1-x0)
                label = DirectLabel(parent=self.aspect2d, text=str(hour),
                    text_align=TextNode.ACenter, text_fg=(0.65,0.78,0.85,1),
                    text_scale=0.017, frameColor=(0,0,0,0), pos=(x,0,z0-0.018))
                self.graph_labels.append(label)
""",
"reset_camera": r"""    def reset_camera(self):
        self.camera_distance = 12.8
        self.camera.setPos(self.moon_center.x + 0.15, -self.camera_distance,
                           self.moon_center.z + 0.35)
        self.camera.lookAt(self.moon_center)
"""
}

nodes = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
missing = [name for name in replacements if name not in nodes]
if missing:
    raise SystemExit("Metodi attesi non trovati: " + ", ".join(missing) + ". Sorgente non modificato.")

lines = source.splitlines(keepends=True)
spans = []
for name, new_text in replacements.items():
    node = nodes[name]
    spans.append((node.lineno - 1, node.end_lineno, new_text.rstrip() + "\n\n"))
for start, end, replacement in sorted(spans, reverse=True):
    lines[start:end] = [replacement]
updated = "".join(lines)
ast.parse(updated)
tmp = TARGET.with_suffix(".py.redesign-tmp")
tmp.write_text(updated, encoding="utf-8")
py_compile.compile(str(tmp), doraise=True)
tmp.replace(TARGET)
print("INTERFACCIA RIDISEGNATA.")
print(f"Backup: {backup.relative_to(ROOT)}")
print(f"File aggiornato: {TARGET.relative_to(ROOT)}")
print("Verifica sintassi: OK")
print("Logica Horizons, finestre operative, modello LRO e asset NASA preservati.")
print("Avvio: python -m src.lunar_mission_3d")

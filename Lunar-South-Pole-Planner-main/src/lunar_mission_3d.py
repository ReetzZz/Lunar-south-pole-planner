# Last updated: 2026-11-14
"""Lunar South Pole Mission Control: scena Panda3D e modello NASA LRO."""

from pathlib import Path
from datetime import datetime, timezone
import math
import traceback

import gltf  # registra il loader glTF/GLB di Panda3D
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import (
    DirectFrame, DirectLabel, DirectButton, DirectScrolledFrame,
    DirectEntry, DirectOptionMenu,
)
from panda3d.core import (
    AmbientLight, DirectionalLight, Vec4, Vec3,
    LineSegs, TextNode, WindowProperties, Quat, Point2, Point3,
)

from src.astronomy import SITES, query_observations
from src.mission_planning import find_operational_windows
from src.mission_planner import MissionConfig, build_mission_plan, save_mission_plan, rank_operational_windows


ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data/terrain/global/Moon_NASA_LRO_8k_Topo_Small.glb"


def site_coordinates(name):
    """Legge le coordinate dai formati comuni della tabella SITES."""
    value = SITES[name]

    if isinstance(value, dict):
        lat = value.get("latitude", value.get("lat"))
        lon = value.get("longitude", value.get("lon", value.get("longitude_deg")))
    elif isinstance(value, (tuple, list)) and len(value) >= 2:
        lat, lon = value[0], value[1]
    else:
        lat = getattr(value, "latitude", getattr(value, "lat", None))
        lon = getattr(value, "longitude", getattr(value, "lon", None))

    if lat is None or lon is None:
        raise ValueError(f"Coordinate non riconosciute per {name}: {value!r}")

    return float(lat), float(lon)


class LunarMission3D(ShowBase):
    def __init__(self):
        super().__init__()
        self.disableMouse()
        self.setBackgroundColor(0.003, 0.008, 0.019, 1)
        self.setFrameRateMeter(False)

        props = WindowProperties()
        props.setTitle("LUNAR SOUTH POLE | MISSION CONTROL // PLANNER")
        props.setSize(1600, 950)
        self.win.requestProperties(props)

        self.site_names = list(SITES.keys())
        self.selected_site = self.site_names[0]
        self.observation_nodes = []
        self.last_mission_windows = []
        self.last_astronomy_status = 'not_run'
        self.model = None
        self.camera_angle = 0.0
        self.camera_distance = 17.0
        self.dragging = False
        self.last_mouse = None

        self._setup_lighting()
        self._load_moon()
        self._load_nasa_assets()
        self._setup_camera()
        self._setup_controls()
        self._setup_top_bar()
        self._setup_scene_labels()
        self._setup_holographic_hubs()
        self._setup_mouse()

        self.update_status(
            "Modello NASA caricato. Seleziona sito e data, poi aggiorna "
            "le osservazioni. Le coordinate sul modello globale non sono "
            "ancora georeferenziate."
        )

        self.taskMgr.add(self._animate, "animate-moon")
        self.taskMgr.add(self._mouse_camera, "mouse-camera")
        self.taskMgr.add(self._update_site_annotation, "site-annotation")
        # Carica le effemeridi dopo l'avvio della finestra.
        self.taskMgr.doMethodLater(
            0.5, self._initial_astronomy_refresh, "initial-astronomy-refresh"
        )

    def _initial_astronomy_refresh(self, task):
        self.refresh_astronomy()
        return task.done

    def _setup_lighting(self):
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.46, 0.49, 0.60, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        sun = DirectionalLight("sun-light")
        sun.setColor(Vec4(1.0, 0.93, 0.80, 1))
        sun.setDirection(Vec3(-1, -3, -1))
        self.render.setLight(self.render.attachNewNode(sun))

    def _load_moon(self):
        if not MODEL.is_file():
            raise FileNotFoundError(f"Modello NASA assente: {MODEL}")

        self.update_status("Caricamento modello topografico NASA LRO…")
        model = self.loader.loadModel(str(MODEL))
        if model.isEmpty():
            raise RuntimeError("Panda3D non è riuscito a caricare il GLB.")

        bounds = model.getTightBounds()
        if not bounds or bounds[0] is None or bounds[1] is None:
            raise RuntimeError("Impossibile calcolare i limiti del modello NASA.")

        lo, hi = bounds
        center = (lo + hi) * 0.5
        extent = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
        if extent <= 0:
            raise RuntimeError("Il modello NASA ha dimensioni non valide.")

        scale = 4.65 / extent
        self.moon_radius = 2.325
        self.moon_center = Vec3(0.0, 0, 0)

        # Il pivot rimane fisso. Si ruota il globo attorno al suo centro,
        # non la camera e non la posizione del centro della Luna.
        self.moon_pivot = self.render.attachNewNode("moon-fixed-center")
        self.moon_pivot.setPos(self.moon_center)

        model.reparentTo(self.moon_pivot)
        model.setScale(scale)
        model.setPos(-center.x * scale, -center.y * scale, -center.z * scale)
        model.setTwoSided(True)
        self.model = model
        self.site_marker = None

    def _load_nasa_assets(self):
        """Carica i modelli NASA nella scena dimostrativa."""
        from panda3d.core import Vec3

        asset_dir = ROOT / "data" / "models" / "nasa"
        self.nasa_assets = []

        # Dimensioni visive obiettivo in unità della scena.
        # Le posizioni orbitali sono illustrative, non orbite calcolate.
        definitions = [
            ("Gateway_Core.glb", "Gateway", 1.05,
             Vec3(3.45, -1.25, 1.00), "orbit"),
            ("LRO_A_fixed.glb", "LRO A", 0.72,
             Vec3(-2.65, -1.35, 1.05), "orbit"),
            ("LRO_B_fixed.glb", "LRO B", 0.62,
             Vec3(0.10, -3.45, -1.35), "orbit"),
            ("Apollo_Lunar_Module_fixed.glb", "Lunar Module", 0.72,
             Vec3(1.45, -2.30, -1.05), "surface"),
            ("Astronaut_compatible.glb", "Astronaut", 0.48,
             Vec3(-1.05, -2.45, -0.65), "surface"),
        ]

        for filename, label, target_size, position, placement in definitions:
            path = asset_dir / filename
            if not path.is_file():
                print(f"[NASA ASSET] File assente: {path.name}")
                continue

            model = None
            try:
                model = self.loader.loadModel(str(path))
                if model.isEmpty():
                    print(f"[NASA ASSET] Modello vuoto: {path.name}")
                    continue

                bounds = model.getTightBounds()
                if not bounds or bounds[0] is None or bounds[1] is None:
                    print(f"[NASA ASSET] Limiti non validi: {path.name}")
                    model.removeNode()
                    continue

                lo, hi = bounds
                center = (lo + hi) * 0.5
                extent = max(
                    hi.x - lo.x, hi.y - lo.y, hi.z - lo.z
                )
                if extent <= 0:
                    print(f"[NASA ASSET] Dimensioni nulle: {path.name}")
                    model.removeNode()
                    continue

                scale = target_size / extent
                parent = (
                    self.moon_pivot
                    if placement == "surface"
                    else self.render
                )

                # Calcola il centro del modello rispetto al suo pivot.
                model.reparentTo(parent)
                model.setScale(scale)
                model.setPos(
                    -center.x * scale,
                    -center.y * scale,
                    -center.z * scale,
                )

                if placement == "surface":
                    # Porta il centro del modello appena sopra il raggio
                    # lunare, seguendo una direzione del lato visibile.
                    direction = Vec3(position.x, position.y, position.z)
                    if direction.lengthSquared() == 0:
                        raise ValueError("Direzione di superficie nulla")

                    direction.normalize()
                    radius = self.moon_radius + target_size * 0.30
                    anchor = direction * radius
                    model.setPos(
                        model.getPos() + anchor
                    )
                else:
                    model.setPos(
                        position.x - center.x * scale,
                        position.y - center.y * scale,
                        position.z - center.z * scale,
                    )

                model.setTwoSided(True)
                model.setName(
                    "nasa-" + label.lower().replace(" ", "-")
                )
                self.nasa_assets.append(model)

                print(
                    f"[NASA ASSET] OK: {label} | "
                    f"dimensione={target_size:.2f} | "
                    f"collocazione={placement}"
                )

            except Exception as exc:
                if model is not None and not model.isEmpty():
                    model.removeNode()
                print(f"[NASA ASSET] ERRORE {label}: {exc}")

        print(
            f"[NASA ASSET] Totale: {len(self.nasa_assets)}"
            f"/{len(definitions)} modelli caricati."
        )

    def _setup_camera(self):
        self.camera_distance = 13.2
        self.camera.setPos(self.moon_center.x, -self.camera_distance,
                           self.moon_center.z + 0.20)
        self.camera.lookAt(self.moon_center)


    def _setup_controls(self):
        panel_color = (0.012, 0.035, 0.060, 0.97)
        cyan = (0.22, 0.88, 1.0, 1)
        white = (0.82, 0.91, 0.97, 1)
        muted = (0.48, 0.67, 0.77, 1)
        self.panel = DirectFrame(parent=self.aspect2d, frameColor=panel_color,
            frameSize=(-0.34, 0.34, -0.82, 0.67), pos=(-1.28, 0, 0.10))
        DirectLabel(parent=self.panel, text="MISSION SETUP", text_align=TextNode.ALeft,
            text_fg=cyan, text_scale=0.065, frameColor=(0,0,0,0), pos=(-0.29,0,0.57))
        DirectLabel(parent=self.panel, text="LUNAR SOUTH POLE / LRO", text_align=TextNode.ALeft,
            text_fg=muted, text_scale=0.041, frameColor=(0,0,0,0), pos=(-0.29,0,0.51))
        DirectLabel(parent=self.panel, text="01  TARGET SITE", text_align=TextNode.ALeft,
            text_fg=white, text_scale=0.047, frameColor=(0,0,0,0), pos=(-0.29,0,0.41))
        self.site_menu = DirectOptionMenu(parent=self.panel, items=self.site_names,
            initialitem=0, command=self.on_site_changed, scale=0.035, pos=(-0.28,0,0.33),
            text_fg=white, frameColor=(0.025,0.095,0.135,1),
            item_frameColor=(0.025,0.095,0.135,1))
        DirectLabel(parent=self.panel, text="02  START DATE / UTC", text_align=TextNode.ALeft,
            text_fg=white, text_scale=0.044, frameColor=(0,0,0,0), pos=(-0.29,0,0.21))
        self.date_entry = DirectEntry(parent=self.panel,
            initialText=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            scale=0.034, width=12, pos=(-0.28,0,0.13),
            frameColor=(0.018,0.065,0.095,1), text_fg=(1,1,1,1), numLines=1)
        DirectLabel(parent=self.panel, text="03  ANALYSIS HORIZON", text_align=TextNode.ALeft,
            text_fg=white, text_scale=0.044, frameColor=(0,0,0,0), pos=(-0.29,0,0.015))
        self.duration_entry = DirectEntry(parent=self.panel,
            initialText="48", scale=0.030, width=5,
            pos=(-0.28,0,-0.065),
            frameColor=(0.018,0.065,0.095,1),
            text_fg=(1,1,1,1), numLines=1)
        DirectLabel(parent=self.panel, text="HOURS (1-720)",
            text_align=TextNode.ALeft, text_fg=cyan, text_scale=0.033,
            frameColor=(0,0,0,0), pos=(-0.10,0,-0.055))

        DirectLabel(parent=self.panel,
            text="SCIENCE / ENGINEERING PRIORITY (1-5)",
            text_align=TextNode.ALeft, text_fg=white, text_scale=0.030,
            frameColor=(0,0,0,0), pos=(-0.29,0,-0.125))
        DirectLabel(parent=self.panel, text="SCIENCE",
            text_align=TextNode.ALeft, text_fg=cyan, text_scale=0.028,
            frameColor=(0,0,0,0), pos=(-0.28,0,-0.155))
        self.science_priority_entry = DirectEntry(parent=self.panel,
            initialText="5", scale=0.029, width=3,
            pos=(-0.28,0,-0.205),
            frameColor=(0.018,0.065,0.095,1),
            text_fg=(1,1,1,1), numLines=1)
        DirectLabel(parent=self.panel, text="ENGINEERING",
            text_align=TextNode.ALeft, text_fg=cyan, text_scale=0.028,
            frameColor=(0,0,0,0), pos=(-0.02,0,-0.155))
        self.engineering_priority_entry = DirectEntry(parent=self.panel,
            initialText="5", scale=0.029, width=3,
            pos=(-0.02,0,-0.205),
            frameColor=(0.018,0.065,0.095,1),
            text_fg=(1,1,1,1), numLines=1)
        DirectLabel(parent=self.panel, text="MIN ELEVATION (DEG)",
            text_align=TextNode.ALeft, text_fg=white, text_scale=0.028,
            frameColor=(0,0,0,0), pos=(-0.29,0,-0.245))
        DirectLabel(parent=self.panel, text="SUN",
            text_align=TextNode.ALeft, text_fg=cyan, text_scale=0.027,
            frameColor=(0,0,0,0), pos=(-0.28,0,-0.273))
        self.sun_threshold_entry = DirectEntry(parent=self.panel,
            initialText="5", scale=0.028, width=4,
            pos=(-0.28,0,-0.310),
            frameColor=(0.018,0.065,0.095,1),
            text_fg=(1,1,1,1), numLines=1)
        DirectLabel(parent=self.panel, text="EARTH",
            text_align=TextNode.ALeft, text_fg=cyan, text_scale=0.027,
            frameColor=(0,0,0,0), pos=(-0.02,0,-0.273))
        self.earth_threshold_entry = DirectEntry(parent=self.panel,
            initialText="5", scale=0.028, width=4,
            pos=(-0.02,0,-0.310),
            frameColor=(0.018,0.065,0.095,1),
            text_fg=(1,1,1,1), numLines=1)
        DirectButton(parent=self.panel, text="RUN HORIZONS", text_scale=0.052, scale=0.44,
            textMayChange=False, frameColor=(0.02,0.34,0.46,1), text_fg=(1,1,1,1),
            pos=(-0.16,0,-0.405), command=self.refresh_astronomy)
        DirectButton(parent=self.panel, text="EXPORT MISSION JSON",
            text_scale=0.046, scale=0.44, textMayChange=False,
            frameColor=(0.02,0.34,0.46,1), text_fg=(1,1,1,1),
            pos=(0.16,0,-0.405), command=self.export_mission_plan)
        DirectButton(parent=self.panel, text="RESET 3D VIEW", text_scale=0.052, scale=0.44,
            textMayChange=False, frameColor=(0.025,0.09,0.13,1), text_fg=cyan,
            pos=(-0.16,0,-0.505), command=self.reset_camera)
        DirectLabel(parent=self.panel, text="SYSTEM STATUS", text_align=TextNode.ALeft,
            text_fg=muted, text_scale=0.036, frameColor=(0,0,0,0), pos=(-0.29,0,-0.675))
        self.status_label = DirectLabel(parent=self.panel, text="Initialising mission systems…",
            text_align=TextNode.ALeft, text_wordwrap=18, text_fg=white, text_scale=0.030,
            frameColor=(0,0,0,0), pos=(-0.29,0,-0.715))
        self.site_label = self.render.attachNewNode("site-coordinate-label")
        self.site_label.setPos(-5.0, 0.0, 3.0)
        self._set_site_label()


    def _setup_top_bar(self):
        self.top_bar = DirectFrame(parent=self.aspect2d, frameColor=(0.002,0.010,0.022,0.995),
            frameSize=(-1.66,1.66,-0.075,0.075), pos=(0,0,0.91))
        DirectLabel(parent=self.top_bar, text="LUNAR", text_align=TextNode.ALeft,
            text_fg=(0.20,0.88,1,1), text_scale=0.066, frameColor=(0,0,0,0),
            pos=(-1.58,0,-0.015))
        DirectLabel(parent=self.top_bar, text="MISSION CONTROL", text_align=TextNode.ALeft,
            text_fg=(0.88,0.94,1,1), text_scale=0.057, frameColor=(0,0,0,0),
            pos=(-1.18,0,-0.012))
        DirectLabel(parent=self.top_bar, text="NASA LRO / JPL HORIZONS / SOUTH POLE",
            text_align=TextNode.ARight, text_fg=(0.35,0.75,0.85,1), text_scale=0.043,
            frameColor=(0,0,0,0), pos=(1.57,0,-0.01))


    def _setup_scene_labels(self):
        cyan = (0.18,0.86,1.0,1)
        white = (0.82,0.92,0.98,1)
        self.site_info_frame = DirectFrame(parent=self.aspect2d,
            frameColor=(0.004,0.018,0.034,0.985), frameSize=(-0.43,0.33,-0.24,0.27),
            pos=(1.17,0,0.52))
        self.site_info_title = DirectLabel(parent=self.site_info_frame,
            text="TARGET / SITE TELEMETRY", text_align=TextNode.ALeft, text_fg=cyan,
            text_scale=0.041, frameColor=(0,0,0,0), pos=(-0.38,0,0.21))
        self.site_info_label = DirectLabel(parent=self.site_info_frame, text="SELECT SITE",
            text_align=TextNode.ALeft, text_fg=white, text_scale=0.045, text_wordwrap=25,
            frameColor=(0,0,0,0), pos=(-0.29,0,0.10))
        self.mission_window_frame = DirectFrame(parent=self.aspect2d,
            frameColor=(0.004,0.018,0.034,0.985), frameSize=(-0.43,0.33,-0.31,0.31),
            pos=(1.17,0,-0.13))
        DirectLabel(parent=self.mission_window_frame, text="OPERATIONAL WINDOWS",
            text_align=TextNode.ALeft, text_fg=cyan, text_scale=0.040,
            frameColor=(0,0,0,0), pos=(-0.38,0,0.25))
        self.mission_window_label = DirectLabel(parent=self.mission_window_frame,
            text="Awaiting Horizons data…", text_align=TextNode.ALeft, text_fg=white,
            text_scale=0.038, text_wordwrap=29, frameColor=(0,0,0,0), pos=(-0.38,0,0.15))

        # Pannello scientifico separato: non sovrascrive le finestre operative.
        self.science_status_frame = DirectFrame(
            parent=self.aspect2d,
            frameColor=(0.004,0.018,0.034,0.96),
            frameSize=(-0.43,0.33,-0.20,0.20),
            pos=(1.17,0,-0.585),
        )
        DirectLabel(
            parent=self.science_status_frame,
            text="SCIENCE / TERRAIN STATUS",
            text_align=TextNode.ALeft,
            text_fg=cyan,
            text_scale=0.032,
            frameColor=(0,0,0,0),
            pos=(-0.39,0,0.145),
        )
        self.science_scroll = DirectScrolledFrame(
            parent=self.science_status_frame,
            frameSize=(-0.385, 0.30, -0.145, 0.095),
            canvasSize=(-0.36, 0.26, -2.20, 0.0),
            frameColor=(0,0,0,0),
            scrollBarWidth=0.025,
            verticalScroll_frameColor=(0.02,0.12,0.17,1),
            verticalScroll_thumb_frameColor=(0.08,0.58,0.72,1),
            manageScrollBars=True,
            autoHideScrollBars=True,
            pos=(0,0,0),
        )
        self.science_status_label = DirectLabel(
            parent=self.science_scroll.getCanvas(),
            text="Audit scientifico non ancora eseguito.",
            text_align=TextNode.ALeft,
            text_fg=white,
            text_scale=0.030,
            text_wordwrap=20,
            frameColor=(0,0,0,0),
            pos=(-0.32,0,-0.045),
        )

        # Separatore visivo tra pannello scientifico e grafici.
        science_border = LineSegs("science-status-border")
        science_border.setThickness(2.0)
        science_border.setColor(0.08, 0.72, 0.90, 0.95)

        # Contorno del pannello scientifico.
        science_border.moveTo(0.74, 0, -0.785)
        science_border.drawTo(1.50, 0, -0.785)
        science_border.drawTo(1.50, 0, -0.385)
        science_border.drawTo(0.74, 0, -0.385)
        science_border.drawTo(0.74, 0, -0.785)

        self.science_border_node = self.aspect2d.attachNewNode(
            science_border.create()
        )
        self.science_border_node.setBin("background", 1)

        self.graph_panel = DirectFrame(parent=self.aspect2d,
            frameColor=(0.003,0.012,0.026,0.985), frameSize=(-0.80,0.80,-0.205,0.205),
            pos=(0.02,0,-0.625))
        self.graph_root = self.aspect2d.attachNewNode("astronomy-2d-curves")
        self.graph_axes_root = self.aspect2d.attachNewNode("astronomy-2d-axes")
        self.graph_labels = []
        self.graph_bounds = {"sun": (-0.70,-0.015,-0.735,-0.535),
                             "earth": (0.095,0.78,-0.735,-0.535)}
        self.site_annotation_line = None
        self._set_site_label()
        separator = LineSegs("hud-separator")
        separator.setThickness(1.8)
        separator.setColor(0.08,0.40,0.52,0.85)
        separator.moveTo(-1.65,0,0.805)
        separator.drawTo(1.65,0,0.805)
        self.aspect2d.attachNewNode(separator.create())
        # Etichette di asse e titolo dei grafici sono create dal metodo seguente.
        self._draw_graph_axes()




    def _setup_holographic_hubs(self):
        items = [("SITE TRACKING", self._hub_site_tracking),
                 ("HORIZONS REFRESH", self._hub_horizons),
                 ("DTM STATUS", self._hub_dtm),
                 ("MISSION WINDOWS", self._hub_windows),
                 ("RESET CAMERA", self._hub_view)]
        self.hologram_nodes = []
        xs = [-1.30,-0.65,0.0,0.65,1.30]
        for (label, action), x in zip(items, xs):
            button = DirectButton(parent=self.aspect2d, text=label, text_scale=0.048,
                scale=0.72, textMayChange=False, frameColor=(0.012,0.065,0.090,0.98),
                text_fg=(0.30,0.88,1.0,1), frameSize=(-0.43,0.43,-0.065,0.065),
                pos=(x,0,-0.875), command=action)
            self.hologram_nodes.append(button)



    def _hub_windows(self):
        self._show_science_status("planning")
        self.refresh_astronomy()


    def _hub_view(self):
        self.reset_camera()
        self.update_status("Camera ripristinata sulla vista lunare.")

    def _hub_site_tracking(self):
        self.reset_camera()
        self.update_status(
            f"Site tracking: {self.selected_site}. "
            "Georeferenziazione del modello ancora provvisoria."
        )

    def _hub_horizons(self):
        self.update_status("Aggiornamento effemeridi NASA/JPL Horizons...")
        self.refresh_astronomy()


    def _hub_dtm(self):
        self._show_science_status("dtm")


    def _draw_graph_axes(self):
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
                text_align=TextNode.ALeft, text_fg=color, text_scale=0.051,
                frameColor=(0,0,0,0), pos=(x0,0,z1+0.032))
            self.graph_labels.append(title)
            for hour in (0,12,24,36,48):
                x = x0 + hour/48.0*(x1-x0)
                label = DirectLabel(parent=self.aspect2d, text=str(hour),
                    text_align=TextNode.ACenter, text_fg=(0.65,0.78,0.85,1),
                    text_scale=0.042, frameColor=(0,0,0,0), pos=(x,0,z0-0.024))
                self.graph_labels.append(label)


    def _setup_mouse(self):
        self.accept("wheel_up", self._on_wheel_up)
        self.accept("wheel_down", self._on_wheel_down)
        self.accept("mouse1", self._begin_drag)
        self.accept("mouse1-up", self._end_drag)
        self.accept("escape", self.userExit)

    def _begin_drag(self):
        if self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            self.last_mouse = (m.x, m.y)
            self.dragging = True

    def _end_drag(self):
        self.dragging = False
        self.last_mouse = None

    def _mouse_camera(self, task):
        if self.dragging and self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            if self.last_mouse is not None and self.moon_pivot is not None:
                dx = m.x - self.last_mouse[0]
                dy = m.y - self.last_mouse[1]

                # Rotazione del globo sul suo pivot fisso.
                self.moon_pivot.setH(self.moon_pivot.getH() - dx * 120)
                self.moon_pivot.setP(
                    max(-80, min(80, self.moon_pivot.getP() + dy * 80))
                )

            self.last_mouse = (m.x, m.y)
        return task.cont

    def _zoom(self, direction):
        # Zoom lungo il raggio che passa per il puntatore, senza ricentrare
        # la telecamera dopo ogni rotazione della rotellina.
        if not self.mouseWatcherNode.hasMouse():
            return

        mouse = self.mouseWatcherNode.getMouse()
        near = Point3()
        far = Point3()
        if not self.camLens.extrude(mouse, near, far):
            return

        near_world = self.render.getRelativePoint(self.camera, near)
        far_world = self.render.getRelativePoint(self.camera, far)
        ray = far_world - near_world
        if ray.lengthSquared() < 1e-12:
            return
        ray.normalize()

        old_distance = self.camera_distance
        self.camera_distance = max(7.0, min(38.0, old_distance + direction))
        movement = old_distance - self.camera_distance
        if abs(movement) < 1e-9:
            return

        # Muovendo la camera lungo il raggio del mouse, il punto indicato
        # resta nella stessa direzione dello schermo durante lo zoom.
        camera_pos = self.camera.getPos(self.render)
        self.camera.setPos(self.render, camera_pos + ray * movement)

    def reset_camera(self):
        self.camera_distance = 13.2
        self.camera.setPos(self.moon_center.x, -self.camera_distance,
                           self.moon_center.z + 0.20)
        self.camera.lookAt(self.moon_center)


    def _animate(self, task):
        if self.moon_pivot is not None:
            self.moon_pivot.setH(self.moon_pivot.getH() + 0.025)
        return task.cont

    def update_status(self, message):
        if hasattr(self, "status_label"):
            self.status_label["text"] = message
        else:
            print(message)

    def on_site_changed(self, name):
        self.selected_site = name
        self._set_site_label()
        self.update_status(
            f"Sito selezionato: {name}. Il centro della Luna resta fisso; "
            "il globo viene ruotato per portare il sito verso la camera. "
            "Orientamento geografico da validare sul modello NASA."
        )

    def _set_site_label(self):
        try:
            lat, lon = site_coordinates(self.selected_site)
            self.site_label.setPythonTag("coordinates", (lat, lon))

            if self.site_marker is not None and not self.site_marker.isEmpty():
                self.site_marker.removeNode()

            # Punto di riferimento sulla sfera. Il frame geografico del GLB
            # resta da validare, quindi la posizione è indicativa.
            lat_r = math.radians(lat)
            lon_r = math.radians(lon)
            radius = self.moon_radius * 1.006
            x = radius * math.cos(lat_r) * math.cos(lon_r)
            y = radius * math.cos(lat_r) * math.sin(lon_r)
            z = radius * math.sin(lat_r)

            self.site_marker = self.moon_pivot.attachNewNode(
                "selected-site-anchor"
            )
            self.site_marker.setPos(x, y, z)

            self.site_info_label["text"] = (
                f"SITE  |  {self.selected_site.upper()}\n"
                f"LATITUDE   {lat:+.4f} deg\n"
                f"LONGITUDE  {lon:+.4f} deg\n"
                "ELEVATION  N/A\n"
                "GEOREFERENCE  NOT VERIFIED"
            )
        except Exception as exc:
            self.update_status(f"Impossibile aggiornare il sito: {exc}")

    def _update_site_annotation(self, task):
        # Marker HUD: mai nella fascia inferiore riservata ai grafici.
        if self.site_marker is None or self.site_marker.isEmpty():
            return task.cont

        for node in getattr(self, "site_pulse_nodes", []):
            if not node.isEmpty():
                node.removeNode()
        self.site_pulse_nodes = []

        point_camera = self.site_marker.getPos(self.camera)
        projected = Point2()
        visible = self.camLens.project(point_camera, projected)
        if not visible or point_camera.y <= 0:
            return task.cont

        aspect = self.getAspectRatio()
        tip_x = projected.x * aspect
        tip_z = projected.y

        # La fascia dei grafici non deve contenere il marker.
        if -0.76 <= tip_x <= 0.84 and tip_z <= -0.515:
            return task.cont

        # Non disegnare indicatori fuori dalla zona centrale della scena.
        if not (-0.98 <= tip_x <= 0.98 and -0.52 <= tip_z <= 0.78):
            return task.cont

        phase = task.time * 2.4
        for index in range(2):
            pulse = (phase + index * math.pi) % (2 * math.pi)
            radius = 0.016 + 0.012 * (0.5 - 0.5 * math.cos(pulse))
            alpha = 0.45 + 0.45 * (0.5 + 0.5 * math.cos(pulse))

            ring = LineSegs(f"site-target-ring-{index}")
            ring.setThickness(1.5)
            ring.setColor(0.12, 0.90, 1.0, alpha)

            for step in range(41):
                angle = 2.0 * math.pi * step / 40
                x = tip_x + radius * math.cos(angle)
                z = tip_z + radius * math.sin(angle)
                if step == 0:
                    ring.moveTo(x, 0, z)
                else:
                    ring.drawTo(x, 0, z)

            self.site_pulse_nodes.append(
                self.aspect2d.attachNewNode(ring.create())
            )

        return task.cont



    def _audit_dtm_metadata(self):
        candidates = []
        terrain = ROOT / "data" / "terrain"
        if terrain.exists():
            for pattern in ("*.tif", "*.tiff", "*.img", "*.jp2"):
                candidates.extend(terrain.rglob(pattern))
        lines = ["DTM / TERRAIN AUDIT"]
        if not candidates:
            return "\\n".join(lines + [
                "Raster DTM: NON TROVATO",
                "Georeferenziazione: NON VERIFICABILE",
                "Pendenze e profili: non calcolati"
            ])
        lines.append(f"Raster candidati: {len(candidates)}")
        try:
            import rasterio
            for path in candidates[:10]:
                try:
                    with rasterio.open(path) as ds:
                        lines.append(f"{path.name}: {ds.width} x {ds.height}")
                        lines.append(f"CRS={ds.crs or 'ASSENTE'}")
                        lines.append(f"Pixel={ds.res}; NoData={ds.nodata}")
                except Exception as exc:
                    lines.append(f"{path.name}: errore lettura: {exc}")
            lines.append("CRS lunare: da verificare rispetto ai metadati originali.")
            lines.append("Pendenze, ombre e sicurezza: non certificati.")
        except ImportError:
            lines.append("rasterio non installato: metadati raster non letti.")
        return "\\n".join(lines)

    def _pointer_over_science_panel(self):
        """True se il puntatore si trova sopra il pannello scientifico."""
        if not self.mouseWatcherNode.hasMouse():
            return False

        mouse = self.mouseWatcherNode.getMouse()
        x, y = mouse.getX(), mouse.getY()
        return 0.74 <= x <= 1.50 and -0.84 <= y <= -0.36

    def _science_scroll_wheel(self, direction):
        """Scorre il pannello scientifico; restituisce True se gestito."""
        widget = getattr(self, "science_scroll", None)
        if widget is None:
            return False

        bar = getattr(widget, "verticalScroll", None)
        if bar is None:
            return False

        try:
            current = float(bar["value"])
            bar["value"] = max(0.0, min(1.0, current + direction * 0.12))
            return True
        except (KeyError, TypeError, ValueError, AttributeError):
            return False

    def _on_wheel_up(self):
        if self._pointer_over_science_panel():
            if self._science_scroll_wheel(-1):
                return
        self._zoom(-1)

    def _on_wheel_down(self):
        if self._pointer_over_science_panel():
            if self._science_scroll_wheel(1):
                return
        self._zoom(1)

    def _show_science_status(self, topic):
        if topic == "dtm":
            message = self._audit_dtm_metadata()
        elif topic == "planning":
            message = (
                "MISSION CONSTRAINTS\\n"
                "Soglie attuali: Sole >= 5°, Terra >= 5°.\\n"
                "Energia, termica, radio e mobilità: non modellati.\\n"
                "Sicurezza del sito: non certificata."
            )
        else:
            message = (
                "SUN / EARTH GEOMETRY\\n"
                "Effemeridi: disponibili tramite Horizons.\\n"
                "Ombre e orizzonte del terreno: non calcolati.\\n"
                "Linea di vista radio: non verificata."
            )
        # I messaggi scientifici non devono sovrascrivere
        # il riepilogo delle finestre operative.
        if hasattr(self, "science_status_label"):
            self.science_status_label["text"] = message
        self.update_status("Pannello scientifico: " + topic.upper())

    def _clear_plot(self):
        for node in self.observation_nodes:
            if not node.isEmpty():
                node.removeNode()
        self.observation_nodes.clear()

    def refresh_astronomy(self):
        try:
            date_text = self.date_entry.get().strip()
            start_time = datetime.strptime(
                date_text, "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)

            duration_hours = int(self.duration_entry.get().strip())
            science_priority = int(
                self.science_priority_entry.get().strip()
            )
            engineering_priority = int(
                self.engineering_priority_entry.get().strip()
            )
            min_sun_elevation_deg = float(
                self.sun_threshold_entry.get().strip()
            )
            min_earth_elevation_deg = float(
                self.earth_threshold_entry.get().strip()
            )
            if not -90.0 <= min_sun_elevation_deg <= 90.0:
                raise ValueError("Soglia Sole ammessa: da -90 a 90 gradi.")
            if not -90.0 <= min_earth_elevation_deg <= 90.0:
                raise ValueError("Soglia Terra ammessa: da -90 a 90 gradi.")
            if not 1 <= duration_hours <= 720:
                raise ValueError("Durata ammessa: da 1 a 720 ore.")
            if not 1 <= science_priority <= 5:
                raise ValueError("Priorità scientifica ammessa: da 1 a 5.")
            if not 1 <= engineering_priority <= 5:
                raise ValueError(
                    "Priorità ingegneristica ammessa: da 1 a 5."
                )

            self.current_mission_parameters = {
                "duration_hours": duration_hours,
                "science_priority": science_priority,
                "engineering_priority": engineering_priority,
                "min_sun_elevation_deg": min_sun_elevation_deg,
                "min_earth_elevation_deg": min_earth_elevation_deg,
            }

            lat, lon = site_coordinates(self.selected_site)
            self.update_status("Recupero effemeridi NASA/JPL Horizons...")
            self._clear_plot()

            sun = query_observations(
                "10", lat, lon, start_time, hours=duration_hours, step="1h"
            )
            earth = query_observations(
                "399", lat, lon, start_time, hours=duration_hours, step="1h"
            )

            self._plot_observations(sun, (1.0, 0.70, 0.20, 1), -0.2)
            self._plot_observations(earth, (0.20, 0.85, 1.0, 1), 0.18)

            count = min(len(sun), len(earth))
            sun = sun[:count]
            earth = earth[:count]

            sun_values = [
                o.elevation_deg for o in sun
                if o.elevation_deg is not None
            ]
            earth_values = [
                o.elevation_deg for o in earth
                if o.elevation_deg is not None
            ]

            if not sun_values or not earth_values:
                raise ValueError("Horizons non ha restituito elevazioni valide.")

            windows = find_operational_windows(
                [o.elevation_deg for o in sun],
                [o.elevation_deg for o in earth],
                min_sun_elevation_deg=min_sun_elevation_deg,
                min_earth_elevation_deg=min_earth_elevation_deg,
            )

            ranked_windows = rank_operational_windows(
                windows,
                [o.elevation_deg for o in sun],
                [o.elevation_deg for o in earth],
                MissionConfig(
                    site=self.selected_site,
                    start_date_utc=date_text,
                    duration_hours=duration_hours,
                    science_priority=science_priority,
                    engineering_priority=engineering_priority,
                    min_sun_elevation_deg=min_sun_elevation_deg,
                    min_earth_elevation_deg=min_earth_elevation_deg,
                ),
            )
            self.last_mission_windows = [
                {
                    **candidate,
                    "start_utc": sun[candidate["start_index"]].time_utc,
                    "end_utc": sun[candidate["end_index"]].time_utc,
                }
                for candidate in ranked_windows
            ]
            self.last_astronomy_status = "computed"

            lines = [
                f"SITO: {self.selected_site}  |  UTC: {date_text}",
                f"ORIZZONTE: {duration_hours} h  |  CAMPIONI: {count}",
                f"SOLE: {min(sun_values):.2f}°–{max(sun_values):.2f}°",
                f"TERRA: {min(earth_values):.2f}°–{max(earth_values):.2f}°",
            ]

            def format_time(value):
                try:
                    parsed = datetime.fromisoformat(
                        value.replace("Z", "+00:00")
                    )
                    return parsed.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError, AttributeError):
                    return str(value)

            if not windows:
                lines.extend([
                    "FINESTRE SIMULTANEE: 0",
                    "Motivo: nessun campione soddisfa entrambe le soglie.",
                ])
            else:
                lines.append(f"FINESTRE SIMULTANEE: {len(windows)}")
                for w in windows[:3]:
                    begin = sun[w.start_index].time_utc
                    end = sun[w.end_index].time_utc

                    try:
                        t0 = datetime.fromisoformat(
                            begin.replace("Z", "+00:00")
                        )
                        t1 = datetime.fromisoformat(
                            end.replace("Z", "+00:00")
                        )
                        elapsed_hours = (
                            t1 - t0
                        ).total_seconds() / 3600.0
                        duration = f"{elapsed_hours:g} h"
                    except (ValueError, TypeError):
                        duration = f"{w.duration_samples} campioni"

                    lines.append(
                        f"{format_time(begin)} - {format_time(end)} UTC "
                        f"| {duration} | {w.duration_samples} campioni"
                    )

                if len(windows) > 3:
                    lines.append(f"... altre {len(windows) - 3} finestre")

            lines.append(
                f"SOGLIE: Sole >= {min_sun_elevation_deg:g}° | "
                f"Terra >= {min_earth_elevation_deg:g}°"
            )
            if windows:
                lines.append(f"FINESTRE VALIDE: {len(windows)}")
            else:
                lines.append("FINESTRE VALIDE: 0")
            lines.append("Geometria preliminare; terreno e radio non verificati.")

            # Mostra un riepilogo breve, mantenendo i calcoli completi.
            self.mission_window_label["text"] = "\n".join(lines[:6])
            self.update_status(
                f"Horizons aggiornato: {self.selected_site}, {date_text}; "
                f"{count} campioni confrontati."
            )

        except Exception as exc:
            message = f"Errore effemeridi/finestre: {exc}"
            if hasattr(self, "mission_window_label"):
                self.mission_window_label["text"] = message
            self.update_status(message)
            traceback.print_exc()

    def export_mission_plan(self):
        """Esporta un piano preliminare con i risultati astronomici disponibili."""
        try:
            date_text = self.date_entry.get().strip()
            config = MissionConfig(
                site=self.selected_site,
                start_date_utc=date_text,
                duration_hours=int(self.duration_entry.get().strip()),
                science_priority=int(
                    self.science_priority_entry.get().strip()
                ),
                engineering_priority=int(
                    self.engineering_priority_entry.get().strip()
                ),
                min_sun_elevation_deg=float(
                    self.sun_threshold_entry.get().strip()
                ),
                min_earth_elevation_deg=float(
                    self.earth_threshold_entry.get().strip()
                ),
            )
            if not -90.0 <= config.min_sun_elevation_deg <= 90.0:
                raise ValueError("Soglia Sole ammessa: da -90 a 90 gradi.")
            if not -90.0 <= config.min_earth_elevation_deg <= 90.0:
                raise ValueError("Soglia Terra ammessa: da -90 a 90 gradi.")
            expected = {
                "duration_hours": config.duration_hours,
                "science_priority": config.science_priority,
                "engineering_priority": config.engineering_priority,
                "min_sun_elevation_deg": config.min_sun_elevation_deg,
                "min_earth_elevation_deg": config.min_earth_elevation_deg,
            }
            windows_match = (
                getattr(self, "last_astronomy_status", "not_run") == "computed"
                and getattr(self, "current_mission_parameters", None) == expected
            )
            plan = build_mission_plan(
                config,
                valid_sites=self.site_names,
                observations_status=(
                    "computed" if windows_match
                    else "not_run_or_config_mismatch"
                ),
                operational_windows=(
                    self.last_mission_windows if windows_match else []
                ),
            )

            if not windows_match:
                plan["notice"] += (
                    " Finestre omesse: eseguire RUN HORIZONS con la "
                    "configurazione corrente prima di esportare."
                )

            if not windows_match:
                plan["notice"] += (
                    " Attenzione: le effemeridi non sono ancora state "
                    "calcolate in questa sessione."
                )

            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            safe_site = "".join(
                c if c.isalnum() or c in "-_" else "_"
                for c in self.selected_site
            )
            output = ROOT / "data" / "missions" / (
                f"mission_{safe_site}_{date_text}_{stamp}.json"
            )
            saved = save_mission_plan(plan, output)
            self.update_status(f"Piano preliminare esportato: {saved.name}")
            print(f"[MISSION PLAN] Salvato: {saved}")
            print(
                f"[MISSION PLAN] Stato astronomia: "
                f"{plan['astronomy']['status']} | "
                f"finestre: {plan['astronomy']['window_count']}"
            )
        except Exception as exc:
            self.update_status(f"Errore esportazione piano: {exc}")
            traceback.print_exc()

    def _plot_observations(self, observations, color, y_offset):
        rows = observations
        if isinstance(observations, dict):
            rows = observations.get("observations", observations.get("data", []))
        elif hasattr(observations, "observations"):
            rows = observations.observations
        rows = list(rows or [])

        values = []
        for row in rows:
            if isinstance(row, dict):
                elevation = row.get("elevation_deg", row.get("elevation"))
            else:
                elevation = getattr(
                    row, "elevation_deg", getattr(row, "elevation", None)
                )
            try:
                values.append(
                    float(elevation) if elevation is not None else None
                )
            except (TypeError, ValueError):
                values.append(None)

        key = "sun" if y_offset < 0 else "earth"
        x0, x1, z0, z1 = self.graph_bounds[key]
        valid = [(i, v) for i, v in enumerate(values) if v is not None]
        if len(valid) < 2:
            return

        denominator = max(1, len(values) - 1)
        points = []
        for i, elevation in valid:
            x = x0 + (x1 - x0) * i / denominator
            # Limita solo la visualizzazione, non i dati scientifici.
            elevation_for_plot = max(0.0, min(10.0, elevation))
            z = z0 + (elevation_for_plot / 10.0) * (z1 - z0)
            points.append((x, 0, z))

        curve = LineSegs(f"{key}-elevation-curve-zoom")
        curve.setThickness(2.2)
        curve.setColor(*color)
        curve.moveTo(*points[0])
        for point in points[1:]:
            curve.drawTo(*point)

        node = self.graph_root.attachNewNode(curve.create())
        self.observation_nodes.append(node)

def main():
    app = LunarMission3D()
    app.run()


if __name__ == "__main__":
    main()

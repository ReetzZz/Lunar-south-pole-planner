# Last updated: 2026-11-14
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timezone
import math
import random
import threading
import json
from pathlib import Path
from tkinter import messagebox
from src.astronomy import query_observations, SITES, AstronomyError
from src.data_quality import audit_raster
from src.psystem_adapter import MissionJournal
from src.mission_planning import SiteMetrics, SiteWeights, score_site, find_operational_windows
from src.rover_planning import plan_rover_path
from src.mission_report import build_mission_report, write_mission_report
from src.site_comparison import compare_candidate_sites, write_comparison_report

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except ImportError:
    raise SystemExit(
        "Matplotlib non disponibile. Installa python3-matplotlib."
    )




class LunarPlanner:
    def __init__(self, root):
        self.root = root
        self.root.title("Lunar South Pole Mission Planner")
        self.root.geometry("1200x780")
        self.root.minsize(950, 650)

        self.bg = "#101820"
        self.panel = "#1b2838"
        self.fg = "#eaf2f8"
        self.accent = "#48cae4"

        self.root.configure(bg=self.bg)

        self.site_var = tk.StringVar(value="Shackleton")
        self.date_var = tk.StringVar(
            value=datetime.now().strftime("%Y-%m-%d")
        )
        self.science_var = tk.IntVar(value=5)
        self.engineering_var = tk.IntVar(value=5)
        self.duration_var = tk.IntVar(value=48)
        self.last_horizons_results = []
        self.last_horizons_site = None

        self.build_ui()
        self.update_simulation()

    def build_ui(self):
        header = tk.Frame(self.root, bg=self.bg, padx=20, pady=15)
        header.pack(fill="x")

        tk.Label(
            header,
            text="LUNAR SOUTH POLE",
            font=("DejaVu Sans", 24, "bold"),
            fg=self.accent,
            bg=self.bg,
        ).pack(anchor="w")

        tk.Label(
            header,
            text="MISSION PLANNER  |  SCIENCE • ENGINEERING • P-SYSTEM",
            font=("DejaVu Sans", 10),
            fg=self.fg,
            bg=self.bg,
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(self.root, bg=self.bg, padx=15, pady=5)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=self.panel, padx=15, pady=15)
        sidebar.pack(side="left", fill="y", padx=(0, 12))

        tk.Label(
            sidebar, text="MISSION PARAMETERS",
            font=("DejaVu Sans", 12, "bold"),
            bg=self.panel, fg=self.accent
        ).pack(anchor="w", pady=(0, 12))

        self.add_label(sidebar, "Candidate landing site")
        site_box = ttk.Combobox(
            sidebar,
            textvariable=self.site_var,
            values=list(SITES.keys()),
            state="readonly",
            width=23,
        )
        site_box.pack(fill="x", pady=(0, 12))
        site_box.bind("<<ComboboxSelected>>", self.on_change)

        self.add_label(sidebar, "Planning date (YYYY-MM-DD)")
        date_entry = tk.Entry(
            sidebar, textvariable=self.date_var, width=25
        )
        date_entry.pack(fill="x", pady=(0, 12))

        self.add_label(sidebar, "Planning horizon (hours)")
        tk.Scale(
            sidebar,
            from_=6, to=168, resolution=6,
            orient="horizontal",
            variable=self.duration_var,
            bg=self.panel, fg=self.fg,
            highlightthickness=0,
            command=lambda _: self.update_simulation(),
        ).pack(fill="x", pady=(0, 12))

        self.add_label(sidebar, "Science priority")
        tk.Scale(
            sidebar, from_=1, to=5, orient="horizontal",
            variable=self.science_var,
            bg=self.panel, fg=self.fg,
            highlightthickness=0,
            command=lambda _: self.update_simulation(),
        ).pack(fill="x", pady=(0, 12))

        self.add_label(sidebar, "Engineering priority")
        tk.Scale(
            sidebar, from_=1, to=5, orient="horizontal",
            variable=self.engineering_var,
            bg=self.panel, fg=self.fg,
            highlightthickness=0,
            command=lambda _: self.update_simulation(),
        ).pack(fill="x", pady=(0, 12))

        tk.Button(
            sidebar,
            text="RUN SIMULATION",
            command=self.update_simulation,
            bg=self.accent,
            fg="#07131a",
            activebackground="#90e0ef",
            font=("DejaVu Sans", 10, "bold"),
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=(10, 6))

        tk.Button(
            sidebar,
            text="LUNAR GLOBE 3D",
            command=self.open_3d_globe,
            bg="#063b50",
            fg="#7df9ff",
            relief="flat",
            padx=10, pady=9,
        ).pack(fill="x", pady=(4, 8))

        tk.Button(
            sidebar,
            text="COMPARE CANDIDATE SITES",
            command=self.compare_sites,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="P-SYSTEM JOURNAL",
            command=self.show_psystem,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="COORDINAMENTO MULTI-ROVER",
            command=self.show_multi_rover_coordinator,
            bg="#24566b",
            fg="white",
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="ANALISI LOCALE PENDENZA / RUGOSITÀ",
            command=self.analyze_local_terrain,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="STIMA ILLUMINAZIONE DA ORIZZONTE (DIAGNOSTICA)",
            command=self.analyze_solar_illumination,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="PROFILO ORIZZONTE LOCALE (DIAGNOSTICO)",
            command=self.analyze_local_horizon,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="AUDIT DEM LUNARI",
            command=self.audit_dem,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)
        tk.Button(
            sidebar,
            text="FINESTRE OPERATIVE REALI",
            command=self.show_operational_windows,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="PIANIFICA PERCORSO ROVER",
            command=self.open_rover_planner,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="STIMA ENERGETICA PERCORSO ROVER",
            command=self.assess_rover_energy,
            bg="#24566b",
            fg="white",
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="SCORING SITO CON DATI REALI",
            command=self.score_current_site,
            bg="#334b60",
            fg=self.fg,
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="ESPORTA RAPPORTO MISSIONE",
            command=self.export_mission_report,
            bg="#24566b",
            fg="white",
            relief="flat",
            padx=10, pady=8,
        ).pack(fill="x", pady=4)

        tk.Button(
            sidebar,
            text="AGGIORNA DATI NASA/JPL",
            command=self.refresh_horizons,
            bg="#007f8b",
            fg="white",
            activebackground="#00a6b2",
            font=("DejaVu Sans", 10, "bold"),
            relief="flat",
            padx=10,
            pady=8,
        ).pack(fill="x", pady=(10, 4))

        tk.Button(
            sidebar,
            text="APRI GRAFICO NASA/JPL",
            command=self.open_horizons_window,
            bg="#24566b",
            fg="white",
            activebackground="#367b92",
            font=("DejaVu Sans", 9, "bold"),
            relief="flat",
            padx=10,
            pady=8,
        ).pack(fill="x", pady=(4, 4))

        self.status = tk.Label(
            sidebar,
            text="MODE: DEMONSTRATION",
            bg=self.panel, fg="#ffd166",
            font=("DejaVu Sans", 9, "bold"),
        )
        self.status.pack(anchor="w", pady=(20, 0))

        main = tk.Frame(body, bg=self.bg)
        main.pack(side="left", fill="both", expand=True)

        self.site_title = tk.Label(
            main, text="", bg=self.bg, fg=self.fg,
            font=("DejaVu Sans", 17, "bold"),
        )
        self.site_title.pack(anchor="w", pady=(0, 10))

        cards = tk.Frame(main, bg=self.bg)
        cards.pack(fill="x", pady=(0, 10))

        self.lat_card = self.make_card(cards, "LATITUDE")
        self.lon_card = self.make_card(cards, "LONGITUDE")
        self.light_card = self.make_card(cards, "LIGHT INDEX")
        self.comm_card = self.make_card(cards, "EARTH VISIBILITY")

        self.figure = Figure(figsize=(8, 3.8), dpi=100)
        self.figure.patch.set_facecolor(self.bg)
        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)

        for ax in (self.ax1, self.ax2):
            ax.set_facecolor(self.panel)
            ax.tick_params(colors=self.fg)
            for spine in ax.spines.values():
                spine.set_color("#526579")
            ax.xaxis.label.set_color(self.fg)
            ax.yaxis.label.set_color(self.fg)
            ax.title.set_color(self.fg)
            ax.grid(True, alpha=0.15)

        self.canvas = FigureCanvasTkAgg(self.figure, master=main)
        self.canvas.get_tk_widget().pack(fill="x", expand=False)

        # Real astronomical observations: separate from demo curves.
        self.real_figure = Figure(figsize=(10, 5.0), dpi=100)
        self.real_figure.patch.set_facecolor(self.bg)
        self.real_ax = self.real_figure.add_subplot(111)
        self.real_ax.set_facecolor(self.panel)
        self.real_ax.set_title(
            "NASA/JPL Horizons — apparent elevation",
            color=self.fg,
        )
        self.real_ax.set_xlabel("UTC", color=self.fg)
        self.real_ax.set_ylabel("Elevation (degrees)", color=self.fg)
        self.real_ax.tick_params(colors=self.fg)
        self.real_ax.axhline(0, color="#ffd166", linestyle="--", linewidth=1)
        self.real_ax.grid(True, alpha=0.15)
        for spine in self.real_ax.spines.values():
            spine.set_color("#526579")

        self.real_canvas = FigureCanvasTkAgg(
            self.real_figure, master=main
        )
        self.real_canvas_widget = self.real_canvas.get_tk_widget()
        self.real_canvas_widget.configure(height=240)
        self.real_canvas_widget.pack(fill="x", expand=False)

        # Real Horizons observations, separate from demonstration curves.
        horizons_frame = tk.Frame(main, bg=self.panel, padx=10, pady=8)
        horizons_frame.pack(fill="x", pady=(8, 6))

        tk.Label(
            horizons_frame,
            text="DATI ASTRONOMICI NASA/JPL HORIZONS",
            bg=self.panel,
            fg=self.accent,
            font=("DejaVu Sans", 11, "bold"),
        ).pack(anchor="w")

        self.horizons_status = tk.Label(
            horizons_frame,
            text="Nessuna osservazione caricata. Premi AGGIORNA DATI NASA/JPL.",
            bg=self.panel,
            fg="#ffd166",
            font=("DejaVu Sans", 9),
            anchor="w",
            justify="left",
        )
        self.horizons_status.pack(fill="x", pady=(4, 6))

        columns = ("object", "utc", "azimuth", "elevation")
        self.horizons_table = ttk.Treeview(
            horizons_frame,
            columns=columns,
            show="headings",
            height=5,
        )
        self.horizons_table.heading("object", text="Oggetto")
        self.horizons_table.heading("utc", text="Data/ora UTC")
        self.horizons_table.heading("azimuth", text="Azimut (°)")
        self.horizons_table.heading("elevation", text="Elevazione (°)")

        self.horizons_table.column("object", width=100, anchor="w")
        self.horizons_table.column("utc", width=200, anchor="w")
        self.horizons_table.column("azimuth", width=100, anchor="e")
        self.horizons_table.column("elevation", width=120, anchor="e")
        self.horizons_table.pack(fill="x")

        self.footer = tk.Label(
            self.root,
            text=(
                "DEMO DATA ONLY — no validated lunar ephemerides, "
                "terrain horizon or radio link model yet."
            ),
            bg="#263746", fg="#ffd166",
            font=("DejaVu Sans", 9), padx=10, pady=7,
        )
        self.footer.pack(fill="x", side="bottom")

    def add_label(self, parent, text):
        tk.Label(
            parent, text=text, bg=self.panel, fg=self.fg,
            font=("DejaVu Sans", 9),
        ).pack(anchor="w", pady=(3, 4))

    def make_card(self, parent, title):
        frame = tk.Frame(parent, bg=self.panel, padx=12, pady=10)
        frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(
            frame, text=title, bg=self.panel, fg="#a9c1d3",
            font=("DejaVu Sans", 8, "bold"),
        ).pack(anchor="w")
        value = tk.Label(
            frame, text="--", bg=self.panel, fg=self.accent,
            font=("DejaVu Sans", 16, "bold"),
        )
        value.pack(anchor="w", pady=(5, 0))
        return value

    def on_change(self, _event=None):
        self.update_simulation()

    def update_simulation(self):
        name = self.site_var.get()
        lat, lon = SITES[name]
        self.site_title.config(text=f"Selected site: {name}")
        self.lat_card.config(text=f"{lat:.2f}°")
        self.lon_card.config(text=f"{lon:.2f}°")

        hours = list(range(0, self.duration_var.get() + 1))
        seed = sum(map(ord, name))
        seed += sum(map(ord, self.date_var.get()))
        rng = random.Random(seed)

        # Illustrative curves only, NOT lunar astronomical predictions.
        light = [
            max(0, min(100, 50 + 38 * math.sin(
                2 * math.pi * h / max(1, self.duration_var.get()) - 0.8
            ) + rng.uniform(-3, 3)))
            for h in hours
        ]
        earth = [
            max(0, min(100, 75 + 20 * math.sin(
                2 * math.pi * h / max(1, self.duration_var.get()) + 0.7
            ) + rng.uniform(-2, 2)))
            for h in hours
        ]

        self.light_card.config(text="DEMO")
        self.comm_card.config(text="DEMO")

        sw = self.science_var.get()
        ew = self.engineering_var.get()
        score = [
            (sw * l + ew * e) / (sw + ew)
            for l, e in zip(light, earth)
        ]

        self.ax1.clear()
        self.ax1.set_facecolor(self.panel)
        self.ax1.plot(hours, light, color="#ffd166", label="Light index")
        self.ax1.plot(hours, earth, color="#48cae4", label="Earth visibility")
        self.ax1.set_title("DEMO ONLY — not a lunar ephemeris")
        self.ax1.set_ylabel("Index (%)")
        self.ax1.set_ylim(0, 100)
        self.ax1.legend(facecolor=self.panel, labelcolor=self.fg)
        self.ax1.grid(True, alpha=0.15)

        self.ax2.clear()
        self.ax2.set_facecolor(self.panel)
        self.ax2.plot(hours, score, color="#80ed99")
        self.ax2.fill_between(hours, score, alpha=0.12, color="#80ed99")
        self.ax2.set_title("DEMO ONLY — illustrative priority balance")
        self.ax2.set_xlabel("Hours from simulation start")
        self.ax2.set_ylabel("Illustrative score")
        self.ax2.set_ylim(0, 100)
        self.ax2.grid(True, alpha=0.15)

        for ax in (self.ax1, self.ax2):
            ax.tick_params(colors=self.fg)
            for spine in ax.spines.values():
                spine.set_color("#526579")
            ax.xaxis.label.set_color(self.fg)
            ax.yaxis.label.set_color(self.fg)
            ax.title.set_color(self.fg)

        self.figure.tight_layout()
        self.canvas.draw_idle()

    def refresh_horizons(self):
        """Retrieve real Horizons data without blocking the UI."""
        name = self.site_var.get()
        if name not in SITES:
            messagebox.showerror("Horizons", "Sito non riconosciuto.")
            return

        latitude, longitude = SITES[name][:2]

        try:
            selected_date = datetime.strptime(
                self.date_var.get().strip(), "%Y-%m-%d"
            )
        except ValueError:
            messagebox.showerror(
                "Data non valida",
                "Inserisci la data nel formato YYYY-MM-DD, ad esempio 2026-10-22."
            )
            return

        start = selected_date.replace(tzinfo=timezone.utc)
        hours_to_query = max(1, min(int(self.duration_var.get()), 168))

        self.horizons_status.config(
            text=f"Richiesta NASA/JPL in corso per {name}...",
            fg="#ffd166",
        )

        def worker():
            results = []
            errors = []

            for target, label in (("10", "Sole"), ("399", "Terra")):
                try:
                    observations = query_observations(
                        target,
                        latitude,
                        longitude,
                        start,
                        hours=hours_to_query,
                        step="1h",
                    )
                    results.extend(
                        (label, row) for row in observations
                    )
                except Exception as exc:
                    errors.append(f"{label}: {exc}")

            self.root.after(
                0, lambda: self._show_horizons_results(
                    name, results, errors
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _show_horizons_results(self, site_name, results, errors):
        self.last_horizons_results = list(results)
        self.last_horizons_site = site_name
        for item in self.horizons_table.get_children():
            self.horizons_table.delete(item)

        self.real_ax.clear()
        self.real_ax.set_facecolor(self.panel)
        self.real_ax.set_title(
            f"NASA/JPL Horizons — {site_name}",
            color=self.fg,
        )
        self.real_ax.set_xlabel("UTC", color=self.fg)
        self.real_ax.set_ylabel("Apparent elevation (degrees)", color=self.fg)
        self.real_ax.axhline(
            0, color="#ffd166", linestyle="--", linewidth=1,
            label="Geometric horizon (0°)"
        )
        self.real_ax.grid(True, alpha=0.15)
        for spine in self.real_ax.spines.values():
            spine.set_color("#526579")

        for label in ("Sole", "Terra"):
            series = [
                row for obj, row in results if obj == label
            ]
            if series:
                self.real_ax.plot(
                    [row.time_utc for row in series],
                    [row.elevation_deg for row in series],
                    marker="o",
                    markersize=3,
                    label=label,
                )

        import matplotlib.dates as mdates

        self.real_ax.xaxis.set_major_locator(
            mdates.AutoDateLocator(minticks=4, maxticks=8)
        )
        self.real_ax.xaxis.set_major_formatter(
            mdates.DateFormatter("%m-%d %H:%M", tz=timezone.utc)
        )
        self.real_ax.tick_params(colors=self.fg, labelsize=8)
        self.real_ax.tick_params(axis="x", labelrotation=25)
        self.real_ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.28),
            ncol=3,
            facecolor=self.panel,
            labelcolor=self.fg,
            fontsize=8,
        )
        self.real_figure.subplots_adjust(
            left=0.12, right=0.98, top=0.88, bottom=0.42
        )
        self.real_canvas.draw_idle()

        for label, row in results:
            self.horizons_table.insert(
                "",
                "end",
                values=(
                    label,
                    row.time_utc.replace("T", " ")[:19],
                    f"{row.azimuth_deg:.3f}",
                    f"{row.elevation_deg:.3f}",
                ),
            )

        if errors:
            self.horizons_status.config(
                text=(
                    f"{site_name}: dati ricevuti parzialmente o assenti. "
                    + " | ".join(errors)
                ),
                fg="#ffb4a2",
            )
        elif results:
            self.horizons_status.config(
                text=(
                    f"{site_name}: {len(results)} osservazioni ricevute "
                    "da NASA/JPL Horizons. UTC; azimut ed elevazione "
                    "apparente rispetto all'orizzonte geometrico."
                ),
                fg="#80ed99",
            )
        else:
            self.horizons_status.config(
                text="Horizons non ha restituito osservazioni utilizzabili.",
                fg="#ffb4a2",
            )

    def open_horizons_window(self):
        """Open a large, dedicated window for real Horizons observations."""
        if not hasattr(self, "horizons_table"):
            messagebox.showinfo(
                "NASA/JPL Horizons",
                "Prima aggiorna i dati con il pulsante AGGIORNA DATI NASA/JPL.",
            )
            return

        window = tk.Toplevel(self.root)
        window.title("NASA/JPL Horizons — elevazione apparente")
        window.geometry("1200x760")
        window.configure(bg=self.bg)

        title = tk.Label(
            window,
            text="OSSERVAZIONI ASTRONOMICHE NASA/JPL HORIZONS",
            bg=self.bg,
            fg=self.accent,
            font=("DejaVu Sans", 14, "bold"),
        )
        title.pack(anchor="w", padx=16, pady=(12, 4))

        note = tk.Label(
            window,
            text=(
                "Elevazione apparente in gradi rispetto all'orizzonte geometrico. "
                "Non include ostacoli del terreno lunare."
            ),
            bg=self.bg,
            fg=self.fg,
            font=("DejaVu Sans", 9),
        )
        note.pack(anchor="w", padx=16, pady=(0, 8))

        figure = Figure(figsize=(12, 5.8), dpi=100)
        figure.patch.set_facecolor(self.bg)
        ax = figure.add_subplot(111)
        ax.set_facecolor(self.panel)
        ax.set_title("Sole e Terra — elevazione apparente", color=self.fg)
        ax.set_xlabel("Data e ora UTC", color=self.fg)
        ax.set_ylabel("Elevazione (°)", color=self.fg)
        ax.axhline(
            0, color="#ffd166", linestyle="--", linewidth=1.2,
            label="Orizzonte geometrico (0°)"
        )
        ax.grid(True, alpha=0.2)
        ax.tick_params(colors=self.fg, labelsize=9)

        for spine in ax.spines.values():
            spine.set_color("#526579")

        plotted = False
        for object_label in ("Sole", "Terra"):
            rows = []
            for item in self.horizons_table.get_children():
                values = self.horizons_table.item(item, "values")
                if not values or values[0] != object_label:
                    continue
                try:
                    timestamp = datetime.strptime(
                        values[1], "%Y-%m-%d %H:%M:%S"
                    )
                    elevation = float(values[3])
                except (ValueError, IndexError):
                    continue
                rows.append((timestamp, elevation))

            if rows:
                rows.sort(key=lambda point: point[0])
                ax.plot(
                    [point[0] for point in rows],
                    [point[1] for point in rows],
                    marker="o",
                    markersize=2.5,
                    linewidth=1.5,
                    label=object_label,
                )
                plotted = True

        if not plotted:
            window.destroy()
            messagebox.showinfo(
                "NASA/JPL Horizons",
                "Nessuna osservazione utilizzabile. Premi prima AGGIORNA DATI NASA/JPL.",
            )
            return

        import matplotlib.dates as mdates
        ax.xaxis.set_major_locator(
            mdates.AutoDateLocator(minticks=5, maxticks=10)
        )
        ax.xaxis.set_major_formatter(
            mdates.DateFormatter("%d %b %H:%M", tz=timezone.utc)
        )
        ax.tick_params(axis="x", labelrotation=25)
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.22),
            ncol=3,
            facecolor=self.panel,
            labelcolor=self.fg,
        )
        figure.subplots_adjust(
            left=0.09, right=0.98, top=0.90, bottom=0.25
        )

        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(
            fill="both", expand=True, padx=12, pady=(0, 12)
        )

    def show_operational_windows(self):
        """Show sampled geometric windows from actual Horizons observations."""
        if not self.last_horizons_results:
            messagebox.showinfo(
                "Finestre operative",
                "Prima premi AGGIORNA DATI NASA/JPL. Le curve demo non vengono usate.",
            )
            return

        by_object = {"Sole": {}, "Terra": {}}
        for label, row in self.last_horizons_results:
            if label in by_object:
                by_object[label][row.time_utc] = row.elevation_deg
        times = sorted(set(by_object["Sole"]) & set(by_object["Terra"]))
        if not times:
            messagebox.showwarning(
                "Finestre operative",
                "Non esistono timestamp comuni tra le osservazioni di Sole e Terra.",
            )
            return

        sun = [by_object["Sole"][t] for t in times]
        earth = [by_object["Terra"][t] for t in times]
        windows = find_operational_windows(
            sun, earth, min_sun_elevation_deg=5.0, min_earth_elevation_deg=5.0
        )
        lines = [
            f"Finestre geometriche — {self.last_horizons_site}",
            "Soglie: Sole >= 5° e Terra >= 5°; campionamento Horizons circa orario.",
            "Non è un link budget RF né una stima di potenza solare.",
            "",
        ]
        if not windows:
            lines.append("Nessuna finestra campionata soddisfa entrambe le soglie.")
        else:
            for i, w in enumerate(windows, 1):
                lines.append(
                    f"{i}. {times[w.start_index]} → {times[w.end_index]} UTC "
                    f"({w.duration_samples} campioni, intervallo nominale circa {max(0,w.duration_samples-1)} h)"
                )
        messagebox.showinfo("Finestre operative", "\n".join(lines))

    def score_current_site(self):
        """Build a transparent score from Horizons samples and an explicit DEM grid cell."""
        from tkinter import simpledialog
        from src.site_assessment import assess_candidate, write_assessment

        if not self.last_horizons_results or self.last_horizons_site != self.site_var.get():
            messagebox.showinfo(
                "Scoring sito",
                "Aggiorna prima i dati NASA/JPL per il sito attualmente selezionato.\n"
                "Le curve dimostrative non vengono utilizzate.",
            )
            return

        by_object = {"Sole": [], "Terra": []}
        for label, row in self.last_horizons_results:
            if label in by_object:
                by_object[label].append(float(row.elevation_deg))
        if not by_object["Sole"] or not by_object["Terra"]:
            messagebox.showwarning("Scoring sito", "Osservazioni di Sole o Terra mancanti.")
            return
        if len(by_object["Sole"]) != len(by_object["Terra"]):
            messagebox.showwarning(
                "Scoring sito",
                "Il numero di campioni di Sole e Terra non coincide. Non verranno accoppiati implicitamente.",
            )
            return

        dem_path = Path("data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif")
        if not dem_path.is_file():
            messagebox.showwarning("Scoring sito", f"DEM LOLA non trovato: {dem_path}")
            return
        row = simpledialog.askinteger(
            "Scoring sito — posizione DEM",
            "Indice riga (0-based) del candidato nel raster LOLA:",
            minvalue=0, parent=self.root,
        )
        if row is None:
            return
        col = simpledialog.askinteger(
            "Scoring sito — posizione DEM",
            "Indice colonna (0-based) del candidato nel raster LOLA:",
            minvalue=0, parent=self.root,
        )
        if col is None:
            return
        radius = simpledialog.askinteger(
            "Scoring sito — finestra terreno",
            "Raggio locale in pixel (2-250):", initialvalue=10,
            minvalue=2, maxvalue=250, parent=self.root,
        )
        if radius is None:
            return

        try:
            assessment = assess_candidate(
                candidate_name=self.site_var.get(), dem_path=dem_path,
                row=row, col=col, radius_pixels=radius,
                sun_elevations_deg=by_object["Sole"],
                earth_elevations_deg=by_object["Terra"],
                confidence_path=Path(
                    "data/terrain/processed/"
                    "NAC_DTM_ESALL_SR12_CONF_PDS3_exact_20261025-131507.tif"
                ),
            )
            out = write_assessment(assessment)
            score = assessment.score
            lines = [
                f"Candidato: {assessment.candidate_name}",
                f"Cella DEM: riga {row}, colonna {col}; raggio {radius} pixel",
                f"Punteggio parziale: {score['score_0_100']}/100" if score['score_0_100'] is not None else "Punteggio non disponibile",
                f"Copertura dei pesi: {100*score['coverage_fraction']:.1f}%",
                "Componenti disponibili:",
            ]
            lines.extend(f"  • {key}: {value:.2f}/100" for key, value in score["components_0_100"].items())
            lines.append("Metriche mancanti: " + (", ".join(score["missing_metrics"]) or "nessuna"))
            lines.append(f"Pendenza P95 locale: {assessment.terrain_metrics['slope_p95_deg']:.2f}°")
            lines.append(f"Rugosità locale: {assessment.terrain_metrics['roughness_plane_residual_std_m']:.3f} m")
            lines.append(f"Copertura valida DEM: {100*assessment.terrain_metrics['valid_fraction']:.1f}%")
            cm = assessment.confidence_metrics
            if cm and cm.get("exists"):
                lines.append("Confidenza LROC — riepilogo globale:")
                for cls, count in sorted(cm["class_counts"].items(), key=lambda x: int(x[0])):
                    lines.append(f"  Classe PDS3 {cls}: {count:,} pixel")
                if cm.get("undocumented_classes"):
                    lines.append("Classi non documentate: " + ", ".join(map(str, cm["undocumented_classes"])))
            else:
                lines.append("Confidenza LROC: riepilogo non disponibile.")
            lines.extend(["", "AVVERTENZE:", *[f"• {item}" for item in assessment.warnings]])
            lines.append(f"\nRapporto salvato: {out}")
            messagebox.showinfo("Valutazione preliminare candidato", "\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Scoring sito", str(exc), parent=self.root)

    def open_rover_planner(self):
        """Open a DEM-grid planner; uses row/column, not unvalidated lat/lon."""
        window = tk.Toplevel(self.root)
        window.title("Pianificatore rover — DEM grid")
        window.geometry("620x540")
        window.configure(bg=self.bg)

        tk.Label(
            window,
            text="PERCORSO ROVER SU GRIGLIA DEM",
            bg=self.bg, fg=self.accent, font=("DejaVu Sans", 14, "bold")
        ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(
            window,
            text=("Inserisci righe/colonne del raster LOLA. Coordinate geografiche non vengono "
                  "convertite perché l'allineamento del frame è ancora da validare."),
            bg=self.bg, fg=self.fg, wraplength=580, justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 12))

        form = tk.Frame(window, bg=self.panel, padx=12, pady=12)
        form.pack(fill="x", padx=16)
        fields = [
            ("Start row", "start_row", "100"),
            ("Start col", "start_col", "100"),
            ("Goal row", "goal_row", "120"),
            ("Goal col", "goal_col", "120"),
            ("Pendenza massima (°)", "slope", "15"),
            ("Consumo stimato (Wh/m)", "energy_per_m", "0.02"),
            ("Budget energia (Wh)", "budget", "100"),
        ]
        vars_ = {}
        for i, (label, key, default) in enumerate(fields):
            tk.Label(form, text=label, bg=self.panel, fg=self.fg).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=4)
            var = tk.StringVar(value=default)
            vars_[key] = var
            tk.Entry(form, textvariable=var, width=18).grid(row=i, column=1, sticky="ew", pady=4)
        form.columnconfigure(1, weight=1)

        status = tk.Label(window, text="DEM non caricato.", bg=self.bg, fg="#ffd166", wraplength=580, justify="left")
        status.pack(fill="x", padx=16, pady=10)

        def start_planning():
            values = {}
            try:
                for key in ("start_row", "start_col", "goal_row", "goal_col"):
                    values[key] = int(vars_[key].get().strip())
                for key in ("slope", "energy_per_m", "budget"):
                    values[key] = float(vars_[key].get().strip())
                if values["energy_per_m"] < 0 or values["budget"] < 0:
                    raise ValueError("Consumo e budget devono essere non negativi.")
            except ValueError as exc:
                messagebox.showerror("Parametri non validi", str(exc), parent=window)
                return

            status.config(text="Caricamento DEM e ricerca del percorso…", fg="#ffd166")
            button.config(state="disabled")

            def worker():
                try:
                    import numpy as np
                    import rasterio
                    dem_path = Path("data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif")
                    if not dem_path.is_file():
                        raise FileNotFoundError(f"DEM LOLA non trovato: {dem_path}")
                    with rasterio.open(dem_path) as ds:
                        dem = ds.read(1, masked=True).astype(np.float64).filled(np.nan)
                        pixel_size_x = float(abs(ds.transform.a))
                        pixel_size_y = float(abs(ds.transform.e))
                        shape = dem.shape
                    plan = plan_rover_path(
                        dem,
                        (values["start_row"], values["start_col"]),
                        (values["goal_row"], values["goal_col"]),
                        pixel_size_x_m=pixel_size_x,
                        pixel_size_y_m=pixel_size_y,
                        max_slope_deg=values["slope"],
                        energy_wh_per_m=values["energy_per_m"],
                        energy_budget_wh=values["budget"],
                    )
                    out = Path("reports/mission/rover_plan.json")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    payload = plan.to_dict()
                    payload["dem_path"] = str(dem_path)
                    payload["dem_shape"] = list(shape)
                    payload["pixel_size_x_m"] = pixel_size_x
                    payload["pixel_size_y_m"] = pixel_size_y
                    payload["coordinates"] = "DEM row/column only; geodetic frame not validated"
                    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    message = (
                        f"Percorso calcolato su DEM {shape[1]}x{shape[0]} (pixel {pixel_size_x:.2f} x {pixel_size_y:.2f} m).\n"
                        f"Celle nel percorso: {len(plan.path_rc)}\nDistanza: {plan.distance_m:.2f} m\n"
                        f"Energia stimata: {plan.estimated_energy_wh:.2f} Wh\n"
                        f"Pendenza massima: {plan.max_slope_deg:.2f}°\nNodi espansi: {plan.cells_expanded}\n"
                        f"Rapporto: {out}\n\nStima preliminare: non modella dinamica, slittamento o incertezza del rover."
                    )
                    window.after(0, lambda: status.config(text=message, fg="#80ed99"))
                except Exception as exc:
                    window.after(0, lambda err=str(exc): status.config(text=f"Pianificazione non riuscita: {err}", fg="#ffb4a2"))
                finally:
                    window.after(0, lambda: button.config(state="normal"))

            threading.Thread(target=worker, daemon=True).start()

        button = tk.Button(window, text="CALCOLA PERCORSO", command=start_planning, bg=self.accent, fg="#07131a", relief="flat", padx=12, pady=8)
        button.pack(anchor="w", padx=16, pady=(0, 12))


    def assess_rover_energy(self):
        """Estimate route energy from a saved DEM-grid route and explicit assumptions."""
        from tkinter import simpledialog
        from src.rover_energy import estimate_route_energy

        window = tk.Toplevel(self.root)
        window.title("Stima energetica rover — preliminare")
        window.geometry("520x540")
        window.configure(bg=self.bg)
        tk.Label(
            window, text="MODELLO ENERGETICO PRELIMINARE",
            bg=self.bg, fg=self.accent, font=("DejaVu Sans", 13, "bold")
        ).pack(anchor="w", padx=16, pady=(14, 6))
        tk.Label(
            window,
            text=("Richiede un percorso già salvato da PIANIFICA PERCORSO ROVER. "
                  "Include rotolamento, salita, perdite della trasmissione e carichi ausiliari; "
                  "non accredita energia solare o recupero in discesa."),
            bg=self.bg, fg=self.fg, wraplength=480, justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 12))
        form = tk.Frame(window, bg=self.panel, padx=12, pady=12)
        form.pack(fill="x", padx=16)
        fields = [
            ("Massa rover (kg)", "mass", "120"),
            ("Coefficiente rotolamento (assunto)", "crr", "0.08"),
            ("Efficienza trasmissione (0-1)", "eff", "0.70"),
            ("Potenza ausiliaria media (W)", "aux", "25"),
            ("Durata missione (h)", "hours", str(int(self.duration_var.get()))),
            ("Capacità batteria (Wh)", "battery", "1200"),
            ("Riserva batteria (%)", "reserve", "20"),
        ]
        variables = {}
        for i, (label, key, default) in enumerate(fields):
            tk.Label(form, text=label, bg=self.panel, fg=self.fg).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=5)
            var = tk.StringVar(value=default)
            variables[key] = var
            tk.Entry(form, textvariable=var, width=14).grid(row=i, column=1, sticky="ew", pady=5)
        form.columnconfigure(1, weight=1)
        status = tk.Label(window, text="In attesa dei parametri.", bg=self.bg, fg="#ffd166", wraplength=480, justify="left")
        status.pack(fill="x", padx=16, pady=12)

        def calculate():
            try:
                values = {key: float(var.get().strip()) for key, var in variables.items()}
                result = estimate_route_energy(
                    "reports/mission/rover_plan.json",
                    mass_kg=values["mass"],
                    rolling_resistance_coefficient=values["crr"],
                    drivetrain_efficiency=values["eff"],
                    auxiliary_power_w=values["aux"],
                    mission_duration_hours=values["hours"],
                    battery_capacity_wh=values["battery"],
                    reserve_percent=values["reserve"],
                    output_path="reports/mission/rover_energy_assessment.json",
                )
                energy = result["energy_wh"]
                status.config(
                    text=(f"Distanza: {result['distance_m']:.1f} m\n"
                          f"Salita cumulativa: {result['positive_ascent_m']:.1f} m\n"
                          f"Energia trazione: {energy['traction_after_drivetrain']:.1f} Wh\n"
                          f"Carichi ausiliari: {energy['auxiliary_load']:.1f} Wh\n"
                          f"Totale stimato: {energy['total_estimated']:.1f} Wh\n"
                          f"Batteria utilizzabile (riserva esclusa): {energy['usable_battery_after_reserve']:.1f} Wh\n"
                          f"Budget rispettato: {'sì' if energy['within_budget'] else 'NO'}\n"
                          f"Rapporto: {result['output_path']}\n\n"
                          "Stima preliminare: parametri da validare; non è una certificazione operativa."),
                    fg="#80ed99" if energy["within_budget"] else "#ffb4a2",
                )
            except Exception as exc:
                messagebox.showerror("Stima energetica", str(exc), parent=window)

        tk.Button(window, text="CALCOLA STIMA ENERGETICA", command=calculate, bg=self.accent, fg="#07131a", relief="flat", padx=12, pady=8).pack(anchor="w", padx=16, pady=(0, 12))

    def export_mission_report(self):
        """Export a snapshot of currently available mission data without network access."""
        try:
            report = build_mission_report(
                site_name=self.site_var.get(),
                planning_date=self.date_var.get().strip(),
                horizon_hours=int(self.duration_var.get()),
                horizons_observations=(
                    self.last_horizons_results
                    if self.last_horizons_site == self.site_var.get() else []
                ),
                project_root=Path.cwd(),
                rover_plan_path=Path("reports/mission/rover_plan.json"),
                energy_assessment_path=(
                    Path("reports/mission/rover_energy_assessment.json")
                    if Path("reports/mission/rover_energy_assessment.json").is_file()
                    else None
                ),
            )
            json_path, md_path = write_mission_report(report, Path.cwd() / "reports")
            messagebox.showinfo(
                "Rapporto missione esportato",
                "Rapporto creato senza richieste di rete e senza modificare i raster.\n\n"
                f"JSON: {json_path}\nMarkdown: {md_path}\n\n"
                f"Osservazioni Sole: {len(report['astronomy']['sun_observations'])}\n"
                f"Osservazioni Terra: {len(report['astronomy']['earth_observations'])}\n"
                f"Piano rover disponibile: {'sì' if report['rover_plan']['available'] else 'no'}\n"
                "La georeferenziazione fisica è ancora dichiarata non validata."
            )
        except Exception as exc:
            messagebox.showerror("Esportazione rapporto", str(exc))

    def open_3d_globe(self):
        """Apre il modello topografico NASA LRO in una finestra separata."""
        import subprocess
        import sys

        from pathlib import Path

        process = getattr(self, "_moon_viewer_process", None)
        if process is not None and process.poll() is None:
            messagebox.showinfo(
                "Luna NASA 3D",
                "Il visualizzatore della Luna è già aperto.",
                parent=self.root,
            )
            return

        project_root = Path(__file__).resolve().parent
        viewer_script = project_root / "src" / "lunar_native_viewer.py"

        if not viewer_script.is_file():
            messagebox.showerror(
                "Luna NASA 3D",
                f"Visualizzatore non trovato:\n{viewer_script}",
                parent=self.root,
            )
            return

        try:
            self._moon_viewer_process = subprocess.Popen(
                [sys.executable, str(viewer_script)],
                cwd=str(project_root),
            )
        except Exception as exc:
            messagebox.showerror(
                "Luna NASA 3D",
                f"Impossibile avviare il visualizzatore:\n{exc}",
                parent=self.root,
            )

    def compare_sites(self):
        """Confronta i siti con osservazioni geometriche NASA/JPL."""
        try:
            start = datetime.strptime(
                self.date_var.get().strip(), "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)
            hours = max(1, min(int(self.duration_var.get()), 168))
        except (ValueError, TypeError) as exc:
            messagebox.showerror(
                "Confronto siti", f"Data o durata non valida: {exc}",
                parent=self.root,
            )
            return

        progress = tk.Toplevel(self.root)
        progress.title("Confronto siti — NASA/JPL")
        progress.geometry("470x120")
        progress.transient(self.root)
        tk.Label(
            progress,
            text="Recupero dei dati del Sole e della Terra per tutti i siti...",
            wraplength=430, padx=18, pady=18,
        ).pack(fill="both", expand=True)

        def worker():
            try:
                report = compare_candidate_sites(SITES, start, hours=hours)
                output_path = write_comparison_report(report)
                error = None
            except Exception as exc:
                report, output_path, error = None, None, str(exc)

            def finish():
                if not progress.winfo_exists():
                    return
                progress.destroy()

                if error:
                    messagebox.showerror(
                        "Confronto siti", error, parent=self.root
                    )
                    return

                win = tk.Toplevel(self.root)
                win.title("Confronto geometrico dei siti candidati")
                win.geometry("900x600")
                win.minsize(680, 420)

                frame = tk.Frame(win, padx=12, pady=12)
                frame.pack(fill="both", expand=True)
                text = tk.Text(
                    frame, wrap="word",
                    font=("DejaVu Sans Mono", 10),
                )
                scroll = ttk.Scrollbar(
                    frame, orient="vertical", command=text.yview
                )
                text.configure(yscrollcommand=scroll.set)
                scroll.pack(side="right", fill="y")
                text.pack(side="left", fill="both", expand=True)

                lines = [
                    "CONFRONTO GEOMETRICO DEI SITI CANDIDATI",
                    f"Inizio UTC: {report['start_utc']}",
                    f"Durata: {report['hours']} ore; passo: {report['step']}",
                    "Fonte: NASA/JPL Horizons",
                    "Soglie: elevazione Sole >= 5° e Terra >= 5°",
                    "",
                ]

                for site in report["sites"]:
                    lines.append(f"=== {site['site']} ===")
                    lines.append(
                        f"Coordinate: {site['latitude_deg']:.5f}°, "
                        f"{site['longitude_deg']:.5f}° "
                        "(riferimento fisico da validare)"
                    )
                    lines.append(
                        f"Campioni comuni Sole/Terra: {site['matched_samples']}"
                    )

                    if site["error"]:
                        lines.append(f"ERRORE: {site['error']}")
                    elif site["matched_samples"]:
                        lines.append(
                            f"Massima elevazione campionata: "
                            f"Sole {site['sun_max_elevation_deg']:.2f}°; "
                            f"Terra {site['earth_max_elevation_deg']:.2f}°"
                        )
                        windows = site["geometric_windows"]
                        if not windows:
                            lines.append(
                                "Nessuna finestra geometrica comune "
                                "alle soglie nei campioni disponibili."
                            )
                        else:
                            lines.append("Finestre geometriche comuni:")
                            for item in windows:
                                lines.append(
                                    f"  {item['start_utc']} -> "
                                    f"{item['end_utc']} "
                                    f"({item['sample_count']} campioni; "
                                    f"durata campionata circa "
                                    f"{item['approx_duration_hours']:.1f} h)"
                                )
                    lines.append("")

                lines.extend([
                    "LIMITI IMPORTANTI",
                    "- Non è incluso l'orizzonte reale del terreno.",
                    "- Non vengono calcolati watt o energia generata.",
                    "- Non viene verificato un collegamento radio o il suo budget RF.",
                    "- Le finestre dipendono dalla cadenza oraria dei campioni.",
                    "- Le coordinate e il loro riferimento lunare richiedono verifica.",
                    "",
                    f"Rapporto JSON: {output_path}",
                ])
                text.insert("1.0", "\n".join(lines))
                text.configure(state="disabled")

                tk.Button(
                    win, text="Mostra percorso del rapporto",
                    command=lambda: messagebox.showinfo(
                        "Rapporto JSON", str(output_path), parent=win
                    ),
                ).pack(pady=(0, 10))

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def analyze_local_terrain(self):
        """Compute local slope/roughness at explicit raster row/column indices."""
        from tkinter import simpledialog
        from src.terrain_metrics import analyze_local_terrain, write_metrics
        from pathlib import Path
        raster = Path("data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif")
        if not raster.is_file():
            messagebox.showwarning("Analisi terreno", f"DEM LOLA non trovato: {raster}")
            return
        row = simpledialog.askinteger("Analisi terreno", "Indice riga DEM LOLA (0-based):", minvalue=0, parent=self.root)
        if row is None: return
        col = simpledialog.askinteger("Analisi terreno", "Indice colonna DEM LOLA (0-based):", minvalue=0, parent=self.root)
        if col is None: return
        radius = simpledialog.askinteger("Analisi terreno", "Raggio finestra in pixel (2-250):", initialvalue=10, minvalue=2, maxvalue=250, parent=self.root)
        if radius is None: return
        try:
            metrics = analyze_local_terrain(raster, row, col, radius)
            out = write_metrics(metrics, "reports/local_terrain_metrics.json")
            messagebox.showinfo(
                "Metriche locali DEM",
                f"Centro griglia: riga {row}, colonna {col}\n"
                f"Quota centro: {metrics.center_elevation_m if metrics.center_elevation_m is not None else 'NoData'} m\n"
                f"Pendenza al centro: {metrics.slope_at_center_deg if metrics.slope_at_center_deg is not None else 'n/d'}°\n"
                f"Pendenza mediana/P95: {metrics.slope_median_deg:.2f}° / {metrics.slope_p95_deg:.2f}°\n"
                f"Rugosità (std residui piano): {metrics.roughness_plane_residual_std_m:.3f} m\n"
                f"Copertura valida: {metrics.valid_pixels}/{metrics.total_pixels}\n\n"
                f"Rapporto: {out}\n\n"
                "ATTENZIONE: indici di griglia, non coordinate geografiche. "
                "La georeferenziazione del sito non è validata."
            )
        except Exception as exc:
            messagebox.showerror("Analisi terreno", str(exc), parent=self.root)

    def analyze_local_horizon(self):
        """Calculate and export a diagnostic DEM horizon from explicit grid indices."""
        from tkinter import simpledialog
        from pathlib import Path
        from src.horizon_analysis import calculate_and_write_horizon

        raster = Path("data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif")
        if not raster.is_file():
            messagebox.showwarning("Profilo orizzonte", f"DEM LOLA non trovato: {raster}", parent=self.root)
            return
        row = simpledialog.askinteger(
            "Profilo orizzonte — posizione DEM",
            "Indice riga (0-based) del punto osservatore:", minvalue=0, parent=self.root,
        )
        if row is None:
            return
        col = simpledialog.askinteger(
            "Profilo orizzonte — posizione DEM",
            "Indice colonna (0-based) del punto osservatore:", minvalue=0, parent=self.root,
        )
        if col is None:
            return
        height = simpledialog.askfloat(
            "Profilo orizzonte", "Altezza osservatore sopra il terreno (m):",
            initialvalue=1.0, minvalue=0.0, parent=self.root,
        )
        if height is None:
            return
        distance = simpledialog.askinteger(
            "Profilo orizzonte", "Distanza massima di analisi (m):",
            initialvalue=5000, minvalue=100, maxvalue=20000, parent=self.root,
        )
        if distance is None:
            return
        try:
            out = calculate_and_write_horizon(
                raster, row, col, observer_height_m=height,
                max_distance_m=float(distance),
                output_path="reports/local_horizon_profile.json",
            )
            messagebox.showinfo(
                "Profilo orizzonte creato",
                f"Profilo diagnostico salvato in:\n{out}\n\n"
                f"Cella DEM: riga {row}, colonna {col}\n"
                f"Altezza osservatore: {height:.2f} m\n"
                f"Distanza massima: {distance} m\n\n"
                "IMPORTANTE: gli azimut sono riferiti agli assi della griglia raster, "
                "non necessariamente al nord locale. Non sono stati confrontati con Horizons. "
                "La georeferenziazione fisica resta non validata.",
                parent=self.root,
            )
        except Exception as exc:
            messagebox.showerror("Profilo orizzonte", str(exc), parent=self.root)


    def analyze_solar_illumination(self):
        """Estimate direct-sun visibility using a saved horizon and explicit azimuth offset."""
        from tkinter import simpledialog
        from pathlib import Path
        from src.illumination_analysis import estimate_direct_solar_visibility

        horizon_path = Path("reports/local_horizon_profile.json")
        if not horizon_path.is_file():
            messagebox.showwarning(
                "Illuminazione diagnostica",
                "Prima genera un profilo con PROFILO ORIZZONTE LOCALE (DIAGNOSTICO).",
                parent=self.root,
            )
            return
        solar = []
        for obj, row in getattr(self, "last_horizons_results", []):
            if obj != "Sole":
                continue
            solar.append({
                "time_utc": str(row.time_utc),
                "azimuth_deg": float(row.azimuth_deg),
                "elevation_deg": float(row.elevation_deg),
            })
        if not solar:
            messagebox.showwarning(
                "Illuminazione diagnostica",
                "Nessuna osservazione solare disponibile. Aggiorna prima i dati NASA/JPL Horizons.",
                parent=self.root,
            )
            return
        offset = simpledialog.askfloat(
            "Offset azimutale da validare",
            "Offset in gradi: azimut_griglia = (azimut_Horizons + offset) mod 360.\n"
            "Inserisci solo un offset determinato da una verifica indipendente.\n"
            "Il valore non viene stimato automaticamente.",
            initialvalue=0.0, parent=self.root,
        )
        if offset is None:
            return
        try:
            out = estimate_direct_solar_visibility(
                horizon_path, solar, grid_azimuth_offset_deg=offset,
                output_path="reports/solar_illumination_diagnostic.json",
            )
            result = __import__("json").loads(out.read_text(encoding="utf-8"))
            messagebox.showinfo(
                "Stima diagnostica completata",
                f"Rapporto: {out}\nOsservazioni solari: {result['observation_count']}\n"
                f"Sole geometricamente visibile sopra il profilo: {result['estimated_sun_visible_count']}\n\n"
                "ATTENZIONE: risultato non validato finché offset azimutale e georeferenziazione non sono verificati. "
                "Non rappresenta una stima di energia disponibile.",
                parent=self.root,
            )
        except Exception as exc:
            messagebox.showerror("Illuminazione diagnostica", str(exc), parent=self.root)

    def audit_dem(self):
        """Audit non distruttivo del DEM LOLA configurato per il progetto."""
        from pathlib import Path
        candidates = [
            Path("data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif"),
            Path("data/terrain/reference-lroc/NAC_DTM_ESALL_SR12.TIF"),
        ]
        existing = [p for p in candidates if p.is_file()]
        if not existing:
            messagebox.showwarning(
                "Audit DEM", "Raster non trovati nei percorsi standard.\n\n"
                "Verifica data/terrain/official-lola e data/terrain/reference-lroc."
            )
            return
        lines = ["AUDIT METADATI DEM — NESSUN FILE MODIFICATO\n"]
        for path in existing:
            try:
                report = audit_raster(path)
                lines.append(
                    f"{path.name}\n"
                    f"  Dimensioni: {report.width} x {report.height}\n"
                    f"  Risoluzione: {report.resolution_x_m} x {report.resolution_y_m} m\n"
                    f"  Copertura valida: {report.valid_percent:.2f}%\n"
                    f"  Quote min/mediana/max: {report.elevation_min_m} / {report.elevation_median_m} / {report.elevation_max_m} m\n"
                    f"  Avvertenze: {'; '.join(report.warnings) or 'nessuna avvertenza metadati'}\n"
                )
            except Exception as exc:
                lines.append(f"{path}: audit non riuscito: {exc}\n")
        lines.append("\nL'audit dei metadati non certifica l'allineamento geodetico fisico.")
        messagebox.showinfo("Audit DEM lunari", "\n".join(lines))

    def show_multi_rover_coordinator(self):
        """Pianificatore locale di alto livello per assegnare task a più rover."""
        from tkinter import simpledialog
        from src.multi_rover import allocate_tasks

        window = tk.Toplevel(self.root)
        window.title("Coordinamento multi-rover — piano locale")
        window.geometry("900x700")
        window.configure(bg=self.bg)
        tk.Label(window, text="MULTI-ROVER TASK COORDINATOR", bg=self.bg, fg=self.accent,
                 font=("DejaVu Sans", 14, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(window,
                 text="Inserisci rover e task in JSON. Le posizioni devono usare lo stesso frame metrico locale. "
                      "L'assegnazione è di alto livello: non sostituisce il routing sul DEM né una connessione P-System remota.",
                 bg=self.bg, fg="#ffd166", wraplength=850, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        editor = tk.Text(window, bg=self.panel, fg=self.fg, insertbackground=self.fg,
                         wrap="none", height=22, font=("DejaVu Sans Mono", 9))
        editor.pack(fill="both", expand=True, padx=14, pady=6)
        example = {
            "rovers": [
                {"id": "rover-01", "position_xy": [0, 0], "capabilities": ["camera", "sampling"], "available_energy_wh": 180, "energy_wh_per_m": 0.02},
                {"id": "rover-02", "position_xy": [100, 0], "capabilities": ["camera", "drill"], "available_energy_wh": 150, "energy_wh_per_m": 0.025}
            ],
            "tasks": [
                {"id": "survey-A", "position_xy": [30, 20], "required_capabilities": ["camera"], "priority": 5, "estimated_energy_wh": 15, "description": "Ricognizione"},
                {"id": "sample-B", "position_xy": [140, 10], "required_capabilities": ["sampling"], "priority": 4, "estimated_energy_wh": 25, "description": "Campionamento"},
                {"id": "drill-C", "position_xy": [180, 25], "required_capabilities": ["drill"], "priority": 3, "estimated_energy_wh": 35, "description": "Analisi sottosuolo"}
            ]
        }
        editor.insert("1.0", json.dumps(example, indent=2, ensure_ascii=False))
        output = tk.Text(window, bg="#0b1118", fg=self.fg, insertbackground=self.fg,
                         wrap="word", height=10, font=("DejaVu Sans Mono", 9))
        output.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        def allocate():
            try:
                data = json.loads(editor.get("1.0", "end-1c"))
                result = allocate_tasks(data.get("rovers"), data.get("tasks"),
                                        output_path="reports/multi_rover_plan.json")
                journal = MissionJournal("reports/mission_events.jsonl", "lunar-planner-ui")
                for item in result["assignments"]:
                    journal.append(item["rover_id"], "task_assigned", {
                        "task_id": item["task_id"],
                        "plan": "reports/multi_rover_plan.json",
                        "distance_estimate_m": item["distance_from_previous_position_m"],
                        "energy_reserved_wh": item["total_energy_reserved_wh"],
                    })
                output.delete("1.0", "end")
                output.insert("end", json.dumps(result, indent=2, ensure_ascii=False))
                output.insert("end", "\n\nEventi assegnazione aggiunti al journal locale.\n")
                output.insert("end", "Connessione P-System remota: non configurata.\n")
                output.insert("end", "Rapporto: reports/multi_rover_plan.json")
            except Exception as exc:
                messagebox.showerror("Coordinamento multi-rover", str(exc), parent=window)

        controls = tk.Frame(window, bg=self.bg)
        controls.pack(fill="x", padx=14, pady=(0, 12))
        tk.Button(controls, text="ASSEGNA TASK E REGISTRA EVENTI", command=allocate,
                  bg=self.accent, fg="#07131a", relief="flat", padx=12, pady=8).pack(side="left")
        tk.Button(controls, text="RIPRISTINA ESEMPIO", command=lambda: (editor.delete("1.0", "end"), editor.insert("1.0", json.dumps(example, indent=2, ensure_ascii=False))),
                  bg="#334b60", fg=self.fg, relief="flat", padx=10, pady=8).pack(side="left", padx=8)

    def show_psystem(self):
        """Journal locale dimostrativo; non dichiara una connessione remota."""
        from tkinter import simpledialog
        window = tk.Toplevel(self.root)
        window.title("P-System — journal locale")
        window.geometry("760x520")
        window.configure(bg=self.bg)
        tk.Label(window, text="MISSION EVENT JOURNAL", bg=self.bg, fg=self.accent,
                 font=("DejaVu Sans", 14, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(window, text="Prototipo locale append-only. Nessun nodo P-System remoto collegato.",
                 bg=self.bg, fg="#ffd166", wraplength=700, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        text = tk.Text(window, bg=self.panel, fg=self.fg, insertbackground=self.fg, wrap="word")
        text.pack(fill="both", expand=True, padx=14, pady=6)
        journal = MissionJournal("reports/mission_events.jsonl", "lunar-planner-ui")
        def refresh():
            text.delete("1.0", "end")
            events = journal.read_events()
            if not events:
                text.insert("end", "Nessun evento registrato.\n")
            for event in events[-100:]:
                text.insert("end", f"[{event.logical_clock}] {event.node_id} | {event.entity_id} | {event.event_type} | {event.payload}\n")
            text.insert("end", f"\nEventi locali: {len(events)}\nConnessione remota: non configurata\n")
        def add_event():
            entity = simpledialog.askstring("Nuovo evento", "ID entità (es. rover-01):", parent=window)
            if not entity: return
            event_type = simpledialog.askstring("Nuovo evento", "Tipo evento (es. waypoint_assigned):", parent=window)
            if not event_type: return
            detail = simpledialog.askstring("Nuovo evento", "Nota breve:", parent=window) or ""
            try:
                journal.append(entity.strip(), event_type.strip(), {"note": detail, "site": self.site_var.get()})
                refresh()
            except Exception as exc:
                messagebox.showerror("Journal", str(exc), parent=window)
        controls = tk.Frame(window, bg=self.bg)
        controls.pack(fill="x", padx=14, pady=(4, 12))
        tk.Button(controls, text="AGGIUNGI EVENTO", command=add_event, bg=self.accent, fg="#07131a", relief="flat", padx=10, pady=7).pack(side="left")
        tk.Button(controls, text="AGGIORNA", command=refresh, bg="#334b60", fg=self.fg, relief="flat", padx=10, pady=7).pack(side="left", padx=8)
        refresh()


def main():
    root = tk.Tk()
    LunarPlanner(root)
    root.mainloop()


if __name__ == "__main__":
    main()

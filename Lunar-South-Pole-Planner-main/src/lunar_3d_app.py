# Last updated: 2026-11-14
"""Interfaccia principale 3D per Lunar South Pole Planner.

Il server usa la libreria standard Python; Plotly viene servito localmente.
Le quote DEM vengono visualizzate in scala metrica convertita in km.
Il riferimento geografico dei singoli raster resta da validare.
"""
from __future__ import annotations

import json
import math
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import numpy as np
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

from src.astronomy import SITES, query_observations

ROOT = Path(__file__).resolve().parents[1]
UI_FILE = ROOT / "ui" / "lunar_explorer.html"

DEM_DATASETS = {
    "Site04": ROOT / "data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif",
    "Site01": ROOT / "data/terrain/official-lola/Site01_final_adj_5mpp_surf.tif",
    "Site06": ROOT / "data/terrain/official-lola/Site06_final_adj_5mpp_surf.tif",
    "LROC": ROOT / "data/terrain/reference-lroc/NAC_DTM_ESALL_SR12.TIF",
    "Shackleton": ROOT / "data/terrain/shackleton_site04_dem.tif",
}


def json_safe(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def get_sites():
    result = []
    for name, coords in SITES.items():
        lat, lon = float(coords[0]), float(coords[1])
        result.append({
            "name": name,
            "lat": lat,
            "lon": lon,
            "frame_note": "Coordinate candidate: riferimento lunare da validare",
        })
    return result


def make_globe():
    latitudes = np.linspace(-90, 90, 91)
    longitudes = np.linspace(-180, 180, 181)
    lon, lat = np.meshgrid(longitudes, latitudes)
    lat_r, lon_r = np.radians(lat), np.radians(lon)

    # Sfera di riferimento: non è presentata come topografia globale.
    radius = 1737.4
    x = radius * np.cos(lat_r) * np.cos(lon_r)
    y = radius * np.cos(lat_r) * np.sin(lon_r)
    z = radius * np.sin(lat_r)

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=x, y=y, z=z,
        surfacecolor=lat,
        colorscale=[
            [0.0, "#263744"], [0.35, "#596b76"],
            [0.65, "#8798a0"], [1.0, "#b8c3c9"],
        ],
        cmin=-90, cmax=90,
        showscale=False,
        opacity=0.98,
        hoverinfo="skip",
        name="Sfera lunare di riferimento",
        lighting=dict(ambient=0.42, diffuse=0.8, specular=0.18, roughness=0.9),
    ))

    sites = get_sites()
    if sites:
        sx, sy, sz = [], [], []
        for site in sites:
            phi, lam = math.radians(site["lat"]), math.radians(site["lon"])
            r = radius * 1.004
            sx.append(r * math.cos(phi) * math.cos(lam))
            sy.append(r * math.cos(phi) * math.sin(lam))
            sz.append(r * math.sin(phi))
        fig.add_trace(go.Scatter3d(
            x=sx, y=sy, z=sz,
            mode="markers+text",
            text=[s["name"] for s in sites],
            textposition="top center",
            textfont=dict(color="#a7f3ff", size=10),
            marker=dict(size=4, color="#37e7ff"),
            customdata=[[s["name"], s["lat"], s["lon"]] for s in sites],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Lat: %{customdata[1]:.4f}°<br>"
                "Lon: %{customdata[2]:.4f}°"
                "<extra></extra>"
            ),
            name="Siti candidati",
        ))

    fig.update_layout(
        paper_bgcolor="#061019",
        plot_bgcolor="#061019",
        font=dict(color="#d9edf7"),
        margin=dict(l=0, r=0, t=8, b=0),
        showlegend=False,
        scene=dict(
            bgcolor="#061019",
            aspectmode="data",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            camera=dict(eye=dict(x=1.65, y=-1.65, z=1.15)),
        ),
    )
    return fig.to_json()


def make_terrain(dataset):
    import rasterio
    from rasterio.enums import Resampling

    path = DEM_DATASETS.get(dataset)
    if path is None:
        raise ValueError("Dataset DEM non riconosciuto.")
    if not path.is_file():
        raise FileNotFoundError(f"DEM non trovato: {path.relative_to(ROOT)}")

    with rasterio.open(path) as ds:
        scale = min(1.0, 180.0 / max(ds.width, ds.height))
        width = max(2, int(ds.width * scale))
        height = max(2, int(ds.height * scale))
        raw = ds.read(
            1,
            out_shape=(height, width),
            masked=True,
            resampling=Resampling.average,
        )
        elevation = np.asarray(raw.filled(np.nan), dtype=float)
        transform = ds.transform * ds.transform.scale(
            ds.width / width, ds.height / height
        )
        xs = transform.c + (np.arange(width) + 0.5) * transform.a
        ys = transform.f + (np.arange(height) + 0.5) * transform.e
        bounds = [float(v) for v in ds.bounds]
        source_resolution = [float(v) for v in ds.res]
        crs = str(ds.crs) if ds.crs else None
        description = ds.tags()

    # Il raster è mostrato in coordinate locali. X/Y e quota sono convertiti
    # in km per evitare che la scala verticale venga confusa con quella orizzontale.
    x_km = xs / 1000.0
    y_km = ys / 1000.0
    z_km = elevation / 1000.0

    finite = elevation[np.isfinite(elevation)]
    if finite.size == 0:
        raise ValueError("Il DEM non contiene quote valide.")
    low, high = np.percentile(finite, [2, 98])
    if not high > low:
        low, high = float(finite.min()), float(finite.max() + 1)

    fig = go.Figure(go.Surface(
        x=x_km,
        y=y_km,
        z=z_km,
        surfacecolor=elevation,
        colorscale=[
            [0.0, "#142b38"], [0.25, "#315363"],
            [0.5, "#708993"], [0.75, "#b2c3ca"], [1.0, "#eef4f6"],
        ],
        cmin=float(low),
        cmax=float(high),
        connectgaps=False,
        colorbar=dict(
            title=dict(text="Quota DEM (m)", font=dict(color="#d9edf7")),
            tickfont=dict(color="#d9edf7"),
        ),
        lighting=dict(ambient=0.4, diffuse=0.9, specular=0.2, roughness=0.9),
        hovertemplate=(
            "X locale: %{x:.3f} km<br>"
            "Y locale: %{y:.3f} km<br>"
            "Quota: %{surfacecolor:.1f} m<extra></extra>"
        ),
        name=f"DEM {dataset}",
    ))
    fig.update_layout(
        paper_bgcolor="#061019",
        plot_bgcolor="#061019",
        font=dict(color="#d9edf7"),
        margin=dict(l=0, r=0, t=8, b=0),
        scene=dict(
            bgcolor="#061019",
            aspectmode="data",
            xaxis_title="X raster (km)",
            yaxis_title="Y raster (km)",
            zaxis_title="Quota (km)",
            camera=dict(eye=dict(x=1.5, y=-1.5, z=1.0)),
        ),
    )

    return {
        "figure": fig.to_json(),
        "dataset": dataset,
        "file": str(path.relative_to(ROOT)),
        "dimensions": [int(width), int(height)],
        "source_dimensions": [int(ds.width), int(ds.height)],
        "source_resolution_m": source_resolution,
        "bounds": bounds,
        "crs": crs,
        "description": description,
        "reference_warning": (
            "Coordinate del raster visualizzate nel loro sistema locale. "
            "La registrazione rispetto ai siti candidati non è dichiarata validata."
        ),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[Lunar3D] " + (fmt % args))

    def send_bytes(self, data, content_type="application/json; charset=utf-8", status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        try:
            if parsed.path == "/":
                self.send_bytes(UI_FILE.read_bytes(), "text/html; charset=utf-8")
                return

            if parsed.path == "/assets/moon.glb":
                model = ROOT / "data/terrain/global/Moon_NASA_LRO_8k_Topo_Small.glb"
                self.send_bytes(model.read_bytes(), "model/gltf-binary")
                return

            if parsed.path == "/vendor/model-viewer.min.js":
                script = ROOT / "ui/vendor/model-viewer.min.js"
                self.send_bytes(script.read_bytes(), "text/javascript; charset=utf-8")
                return

            if parsed.path == "/plotly.min.js":
                self.send_bytes(get_plotlyjs().encode("utf-8"), "text/javascript; charset=utf-8")
                return

            if parsed.path == "/api/sites":
                self.send_bytes(json_safe({
                    "sites": get_sites(),
                    "datasets": sorted(DEM_DATASETS.keys()),
                }))
                return

            if parsed.path == "/api/globe":
                self.send_bytes(json_safe({"figure": make_globe()}))
                return

            if parsed.path == "/api/terrain":
                dataset = params.get("dataset", ["Site04"])[0]
                self.send_bytes(json_safe(make_terrain(dataset)))
                return

            if parsed.path == "/api/astronomy":
                site_name = params.get("site", ["Shackleton"])[0]
                hours = int(params.get("hours", ["48"])[0])
                if site_name not in SITES:
                    raise ValueError("Sito candidato sconosciuto.")
                if hours < 1 or hours > 168:
                    raise ValueError("L'orizzonte temporale deve essere tra 1 e 168 ore.")

                lat, lon = SITES[site_name][:2]
                start = datetime.now().astimezone().astimezone(
                    __import__("datetime").timezone.utc
                ).replace(tzinfo=__import__("datetime").timezone.utc)
                start_text = start.strftime("%Y-%m-%dT%H:%M:%S")
                sun = query_observations("10", lat, lon, start_text, hours=hours, step="1h")
                earth = query_observations("399", lat, lon, start_text, hours=hours, step="1h")

                def pack(rows):
                    return [{
                        "time_utc": str(r.time_utc),
                        "azimuth_deg": float(r.azimuth_deg),
                        "elevation_deg": float(r.elevation_deg),
                        "distance_au": float(r.distance_au),
                    } for r in rows]

                self.send_bytes(json_safe({
                    "site": site_name,
                    "sun": pack(sun),
                    "earth": pack(earth),
                    "warning": (
                        "Elevazioni geometriche/apparenti restituite dal modulo astronomico. "
                        "Non equivalgono a illuminazione dopo occultazione del terreno, "
                        "potenza elettrica o verifica del collegamento radio."
                    ),
                }))
                return

            self.send_bytes(json_safe({"error": "Endpoint non trovato."}), status=404)

        except Exception as exc:
            self.send_bytes(json_safe({
                "error": str(exc),
                "type": type(exc).__name__,
            }), status=500)


def main():
    if not UI_FILE.is_file():
        raise FileNotFoundError(f"Interfaccia non trovata: {UI_FILE}")

    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    url = "http://127.0.0.1:8765/"
    print(f"\nLUNAR SOUTH POLE PLANNER 3D")
    print(f"Interfaccia: {url}")
    print("Server locale. Premi Ctrl+C per terminare.\n")

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nChiusura Lunar 3D...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

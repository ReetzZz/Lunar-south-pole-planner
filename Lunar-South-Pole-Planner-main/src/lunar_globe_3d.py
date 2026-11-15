# Last updated: 2026-11-14
"""Lunar Explorer 3D: globo e terreno locale da DEM."""
from pathlib import Path
import math
import webbrowser

import numpy as np
import rasterio
import plotly.graph_objects as go

from src.astronomy import SITES


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "visualization"
DEM = ROOT / "data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif"


def _sphere(lat, lon, radius=1.0):
    lat = np.radians(lat)
    lon = np.radians(lon)
    return (
        radius * np.cos(lat) * np.cos(lon),
        radius * np.cos(lat) * np.sin(lon),
        radius * np.sin(lat),
    )


def _global_globe():
    lat = np.linspace(-90, 90, 180)
    lon = np.linspace(-180, 180, 360)
    LON, LAT = np.meshgrid(lon, lat)

    # Visualizzazione globale schematica: non è un DEM globale.
    texture = (
        0.012 * np.sin(np.radians(LAT * 7))
        * np.cos(np.radians(LON * 9))
        + 0.006 * np.cos(np.radians(LAT * 13 + LON * 4))
    )
    R = 1 + texture
    X = R * np.cos(np.radians(LAT)) * np.cos(np.radians(LON))
    Y = R * np.cos(np.radians(LAT)) * np.sin(np.radians(LON))
    Z = R * np.sin(np.radians(LAT))

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z,
        surfacecolor=texture,
        colorscale=[
            [0, "#252b35"], [0.35, "#596573"],
            [0.65, "#a5afb8"], [1, "#e1e8ec"],
        ],
        cmin=-0.02, cmax=0.02,
        showscale=False,
        lighting=dict(ambient=0.35, diffuse=0.85, specular=0.3,
                      roughness=0.9),
        name="Globo schematico",
        hoverinfo="skip",
    ))

    for name, (lat, lon, *_) in SITES.items():
        x, y, z = _sphere(lat, lon, 1.025)
        fig.add_trace(go.Scatter3d(
            x=[x], y=[y], z=[z],
            mode="markers+text",
            text=[name],
            textposition="top center",
            textfont=dict(color="#7df9ff", size=10),
            marker=dict(size=5, color="#00e5ff"),
            customdata=[[lat, lon]],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Lat: %{customdata[0]:.5f}°<br>"
                "Lon: %{customdata[1]:.5f}°<extra></extra>"
            ),
            name=name,
        ))

    fig.update_layout(
        title="LUNAR EXPLORER // GLOBAL VIEW",
        paper_bgcolor="#07111b",
        font=dict(color="#c5e8f4"),
        margin=dict(l=0, r=0, t=60, b=0),
        scene=dict(
            bgcolor="#07111b",
            aspectmode="data",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            camera=dict(eye=dict(x=1.6, y=-1.6, z=1.1)),
        ),
        annotations=[dict(
            text="Vista globale schematica • superficie non derivata da DEM globale",
            x=0.02, y=0.02, xref="paper", yref="paper",
            showarrow=False, font=dict(color="#7bacc2", size=11),
        )],
    )
    return fig


def _local_dem():
    if not DEM.is_file():
        raise FileNotFoundError(f"DEM LOLA non trovato: {DEM}")

    with rasterio.open(DEM) as ds:
        # Riduzione della griglia per mantenere fluida la navigazione web.
        max_side = 300
        scale = max(1, math.ceil(max(ds.width, ds.height) / max_side))
        height = math.ceil(ds.height / scale)
        width = math.ceil(ds.width / scale)

        z = ds.read(
            1, out_shape=(height, width),
            masked=True,
            resampling=rasterio.enums.Resampling.average,
        ).astype("float64").filled(np.nan)

        transform = ds.transform * ds.transform.scale(
            ds.width / width, ds.height / height
        )
        xs = transform.c + (np.arange(width) + 0.5) * transform.a
        ys = transform.f + (np.arange(height) + 0.5) * transform.e
        bounds = tuple(ds.bounds)
        pixel_size = ds.res

    # Coordinate locali del raster, centrate per la visualizzazione.
    X, Y = np.meshgrid(xs / 1000.0, ys / 1000.0)
    X -= np.nanmean(X)
    Y -= np.nanmean(Y)

    valid = z[np.isfinite(z)]
    if valid.size == 0:
        raise ValueError("Il DEM non contiene quote valide.")

    low, high = np.nanpercentile(valid, [2, 98])
    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=X, y=Y, z=z,
        surfacecolor=z,
        colorscale=[
            [0, "#152633"], [0.25, "#315263"],
            [0.5, "#718996"], [0.75, "#b3c3ca"],
            [1, "#f0f6f8"],
        ],
        cmin=float(low), cmax=float(high),
        colorbar=dict(title="Quota DEM (m)", tickfont=dict(color="#d7eef7")),
        connectgaps=False,
        lighting=dict(ambient=0.35, diffuse=0.9, specular=0.25,
                      roughness=0.85),
        name="LOLA DEM Site04",
        hovertemplate="X: %{x:.3f} km<br>Y: %{y:.3f} km"
                      "<br>Quota: %{z:.1f} m<extra></extra>",
    ))

    fig.update_layout(
        title="LUNAR EXPLORER // LOLA TERRAIN",
        paper_bgcolor="#07111b",
        font=dict(color="#c5e8f4"),
        margin=dict(l=0, r=0, t=60, b=0),
        scene=dict(
            bgcolor="#07111b",
            aspectmode="data",
            xaxis_title="X locale (km)",
            yaxis_title="Y locale (km)",
            zaxis_title="Quota raster (m)",
            camera=dict(eye=dict(x=1.55, y=-1.55, z=1.15)),
        ),
        annotations=[dict(
            text=(
                f"LOLA Site04 • griglia visualizzata {width} × {height} • "
                f"risoluzione sorgente {pixel_size[0]:g} m/pixel"
                "<br>Coordinate locali: registrazione geografica fisica da validare"
            ),
            x=0.02, y=0.02, xref="paper", yref="paper",
            showarrow=False, font=dict(color="#7bacc2", size=10),
        )],
    )
    return fig


def open_lunar_globe():
    OUT.mkdir(parents=True, exist_ok=True)

    global_path = OUT / "lunar_global_3d.html"
    terrain_path = OUT / "lunar_terrain_site04_3d.html"
    index_path = OUT / "lunar_explorer_3d.html"

    _global_globe().write_html(
        str(global_path), include_plotlyjs=True,
        config={"responsive": True, "scrollZoom": True, "displaylogo": False},
    )
    _local_dem().write_html(
        str(terrain_path), include_plotlyjs=True,
        config={"responsive": True, "scrollZoom": True, "displaylogo": False},
    )

    index_path.write_text(f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lunar Explorer 3D</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#07111b;color:#c5e8f4;
font:14px system-ui,sans-serif}} header{{padding:14px 20px;border-bottom:1px solid #19445a;
display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
h1{{font-size:18px;letter-spacing:2px;margin:0;color:#7df9ff}}
nav{{display:flex;gap:8px}} button{{background:#102b3d;color:#c5e8f4;
border:1px solid #27617b;border-radius:6px;padding:10px 14px;cursor:pointer}}
button:hover{{background:#17445b}} iframe{{width:100%;height:calc(100vh - 118px);
border:0}} footer{{padding:8px 18px;color:#7bacc2;font-size:11px}}
</style></head>
<body>
<header><h1>LUNAR EXPLORER 3D</h1><nav>
<button onclick="view('global')">Globo lunare</button>
<button onclick="view('terrain')">Terreno LOLA Site04</button>
</nav></header>
<iframe id="scene" src="{global_path.name}"></iframe>
<footer>Prototype 3D • il globo globale è schematico; la vista locale usa il DEM LOLA.
Il riferimento fisico delle coordinate del raster non è ancora validato.</footer>
<script>
function view(which){{
 document.getElementById('scene').src =
 which==='terrain' ? '{terrain_path.name}' : '{global_path.name}';
}}
</script></body></html>""", encoding="utf-8")

    webbrowser.open(index_path.resolve().as_uri())
    return index_path

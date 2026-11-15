# Last updated: 2026-11-14
from contextlib import ExitStack
from datetime import date, time, datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from skyfield.api import PlanetaryConstants, load

BASE = Path(__file__).resolve().parent
KERNELS = BASE / "data" / "terrain" / "kernels"
EPHEMERIS = BASE / "de421.bsp"

SITES = {
    "Shackleton": (-89.7668, -171.87),
    "Connecting Ridge": (-89.4632, -137.49),
    "Nobile": (-85.4381, 37.36667),
}

st.set_page_config(
    page_title="Lunar South Pole Planner",
    page_icon="🌑",
    layout="wide",
)

@st.cache_resource
def load_lunar_model():
    if not EPHEMERIS.exists():
        raise FileNotFoundError(f"Effemeride non trovata: {EPHEMERIS}")
    for name in (
        "moon_080317.tf",
        "pck00008.tpc",
        "moon_pa_de421_1900-2050.bpc",
    ):
        if not (KERNELS / name).exists():
            raise FileNotFoundError(f"Kernel mancante: {KERNELS / name}")

    eph = load(str(EPHEMERIS))
    ts = load.timescale()
    pc = PlanetaryConstants()

    # I file restano aperti: jplephem può leggere i dati in modo differito.
    stack = ExitStack()
    try:
        for name in ("moon_080317.tf", "pck00008.tpc"):
            f = stack.enter_context((KERNELS / name).open("rb"))
            pc.read_text(f)

        bpc = stack.enter_context(
            (KERNELS / "moon_pa_de421_1900-2050.bpc").open("rb")
        )
        pc.read_binary(bpc)

        frame = pc.build_frame_named("MOON_ME_DE421")
        return eph, ts, pc, frame, stack
    except Exception:
        stack.close()
        raise

def observe(site, body, ts, eph, frame, lat, lon, dt):
    t = ts.from_datetime(dt)
    observer = eph["moon"] + site
    apparent = observer.at(t).observe(eph[body]).apparent()
    alt, az, distance = apparent.altaz()
    return {
        "UTC": dt.strftime("%Y-%m-%d %H:%M"),
        "Corpo": body.upper(),
        "Elevazione (°)": alt.degrees,
        "Azimut (°)": az.degrees,
        "Distanza (km)": distance.km,
    }

st.title("Lunar South Pole Planner")
st.caption(
    "Prototipo scientifico · Skyfield + effemeride DE421 · "
    "Frame lunare MOON_ME_DE421"
)

with st.sidebar:
    st.header("Parametri della missione")
    site_name = st.selectbox("Sito lunare", list(SITES))
    selected_date = st.date_input("Data UTC", value=date(2026, 10, 25))
    selected_time = st.time_input("Ora UTC", value=time(0, 0))
    hours = st.slider("Durata simulazione (ore)", 1, 48, 12)
    step_hours = st.selectbox("Passo temporale", [1, 2, 3, 6], index=0)

lat, lon = SITES[site_name]
st.write(
    f"**Sito:** {site_name} · **Latitudine:** {lat}° · "
    f"**Longitudine est:** {lon}°"
)

try:
    eph, ts, pc, frame, stack = load_lunar_model()
except Exception as exc:
    st.error(f"Impossibile caricare il modello astronomico: {exc}")
    st.stop()

site = pc.build_latlon_degrees(frame, lat, lon)
start = datetime.combine(selected_date, selected_time, tzinfo=timezone.utc)
times = [
    start.replace(tzinfo=timezone.utc)
    for _ in range(1)
]
times = [
    datetime.fromtimestamp(
        start.timestamp() + i * step_hours * 3600,
        tz=timezone.utc,
    )
    for i in range(hours // step_hours + 1)
]

rows = []
for dt in times:
    for body in ("sun", "earth"):
        t = ts.from_datetime(dt)
        apparent = (eph["moon"] + site).at(t).observe(eph[body]).apparent()
        alt, az, distance = apparent.altaz()
        rows.append({
            "UTC": dt,
            "Corpo": body.upper(),
            "Elevazione (°)": alt.degrees,
            "Azimut (°)": az.degrees,
            "Distanza (km)": distance.km,
        })

df = pd.DataFrame(rows)
sun = df[df["Corpo"] == "SUN"].iloc[0]
earth = df[df["Corpo"] == "EARTH"].iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Elevazione Sole", f"{sun['Elevazione (°)']:.4f}°")
c2.metric("Azimut Sole", f"{sun['Azimut (°)']:.4f}°")
c3.metric("Elevazione Terra", f"{earth['Elevazione (°)']:.4f}°")
c4.metric("Azimut Terra", f"{earth['Azimut (°)']:.4f}°")

fig = go.Figure()
for body, color in (("SUN", "#F5B700"), ("EARTH", "#39A0ED")):
    part = df[df["Corpo"] == body]
    fig.add_trace(go.Scatter(
        x=part["UTC"],
        y=part["Elevazione (°)"],
        mode="lines+markers",
        name=body,
        line={"width": 3, "color": color},
    ))

fig.add_hline(y=0, line_dash="dash", line_color="gray")
fig.update_layout(
    title="Elevazione astronomica nel tempo",
    xaxis_title="Tempo UTC",
    yaxis_title="Elevazione rispetto all'orizzonte geometrico (°)",
    hovermode="x unified",
    template="plotly_dark",
    legend_title="Corpo celeste",
)
st.plotly_chart(fig, use_container_width=True)

polar = go.Figure()
for body, color in (("SUN", "#F5B700"), ("EARTH", "#39A0ED")):
    part = df[df["Corpo"] == body]
    polar.add_trace(go.Scatterpolar(
        r=part["Elevazione (°)"],
        theta=part["Azimut (°)"],
        mode="markers+lines",
        name=body,
        line={"color": color},
    ))
polar.update_layout(
    title="Direzione astronomica: azimut ed elevazione",
    template="plotly_dark",
    polar={"angularaxis": {"direction": "clockwise", "rotation": 90}},
)
st.plotly_chart(polar, use_container_width=True)

with st.expander("Tabella completa dei calcoli"):
    shown = df.copy()
    shown["UTC"] = shown["UTC"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(shown, use_container_width=True)



st.divider()
st.header("Profilo diagnostico dell'orizzonte — DEM LOLA")

st.warning(
    "Profilo riferito agli assi della griglia raster. "
    "La georeferenziazione fisica e la rotazione verso il nord locale "
    "non sono ancora validate: non usare questo grafico per dichiarare "
    "la visibilità effettiva di Sole o Terra."
)

from src.terrain_horizon import calculate_horizon

dem_path = BASE / "data" / "terrain" / "official-lola" / "Site04_final_adj_5mpp_surf.tif"

if site_name != "Shackleton":
    st.info(
        "Il DEM LOLA attualmente configurato è il mosaico Site04, "
        "associato all'area di Shackleton. Per gli altri siti il profilo "
        "non viene calcolato automaticamente."
    )
else:
    with st.expander("Parametri del profilo terreno", expanded=True):
        az_step = st.selectbox("Passo azimutale (°)", [2.0, 5.0, 10.0], index=1)
        max_range = st.slider("Distanza massima terreno (m)", 1000, 7000, 5000, 500)
        observer_height = st.number_input(
            "Altezza osservatore sopra il terreno (m)",
            min_value=0.0, max_value=10.0, value=1.0, step=0.5
        )

    @st.cache_data(show_spinner="Calcolo del profilo LOLA...")
    def cached_horizon(dem, x, y, step, distance, height):
        profile = calculate_horizon(
            dem,
            x,
            y,
            azimuth_step_deg=step,
            max_distance_m=distance,
            observer_height_m=height,
        )
        return {
            "azimuth": profile.azimuth_deg.tolist(),
            "elevation": profile.elevation_deg.tolist(),
            "distance": profile.max_distance_m.tolist(),
            "valid": profile.valid_samples.tolist(),
            "row": profile.observer_row,
            "col": profile.observer_col,
            "observer_elevation": profile.observer_elevation_m,
            "georeference_validated": profile.georeference_validated,
        }

    try:
        from src.lunar_geometry import locate_observer

        lat, lon = SITES[site_name]
        location = locate_observer(dem_path, lon, lat)

        if not location.inside_raster:
            st.error("Il punto candidato risulta fuori dal raster con la trasformazione attuale.")
        else:
            st.caption(
                f"Cella candidata: riga {location.row}, colonna {location.col}. "
                f"Quota con altezza osservatore: {location.x_m:.1f} m X, "
                f"{location.y_m:.1f} m Y."
            )
            result = cached_horizon(
                str(dem_path),
                location.x_m,
                location.y_m,
                az_step,
                max_range,
                observer_height,
            )

            import numpy as np

            azimuth = np.asarray(result["azimuth"], dtype=float)
            elevation = np.asarray(result["elevation"], dtype=float)
            distance = np.asarray(result["distance"], dtype=float)
            valid = np.isfinite(elevation)

            if not valid.any():
                st.error("Nessun campione valido nel profilo del terreno.")
            else:
                fig_horizon = go.Figure()
                fig_horizon.add_trace(go.Scatterpolar(
                    theta=azimuth[valid],
                    r=elevation[valid],
                    mode="lines",
                    fill="toself",
                    name="Orizzonte DEM",
                    customdata=distance[valid],
                    hovertemplate=(
                        "Azimut griglia: %{theta:.1f}°"
                        "<br>Elevazione: %{r:.2f}°"
                        "<br>Distanza ostacolo: %{customdata:.0f} m"
                        "<extra></extra>"
                    ),
                ))
                fig_horizon.update_layout(
                    title="Elevazione del terreno per azimut della griglia",
                    template="plotly_dark",
                    polar={
                        "angularaxis": {
                            "direction": "clockwise",
                            "rotation": 90,
                        },
                        "radialaxis": {
                            "title": "Elevazione orizzonte (°)",
                        },
                    },
                )
                st.plotly_chart(fig_horizon, use_container_width=True)

                c1, c2, c3 = st.columns(3)
                c1.metric("Azimut validi", f"{int(valid.sum())}/{len(valid)}")
                c2.metric("Orizzonte massimo", f"{np.max(elevation[valid]):.2f}°")
                c3.metric("Orizzonte minimo", f"{np.min(elevation[valid]):.2f}°")

                st.caption(
                    f"Quota osservatore inclusa: {result['observer_elevation']:.2f} m. "
                    f"Georeferenziazione validata: {result['georeference_validated']}."
                )
    except Exception as exc:
        st.error(f"Errore durante l'analisi LOLA: {type(exc).__name__}: {exc}")


st.info(
    "Limiti del prototipo: il grafico mostra la geometria astronomica "
    "rispetto all'orizzonte geometrico. Non include ancora l'ostruzione "
    "dei rilievi DEM, la potenza solare, il bilancio energetico o il "
    "budget del collegamento radio. Le finestre non sono ancora "
    "certificate come operative."
)

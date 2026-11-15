# Last updated: 2026-11-14
import json
import sys
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse, parse_qs

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.astronomy import SITES, query_observations, AstronomyError
from src.mission_planning import find_operational_windows
from src.mission_analytics import summarize_ephemerides
from src.communications import calculate_link_budget
from src.thermal_model import simulate_single_node_thermal

PORT = 8765


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        routes = {
            "/api/communications/link-budget": calculate_link_budget,
            "/api/thermal/simulate": simulate_single_node_thermal,
        }
        operation = routes.get(parsed.path)
        if operation is None:
            return self.send_json(404, {"status": "error", "error": "Endpoint non trovato."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("Body JSON mancante o troppo grande (max 1 MB).")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Il body deve essere un oggetto JSON.")
            result = operation(**payload)
            return self.send_json(200, {"status": "ok", "result": result})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"status": "error", "error": str(exc)})
        except Exception as exc:
            return self.send_json(500, {"status": "error", "error": f"Calcolo non riuscito: {exc}"})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/ephemerides":
            return super().do_GET()

        try:
            q = parse_qs(parsed.query)
            site = q.get("site", ["Shackleton"])[0]
            if site not in SITES:
                raise ValueError(f"Sito non riconosciuto: {site}")

            start_text = q.get("start", [""])[0]
            if not start_text:
                raise ValueError("Seleziona la data e l'ora di inizio UTC.")

            start = datetime.fromisoformat(start_text)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            start = start.astimezone(timezone.utc)

            hours = int(q.get("hours", ["48"])[0])
            min_sun = float(q.get("min_sun", ["5"])[0])
            min_earth = float(q.get("min_earth", ["5"])[0])

            if not 1 <= hours <= 720:
                raise ValueError("La durata deve essere compresa tra 1 e 720 ore.")
            if not -90 <= min_sun <= 90 or not -90 <= min_earth <= 90:
                raise ValueError("Le soglie di elevazione devono essere tra -90° e 90°.")

            latitude, longitude = SITES[site]

            sun = query_observations(
                "10", latitude, longitude, start, hours=hours, step="1h"
            )
            earth = query_observations(
                "399", latitude, longitude, start, hours=hours, step="1h"
            )

            # Le due serie devono riferirsi agli stessi istanti.
            earth_by_time = {o.time_utc: o for o in earth}
            common_times = [o.time_utc for o in sun if o.time_utc in earth_by_time]
            if not common_times:
                raise AstronomyError(
                    "Nessun timestamp comune tra le effemeridi di Sole e Terra."
                )

            sun_by_time = {o.time_utc: o for o in sun}
            sun_values = [sun_by_time[t].elevation_deg for t in common_times]
            earth_values = [earth_by_time[t].elevation_deg for t in common_times]

            windows = find_operational_windows(
                sun_values,
                earth_values,
                min_sun_elevation_deg=min_sun,
                min_earth_elevation_deg=min_earth,
            )

            observations_payload = [{
                "time_utc": t,
                "sun_elevation_deg": sun_by_time[t].elevation_deg,
                "sun_azimuth_deg": sun_by_time[t].azimuth_deg,
                "earth_elevation_deg": earth_by_time[t].elevation_deg,
                "earth_azimuth_deg": earth_by_time[t].azimuth_deg,
            } for t in common_times]
            windows_payload = [{
                "start_utc": common_times[w.start_index],
                "end_utc": common_times[w.end_index],
                "duration_samples": w.duration_samples,
                "sample_step_hours": 1,
                "sampled_span_hours": max(0, w.duration_samples - 1),
                "sun_threshold_deg": min_sun,
                "earth_threshold_deg": min_earth,
                "min_sun_elevation_deg": round(min(sun_values[w.start_index:w.end_index + 1]), 2),
                "min_earth_elevation_deg": round(min(earth_values[w.start_index:w.end_index + 1]), 2),
            } for w in windows]
            analytics = summarize_ephemerides(
                observations_payload,
                min_sun_elevation_deg=min_sun,
                min_earth_elevation_deg=min_earth,
                windows=windows_payload,
            )

            return self.send_json(200, {
                "status": "ok",
                "source": "NASA/JPL Horizons",
                "site": site,
                "latitude_deg": latitude,
                "longitude_east_deg": longitude,
                "start_utc": start.isoformat(),
                "duration_hours": hours,
                "step": "1h",
                "thresholds": {
                    "sun_elevation_deg": min_sun,
                    "earth_elevation_deg": min_earth,
                },
                "observations": observations_payload,
                "windows": windows_payload,
                "analytics": analytics,
                "notice": (
                    "Finestre geometriche preliminari. Non verificano "
                    "ostruzioni del terreno, budget radio o sicurezza di atterraggio."
                ),
            })

        except (ValueError, TypeError) as exc:
            return self.send_json(400, {"status": "error", "error": str(exc)})
        except Exception as exc:
            return self.send_json(502, {
                "status": "error",
                "error": f"Calcolo astronomico non disponibile: {exc}",
            })


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server_thread = Thread(
        target=server.serve_forever,
        name="lunar-http-server",
        daemon=True,
    )
    server_thread.start()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    window = QMainWindow()
    window.setWindowTitle("LUNAR // Mission Control")
    window.resize(1600, 1000)

    view = QWebEngineView(window)
    view.setUrl(QUrl(f"http://127.0.0.1:{PORT}/src/ui_web/index.html"))
    window.setCentralWidget(view)

    # Mantiene riferimenti espliciti agli oggetti per tutta la vita dell'app.
    app._lunar_window = window
    app._lunar_view = view
    app._lunar_server = server
    app._lunar_server_thread = server_thread

    window.show()

    try:
        return app.exec()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())

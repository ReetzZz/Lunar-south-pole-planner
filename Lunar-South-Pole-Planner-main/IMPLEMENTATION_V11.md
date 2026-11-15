<!-- Last updated: 2026-11-14 -->
# Lunar South Pole Planner — implementation increment v11

This is an additive backend increment intended to be overlaid on the existing project. It does not modify the Three.js scene, GLB loading, camera, lighting, rotation, or mouse controls.

## Added

- `src/mission_analytics.py`: server-side statistics for paired Sun/Earth elevation samples. Invalid/missing samples are counted, never interpolated or silently replaced. Window duration uses elapsed sample span (`N-1` intervals), not sample count.
- `src/communications.py`: transparent free-space RF link-budget calculator (FSPL, received power, link margin, configured margin check).
- `src/thermal_model.py`: single-node transient thermal estimator using solar absorption, internal heat, thermal radiation, and optional conductive coupling, integrated with RK4.
- `src/ui_web/app.py`: includes server-side analytics in `/api/ephemerides`; adds JSON POST endpoints:
  - `/api/communications/link-budget`
  - `/api/thermal/simulate`
- Unit tests for the three new scientific calculation modules.

## API examples

`POST /api/communications/link-budget` JSON:

```json
{
  "distance_km": 1000,
  "frequency_ghz": 2.2,
  "transmit_power_dbm": 30,
  "transmit_antenna_gain_dbi": 20,
  "receive_antenna_gain_dbi": 30,
  "system_losses_db": 3,
  "receiver_sensitivity_dbm": -110,
  "required_margin_db": 3
}
```

`POST /api/thermal/simulate` JSON:

```json
{
  "duration_s": 3600,
  "step_s": 10,
  "initial_temperature_k": 250,
  "thermal_capacity_j_k": 10000,
  "solar_flux_w_m2": 1361,
  "projected_area_m2": 0.2,
  "absorptivity": 0.7,
  "emissivity": 0.8,
  "radiator_area_m2": 0.3,
  "internal_power_w": 20,
  "environment_temperature_k": 3,
  "illumination_fraction": 0.5,
  "conductive_coupling_w_k": 0,
  "sink_temperature_k": 100
}
```

All POST endpoints return `{ "status": "ok", "result": ... }` or a structured error. JSON request bodies are limited to 1 MB.

## Verification performed in the build environment

- 7 new unit tests passed.
- Python bytecode compilation passed for all changed Python modules.

## Scientific limits — do not remove these caveats

- RF results are free-space link-budget estimates. They do not establish terrain line-of-sight, antenna pointing, interference margin, modulation/coding performance, or flight hardware qualification. Any unmodeled losses must be entered explicitly.
- Thermal results are a single lumped-node estimate. They are not a multi-node spacecraft thermal model and do not establish hardware temperature compliance.
- Existing terrain, DEM, horizon, rover, and descent modules are not automatically certified by this increment. Coordinate-frame/georeferencing validation remains a prerequisite before treating terrain visibility or hazard classifications as operational truth.
- The P-System journal in the source project remains local; this increment does not create a remote P-System connection.

## Install

Extract the ZIP at the root of the existing project, allowing files to merge. The archive contains only additive/new files and the updated `src/ui_web/app.py`; it does not contain the 3D renderer files.

Run tests from the project root:

```bash
python -m unittest discover -s tests -v
```

Start the app using the project's existing launch command.

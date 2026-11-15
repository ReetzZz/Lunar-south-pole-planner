# Last updated: 2026-11-14
"""Single-node transient thermal estimate for a lunar surface asset.

The model solves a lumped energy balance with solar absorption, internal heat,
thermal radiation and optional conductive coupling. It is not a validated
spacecraft thermal design or a substitute for a multi-node thermal model.
"""
from __future__ import annotations
import math

STEFAN_BOLTZMANN = 5.670374419e-8


def simulate_single_node_thermal(
    *, duration_s: float, step_s: float, initial_temperature_k: float,
    thermal_capacity_j_k: float, solar_flux_w_m2: float,
    projected_area_m2: float, absorptivity: float, emissivity: float,
    radiator_area_m2: float, internal_power_w: float,
    environment_temperature_k: float = 3.0,
    illumination_fraction: float = 1.0,
    conductive_coupling_w_k: float = 0.0,
    sink_temperature_k: float = 100.0,
) -> dict:
    p = locals().copy()
    for key, value in p.items():
        if not math.isfinite(float(value)):
            raise ValueError(f"{key} must be finite")
    if duration_s <= 0 or step_s <= 0 or thermal_capacity_j_k <= 0:
        raise ValueError("duration_s, step_s and thermal_capacity_j_k must be > 0")
    if initial_temperature_k <= 0 or environment_temperature_k < 0 or sink_temperature_k < 0:
        raise ValueError("Temperatures must be physically valid in kelvin")
    if solar_flux_w_m2 < 0 or projected_area_m2 < 0 or radiator_area_m2 < 0 or internal_power_w < 0 or conductive_coupling_w_k < 0:
        raise ValueError("Power, areas and conductance must be non-negative")
    if not 0 <= absorptivity <= 1 or not 0 <= emissivity <= 1 or not 0 <= illumination_fraction <= 1:
        raise ValueError("absorptivity, emissivity and illumination_fraction must be in [0, 1]")

    def net_power(temp_k: float) -> float:
        solar = absorptivity * solar_flux_w_m2 * projected_area_m2 * illumination_fraction
        internal = internal_power_w
        radiated = emissivity * STEFAN_BOLTZMANN * radiator_area_m2 * (temp_k**4 - environment_temperature_k**4)
        conducted = conductive_coupling_w_k * (temp_k - sink_temperature_k)
        return solar + internal - radiated - conducted

    # Explicit integration with bounded substeps to keep the solver predictable.
    max_step = min(float(step_s), 5.0)
    count = max(1, math.ceil(duration_s / max_step))
    if count > 1_000_000:
        raise ValueError("Simulation would require over 1,000,000 integration steps; increase step_s or reduce duration_s")
    dt = duration_s / count
    temp = float(initial_temperature_k)
    samples = [{"time_s": 0.0, "temperature_k": temp}]
    for i in range(1, count + 1):
        # RK4 on dT/dt = Q_net/C.
        k1 = net_power(temp) / thermal_capacity_j_k
        k2 = net_power(temp + 0.5 * dt * k1) / thermal_capacity_j_k
        k3 = net_power(temp + 0.5 * dt * k2) / thermal_capacity_j_k
        k4 = net_power(temp + dt * k3) / thermal_capacity_j_k
        temp += dt * (k1 + 2*k2 + 2*k3 + k4) / 6
        if not math.isfinite(temp) or temp <= 0 or temp > 5000:
            raise ArithmeticError("Thermal integration became non-physical; reduce step or review inputs")
        if i == count or i % max(1, round(count / 200)) == 0:
            samples.append({"time_s": min(duration_s, i * dt), "temperature_k": temp})

    temperatures = [s["temperature_k"] for s in samples]
    return {
        "schema": "lunar-single-node-thermal/1.0",
        "status": "preliminary_estimate",
        "model": "single lumped thermal node; transient RK4 integration",
        "duration_s": float(duration_s),
        "integration_step_s": dt,
        "initial_temperature_k": float(initial_temperature_k),
        "final_temperature_k": temp,
        "minimum_temperature_k": min(temperatures),
        "maximum_temperature_k": max(temperatures),
        "samples": samples,
        "assumptions": ["constant properties and illumination fraction", "uniform node temperature",
                        "radiation to a fixed environment temperature", "no latent heat or contact transients"],
        "not_evaluated": ["multi-node gradients", "dust degradation", "terrain-dependent radiative view factors",
                          "qualified hardware limits", "validated material properties"],
    }

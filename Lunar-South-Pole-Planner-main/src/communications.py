# Last updated: 2026-11-14
"""Transparent free-space RF link-budget estimator for lunar mission studies.

It is a first-order calculator, not a propagation/antenna qualification tool.
Terrain blockage, pointing, polarization, atmosphere, interference, coding,
protocol overhead and hardware temperature effects are not inferred.
"""
from __future__ import annotations
import math


def free_space_path_loss_db(distance_km: float, frequency_ghz: float) -> float:
    distance_km = float(distance_km)
    frequency_ghz = float(frequency_ghz)
    if not math.isfinite(distance_km) or distance_km <= 0:
        raise ValueError("distance_km must be finite and > 0")
    if not math.isfinite(frequency_ghz) or frequency_ghz <= 0:
        raise ValueError("frequency_ghz must be finite and > 0")
    # Friis free-space loss, distance in km and frequency in GHz.
    return 92.45 + 20 * math.log10(distance_km) + 20 * math.log10(frequency_ghz)


def calculate_link_budget(
    *, distance_km: float, frequency_ghz: float,
    transmit_power_dbm: float, transmit_antenna_gain_dbi: float,
    receive_antenna_gain_dbi: float, system_losses_db: float,
    receiver_sensitivity_dbm: float, required_margin_db: float = 3.0,
) -> dict:
    values = {
        "transmit_power_dbm": transmit_power_dbm,
        "transmit_antenna_gain_dbi": transmit_antenna_gain_dbi,
        "receive_antenna_gain_dbi": receive_antenna_gain_dbi,
        "system_losses_db": system_losses_db,
        "receiver_sensitivity_dbm": receiver_sensitivity_dbm,
        "required_margin_db": required_margin_db,
    }
    for key, value in values.items():
        if not math.isfinite(float(value)):
            raise ValueError(f"{key} must be finite")
    if system_losses_db < 0 or required_margin_db < 0:
        raise ValueError("system_losses_db and required_margin_db must be >= 0")

    fspl = free_space_path_loss_db(distance_km, frequency_ghz)
    received = (float(transmit_power_dbm) + float(transmit_antenna_gain_dbi)
                + float(receive_antenna_gain_dbi) - fspl - float(system_losses_db))
    margin = received - float(receiver_sensitivity_dbm)
    return {
        "schema": "lunar-rf-link-budget/1.0",
        "status": "preliminary_estimate",
        "inputs": {"distance_km": float(distance_km),
                   "frequency_ghz": float(frequency_ghz), **{k: float(v) for k, v in values.items()}},
        "free_space_path_loss_db": fspl,
        "received_power_dbm": received,
        "link_margin_db": margin,
        "required_margin_db": float(required_margin_db),
        "margin_check": "meets_configured_margin" if margin >= required_margin_db else "below_configured_margin",
        "assumptions": ["free-space propagation", "constant antenna gains",
                        "lumped system losses", "no terrain blockage or pointing loss unless included in system_losses_db"],
        "not_evaluated": ["terrain_line_of_sight", "multipath", "polarization", "interference",
                          "coding_and_protocol", "hardware_qualification"],
    }

# Last updated: 2026-11-14
import unittest
from src.thermal_model import simulate_single_node_thermal

class ThermalModelTests(unittest.TestCase):
    def test_simulation_returns_finite_temperatures(self):
        result = simulate_single_node_thermal(duration_s=600, step_s=10,
            initial_temperature_k=250, thermal_capacity_j_k=10000,
            solar_flux_w_m2=1361, projected_area_m2=0.2,
            absorptivity=0.7, emissivity=0.8, radiator_area_m2=0.3,
            internal_power_w=20, illumination_fraction=0.5)
        self.assertEqual(result["status"], "preliminary_estimate")
        self.assertGreater(result["final_temperature_k"], 0)
        self.assertGreaterEqual(len(result["samples"]), 2)

    def test_invalid_absorptivity(self):
        with self.assertRaises(ValueError):
            simulate_single_node_thermal(duration_s=10, step_s=1,
                initial_temperature_k=250, thermal_capacity_j_k=1000,
                solar_flux_w_m2=0, projected_area_m2=0,
                absorptivity=2, emissivity=0.8, radiator_area_m2=1,
                internal_power_w=0)

if __name__ == "__main__":
    unittest.main()

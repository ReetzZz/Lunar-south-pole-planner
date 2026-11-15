# Last updated: 2026-11-14
import unittest
from src.communications import free_space_path_loss_db, calculate_link_budget

class CommunicationsTests(unittest.TestCase):
    def test_fspl_known_scale(self):
        self.assertGreater(free_space_path_loss_db(1000, 2.2), 150)

    def test_link_budget_margin(self):
        result = calculate_link_budget(distance_km=1000, frequency_ghz=2.2,
            transmit_power_dbm=30, transmit_antenna_gain_dbi=20,
            receive_antenna_gain_dbi=30, system_losses_db=3,
            receiver_sensitivity_dbm=-110, required_margin_db=3)
        self.assertIn("link_margin_db", result)
        self.assertEqual(result["status"], "preliminary_estimate")

    def test_invalid_distance(self):
        with self.assertRaises(ValueError):
            free_space_path_loss_db(0, 2.2)

if __name__ == "__main__":
    unittest.main()

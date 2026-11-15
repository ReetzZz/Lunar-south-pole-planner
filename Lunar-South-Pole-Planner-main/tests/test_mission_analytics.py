import unittest
from src.mission_analytics import summarize_ephemerides

class MissionAnalyticsTests(unittest.TestCase):
    def test_paired_constraints_and_windows(self):
        rows = [
            {"sun_elevation_deg": 10, "earth_elevation_deg": 8},
            {"sun_elevation_deg": 2, "earth_elevation_deg": 9},
            {"sun_elevation_deg": 12, "earth_elevation_deg": 1},
        ]
        windows = [{"start_utc": "t0", "duration_samples": 2, "sample_step_hours": 1}]
        result = summarize_ephemerides(rows, min_sun_elevation_deg=5,
                                       min_earth_elevation_deg=5, windows=windows)
        self.assertEqual(result["valid_sample_count"], 3)
        self.assertEqual(result["simultaneous"]["passing_samples"], 1)
        self.assertAlmostEqual(result["simultaneous"]["passing_percent"], 33.333, places=2)
        self.assertEqual(result["operational_windows"]["total_sampled_span_hours"], 1.0)

    def test_invalid_rows_are_not_filled(self):
        rows = [{"sun_elevation_deg": 1, "earth_elevation_deg": 2}, {"sun_elevation_deg": None}]
        result = summarize_ephemerides(rows, min_sun_elevation_deg=0,
                                       min_earth_elevation_deg=0)
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["valid_sample_count"], 1)
        self.assertEqual(result["invalid_sample_count"], 1)

if __name__ == "__main__":
    unittest.main()

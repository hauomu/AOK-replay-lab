import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "discord_bot" / "src"))

try:
    from aok_bot.replay_parser import _derive_gather_rates, _resource_sample_from_stats
except ImportError as exc:  # pragma: no cover - optional runtime deps
    _derive_gather_rates = None
    IMPORT_ERROR = exc


@unittest.skipIf(_derive_gather_rates is None, "replay parser dependencies unavailable")
class GatherRateTests(unittest.TestCase):
    def feed(self, history, seconds, gathered, rate=0):
        sample = {"gold": {"gathered_estimate": gathered, "rate": rate}}
        _derive_gather_rates(history, sample, seconds)
        return sample["gold"]["rate"]

    def test_rate_is_per_minute_over_trailing_window(self):
        history = {}
        self.assertEqual(self.feed(history, 0, 0), 0)
        for t in range(10, 61, 10):
            rate = self.feed(history, t, t * 5)  # 5 gold per second
        self.assertEqual(rate, 300)
        # Income stops: after a full window the rate falls back to 0.
        for t in range(70, 121, 10):
            rate = self.feed(history, t, 300)
        self.assertEqual(rate, 0)

    def test_nonzero_tracker_rate_is_kept(self):
        history = {}
        self.feed(history, 0, 0)
        self.assertEqual(self.feed(history, 10, 1000, rate=42), 42)

    def test_missing_time_leaves_sample_alone(self):
        sample = {"gold": {"gathered_estimate": 100, "rate": 0}}
        _derive_gather_rates({}, sample, None)
        self.assertEqual(sample["gold"]["rate"], 0)

    def test_gathered_estimate_does_not_double_count_active_forces(self):
        stats = {
            "m_scoreValueMineralsCurrent": 100,
            "m_scoreValueMineralsUsedCurrentArmy": 400,
            "m_scoreValueMineralsUsedInProgressArmy": 200,
            "m_scoreValueMineralsUsedActiveForces": 600,
            "m_scoreValueMineralsUsedCurrentEconomy": 50,
            "m_scoreValueMineralsLostArmy": 300,
            "m_scoreValueMineralsKilledArmy": 900,
            "m_scoreValueMineralsFriendlyFireArmy": 70,
        }
        samples, _, _ = _resource_sample_from_stats(stats)
        self.assertEqual(samples["gold"]["gathered_estimate"], 100 + 400 + 200 + 50 + 300)


if __name__ == "__main__":
    unittest.main()

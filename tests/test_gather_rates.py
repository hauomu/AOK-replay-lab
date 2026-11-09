import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "discord_bot" / "src"))

try:
    from aok_bot.models import PlayerStats, ReplaySummary
    from aok_bot.replay_parser import (
        _apply_leave_based_results, _build_team_stats, _derive_gather_rates,
        _remove_starting_stock, _resource_sample_from_stats,
    )
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

    def test_starting_stock_is_not_gathered(self):
        state = {}

        def gathered(seconds, raw):
            sample = {"gold": {"gathered_estimate": raw}}
            _remove_starting_stock(state, sample, seconds)
            return sample["gold"]["gathered_estimate"]

        self.assertEqual(gathered(0, 200), 0)        # starting stockpile
        self.assertEqual(gathered(10, 250), 50)      # real income
        self.assertEqual(gathered(20, 1950), 50)     # map spawns 1,700 of units
        self.assertEqual(gathered(30, 2050), 150)
        self.assertEqual(gathered(300, 3050), 1150)  # later big jumps still count

    def test_leaver_average_covers_time_slot_kept_gathering(self):
        p = PlayerStats("Leaver", team_id=0, leave_time_seconds=77)
        p.resource_gathered_estimate["gold"] = 18000
        p.resource_last_gain_seconds = 3600
        summary = ReplaySummary(Path("x"), parser_ok=True, duration_seconds=3600, players=[p])
        _build_team_stats(summary)
        self.assertEqual(p.resource_average_rate["gold"], 300)


@unittest.skipIf(_derive_gather_rates is None, "replay parser dependencies unavailable")
class ContradictoryResultTests(unittest.TestCase):
    def summary(self, *players):
        return ReplaySummary(Path("x"), parser_ok=True, match_mode="Team", duration_seconds=3033,
                             players=list(players))

    def test_win_on_both_teams_names_no_recorded_winner(self):
        s = self.summary(
            # Corpus shape (replay 112): closing exits in the last seconds.
            PlayerStats("A", team_id=0, result="Win"),
            PlayerStats("B", team_id=0, result="Undecided", leave_time_seconds=2819),
            PlayerStats("C", team_id=1, result="Win", leave_time_seconds=3031),
            PlayerStats("D", team_id=1, result="Undecided", leave_time_seconds=2291),
        )
        _apply_leave_based_results(s)
        self.assertNotIn("Win", {p.result for p in s.players})
        self.assertTrue(any("more than one side" in k for k in s.key_findings))
        # One player per side left early, so the shares tie: no likely call.
        self.assertEqual({p.result for p in s.players}, {"Undecided"})

    def test_win_on_both_teams_falls_back_to_leave_events(self):
        s = self.summary(
            PlayerStats("A", team_id=0, result="Win"),
            PlayerStats("B", team_id=1, result="Win", leave_time_seconds=500),
        )
        _apply_leave_based_results(s)
        self.assertEqual([p.result for p in s.players], ["Win", "Loss"])

    def test_single_winning_side_is_kept(self):
        s = self.summary(
            PlayerStats("A", team_id=0, result="Win"),
            PlayerStats("B", team_id=1, result="Loss"),
        )
        _apply_leave_based_results(s)
        self.assertEqual([p.result for p in s.players], ["Win", "Loss"])


@unittest.skipIf(_derive_gather_rates is None, "replay parser dependencies unavailable")
class LikelyWinnerTests(unittest.TestCase):
    def run_case(self, *players, duration=2000):
        s = ReplaySummary(Path("x"), parser_ok=True, match_mode="Team", duration_seconds=duration,
                          players=list(players))
        _apply_leave_based_results(s)
        _build_team_stats(s)
        return s

    def test_side_with_larger_share_gone_is_likely_loser(self):
        s = self.run_case(
            PlayerStats("A", team_id=0, result="Undecided"),
            PlayerStats("B", team_id=0, result="Undecided", leave_time_seconds=1990),  # closing exit
            PlayerStats("C", team_id=1, result="Undecided", leave_time_seconds=1500),
            PlayerStats("D", team_id=1, result="Undecided"),
        )
        self.assertEqual([p.result for p in s.players], ["Likely win", "Likely win", "Likely loss", "Likely loss"])
        self.assertEqual(s.winner_label(), "Unknown")
        self.assertEqual(s.likely_winner_label(), "Team 0 (A, B)")
        self.assertIn("inferred from who left", s.winner_display())

    def test_equal_share_gone_makes_no_call(self):
        s = self.run_case(
            PlayerStats("A", team_id=0, result="Undecided", leave_time_seconds=900),
            PlayerStats("B", team_id=0, result="Undecided"),
            PlayerStats("C", team_id=1, result="Undecided", leave_time_seconds=1200),
            PlayerStats("D", team_id=1, result="Undecided"),
        )
        self.assertEqual({p.result for p in s.players}, {"Undecided"})
        self.assertIsNone(s.likely_winner_label())

    def test_recorded_winner_is_not_overridden(self):
        s = self.run_case(
            PlayerStats("A", team_id=0, result="Win", leave_time_seconds=100),
            PlayerStats("B", team_id=1, result="Undecided"),
        )
        self.assertEqual([p.result for p in s.players], ["Win", "Undecided"])
        self.assertIsNone(s.likely_winner_label())


if __name__ == "__main__":
    unittest.main()

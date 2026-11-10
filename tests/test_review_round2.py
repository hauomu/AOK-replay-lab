"""Regression tests for the second review round (results, embeds, mining)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src"), str(ROOT / "strategy_mining/src")]

try:
    from aok_bot.models import PlayerStats, ReplaySummary
    from aok_bot.replay_parser import (
        _apply_leave_based_results, _build_match_story, _build_team_stats, _player_average_rates,
    )
    from aok_bot.reporting import make_match_embed
except ImportError:  # pragma: no cover - optional runtime deps
    PlayerStats = None

try:
    from aok_ml.replay_events import ExtractedReplay, build_snapshots
except ImportError:  # pragma: no cover
    ExtractedReplay = None


def summary(mode="Team", duration=2000, events_complete=True, *players):
    s = ReplaySummary(Path("x.SC2Replay"), parser_ok=True, match_mode=mode, duration_seconds=duration,
                      players=list(players))
    s.game_events_complete = events_complete
    return s


def run(s):
    _apply_leave_based_results(s)
    _build_team_stats(s)
    return [p.result for p in s.players]


@unittest.skipIf(PlayerStats is None, "bot dependencies unavailable")
class ResultRuleTests(unittest.TestCase):
    def test_ffa_win_on_several_players_names_no_winner(self):
        s = summary("Free-for-all", 1570, True,
                    PlayerStats("A", team_id=1, result="Win"),
                    PlayerStats("B", team_id=2, result="Win"),
                    PlayerStats("C", team_id=3, result="Undecided", leave_time_seconds=900))
        self.assertEqual(run(s), ["Undecided", "Undecided", "Loss"])
        self.assertEqual(s.winner_label(), "Unknown")

    def test_computer_slot_does_not_keep_a_side_alive(self):
        s = summary("Team", 2000, True,
                    PlayerStats("Human", team_id=0, result="Undecided", leave_time_seconds=1200),
                    PlayerStats("Player 2", team_id=0, result="Undecided", is_computer=True),
                    PlayerStats("B", team_id=1, result="Undecided"))
        self.assertEqual(run(s), ["Loss", "Loss", "Win"])
        self.assertEqual(s.result_source, "leaves")

    def test_recorded_winner_means_the_other_side_lost(self):
        s = summary("Team", 2000, True,
                    PlayerStats("A", team_id=0, result="Win"),
                    PlayerStats("B", team_id=1, result="Undecided", leave_time_seconds=1990),
                    PlayerStats("C", team_id=1, result="Undecided", leave_time_seconds=1500))
        self.assertEqual(run(s), ["Win", "Loss", "Loss"])
        self.assertEqual({t.team_id: t.result for t in s.teams}, {0: "Win", 1: "Loss"})

    def test_single_side_gets_no_invented_win(self):
        s = summary("Team", 2000, True,
                    PlayerStats("A", team_id=0, result="Undecided"),
                    PlayerStats("B", team_id=0, result="Undecided", leave_time_seconds=500))
        self.assertEqual(run(s), ["Undecided", "Undecided"])

    def test_everyone_quitting_at_the_end_is_not_a_double_loss(self):
        s = summary("Team", 2000, True,
                    PlayerStats("A", team_id=0, result="Undecided", leave_time_seconds=1995),
                    PlayerStats("B", team_id=1, result="Undecided", leave_time_seconds=1998))
        self.assertNotIn("Loss", run(s))

    def test_incomplete_game_events_skip_leave_inference(self):
        s = summary("Team", 2000, False,
                    PlayerStats("A", team_id=0, result="Undecided"),
                    PlayerStats("B", team_id=1, result="Undecided", leave_time_seconds=500))
        self.assertEqual(run(s), ["Undecided", "Undecided"])

    def test_team_result_does_not_depend_on_player_order(self):
        s = summary("Team", 2000, True,
                    PlayerStats("W", team_id=0, result="Win"),
                    PlayerStats("A", team_id=1, result="Undecided"),
                    PlayerStats("B", team_id=1, result="Loss"),
                    PlayerStats("C", team_id=1, result="Undecided"))
        _build_team_stats(s)
        self.assertEqual({t.team_id: t.result for t in s.teams}, {0: "Win", 1: "Loss"})

    def test_leave_inferred_winner_is_not_called_recorded(self):
        s = summary("Team", 2000, True,
                    PlayerStats("A", team_id=0, result="Undecided"),
                    PlayerStats("B", team_id=1, result="Undecided", leave_time_seconds=600))
        run(s)
        _build_match_story(s)
        self.assertIn("inferred from leave events", s.verdict)
        self.assertNotIn("Recorded winner", s.verdict)

    def test_player_without_team_gets_average_rate(self):
        p = PlayerStats("Solo")
        p.resource_gathered_estimate["gold"] = 600
        s = summary("Team", 60, True, p)
        _player_average_rates(s, p)
        self.assertEqual(p.resource_average_rate["gold"], 600)


@unittest.skipIf(PlayerStats is None, "bot dependencies unavailable")
class EmbedBudgetTests(unittest.TestCase):
    def test_embed_stays_inside_discord_limits(self):
        s = summary("Team", 2000, True,
                    PlayerStats("A" * 40, team_id=0, result="Win"), PlayerStats("B" * 40, team_id=1, result="Loss"))
        s.map_name = "M" * 400
        s.verdict = "v" * 1500
        s.turning_points = ["t" * 900] * 2
        s.team_evaluations = ["e" * 900] * 2
        s.player_takeaways = ["p" * 900] * 2
        s.key_findings = ["k" * 900] * 5
        s.warnings = ["w" * 900] * 3
        _build_team_stats(s)
        embed = make_match_embed(s)
        total = len(embed.title) + sum(len(f.name) + len(f.value) for f in embed.fields)
        self.assertLessEqual(len(embed.title), 256)
        self.assertLessEqual(total, 6000)
        self.assertTrue(all(len(f.value) <= 1024 for f in embed.fields))

    def test_failed_parse_embed_claims_no_winner(self):
        s = summary("Team", 2000, True, PlayerStats("A", team_id=0, result="Win"))
        s.parser_ok = False
        values = {f.name: f.value for f in make_match_embed(s).fields}
        self.assertTrue(values["Winner"].startswith("Unknown"))


@unittest.skipIf(ExtractedReplay is None, "mining dependencies unavailable")
class MiningSnapshotTests(unittest.TestCase):
    def test_no_snapshots_after_the_replay_ends(self):
        ex = ExtractedReplay(replay_id="r", source_name="r", duration_seconds=12 * 60,
                             players=[{"player_index": 0, "player_id": 1, "name": "A", "team_id": 1}])
        minutes = sorted({row["snapshot_minute"] for row in build_snapshots(ex)})
        self.assertEqual(minutes, [5, 10])


if __name__ == "__main__":
    unittest.main()

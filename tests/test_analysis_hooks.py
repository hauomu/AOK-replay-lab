from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot" / "src")]

from aok_bot.analysis_hooks import ANALYSIS_HOOKS, analyze, analyze_coaching, analyze_stats, analyze_team
from aok_bot.models import PlayerStats, ReplaySummary, TeamStats
from aok_bot.reporting import markdown_report


def sample(*, parser_ok: bool = True, match_mode: str = "Team") -> ReplaySummary:
    players = [
        PlayerStats("Ada", team_id=1, role_label="Cavalry pressure", kills=2, losses=5,
                    animal_kills=1, deaths_to_animals=1, commands=120, apm=24, leave_time_seconds=600),
        PlayerStats("Lin", team_id=2, role_label="Ranged support", kills=4, losses=1,
                    commands=80, leave_time_seconds=720),
    ]
    teams = [TeamStats(1, label="Blue", players=["Ada"], kills=2, losses=5),
             TeamStats(2, label="Red", players=["Lin"], kills=4, losses=1)]
    return ReplaySummary(Path("sample.SC2Replay"), parser_ok=parser_ok, match_mode=match_mode,
                         players=players, teams=teams, animal_stats=PlayerStats("Animals", kills=1, losses=1, units_born=3))


class AnalysisHookTests(unittest.TestCase):
    def test_registry_and_default_stats_dispatch(self) -> None:
        summary = sample()
        self.assertEqual(set(ANALYSIS_HOOKS), {"stats", "coaching", "team"})
        self.assertEqual(analyze(summary), analyze_stats(summary))
        self.assertEqual(analyze_coaching(summary)["mode"], "coaching")
        self.assertEqual(analyze_team(summary)["mode"], "team")

    def test_failed_parse_is_unavailable_without_advice(self) -> None:
        result = analyze(sample(parser_ok=False), "coaching")
        self.assertFalse(result["available"])
        self.assertEqual(result["items"], [])
        self.assertTrue(result["warnings"])

    def test_invalid_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analyze(sample(), "build-order")

    def test_coaching_questions_are_grounded_in_recorded_metrics(self) -> None:
        result = analyze_coaching(sample())
        ada = next(item for item in result["items"] if item["subject"] == "Ada")
        self.assertTrue(any("5 PvP losses versus 2 PvP kills" in x for x in ada["observations"]))
        self.assertTrue(any("animal encounters" in x.lower() for x in ada["review_questions"]))
        self.assertTrue(any("120 commands" in x for x in ada["observations"]))
        self.assertTrue(any("600 seconds" in x for x in ada["observations"]))
        rendered = " ".join(ada["observations"] + ada["review_questions"])
        self.assertNotIn("spent", rendered.lower())
        self.assertNotIn("will win", rendered.lower())

    def test_ffa_team_mode_does_not_claim_coordination(self) -> None:
        result = analyze_team(sample(match_mode="Free-for-all"))
        self.assertTrue(any("does not infer team coordination" in x for x in result["limitations"]))
        text = str(result).lower()
        self.assertNotIn("coordinated with", text)

    def test_report_dispatch_renders_selected_mode_without_network(self) -> None:
        coaching = markdown_report(sample(), "coaching")
        team = markdown_report(sample(), "team")
        stats = markdown_report(sample())
        self.assertIn("## Coaching analysis", coaching)
        self.assertIn("Which engagements account for the losses", coaching)
        self.assertIn("## Team analysis", team)
        self.assertIn("role distribution", team)
        self.assertIn("## Stats analysis", stats)


if __name__ == "__main__":
    unittest.main()

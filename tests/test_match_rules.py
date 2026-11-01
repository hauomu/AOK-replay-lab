from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot" / "src"), str(ROOT / "strategy_mining" / "src")]

from aok_bot.match_rules import is_neutral_player, normalize_match_groups
from aok_bot.models import PlayerStats, ReplaySummary
from aok_bot.replay_parser import _classify_player_role, _normalize_match_mode, _team_style
from aok_ml.replay_events import (
    ExtractedReplay,
    _attribute_death,
    build_snapshots,
    classify_role,
    classify_team,
)


class SharedMatchRulesTests(unittest.TestCase):
    def test_role_parity_infantry_and_animal_clear(self) -> None:
        for stats, expected in (
            ({"infantry_units": 300}, "Infantry frontline/mass army"),
            ({"animal_kills": 30}, "Map-control / animal-clear support"),
        ):
            with self.subTest(expected=expected):
                player = PlayerStats(name="p", **stats)
                self.assertEqual(_classify_player_role(player), expected)
                self.assertEqual(classify_role(stats), expected)

    def test_team_style_wrappers_share_rules(self) -> None:
        team = {"infantry_units": 60, "ranged_units": 40}
        self.assertEqual(_team_style(type("Team", (), team)()), classify_team(team))

    def test_duel_team_and_ffa_groups_preserve_raw_ids(self) -> None:
        cases = (
            ([1, 2], "Duel", [1, 2]),
            ([1, 1, 2, 2], "Team", [1, 1, 2, 2]),
            ([1, 1, 1, 1], "Free-for-all", [1, 2, 3, 4]),
            ([1, 2, 3, 4], "Free-for-all", [1, 2, 3, 4]),
        )
        for raw_ids, expected_mode, expected_groups in cases:
            with self.subTest(raw_ids=raw_ids):
                players = [{"name": f"p{i}", "player_id": i + 1, "team_id": team}
                           for i, team in enumerate(raw_ids)]
                mode, groups = normalize_match_groups(players)
                self.assertEqual((mode, groups), (expected_mode, expected_groups))
                if mode == "Free-for-all":
                    for player, original, group in zip(players, raw_ids, groups):
                        player["raw_team_id"] = original
                        player["team_id"] = group
                        self.assertEqual(player["raw_team_id"], original)

    def test_bot_wrapper_assigns_ffa_groups_and_keeps_neutral_separate(self) -> None:
        players = [PlayerStats(name=f"p{i}", team_id=1) for i in range(4)]
        neutral = PlayerStats(name="Player 15", team_id=1)
        summary = ReplaySummary(source_path=Path("synthetic"), players=[*players, neutral])
        _normalize_match_mode(summary)
        self.assertEqual(summary.match_mode, "Free-for-all")
        self.assertEqual([p.team_id for p in players], [1, 2, 3, 4])
        self.assertEqual(neutral.team_id, 1)

    def test_animal_combat_stays_out_of_pvp_totals(self) -> None:
        stats = {0: {"kills": 0, "losses": 0, "animal_kills": 0, "deaths_to_animals": 0},
                 1: {"kills": 0, "losses": 0, "animal_kills": 0, "deaths_to_animals": 0}}
        _attribute_death(stats, {"player_id": 15, "player_index": None,
                                 "killer_player_id": 1, "killer_player_index": 0})
        _attribute_death(stats, {"player_id": 2, "player_index": 1,
                                 "killer_player_id": 15, "killer_player_index": None})
        _attribute_death(stats, {"player_id": 2, "player_index": 1,
                                 "killer_player_id": 1, "killer_player_index": 0})
        self.assertEqual(stats[0], {"kills": 1, "losses": 0, "animal_kills": 1, "deaths_to_animals": 0})
        self.assertEqual(stats[1], {"kills": 0, "losses": 1, "animal_kills": 0, "deaths_to_animals": 1})

    def test_snapshot_rows_expose_match_mode_and_raw_team(self) -> None:
        replay = ExtractedReplay(replay_id="id", source_name="source", match_mode="Free-for-all")
        replay.players = [
            {"player_index": 0, "player_id": 1, "name": "p", "team_id": 3,
             "raw_team_id": 1, "result": "Win"},
            {"player_index": 14, "player_id": 15, "name": "Player 15", "team_id": 1,
             "raw_team_id": 1, "result": None},
        ]
        replay.unit_events = [{"event_type": "unit_died", "player_index": 0, "minute": 1,
                               "killer_player_id": 15, "killer_player_index": 14}]
        rows = build_snapshots(replay)
        self.assertEqual(rows[0]["match_mode"], "Free-for-all")
        self.assertEqual(rows[0]["team_id"], 3)
        self.assertEqual(rows[0]["raw_team_id"], 1)
        self.assertEqual(rows[0]["losses_to_now"], 0)
        self.assertEqual(len(rows), 8)
        self.assertTrue(is_neutral_player(replay.players[1]))


if __name__ == "__main__":
    unittest.main()

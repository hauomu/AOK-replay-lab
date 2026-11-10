import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src"), str(ROOT / "discord_bot/external/s2protocol")]
from aok_bot.defense import DefenseTracker, defense_findings, defense_kind
from aok_bot.models import PlayerStats, ReplaySummary, TeamStats

PREFIX = "NNet.Replay.Tracker."


def ev(kind, tag, **fields):
    return {"_event": PREFIX + kind, "m_unitTagIndex": tag, "m_unitTagRecycle": 1, **fields}


def init(tag, unit, pid, x=10, y=10):
    return ev("SUnitInitEvent", tag, m_unitTypeName=unit.encode(), m_controlPlayerId=pid, m_x=x, m_y=y)


def born(tag, unit, pid, x=10, y=10):
    return ev("SUnitBornEvent", tag, m_unitTypeName=unit.encode(), m_controlPlayerId=pid, m_x=x, m_y=y)


def done(tag):
    return ev("SUnitDoneEvent", tag)


def died(tag, killer, x=10, y=10):
    return ev("SUnitDiedEvent", tag, m_killerPlayerId=killer, m_x=x, m_y=y)


class DefenseKindTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(defense_kind("WatchTower"), "Watch tower")
        self.assertEqual(defense_kind("Outpost"), "Watch tower")
        self.assertEqual(defense_kind("GateOpenVert"), "Gate")
        self.assertEqual(defense_kind("WallHorizontal"), "Wall")
        self.assertEqual(defense_kind("Barricade"), "Barricade")
        self.assertIsNone(defense_kind("Barracks"))


class TrackerTests(unittest.TestCase):
    def run_events(self, events):
        self.players = [PlayerStats("Ada", team_id=1), PlayerStats("Bo", team_id=2), PlayerStats("Cy", team_id=1)]
        teams = {1: 1, 2: 2, 3: 1}
        tracker = DefenseTracker(teams.get, lambda unit: {"Castle": 900, "GuardTower": 300}.get(unit, 50))
        for seconds, event in events:
            tracker.on_event(event, seconds)
        self.events = tracker.finish(self.players, lambda pid: self.players[pid - 1] if pid else None)
        self.tracker = tracker
        return self.players

    def test_completed_standing_and_lost(self):
        ada, bo, _ = self.run_events([
            (10, init(1, "GuardTower", 1)), (50, done(1)),
            (20, init(2, "GuardTower", 1, x=40)), (60, done(2)), (90, died(2, 2, x=40)),
        ])
        self.assertEqual(ada.defense["Guard tower"], {"placed": 2, "completed": 2, "standing": 1, "lost": 1})
        self.assertEqual(ada.defense_value_standing, 300)
        self.assertEqual(bo.denial_inflicted, {"defenses_destroyed": 1})

    def test_cancelled_destroyed_and_unfinished(self):
        ada, bo, cy = self.run_events([
            (10, init(1, "Castle", 1)), (30, died(1, None)),          # cancelled
            (10, init(2, "Castle", 1, x=60)), (40, died(2, 2, x=60)),  # destroyed while being built
            (10, init(3, "Castle", 1, x=90)),                          # never finished
            (10, init(4, "Castle", 3, x=120)), (20, died(4, 1, x=120)),  # ally kill: not denial
        ])
        self.assertEqual(ada.defense["Castle"], {"placed": 3, "cancelled": 1, "destroyed_building": 1, "unfinished": 1})
        self.assertEqual(bo.denial_inflicted, {"builds_destroyed": 1})
        self.assertEqual(cy.defense["Castle"], {"placed": 1, "cancelled": 1})

    def test_builder_kill_outcomes(self):
        ada, bo, _ = self.run_events([
            # Typical castle takes 100 s.
            (0, init(1, "Castle", 1, x=200)), (100, done(1)),
            # Builder killed at 20 s, castle resumes and finishes at 250 s: 150 s late.
            (5, born(50, "Peasant", 1, x=10)), (10, init(2, "Castle", 1)), (20, died(50, 2, x=11)), (260, done(2)),
            # Builder killed, castle destroyed 40 s later in a second push.
            (5, born(51, "Peasant2", 1, x=60)), (10, init(3, "Castle", 1, x=60)), (30, died(51, 2, x=61)), (70, died(3, 2, x=60)),
            # A worker killed far from any site is not a builder kill.
            (5, born(52, "Peasant", 1, x=500)), (40, died(52, 2, x=500)),
        ])
        self.assertEqual(ada.defense_builder_kills,
                         {"sites": 2, "workers": 2, "resumed": 1, "delay_seconds": 150, "destroyed_later": 1})
        self.assertEqual(bo.denial_inflicted, {"builders_killed": 2, "builds_destroyed": 1})
        outcomes = {e["outcome"] for e in self.events}
        self.assertIn("stalled, then destroyed in a later push", outcomes)
        self.assertIn("completed", outcomes)

    def test_standing_value_over_time(self):
        self.run_events([(10, init(1, "Castle", 1)), (50, done(1))])
        self.assertEqual(self.tracker.standing_value([1, 3]), 900)

    def test_findings_name_the_map_control_leader(self):
        ada, bo, cy = self.run_events([(10, init(1, "GuardTower", 1)), (50, done(1))])
        summary = ReplaySummary(Path("x"), match_mode="Team", players=[ada, bo, cy],
                                teams=[TeamStats(1, players=["Ada", "Cy"]), TeamStats(2, players=["Bo"])])
        lines = defense_findings(summary)
        self.assertTrue(any("Ada" in line and "1 guard tower" in line for line in lines), lines)


if __name__ == "__main__":
    unittest.main()

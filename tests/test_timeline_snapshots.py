import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "strategy_mining/src"))
from aok_ml.replay_events import ExtractedReplay, SNAPSHOT_MINUTES, build_snapshots


class TimelineCombatTests(unittest.TestCase):
    def test_attacker_credit_victim_loss_and_time_cutoff(self):
        cutoff = min(SNAPSHOT_MINUTES)
        def death(owner, killer, minute, owner_id=None, killer_id=None):
            return {"event_type": "unit_died", "player_index": owner,
                    "player_id": owner_id if owner_id is not None else owner + 1,
                    "killer_player_index": killer,
                    "killer_player_id": killer_id if killer_id is not None else killer + 1,
                    "minute": minute}
        replay = ExtractedReplay(replay_id="fixture", source_name="fixture",
            players=[{"player_index": 0, "player_id": 1, "name": "A", "team_id": 1},
                     {"player_index": 1, "player_id": 2, "name": "B", "team_id": 2}],
            unit_events=[death(1, 0, cutoff - .5),
                         death(None, 0, cutoff - .4, owner_id=15),
                         death(0, None, cutoff - .3, killer_id=15),
                         death(0, 0, cutoff - .2),
                         death(0, 1, cutoff + .5)])
        rows = {r["player_index"]: r for r in build_snapshots(replay)
                if r["snapshot_minute"] == cutoff}
        self.assertEqual((rows[0]["kills_to_now"], rows[0]["losses_to_now"]), (1, 1))
        self.assertEqual((rows[1]["kills_to_now"], rows[1]["losses_to_now"]), (0, 1))


if __name__ == "__main__":
    unittest.main()

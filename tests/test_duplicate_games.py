import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src"), str(ROOT / "discord_bot/external/s2protocol")]
from aok_bot.models import PlayerStats, ReplaySummary
from aok_bot.replay_parser import game_key
from aok_bot.storage import Storage


def initdata(seed):
    return {"m_syncLobbyState": {"m_gameDescription": {"m_randomValue": seed}}}


class GameKeyTests(unittest.TestCase):
    def test_key_ignores_player_order_and_computers(self):
        self.assertEqual(game_key(initdata(7), ["2-S2-1-2", None, "2-S2-1-1"]), "7:2-S2-1-1,2-S2-1-2")

    def test_no_key_without_seed_or_accounts(self):
        self.assertIsNone(game_key(None, ["2-S2-1-1"]))
        self.assertIsNone(game_key(initdata(7), [None]))


class DuplicateSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = Storage(Path(self.temp.name) / "db.sqlite")

    def save(self, source, key, kills=1, ok=True):
        summary = ReplaySummary(Path(source), parser_ok=ok, game_key=key,
                                players=[PlayerStats("Ada", kills=kills, account_id="2-S2-1-1")])
        return self.storage.save_replay(summary)

    def test_second_copy_of_a_game_replaces_the_first(self):
        self.save("mine.SC2Replay", "7:2-S2-1-1", kills=3)
        self.save("teammate.SC2Replay", "7:2-S2-1-1", kills=3)
        profile = self.storage.player_profile("Ada")
        self.assertEqual((profile["games"], profile["kills"]), (1, 3))

    def test_different_games_are_kept(self):
        self.save("a.SC2Replay", "7:2-S2-1-1")
        self.save("b.SC2Replay", "8:2-S2-1-1")
        self.save("c.SC2Replay", None)
        self.save("d.SC2Replay", None)
        self.assertEqual(self.storage.player_profile("Ada")["games"], 4)

    def test_failed_copy_never_replaces_a_good_one(self):
        good = self.save("a.SC2Replay", "7:2-S2-1-1", kills=3)
        self.assertEqual(self.save("b.SC2Replay", "7:2-S2-1-1", kills=99, ok=False), good)
        self.assertEqual(self.storage.player_profile("Ada")["kills"], 3)


if __name__ == "__main__":
    unittest.main()

import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src"), str(ROOT / "discord_bot/external/s2protocol")]
from aok_bot.models import PlayerStats, ReplaySummary
from aok_bot.replay_parser import _account_handle
from aok_bot.storage import Storage

ALEX_EU = "2-S2-1-111"
ALEX_US = "1-S2-1-222"


class AccountHandleTests(unittest.TestCase):
    def test_handle_from_toon(self):
        toon = {"m_region": 2, "m_programId": b"\x00\x00S2", "m_realm": 1, "m_id": 8333926}
        self.assertEqual(_account_handle(toon), "2-S2-1-8333926")

    def test_empty_or_computer_toon_has_no_handle(self):
        self.assertIsNone(_account_handle({"m_region": 0, "m_programId": b"", "m_realm": 0, "m_id": 0}))
        self.assertIsNone(_account_handle(None))


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "db.sqlite"
        self.storage = Storage(self.path)

    def save(self, source, *players):
        self.storage.save_replay(ReplaySummary(Path(source), parser_ok=True, players=list(players)))

    def test_same_name_different_accounts_stay_apart(self):
        self.save("a", PlayerStats("Alex", kills=3, account_id=ALEX_EU), PlayerStats("alex", kills=7, account_id=ALEX_US))
        ambiguous = self.storage.player_profile("Alex")
        self.assertEqual(ambiguous["games"], 0)
        self.assertEqual(ambiguous["matches"], [f"Alex [{ALEX_EU}]", f"alex [{ALEX_US}]"])
        self.assertEqual(self.storage.player_profile(ALEX_US)["kills"], 7)
        board = {r["name"]: r["kills"] for r in self.storage.leaderboard()}
        self.assertEqual(board, {f"alex [{ALEX_US}]": 7, f"Alex [{ALEX_EU}]": 3})

    def test_renamed_account_is_one_person(self):
        self.save("a", PlayerStats("OldName", kills=2, account_id=ALEX_EU))
        self.save("b", PlayerStats("NewName", kills=5, account_id=ALEX_EU))
        profile = self.storage.player_profile("oldname")
        self.assertEqual((profile["name"], profile["games"], profile["kills"]), ("NewName", 2, 7))
        self.assertEqual(profile["other_names"], ["OldName"])
        self.assertEqual([r["name"] for r in self.storage.leaderboard()], ["NewName"])

    def test_legacy_rows_join_the_only_account_with_that_name(self):
        self.save("old", PlayerStats("Ada", kills=4))  # saved before account ids
        self.save("new", PlayerStats("Ada", kills=1, account_id=ALEX_EU))
        profile = self.storage.player_profile("Ada")
        self.assertEqual((profile["games"], profile["kills"], profile["account_id"]), (2, 5, ALEX_EU))

    def test_legacy_rows_stay_alone_when_several_accounts_share_the_name(self):
        self.save("old", PlayerStats("Alex", kills=4))
        self.save("new", PlayerStats("Alex", kills=1, account_id=ALEX_EU), PlayerStats("Alex", kills=2, account_id=ALEX_US))
        self.assertEqual(len(self.storage.player_profile("Alex")["matches"]), 3)
        self.assertEqual(self.storage.player_profile(ALEX_EU)["kills"], 1)

    def test_old_database_gains_account_column(self):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("DROP INDEX idx_replay_players_account")
            conn.execute("ALTER TABLE replay_players DROP COLUMN account_id")
        Storage(self.path)
        with closing(sqlite3.connect(self.path)) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(replay_players)")}
        self.assertIn("account_id", cols)


if __name__ == "__main__":
    unittest.main()

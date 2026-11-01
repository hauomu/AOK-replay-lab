import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src"), str(ROOT / "strategy_mining/src")]
from aok_bot import bot
from aok_bot.models import PlayerStats, ReplaySummary
from aok_bot.replay_parser import _build_match_story, _build_team_stats, user_player_indices
from aok_bot.reporting import markdown_report
from aok_bot.storage import Storage
from aok_ml import replay_events


def initdata(*user_ids):
    return {"m_syncLobbyState": {"m_lobbyState": {"m_slots": [{"m_userId": u} for u in user_ids]}}}


class UserMappingTests(unittest.TestCase):
    def test_ai_slots_shift_user_ids(self):
        # Corpus shape: players 2 and 5 are AI, so user IDs skip them.
        players = [{"m_workingSetSlotId": slot} for slot in range(7)]
        expected = {0: 0, 1: 2, 2: 3, 3: 5, 4: 6}
        self.assertEqual(user_player_indices(players, initdata(0, None, 1, 2, None, 3, 4)), expected)
        self.assertEqual(replay_events.user_player_indices(players, initdata(0, None, 1, 2, None, 3, 4)), expected)

    def test_missing_initdata_keeps_identity(self):
        players = [{"m_workingSetSlotId": 0}, {"m_workingSetSlotId": 1}]
        self.assertEqual(user_player_indices(players, None), {0: 0, 1: 1})
        self.assertEqual(user_player_indices(players, {"m_syncLobbyState": {}}), {0: 0, 1: 1})


class StorageAggregateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = Storage(Path(self.temp.name) / "db.sqlite")

    def save(self, source, players, ok=True):
        self.storage.save_replay(ReplaySummary(Path(source), parser_ok=ok, players=players))

    def test_failed_parse_never_reaches_public_stats(self):
        self.save("good", [PlayerStats("Ada", kills=2, result="Loss")])
        self.save("bad", [PlayerStats("Ada", kills=50, result="Win"), PlayerStats("Ghost", kills=99)], ok=False)
        profile = self.storage.player_profile("Ada")
        self.assertEqual((profile["games"], profile["kills"], profile["results"]), (1, 2, {"Loss": 1}))
        self.assertEqual([r["name"] for r in self.storage.leaderboard()], ["Ada"])
        self.assertEqual(self.storage.player_profile("Ghost")["games"], 0)

    def test_partial_names_are_never_merged(self):
        self.save("a", [PlayerStats("Bob", kills=1), PlayerStats("Bobby", kills=10), PlayerStats("x_y", kills=3)])
        self.assertEqual(self.storage.player_profile("bob")["kills"], 1)  # exact, case-insensitive
        self.assertEqual(self.storage.player_profile("bobb")["kills"], 10)  # unique partial
        ambiguous = self.storage.player_profile("o")
        self.assertEqual((ambiguous["games"], ambiguous["matches"]), (0, ["Bob", "Bobby"]))
        self.assertEqual(self.storage.player_profile("%")["games"], 0)  # wildcards are literal
        self.assertEqual(self.storage.player_profile("_")["kills"], 3)


class ReportSemanticsTests(unittest.TestCase):
    def test_failed_parse_report_has_no_statistics(self):
        summary = ReplaySummary(Path("f.SC2Replay"), match_mode="Team", warnings=["Replay analysis failed."],
                                players=[PlayerStats("Ada", team_id=1, kills=7, units_born=1)])
        _build_team_stats(summary)
        report = markdown_report(summary)
        self.assertIn("no statistics are reported", report)
        self.assertIn("Replay analysis failed.", report)
        for absent in ("Ada", "7/0", "Duration"):
            self.assertNotIn(absent, report)

    def test_verdict_states_outcome_without_causes(self):
        summary = ReplaySummary(Path("v"), match_mode="Team", parser_ok=True, players=[
            PlayerStats("A", team_id=1, result="Win", units_born=1, commands=1),
            PlayerStats("B", team_id=2, result="Loss")])
        _build_team_stats(summary)
        _build_match_story(summary)
        self.assertIn("Recorded winner:", summary.verdict)
        for claim in ("won through", "strongest evidence", "fight conversion", "remax", "role coverage"):
            self.assertNotIn(claim, markdown_report(summary))


class MultiReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_report_is_attached_up_to_discord_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            reports = []
            for i in range(12):
                reports.append(Path(directory) / f"r{i}.md")
                reports[-1].write_text("report")
            summary = ReplaySummary(Path("x"), parser_ok=True)
            interaction = SimpleNamespace(response=SimpleNamespace(defer=AsyncMock()),
                                          followup=SimpleNamespace(send=AsyncMock()))
            with patch.object(bot, "save_attachment", AsyncMock(return_value=Path(directory) / "u.zip")), \
                 patch.object(bot, "extract_replay_paths", return_value=[Path(str(i)) for i in range(12)]), \
                 patch.object(bot, "parse_replay", return_value=summary), \
                 patch.object(bot, "storage", SimpleNamespace(save_replay=lambda s: None)), \
                 patch.object(bot, "save_markdown_report", side_effect=reports), \
                 patch.object(bot, "make_match_embed", MagicMock()):
                await bot.aok_analyze.callback(interaction, SimpleNamespace(filename="u.zip"))
            call = interaction.followup.send.call_args
            for file in call.kwargs["files"]:
                file.close()
            self.assertEqual(len(call.kwargs["files"]), 10)
            self.assertIn("first 10 of 12 reports", call.args[0])


if __name__ == "__main__":
    unittest.main()

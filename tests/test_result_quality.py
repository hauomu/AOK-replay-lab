import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src"), str(ROOT / "discord_bot/external/s2protocol")]
sys.path.insert(0, str(ROOT / "strategy_mining/src"))
from aok_bot.models import PlayerStats, ReplaySummary, TeamStats
from aok_bot import replay_parser
from aok_ml.replay_events import parse_replay_file
from aok_bot.analysis_hooks import analyze


class ResultQualityTests(unittest.TestCase):
    def _local_native_replay(self):
        records = ROOT / "analysis_outputs/baseline_full/replay_audit_records.jsonl"
        if not records.exists():
            self.skipTest("Requires local read-only corpus audit; no replay files are bundled")
        rows = [json.loads(line) for line in records.read_text(encoding="utf-8").splitlines()]
        candidates = [r for r in rows if r["parse_ok"] and r["metadata"].get("duration_seconds", 0) >= 600
                      and r["metadata"].get("decoder_build", r["metadata"].get("build")) == r["metadata"].get("build")
                      and Path(r["path"]).exists()]
        if not candidates:
            self.skipTest("No suitable local replay")
        return min(candidates, key=lambda r: r["size_bytes"])

    def test_animal_deaths_are_not_also_pvp_losses(self):
        row = self._local_native_replay()
        _, versions = replay_parser._load_s2protocol()
        protocol = versions.build(int(row["metadata"]["build"]))
        events = [
            {"_event": "NNet.Replay.Tracker.SUnitBornEvent", "_gameloop": 16,
             "m_unitTagIndex": 100000, "m_unitTagRecycle": 1, "m_unitTypeName": b"Marine",
             "m_controlPlayerId": 1, "m_upkeepPlayerId": 1},
            {"_event": "NNet.Replay.Tracker.SUnitDiedEvent", "_gameloop": 32,
             "m_unitTagIndex": 100000, "m_unitTagRecycle": 1, "m_killerPlayerId": 15},
        ]
        with patch.object(protocol, "decode_replay_tracker_events", side_effect=lambda _: iter(events)):
            bot = replay_parser.parse_replay(Path(row["path"]))
            miner = parse_replay_file(Path(row["path"]))
        self.assertTrue(bot.parser_ok and miner.parser_ok)
        self.assertEqual((bot.players[0].losses, bot.players[0].deaths_to_animals), (0, 1))
        self.assertEqual((miner.player_stats[0]["losses"], miner.player_stats[0]["deaths_to_animals"]), (0, 1))

    def test_interrupted_tracker_never_exports_successful_unit_features(self):
        row = self._local_native_replay()
        _, versions = replay_parser._load_s2protocol()
        protocol = versions.build(int(row["metadata"]["build"]))
        def interrupted(_):
            yield {"_event": "NNet.Replay.Tracker.SUnitBornEvent", "_gameloop": 16,
                   "m_unitTagIndex": 100000, "m_unitTagRecycle": 1, "m_unitTypeName": b"Marine",
                   "m_controlPlayerId": 1, "m_upkeepPlayerId": 1}
            raise ValueError("injected truncated tracker stream")
        with patch.object(protocol, "decode_replay_tracker_events", interrupted):
            bot, miner = replay_parser.parse_replay(Path(row["path"])), parse_replay_file(Path(row["path"]))
        self.assertFalse(bot.parser_ok or miner.parser_ok)
        self.assertEqual(miner.player_stats, [])
        self.assertEqual(miner.timeline_snapshots, [])
        self.assertIs(miner.replays[0]["tracker_events_complete"], False)

    def test_single_side_has_no_team_comparison(self):
        summary = ReplaySummary(Path("fixture"), parser_ok=True,
            players=[PlayerStats(name="A", team_id=1)], teams=[TeamStats(team_id=1, label="A")])
        result = analyze(summary, "team")
        self.assertFalse(result["available"])
        self.assertEqual(result["items"], [])
        self.assertTrue(any("opposing-side" in w for w in result["warnings"]))

    def test_corrupt_archives_close_handles_and_do_not_invent_match_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.SC2Replay"
            path.write_bytes(b"not an MPQ archive")
            original_open, handles = Path.open, []
            def observed_open(p, *args, **kwargs):
                handle = original_open(p, *args, **kwargs)
                if p == path:
                    handles.append(handle)
                return handle
            with patch.object(Path, "open", observed_open):
                bot, miner = replay_parser.parse_replay(path), parse_replay_file(path)
            self.assertFalse(bot.parser_ok)
            self.assertFalse(miner.parser_ok)
            self.assertEqual((bot.match_mode, miner.match_mode), ("Unknown", "Unknown"))
            self.assertGreaterEqual(len(handles), 2)
            self.assertTrue(all(handle.closed for handle in handles))

    def test_statistical_leader_does_not_become_recorded_winner(self):
        summary = ReplaySummary(Path("fixture"), match_mode="Free-for-all",
            players=[PlayerStats(name="A", team_id=1), PlayerStats(name="B", team_id=2)],
            teams=[TeamStats(team_id=1, label="A", kills=100), TeamStats(team_id=2, label="B", kills=1)])
        self.assertEqual(summary.winner_label(), "Unknown")
        self.assertEqual(summary.likely_leader_label(), "A")
        self.assertEqual(summary.to_dict()["winner_source"], "not_recorded")
        summary.players[1].result = "Win"
        self.assertEqual(summary.winner_label(), "B")
        self.assertIsNone(summary.likely_leader_label())

    def test_interrupted_real_game_stream_never_reports_apm(self):
        row = self._local_native_replay()
        mpyq, versions = replay_parser._load_s2protocol()
        protocol = versions.build(int(row["metadata"]["build"]))
        original = protocol.decode_replay_game_events
        def interrupted(content):
            for event in original(content):
                yield event
                if event.get("_gameloop", 0) >= 4096:
                    break
            raise ValueError("injected truncated game stream")
        original_archive, archives = mpyq.MPQArchive, []
        def observed_archive(*args, **kwargs):
            archive = original_archive(*args, **kwargs)
            archives.append(archive)
            return archive
        with patch.object(protocol, "decode_replay_game_events", interrupted), patch.object(mpyq, "MPQArchive", observed_archive):
            summary = replay_parser.parse_replay(Path(row["path"]))
            miner = parse_replay_file(Path(row["path"]))
        self.assertTrue(archives[0].file.closed)
        self.assertTrue(summary.parser_ok)
        self.assertTrue(any(p.commands for p in summary.players))
        self.assertIs(summary.game_events_complete, False)
        self.assertTrue(all(p.apm is None for p in summary.players))
        self.assertTrue(any("Command counts are partial" in w for w in summary.warnings))
        self.assertIs(summary.to_dict()["game_events_complete"], False)
        self.assertTrue(miner.parser_ok)
        self.assertIs(miner.replays[0]["game_events_complete"], False)
        self.assertTrue(all(p["apm"] is None for p in miner.player_stats))


if __name__ == "__main__":
    unittest.main()

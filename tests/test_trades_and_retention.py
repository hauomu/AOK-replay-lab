import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src")]

from aok_bot.retention import sweep  # noqa: E402

try:
    from aok_bot.replay_parser import _remove_market_trades
except ImportError:  # pragma: no cover - optional runtime deps
    _remove_market_trades = None


def sample(gold_gathered, gold_current, wood_gathered, wood_current):
    return {"gold": {"gathered_estimate": gold_gathered, "current": gold_current},
            "wood": {"gathered_estimate": wood_gathered, "current": wood_current}}


@unittest.skipIf(_remove_market_trades is None, "replay parser dependencies unavailable")
class MarketTradeTests(unittest.TestCase):
    def test_trade_spike_is_removed_from_both_resources(self):
        state = {}
        _remove_market_trades(state, sample(1000, 500, 1000, 500))
        s = sample(1100, 600, 1050, 550)  # normal gathering: +100 gold, +50 wood
        _remove_market_trades(state, s)
        # Corpus shape (Fixed 88): sell 11,822 wood for 17,200 gold, no spending.
        s = sample(1100 + 17200 + 100, 600 + 17200 + 100, 1050 - 11822 + 50, 550 - 11822 + 50)
        _remove_market_trades(state, s)
        # The trade sample keeps the previous sample's income (+100 gold); the rest is the trade.
        self.assertEqual(s["gold"]["gathered_estimate"], 1100 + 100)
        # The sale no longer drags wood down (this sample's +50 wood is inseparable from it).
        self.assertEqual(s["wood"]["gathered_estimate"], 1050)
        self.assertEqual(s["gold"]["bought"], 17200)
        self.assertEqual(s["wood"]["sold"], 11822 - 50)

    def test_spending_is_not_a_trade(self):
        state = {}
        _remove_market_trades(state, sample(1000, 500, 1000, 500))
        _remove_market_trades(state, sample(1100, 600, 1050, 550))
        # Wood stockpile drops because it was spent (gathered estimate unchanged): not a trade.
        s = sample(1500, 1000, 1100, 100)
        _remove_market_trades(state, s)
        self.assertNotIn("bought", s["gold"])
        self.assertEqual(s["gold"]["gathered_estimate"], 1500)

    def test_steady_high_income_is_not_a_trade(self):
        state = {}
        _remove_market_trades(state, sample(1000, 500, 1000, 5000))
        _remove_market_trades(state, sample(1400, 900, 1000, 5000))
        s = sample(1800, 1300, 1000, 4800)  # +400 gold like the previous sample
        _remove_market_trades(state, s)
        self.assertNotIn("bought", s["gold"])


class RetentionTests(unittest.TestCase):
    def test_sweep_removes_only_old_scratch_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            uploads, reports, replays, backups = (root / n for n in ("uploads", "reports", "replays", "backups"))
            for d in (uploads, reports, replays, backups):
                d.mkdir()
            now = time.time()
            old_day, old_cache = now - 2 * 86400, now - 40 * 86400

            def make(path, mtime):
                path.write_bytes(b"x")
                os.utime(path, (mtime, mtime))
                return path

            stale = [make(uploads / "old.SC2Replay", old_day), make(reports / "old.md", old_day),
                     make(replays / "old.SC2Replay", old_cache), make(replays / ".ingest-abc", old_day)]
            kept = [make(uploads / "new.zip", now), make(reports / "new.md", now),
                    make(replays / "recent.SC2Replay", old_day),  # inside the 30-day cache window
                    make(backups / "aok_bot.sqlite3", old_cache)]
            result = sweep(uploads, reports, replays, replay_cache_days=30, now=now)
            self.assertEqual((result.uploads, result.reports, result.replays), (1, 1, 2))
            self.assertTrue(all(not p.exists() for p in stale))
            self.assertTrue(all(p.exists() for p in kept))

    def test_missing_folders_are_fine(self):
        missing = Path(tempfile.gettempdir()) / "aok-no-such-dir"
        self.assertEqual(sweep(missing, missing, missing, 30).total(), 0)


if __name__ == "__main__":
    unittest.main()

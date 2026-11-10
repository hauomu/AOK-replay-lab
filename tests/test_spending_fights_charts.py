import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src")]

try:
    from aok_bot import replay_parser as rp
    from aok_bot.models import PlayerStats, ReplaySummary, TeamStats
    from aok_bot.reporting import _fight_lines, _spending_rows
except ImportError:  # pragma: no cover - optional runtime deps
    rp = None

try:
    import matplotlib  # noqa: F401
    from aok_bot.charts import render_timeline_chart
except ImportError:  # pragma: no cover
    render_timeline_chart = None


@unittest.skipIf(rp is None, "replay parser dependencies unavailable")
class SpendingTests(unittest.TestCase):
    def test_categories_follow_the_map_tags(self):
        cats = {"Swordsman": "Army", "Peasant3": "Economy", "Castle": "Technology"}
        self.assertEqual(rp._spend_category("Swordsman", cats), "Army")
        self.assertEqual(rp._spend_category("Peasant3", cats), "Economy")
        self.assertEqual(rp._spend_category("Castle", cats), "Buildings & defense")
        self.assertEqual(rp._spend_category("SiegeTowerMobile", cats), "Army")       # untagged siege
        self.assertEqual(rp._spend_category("GateOpenVert", cats), "Buildings & defense")
        self.assertEqual(rp._research_category("AgeIVCastleAge"), "Ages")
        self.assertEqual(rp._research_category("MeleeDamageIncrease1"), "Research")

    def test_spending_and_refund_by_category(self):
        p = PlayerStats("A")
        rp._add_costs(p, {"gold": 20, "iron": 40}, category="Army")
        rp._add_costs(p, {"wood": 300, "iron": 300}, category="Buildings & defense")
        rp._add_costs(p, {"wood": 300, "iron": 300}, sign=-1, category="Buildings & defense")
        self.assertEqual(p.resource_spent, {"gold": 20, "wood": 0, "iron": 40})
        self.assertEqual(p.spending_by_category["Army"]["iron"], 40)
        self.assertEqual(p.spending_by_category["Buildings & defense"]["iron"], 0)
        row = _spending_rows(None, [p], lambda x: x.name)[0]
        self.assertEqual(row[1], "20 / 0 / 40")
        self.assertEqual(row[-1], "100%")


@unittest.skipIf(rp is None, "replay parser dependencies unavailable")
class FoodTests(unittest.TestCase):
    def test_capped_by_houses_or_population_limit(self):
        a, b = PlayerStats("A"), PlayerStats("B")
        a.food_used_peak, b.food_used_peak = 200, 150
        a.food_samples = [[0, 150, 300], [60, 200, 300], [120, 200, 400], [180, 190, 400]]  # at 200 limit 60-180
        b.food_samples = [[0, 100, 100], [30, 100, 120], [60, 110, 120]]                    # at house cap 0-30
        s = ReplaySummary(Path("x"), parser_ok=True, players=[a, b])
        rp._finish_food(s)
        self.assertEqual(s.population_limit, 200)
        self.assertEqual((a.supply_capped_seconds, b.supply_capped_seconds), (120, 30))
        self.assertEqual(a.food_samples, [])

    def test_lost_house_lowers_cap(self):
        p, state = PlayerStats("A"), {}
        rp._apply_food_sample(p, {"m_scoreValueFoodUsed": 50 * 4096, "m_scoreValueFoodMade": 100 * 4096}, 10, state)
        rp._apply_food_sample(p, {"m_scoreValueFoodUsed": 50 * 4096, "m_scoreValueFoodMade": 80 * 4096}, 20, state)
        self.assertEqual((p.food_used, p.food_cap, p.food_cap_lost), (50, 80, 20))


@unittest.skipIf(rp is None, "replay parser dependencies unavailable")
class FightTests(unittest.TestCase):
    def test_fights_split_on_pauses_and_rank_by_swing(self):
        deaths = []
        # Fight A, 100-130 s: team 1 loses 8 x 100, team 0 loses 2 x 100.
        deaths += [(100 + i * 4, 1, 0, 100, "Militia") for i in range(8)]
        deaths += [(110, 0, 1, 100, "Swordsman"), (120, 0, 1, 100, "Swordsman")]
        # 200 s pause, fight B, 400-420 s: team 0 loses 7 x 300, team 1 loses 1 x 50.
        deaths += [(400 + i * 3, 0, 1, 300, "Knight") for i in range(7)] + [(410, 1, 0, 50, "Archer")]
        fights = rp._build_fights(deaths, {0: "Team 0 (A)", 1: "Team 1 (B)"})
        self.assertEqual(len(fights), 2)
        self.assertEqual((fights[0]["rank"], fights[0]["start_label"], fights[0]["winner_team"], fights[0]["swing"]),
                         (1, "6:40", 1, 2050))
        self.assertEqual((fights[1]["start_label"], fights[1]["end_label"], fights[1]["winner_team"], fights[1]["swing"]),
                         ("1:40", "2:08", 0, 600))
        summary = ReplaySummary(Path("x"), parser_ok=True, fights=fights)
        line = _fight_lines(summary)[0]
        self.assertIn("6:40-6:58", line)
        self.assertIn("Knight x7", line)

    def test_small_skirmishes_are_not_fights(self):
        self.assertEqual(rp._build_fights([(10, 0, 1, 100, "Militia")] * 3, {}), [])


@unittest.skipIf(rp is None or render_timeline_chart is None, "chart dependencies unavailable")
class ChartTests(unittest.TestCase):
    def test_chart_renders_png(self):
        series = [{"t": t, "teams": {"0": {"gold_rate": t, "wood_rate": 10, "iron_spent": t * 2, "army_value": t * 3},
                                     "1": {"gold_rate": 50, "wood_rate": 5, "iron_spent": t, "army_value": t}}}
                  for t in range(0, 600, 30)]
        s = ReplaySummary(Path("x.SC2Replay"), parser_ok=True, map_name="AoK Legacy", duration_seconds=600,
                          economy_series=series,
                          teams=[TeamStats(team_id=0, players=["A"]), TeamStats(team_id=1, players=["B"])],
                          fights=[{"rank": 1, "start": 120, "end": 180}])
        with tempfile.TemporaryDirectory() as tmp:
            out = render_timeline_chart(s, Path(tmp) / "c.png")
            self.assertTrue(out and out.stat().st_size > 10_000)
            self.assertEqual(out.read_bytes()[:4], b"\x89PNG")

    def test_no_chart_without_data(self):
        s = ReplaySummary(Path("x"), parser_ok=False)
        self.assertIsNone(render_timeline_chart(s, Path(tempfile.gettempdir()) / "none.png"))


try:
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch
    from aok_bot import bot, replay_inputs as inputs
except ImportError:  # pragma: no cover
    bot = None


@unittest.skipIf(rp is None or bot is None, "bot dependencies unavailable")
class ChartAttachmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_chart_is_attached_shown_in_embed_and_cleaned_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload, report, chart = root / "upload.SC2Replay", root / "r.md", root / "c.png"
            upload.write_bytes(b"x"); report.write_text("report"); chart.write_bytes(b"png")
            settings = SimpleNamespace(replays_dir=root, reports_dir=root, uploads_dir=root,
                                       input_limits=inputs.DEFAULT_LIMITS, replay_cache_days=30)
            summary = ReplaySummary(Path("x"), parser_ok=True, players=[PlayerStats("A", team_id=0)],
                                    raw_event_counts={"tracker_events": 1})
            async def thread(function, *args):
                return [Path("a")] if function is inputs.extract_replay_paths else summary
            interaction = SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
                                          followup=SimpleNamespace(send=AsyncMock()))
            with patch.object(bot, "settings", settings),                  patch.object(bot, "storage", SimpleNamespace(save_replay=lambda s: None)),                  patch.object(bot, "save_attachment", AsyncMock(return_value=upload)),                  patch.object(bot, "owned_thread", side_effect=thread),                  patch.object(bot, "save_markdown_report", return_value=report),                  patch.object(bot, "save_timeline_chart", return_value=chart):
                await bot._analyze_job(interaction, None, "stats")
            kwargs = interaction.followup.send.call_args.kwargs
            self.assertEqual([f.filename for f in kwargs["files"]], ["r.md", "c.png"])
            self.assertEqual(kwargs["embed"].image.url, "attachment://c.png")
            self.assertFalse(report.exists() or chart.exists())


if __name__ == "__main__":
    unittest.main()

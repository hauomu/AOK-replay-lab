import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src")]

try:
    from aok_bot import replay_parser as rp
    from aok_bot.models import PlayerStats
except ImportError:  # pragma: no cover - optional runtime deps
    rp = None

LEGACY = "15dc5ce18fae7c71e041444aff9386459e2dec3e459541a25efd6e1b4991964e"
FIXED = "2ee5a56ebd17a4b4995434f16f2a485402020e5440922e4b474e4afc6c478fc3"


@unittest.skipIf(rp is None, "replay parser dependencies unavailable")
class IronSpentTests(unittest.TestCase):
    def test_cost_tables_ship_with_the_bot(self):
        data = rp._load_cost_tables()
        self.assertGreater(len(data["maps"]), 50)
        self.assertTrue(rp.COSTS_PATH.is_file())

    def test_legacy_and_fixed_price_iron_differently(self):
        legacy, match, _ = rp._cost_table_for(LEGACY, "AoK Legacy")
        fixed, _, _ = rp._cost_table_for(FIXED, "Age of Knights Fixed")
        self.assertEqual(match, "exact")
        self.assertEqual(legacy["units"]["Swordsman"], {"gold": 20, "iron": 40})
        self.assertEqual(fixed["units"]["Swordsman"], {"gold": 40, "iron": 30})
        self.assertEqual(legacy["research"]["AgeVImperialAge"]["iron"], 1000)
        self.assertEqual(fixed["research"]["AgeVImperialAge"]["iron"], 2000)

    def test_unknown_version_falls_back_to_newest_same_map(self):
        table, match, note = rp._cost_table_for("0" * 64, "AoK Legacy")
        self.assertEqual(match, "fallback")
        self.assertIn("Swordsman", table["units"])
        self.assertIn("not in the bot's cost tables", note)

    def test_unknown_map_has_no_table(self):
        self.assertEqual(rp._cost_table_for("0" * 64, "Some Other Map"), (None, None, None))

    def test_cancelled_building_is_refunded(self):
        p = PlayerStats("A")
        castle = {"gold": 300, "wood": 300, "iron": 300}
        rp._add_costs(p, castle)
        rp._add_costs(p, castle, sign=-1)
        self.assertEqual(p.resource_spent["iron"], 0)


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "discord_bot/src"))
from aok_bot.protocols import select_protocol


class Registry:
    def __init__(self, supported, broken=None):
        self.supported, self.broken, self.calls = supported, broken, []

    def build(self, build):
        self.calls.append(build)
        if build == self.broken:
            raise ImportError("decoder dependency failed")
        if build not in self.supported:
            raise ImportError(f"protocol{build}")
        return f"decoder-{build}"


class ProtocolSelectionTests(unittest.TestCase):
    def test_exact_decoder_wins_even_for_mapped_build(self):
        registry = Registry({96883, 95299})
        self.assertEqual(select_protocol(registry, 96883), ("decoder-96883", 96883))
        self.assertEqual(registry.calls, [96883])

    def test_validated_mapping_and_provenance(self):
        registry = Registry({95299})
        self.assertEqual(select_protocol(registry, 96883), ("decoder-95299", 95299))
        self.assertEqual(registry.calls, [96883, 95299])

    def test_unknown_build_stays_unsupported(self):
        with self.assertRaisesRegex(ImportError, "protocol99999"):
            select_protocol(Registry({95299}), 99999)

    def test_internal_dependency_failure_is_not_hidden(self):
        registry = Registry({95299}, broken=96883)
        with self.assertRaisesRegex(ImportError, "dependency failed"):
            select_protocol(registry, 96883)
        self.assertEqual(registry.calls, [96883])


if __name__ == "__main__":
    unittest.main()

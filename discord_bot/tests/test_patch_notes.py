from __future__ import annotations

import unittest

from src.aok_bot.patch_notes import (
    extract_patch_notes,
    format_patch_note_body,
    latest_patch_note,
)


class PatchNoteParsingTests(unittest.TestCase):
    def test_extracts_list_and_sorts_semantic_version(self) -> None:
        payload = {
            "info": {
                "arcadeInfo": {
                    "patchNoteSections": [
                        {
                            "title": "VERSION 1.64",
                            "subtitle": "July 26, 2026",
                            "items": ["Added pylons", "Improved starting locations"],
                            "listType": 1,
                        },
                        {
                            "title": "Version 1.100",
                            "subtitle": "August 1, 2026",
                            "items": ["Future test"],
                            "listType": 1,
                        },
                    ]
                }
            }
        }

        notes = extract_patch_notes(payload)

        self.assertEqual([note.version for note in notes], ["1.100", "1.64"])
        self.assertEqual(notes[1].published_at, "July 26, 2026")
        self.assertEqual(notes[1].items[0], "Added pylons")

    def test_accepts_single_section_object(self) -> None:
        payload = {
            "info": {
                "arcadeInfo": {
                    "patchNoteSections": {
                        "title": "v2.4",
                        "subtitle": "2026-08-04",
                        "items": "Line one\nLine two",
                    }
                }
            }
        }

        notes = extract_patch_notes(payload)

        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].version, "2.4")
        self.assertEqual(notes[0].items, ("Line one", "Line two"))

    def test_hash_changes_when_notes_change(self) -> None:
        first = extract_patch_notes(
            {"info": {"arcadeInfo": {"patchNoteSections": {"title": "1.0", "items": ["A"]}}}}
        )[0]
        second = extract_patch_notes(
            {"info": {"arcadeInfo": {"patchNoteSections": {"title": "1.0", "items": ["B"]}}}}
        )[0]

        self.assertNotEqual(first.content_hash, second.content_hash)

    def test_latest_and_discord_body(self) -> None:
        notes = extract_patch_notes(
            {
                "info": {
                    "arcadeInfo": {
                        "patchNoteSections": [
                            {"title": "Version 1.2", "items": ["- Existing bullet", "Plain line"]},
                            {"title": "Version 1.1", "items": []},
                        ]
                    }
                }
            }
        )

        latest = latest_patch_note(notes)
        assert latest is not None
        body = format_patch_note_body(latest)
        self.assertIn("- Existing bullet", body)
        self.assertIn("• Plain line", body)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.aok_bot.patch_note_storage import PatchNoteStorage
from src.aok_bot.patch_notes import PatchNote


class PatchNoteStorageTests(unittest.TestCase):
    def test_persists_and_tracks_discord_sync_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = PatchNoteStorage(Path(temp_dir) / "bot.sqlite3")
            note = PatchNote(
                version="1.64",
                title="Version 1.64",
                published_at="July 26, 2026",
                items=("Added pylons",),
                source_order=0,
            )

            store.upsert_source(2, 131901, note, suppressed_on_insert=False)
            unsynced = store.list_unsynced(2, 131901)
            self.assertEqual(len(unsynced), 1)

            store.mark_posted(
                2,
                131901,
                note.version,
                channel_id=10,
                message_id=20,
                thread_id=30,
                posted_hash=note.content_hash,
            )
            self.assertEqual(store.list_unsynced(2, 131901), [])

            changed = PatchNote(
                version="1.64",
                title="Version 1.64",
                published_at="July 26, 2026",
                items=("Added pylons", "Improved spawns"),
                source_order=0,
            )
            store.upsert_source(2, 131901, changed, suppressed_on_insert=False)
            unsynced = store.list_unsynced(2, 131901)
            self.assertEqual(len(unsynced), 1)
            self.assertEqual(unsynced[0]["discord_message_id"], 20)

    def test_suppressed_baseline_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = PatchNoteStorage(Path(temp_dir) / "bot.sqlite3")
            note = PatchNote(
                version="1.63",
                title="Version 1.63",
                published_at=None,
                items=("Old note",),
                source_order=1,
            )
            store.upsert_source(2, 131901, note, suppressed_on_insert=True)
            self.assertEqual(store.list_unsynced(2, 131901), [])


if __name__ == "__main__":
    unittest.main()

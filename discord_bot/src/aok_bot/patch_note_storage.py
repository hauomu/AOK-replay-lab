from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .patch_notes import PatchNote


SCHEMA = """
CREATE TABLE IF NOT EXISTS patch_note_publications (
    region_id INTEGER NOT NULL,
    map_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TEXT,
    notes_json TEXT NOT NULL,
    source_order INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    posted_hash TEXT,
    suppressed INTEGER NOT NULL DEFAULT 0,
    discord_channel_id INTEGER,
    discord_message_id INTEGER,
    discord_thread_id INTEGER,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    posted_at TEXT,
    last_error TEXT,
    PRIMARY KEY (region_id, map_id, version)
);

CREATE INDEX IF NOT EXISTS idx_patch_note_latest
ON patch_note_publications(region_id, map_id, source_order, version);
"""


class PatchNoteStorage:
    """Persistent source and Discord-publication state for patch notes."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def has_any(self, region_id: int, map_id: int) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM patch_note_publications
                WHERE region_id = ? AND map_id = ?
                LIMIT 1
                """,
                (region_id, map_id),
            ).fetchone()
        return row is not None

    def get(self, region_id: int, map_id: int, version: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM patch_note_publications
                WHERE region_id = ? AND map_id = ? AND version = ?
                """,
                (region_id, map_id, version),
            ).fetchone()
        return self._row_to_dict(row)

    def upsert_source(
        self,
        region_id: int,
        map_id: int,
        note: PatchNote,
        *,
        suppressed_on_insert: bool,
    ) -> None:
        notes_json = json.dumps(note.to_dict(), ensure_ascii=False)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO patch_note_publications (
                    region_id,
                    map_id,
                    version,
                    title,
                    published_at,
                    notes_json,
                    source_order,
                    content_hash,
                    suppressed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(region_id, map_id, version) DO UPDATE SET
                    title = excluded.title,
                    published_at = excluded.published_at,
                    notes_json = excluded.notes_json,
                    source_order = excluded.source_order,
                    content_hash = excluded.content_hash,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (
                    region_id,
                    map_id,
                    note.version,
                    note.title,
                    note.published_at,
                    notes_json,
                    note.source_order,
                    note.content_hash,
                    1 if suppressed_on_insert else 0,
                ),
            )

    def list_unsynced(self, region_id: int, map_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM patch_note_publications
                WHERE region_id = ?
                  AND map_id = ?
                  AND suppressed = 0
                  AND (
                    discord_message_id IS NULL
                    OR posted_hash IS NULL
                    OR posted_hash <> content_hash
                  )
                ORDER BY source_order DESC
                """,
                (region_id, map_id),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows if row is not None]

    def latest(self, region_id: int, map_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM patch_note_publications
                WHERE region_id = ? AND map_id = ?
                ORDER BY source_order ASC, first_seen_at DESC
                """,
                (region_id, map_id),
            ).fetchall()

        if not rows:
            return None

        # Source order is normally newest first. The parser also writes notes in
        # semantic-version order, so the lowest source_order is the latest item.
        return self._row_to_dict(rows[0])

    def mark_posted(
        self,
        region_id: int,
        map_id: int,
        version: str,
        *,
        channel_id: int,
        message_id: int,
        thread_id: int | None,
        posted_hash: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE patch_note_publications
                SET discord_channel_id = ?,
                    discord_message_id = ?,
                    discord_thread_id = ?,
                    posted_hash = ?,
                    posted_at = COALESCE(posted_at, CURRENT_TIMESTAMP),
                    last_error = NULL
                WHERE region_id = ? AND map_id = ? AND version = ?
                """,
                (
                    channel_id,
                    message_id,
                    thread_id,
                    posted_hash,
                    region_id,
                    map_id,
                    version,
                ),
            )

    def mark_edited(
        self,
        region_id: int,
        map_id: int,
        version: str,
        *,
        posted_hash: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE patch_note_publications
                SET posted_hash = ?, last_error = NULL
                WHERE region_id = ? AND map_id = ? AND version = ?
                """,
                (posted_hash, region_id, map_id, version),
            )

    def mark_error(
        self,
        region_id: int,
        map_id: int,
        version: str,
        error: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE patch_note_publications
                SET last_error = ?
                WHERE region_id = ? AND map_id = ? AND version = ?
                """,
                (error[:1000], region_id, map_id, version),
            )

    @staticmethod
    def note_from_row(row: dict[str, Any]) -> PatchNote:
        payload = json.loads(str(row["notes_json"]))
        return PatchNote.from_dict(payload)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}

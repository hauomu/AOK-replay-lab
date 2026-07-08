from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ReplaySummary


SCHEMA = """
CREATE TABLE IF NOT EXISTS replays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT UNIQUE NOT NULL,
    map_name TEXT,
    duration_seconds INTEGER,
    game_version TEXT,
    parser_ok INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS replay_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    replay_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    team_id INTEGER,
    result TEXT,
    apm INTEGER,
    commands INTEGER NOT NULL DEFAULT 0,
    kills INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    units_born INTEGER NOT NULL DEFAULT 0,
    leave_time_seconds INTEGER,
    FOREIGN KEY(replay_id) REFERENCES replays(id)
);

CREATE INDEX IF NOT EXISTS idx_replay_players_name ON replay_players(name);
"""


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def save_replay(self, summary: ReplaySummary) -> int:
        with self.connect() as conn:
            raw_json = json.dumps(summary.to_dict(), ensure_ascii=False)
            warnings_json = json.dumps(summary.warnings, ensure_ascii=False)

            # Re-analyzing the same replay should replace old player rows, not duplicate them.
            old_row = conn.execute(
                "SELECT id FROM replays WHERE source_path = ?",
                (str(summary.source_path),),
            ).fetchone()
            if old_row is not None:
                old_replay_id = int(old_row["id"] if "id" in old_row.keys() else old_row[0])
                conn.execute("DELETE FROM replay_players WHERE replay_id = ?", (old_replay_id,))
                conn.execute("DELETE FROM replays WHERE id = ?", (old_replay_id,))

            conn.execute(
                """
                INSERT INTO replays (
                    source_path, map_name, duration_seconds, game_version,
                    parser_ok, warnings_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(summary.source_path),
                    summary.map_name,
                    summary.duration_seconds,
                    summary.game_version,
                    1 if summary.parser_ok else 0,
                    warnings_json,
                    raw_json,
                ),
            )
            replay_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            for p in summary.players:
                conn.execute(
                    """
                    INSERT INTO replay_players (
                        replay_id, name, team_id, result, apm, commands,
                        kills, losses, units_born, leave_time_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        replay_id,
                        p.name,
                        p.team_id,
                        p.result,
                        p.apm,
                        p.commands,
                        p.kills,
                        p.losses,
                        p.units_born,
                        p.leave_time_seconds,
                    ),
                )
            return replay_id

    def player_profile(self, name: str) -> dict:
        like = f"%{name}%"
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM replay_players
                WHERE name LIKE ?
                ORDER BY id DESC
                """,
                (like,),
            ).fetchall()

        if not rows:
            return {"name": name, "games": 0}

        total_kills = sum(int(r["kills"] or 0) for r in rows)
        total_losses = sum(int(r["losses"] or 0) for r in rows)
        total_units = sum(int(r["units_born"] or 0) for r in rows)
        total_commands = sum(int(r["commands"] or 0) for r in rows)
        apms = [int(r["apm"]) for r in rows if r["apm"] is not None]

        results = {}
        for r in rows:
            key = r["result"] or "unknown"
            results[key] = results.get(key, 0) + 1

        return {
            "name": rows[0]["name"],
            "games": len(rows),
            "kills": total_kills,
            "losses": total_losses,
            "kill_loss_ratio": round(total_kills / total_losses, 3) if total_losses else None,
            "units_born": total_units,
            "commands": total_commands,
            "avg_apm": round(sum(apms) / len(apms), 1) if apms else None,
            "results": results,
        }

    def leaderboard(self, limit: int = 10) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    name,
                    COUNT(*) AS games,
                    SUM(kills) AS kills,
                    SUM(losses) AS losses,
                    SUM(units_born) AS units_born,
                    SUM(commands) AS commands,
                    AVG(apm) AS avg_apm
                FROM replay_players
                GROUP BY name
                HAVING games > 0
                ORDER BY kills DESC, games DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = []
        for r in rows:
            losses = int(r["losses"] or 0)
            kills = int(r["kills"] or 0)
            result.append(
                {
                    "name": r["name"],
                    "games": int(r["games"] or 0),
                    "kills": kills,
                    "losses": losses,
                    "klr": round(kills / losses, 3) if losses else None,
                    "units_born": int(r["units_born"] or 0),
                    "commands": int(r["commands"] or 0),
                    "avg_apm": round(float(r["avg_apm"]), 1) if r["avg_apm"] is not None else None,
                }
            )
        return result

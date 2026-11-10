from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
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
    animal_kills INTEGER NOT NULL DEFAULT 0,
    deaths_to_animals INTEGER NOT NULL DEFAULT 0,
    units_born INTEGER NOT NULL DEFAULT 0,
    mechanical_units INTEGER NOT NULL DEFAULT 0,
    mechanical_kills INTEGER NOT NULL DEFAULT 0,
    mechanical_losses INTEGER NOT NULL DEFAULT 0,
    tech_score INTEGER NOT NULL DEFAULT 0,
    current_age TEXT,
    gold_current INTEGER NOT NULL DEFAULT 0,
    wood_current INTEGER NOT NULL DEFAULT 0,
    iron_current INTEGER NOT NULL DEFAULT 0,
    gold_gathered INTEGER NOT NULL DEFAULT 0,
    wood_gathered INTEGER NOT NULL DEFAULT 0,
    iron_gathered INTEGER NOT NULL DEFAULT 0,
    leave_time_seconds INTEGER,
    FOREIGN KEY(replay_id) REFERENCES replays(id)
);

CREATE INDEX IF NOT EXISTS idx_replay_players_name ON replay_players(name);
"""

# Battle.net handle as stored in replay_players.account_id, e.g. "2-S2-1-8333926".
ACCOUNT_HANDLE = re.compile(r"^\d+-[A-Za-z0-9]+-\d+-\d+$")

# Failed parses keep their diagnostic rows but never feed public profiles or leaderboards.
SUCCESSFUL_PLAYERS = """
    replay_players p JOIN replays r ON r.id = p.replay_id AND r.parser_ok = 1
"""


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _init_db(self) -> None:
        with closing(self.connect()) as conn, conn:
            conn.executescript(SCHEMA)
            # Lightweight migrations for users with v0.1/v0.2 local DBs.
            self._ensure_column(conn, "replay_players", "animal_kills", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "deaths_to_animals", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "mechanical_units", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "mechanical_kills", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "mechanical_losses", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "tech_score", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "current_age", "TEXT")
            self._ensure_column(conn, "replay_players", "gold_current", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "wood_current", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "iron_current", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "gold_gathered", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "wood_gathered", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "replay_players", "iron_gathered", "INTEGER NOT NULL DEFAULT 0")
            # Players are identified by Battle.net account; rows saved before this have NULL.
            self._ensure_column(conn, "replay_players", "account_id", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_replay_players_account ON replay_players(account_id)")

    def save_replay(self, summary: ReplaySummary) -> int:
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            raw_json = json.dumps(summary.to_dict(), ensure_ascii=False)
            warnings_json = json.dumps(summary.warnings, ensure_ascii=False)

            # Re-analyzing the same replay should replace old player rows, not duplicate them.
            old_row = conn.execute(
                "SELECT id, parser_ok FROM replays WHERE source_path = ?",
                (str(summary.source_path),),
            ).fetchone()
            if old_row is not None and old_row["parser_ok"] and not summary.parser_ok:
                return int(old_row["id"])
            if old_row is not None:
                conn.execute("DELETE FROM replay_players WHERE replay_id = ?", (old_row["id"],))
                conn.execute("DELETE FROM replays WHERE id = ?", (old_row["id"],))

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
                        kills, losses, animal_kills, deaths_to_animals,
                        units_born, mechanical_units, mechanical_kills, mechanical_losses,
                        tech_score, current_age,
                        gold_current, wood_current, iron_current,
                        gold_gathered, wood_gathered, iron_gathered,
                        leave_time_seconds, account_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        p.animal_kills,
                        p.deaths_to_animals,
                        p.units_born,
                        p.mechanical_units,
                        p.mechanical_kills,
                        p.mechanical_losses,
                        p.tech_score,
                        p.current_age(),
                        int(p.resource_current.get("gold", 0) or 0),
                        int(p.resource_current.get("wood", 0) or 0),
                        int(p.resource_current.get("iron", 0) or 0),
                        int(p.resource_gathered_estimate.get("gold", 0) or 0),
                        int(p.resource_gathered_estimate.get("wood", 0) or 0),
                        int(p.resource_gathered_estimate.get("iron", 0) or 0),
                        p.leave_time_seconds,
                        p.account_id,
                    ),
                )
            return replay_id

    def _identities(self, conn: sqlite3.Connection) -> dict[str, dict]:
        """Group successful player rows into people. A Battle.net account is one
        person whatever names it used; two accounts sharing a name stay apart.
        Rows saved before account ids were stored join the one account that used
        that name, or stand alone under the exact name when none or several did."""
        rows = conn.execute(
            f"SELECT p.id, p.name, p.account_id FROM {SUCCESSFUL_PLAYERS} ORDER BY p.id"
        ).fetchall()
        accounts_by_name: dict[str, set[str]] = {}
        for r in rows:
            if r["account_id"]:
                accounts_by_name.setdefault(r["name"].casefold(), set()).add(r["account_id"])
        people: dict[str, dict] = {}
        for r in rows:
            key = r["account_id"]
            if not key:
                owners = accounts_by_name.get(r["name"].casefold(), set())
                key = next(iter(owners)) if len(owners) == 1 else f"name:{r['name']}"
            person = people.setdefault(key, {
                "account_id": None if key.startswith("name:") else key,
                "row_ids": [], "names": [], "name": r["name"],
            })
            person["row_ids"].append(int(r["id"]))
            if r["name"] not in person["names"]:
                person["names"].append(r["name"])
            person["name"] = r["name"]  # rows come in id order, so the latest name wins
        return people

    @staticmethod
    def _label(person: dict) -> str:
        return f"{person['name']} [{person['account_id']}]" if person["account_id"] else person["name"]

    @staticmethod
    def _find_people(people: dict[str, dict], query: str) -> list[dict]:
        query = query.strip()
        if ACCOUNT_HANDLE.match(query):
            return [people[query]] if query in people else []
        folded = query.casefold()
        exact = [p for p in people.values() if any(n.casefold() == folded for n in p["names"])]
        if exact:
            return exact
        return [p for p in people.values() if any(folded in n.casefold() for n in p["names"])]

    def player_profile(self, name: str) -> dict:
        """Profile one person. An exact (case-insensitive) name wins over a partial
        one, and a Battle.net handle ("2-S2-1-1234") picks an account directly.
        When the name fits several people nothing is merged: the candidates come
        back in "matches" so the caller can ask for the handle."""
        with closing(self.connect()) as conn, conn:
            people = self._identities(conn)
            found = self._find_people(people, name)
            if len(found) != 1:
                return {"name": name, "games": 0, "matches": sorted(self._label(p) for p in found)[:11]}
            person = found[0]
            ids = person["row_ids"]
            rows = conn.execute(
                f"SELECT * FROM replay_players WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id DESC",
                ids,
            ).fetchall()

        total_kills = sum(int(r["kills"] or 0) for r in rows)
        total_losses = sum(int(r["losses"] or 0) for r in rows)
        total_animal_kills = sum(int(r["animal_kills"] or 0) for r in rows)
        total_deaths_to_animals = sum(int(r["deaths_to_animals"] or 0) for r in rows)
        total_units = sum(int(r["units_born"] or 0) for r in rows)
        total_mechanical_units = sum(int(r["mechanical_units"] or 0) for r in rows)
        total_mechanical_kills = sum(int(r["mechanical_kills"] or 0) for r in rows)
        total_mechanical_losses = sum(int(r["mechanical_losses"] or 0) for r in rows)
        total_tech_score = sum(int(r["tech_score"] or 0) for r in rows)
        total_gold = sum(int(r["gold_gathered"] or 0) for r in rows)
        total_wood = sum(int(r["wood_gathered"] or 0) for r in rows)
        total_iron = sum(int(r["iron_gathered"] or 0) for r in rows)
        total_commands = sum(int(r["commands"] or 0) for r in rows)
        apms = [int(r["apm"]) for r in rows if r["apm"] is not None]
        results: dict[str, int] = {}
        for r in rows:
            key = r["result"] or "unknown"
            results[key] = results.get(key, 0) + 1

        return {
            "name": person["name"],
            "account_id": person["account_id"],
            "other_names": [n for n in person["names"] if n != person["name"]],
            "games": len(rows),
            "kills": total_kills,
            "losses": total_losses,
            "kill_loss_ratio": _ratio(total_kills, total_losses),
            "animal_kills": total_animal_kills,
            "deaths_to_animals": total_deaths_to_animals,
            "animal_kill_loss_ratio": _ratio(total_animal_kills, total_deaths_to_animals),
            "units_born": total_units,
            "mechanical_units": total_mechanical_units,
            "mechanical_kills": total_mechanical_kills,
            "mechanical_losses": total_mechanical_losses,
            "avg_tech_score": round(total_tech_score / len(rows), 1) if rows else 0,
            "gold_gathered_estimate": total_gold,
            "wood_gathered_estimate": total_wood,
            "iron_gathered_estimate": total_iron,
            "commands": total_commands,
            "avg_apm": round(sum(apms) / len(apms), 1) if apms else None,
            "results": results,
        }

    def leaderboard(self, limit: int = 10) -> list[dict]:
        with closing(self.connect()) as conn, conn:
            people = self._identities(conn)
            stats = {
                int(r["id"]): r for r in conn.execute(
                    "SELECT p.id, p.kills, p.losses, p.animal_kills, p.deaths_to_animals, "
                    f"p.units_born, p.commands, p.apm FROM {SUCCESSFUL_PLAYERS}"
                )
            }
        shown: dict[str, int] = {}
        for person in people.values():
            shown[person["name"].casefold()] = shown.get(person["name"].casefold(), 0) + 1
        result = []
        for person in people.values():
            rows = [stats[i] for i in person["row_ids"]]
            kills = sum(int(r["kills"] or 0) for r in rows)
            losses = sum(int(r["losses"] or 0) for r in rows)
            animal_kills = sum(int(r["animal_kills"] or 0) for r in rows)
            deaths_to_animals = sum(int(r["deaths_to_animals"] or 0) for r in rows)
            apms = [int(r["apm"]) for r in rows if r["apm"] is not None]
            # People showing the same name get their handle so they can be told apart.
            same_name = shown[person["name"].casefold()] > 1
            result.append(
                {
                    "name": self._label(person) if same_name else person["name"],
                    "account_id": person["account_id"],
                    "games": len(rows),
                    "kills": kills,
                    "losses": losses,
                    "klr": _ratio(kills, losses),
                    "animal_kills": animal_kills,
                    "deaths_to_animals": deaths_to_animals,
                    "animal_klr": _ratio(animal_kills, deaths_to_animals),
                    "units_born": sum(int(r["units_born"] or 0) for r in rows),
                    "commands": sum(int(r["commands"] or 0) for r in rows),
                    "avg_apm": round(sum(apms) / len(apms), 1) if apms else None,
                }
            )
        result.sort(key=lambda r: (-r["kills"], -r["animal_kills"], -r["games"], r["name"]))
        return result[:limit]

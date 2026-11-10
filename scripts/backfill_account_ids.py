"""Fill replay_players.account_id and replays.game_key for rows saved before
they were stored, then drop extra copies of the same game (the newest row stays).

Stored replays are matched to replay files by their player-name list; when
several files share it, the one whose length is closest to the stored duration
wins (older rows used a 16 loops/s clock, newer ones 22.4, so both are tried).
Only rows whose replay matches a single file, with every stored name found in
it, are updated. Dry run by default; pass --apply to write (back up the DB first).

    python scripts/backfill_account_ids.py DB REPLAY_DIR [REPLAY_DIR ...] [--apply]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "discord_bot/src"))
from aok_bot.protocols import select_protocol  # noqa: E402
from aok_bot.replay_parser import _account_handle, _clean_player_name, _load_s2protocol, game_key  # noqa: E402

TOLERANCE_SECONDS = 5


def scan(dirs: list[Path]) -> dict[tuple[str, ...], list[dict]]:
    mpyq, versions = _load_s2protocol()
    index: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for directory in dirs:
        for path in sorted(directory.glob("*.SC2Replay")):
            try:
                archive = mpyq.MPQArchive(str(path))
                header = versions.latest().decode_replay_header(archive.header["user_data_header"]["content"])
                protocol, _ = select_protocol(versions, header["m_version"]["m_baseBuild"])
                details = protocol.decode_replay_details(archive.read_file("replay.details"))
                initdata = protocol.decode_replay_initdata(archive.read_file("replay.initData"))
            except Exception:
                continue
            players = {}
            for idx, p in enumerate(details.get("m_playerList", [])):
                if p.get("m_control") == 3:
                    continue
                handle = _account_handle(p.get("m_toon"))
                if handle:
                    players[_clean_player_name(p.get("m_name"), f"Player {idx + 1}")] = handle
            loops = header.get("m_elapsedGameLoops", 0)
            key = tuple(sorted(players))
            index[key].append({"path": path, "players": players, "lengths": (loops / 16, loops / 22.4),
                               "game_key": game_key(initdata, list(players.values()))})
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    parser.add_argument("dirs", type=Path, nargs="+")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    index = scan(args.dirs)
    print(f"indexed {sum(len(v) for v in index.values())} replay files")
    with closing(sqlite3.connect(args.db)) as conn, conn:
        conn.row_factory = sqlite3.Row
        replays = conn.execute("SELECT id, duration_seconds FROM replays ORDER BY id").fetchall()
        updates, keys, unmatched = [], [], []
        for replay in replays:
            rows = conn.execute(
                "SELECT id, name FROM replay_players WHERE replay_id = ?", (replay["id"],)
            ).fetchall()
            if not rows:
                continue
            all_names = [r[0] for r in conn.execute("SELECT name FROM replay_players WHERE replay_id = ?", (replay["id"],))]
            candidates = index.get(tuple(sorted(all_names)), [])
            duration = replay["duration_seconds"] or 0
            close = [c for c in candidates if min(abs(x - duration) for x in c["lengths"]) <= TOLERANCE_SECONDS]
            if len(close) != 1 or any(r["name"] not in close[0]["players"] for r in rows):
                unmatched.append((replay["id"], len(candidates), len(close)))
                continue
            match = close[0]
            updates += [(match["players"][r["name"]], r["id"]) for r in rows]
            if match["game_key"]:
                keys.append((match["game_key"], replay["id"]))
            print(f"replay {replay['id']}: {match['path'].name} ({len(rows)} players)")
        print(f"{len(updates)} player rows matched; {len(unmatched)} replays unmatched (id, same-names, close): {unmatched}")
        if args.apply:
            conn.executemany("UPDATE replay_players SET account_id = ? WHERE id = ? AND account_id IS NULL", updates)
            conn.executemany("UPDATE replays SET game_key = ? WHERE id = ? AND game_key IS NULL", keys)
        # Extra copies of one game: keep the newest stored row.
        known = dict(conn.execute("SELECT id, game_key FROM replays WHERE game_key IS NOT NULL").fetchall())
        known.update({replay_id: key for key, replay_id in keys})
        by_key: dict[str, list[int]] = defaultdict(list)
        for replay_id, key in known.items():
            by_key[key].append(replay_id)
        extra = sorted(i for ids in by_key.values() for i in sorted(ids)[:-1])
        print(f"{len(keys)} game keys; duplicate replay rows to drop: {extra}")
        if args.apply:
            for replay_id in extra:
                conn.execute("DELETE FROM replay_players WHERE replay_id = ?", (replay_id,))
                conn.execute("DELETE FROM replays WHERE id = ?", (replay_id,))
            print("applied")
        else:
            print("dry run; pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

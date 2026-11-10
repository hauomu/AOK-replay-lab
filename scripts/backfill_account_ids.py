"""Fill replay_players.account_id for rows saved before account ids were stored.

Stored replays are matched to replay files by their player-name list; when
several files share it, the one whose length is closest to the stored duration
wins (older rows used a 16 loops/s clock, newer ones 22.4, so both are tried).
Only rows whose replay matches a single file, with every stored name found in
it, are updated. Dry run by default; pass --apply to write.

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
from aok_bot.replay_parser import _account_handle, _clean_player_name, _load_s2protocol  # noqa: E402

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
            index[key].append({"path": path, "players": players, "lengths": (loops / 16, loops / 22.4)})
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
        updates, unmatched = [], []
        for replay in replays:
            rows = conn.execute(
                "SELECT id, name FROM replay_players WHERE replay_id = ? AND account_id IS NULL", (replay["id"],)
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
            print(f"replay {replay['id']}: {match['path'].name} ({len(rows)} players)")
        print(f"{len(updates)} player rows matched; {len(unmatched)} replays unmatched (id, same-names, close): {unmatched}")
        if args.apply and updates:
            conn.executemany("UPDATE replay_players SET account_id = ? WHERE id = ? AND account_id IS NULL", updates)
            print("applied")
        elif updates:
            print("dry run; pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

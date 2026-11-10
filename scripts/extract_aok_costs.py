"""Build the AoK unit/research cost tables the bot uses to work out iron spent.

AoK's iron is SC2's Terrazine resource. Replays record only Minerals (gold) and
Vespene (wood) stockpiles, so iron is derived from what players bought: unit,
building and research costs taken from the map's own game data.

The map itself is not in the replay. This script reads local replays to learn
which map versions were played (title + cache hash), opens each version's
.s2ma from the Battle.net cache, and writes compact cost tables keyed by map
hash to discord_bot/src/aok_bot/data/aok_costs.json.

Usage (from the repo root, with the project venv):
    python scripts/extract_aok_costs.py --replays "<SC2 Replays/Multiplayer folder>" [--replays ...]
Optional: --cache "<Battle.net Cache folder>"  --out <json path>
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "discord_bot" / "src"))

from aok_bot.protocols import select_protocol  # noqa: E402
from aok_bot.replay_parser import _load_s2protocol  # noqa: E402

RESOURCE_KEYS = {"Minerals": "gold", "Vespene": "wood", "Terrazine": "iron", "Custom": "food"}
DEFAULT_CACHE = Path("C:/ProgramData/Blizzard Entertainment/Battle.net/Cache")
DEFAULT_OUT = ROOT / "discord_bot" / "src" / "aok_bot" / "data" / "aok_costs.json"


def _text(value) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value or "")


def _costs(element: ET.Element) -> dict[str, int]:
    out: dict[str, int] = {}
    for tag in ("CostResource", "Resource"):
        for node in element.iter(tag):
            key = RESOURCE_KEYS.get(node.get("index") or "")
            value = node.get("value")
            if key and value:
                out[key] = int(float(value))
    return {k: v for k, v in out.items() if v}


def _read(archive, suffix: str) -> bytes | None:
    for name in archive.files or []:
        text = _text(name)
        if text.lower().replace("\\", "/").endswith(suffix.lower()):
            return archive.read_file(text)
    return None


def cost_table(mpyq, map_path: Path) -> dict[str, dict[str, dict[str, int]]]:
    archive = mpyq.MPQArchive(str(map_path))
    units: dict[str, dict[str, int]] = {}
    research: dict[str, dict[str, int]] = {}
    unit_xml = _read(archive, "GameData/UnitData.xml")
    if unit_xml:
        for el in ET.fromstring(unit_xml):
            costs = _costs(el)
            if el.get("id") and costs:
                units[el.get("id")] = costs
    abil_xml = _read(archive, "GameData/AbilData.xml")
    if abil_xml:
        for el in ET.fromstring(abil_xml):
            for info in el.iter("InfoArray"):
                node = info.find("Upgrade")
                upgrade = info.get("Upgrade") or (node.get("value") if node is not None else None)
                costs = _costs(info)
                if upgrade and costs:
                    research[upgrade] = costs
    return {"units": dict(sorted(units.items())), "research": dict(sorted(research.items()))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--replays", action="append", required=True, type=Path)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    mpyq, versions = _load_s2protocol()
    seen: dict[str, dict] = {}
    for folder in args.replays:
        for replay in sorted(folder.glob("*.SC2Replay")):
            try:
                archive = mpyq.MPQArchive(str(replay))
                header = versions.latest().decode_replay_header(archive.header["user_data_header"]["content"])
                protocol, _ = select_protocol(versions, header["m_version"]["m_baseBuild"])
                details = protocol.decode_replay_details(archive.read_file("replay.details"))
            except Exception as exc:  # unreadable replay: skip, keep going
                print(f"skip {replay.name}: {type(exc).__name__}")
                continue
            title = _text(details.get("m_title"))
            if "knight" not in title.lower() and "aok" not in title.lower():
                continue
            handles = details.get("m_cacheHandles") or []
            if not handles:
                continue
            map_hash = binascii.hexlify(bytes(handles[-1])[8:]).decode()
            played = datetime.fromtimestamp(replay.stat().st_mtime, timezone.utc).date().isoformat()
            entry = seen.setdefault(map_hash, {"title": title, "last_played": played, "replays": 0})
            entry["replays"] += 1
            entry["last_played"] = max(entry["last_played"], played)

    tables: dict[str, dict] = {}
    maps: dict[str, dict] = {}
    missing = []
    for map_hash, info in sorted(seen.items()):
        path = args.cache / map_hash[:2] / map_hash[2:4] / f"{map_hash}.s2ma"
        if not path.is_file():
            missing.append((info["title"], map_hash[:8], info["replays"]))
            continue
        try:
            table = cost_table(mpyq, path)
        except Exception as exc:
            print(f"cannot read map {map_hash[:8]}: {type(exc).__name__}")
            continue
        if not table["units"]:
            missing.append((info["title"], map_hash[:8], info["replays"]))
            continue
        table_id = hashlib.sha1(json.dumps(table, sort_keys=True).encode()).hexdigest()[:12]
        tables[table_id] = table
        maps[map_hash] = {"title": info["title"], "table": table_id, "last_played": info["last_played"]}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "about": "AoK cost tables from the map game data (gold=Minerals, wood=Vespene, iron=Terrazine, "
                 "food=Custom). Built by scripts/extract_aok_costs.py.",
        "maps": maps,
        "tables": tables,
    }, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"map versions: {len(maps)} with tables ({len(tables)} distinct), {len(missing)} missing from cache")
    for title, short, count in missing:
        print(f"  missing: {title} {short} ({count} replays)")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

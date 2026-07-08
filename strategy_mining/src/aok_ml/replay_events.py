from __future__ import annotations

import csv
import hashlib
import html
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import tempfile
import types
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

STRUCTURE_HINTS = (
    "House", "Farm", "Barracks", "Stable", "Archery", "Blacksmith", "Market", "Mill",
    "Lumber", "Mine", "Tower", "Castle", "Gate", "Wall", "Post", "Keep", "Town", "Hall",
)
STATIC_DEFENSE_HINTS = ("Wall", "Gate", "Tower", "WatchPost", "GuardPost", "GuardTower", "Castle", "Keep")
WALL_GATE_HINTS = ("Wall", "Gate")
CASTLE_HINTS = ("Castle", "Keep")
CAVALRY_HINTS = ("Horse", "Knight", "Cavalry", "Mounted", "Rider")
RANGED_HINTS = ("Archer", "Crossbow", "HandCannoneer", "Gun", "Rifle", "Musk", "Bow")
INFANTRY_HINTS = ("Swordsman", "Spearman", "Militia", "Pikeman", "Footman", "Infantry", "ManAtArms")
SIEGE_HINTS = ("Ballista", "Bombard", "Catapult", "Trebuchet", "Siege", "Cannon")
ECON_HINTS = ("House", "Farm", "Market", "Mill", "Lumber", "Mine", "TownHall", "Town", "Hall")
PROD_HINTS = ("Barracks", "Stable", "Archery", "Blacksmith", "Castle", "TownHall", "Town", "Hall", "Market")
NON_COMBAT_HINTS = ("Beacon", "Dummy", "Path", "Marker", "Cursor", "Camera", "Missile", "Projectile")

SNAPSHOT_MINUTES = (5, 10, 15, 20, 25, 30, 45, 60)


def _install_imp_compat() -> None:
    if "imp" in sys.modules:
        return
    imp = types.ModuleType("imp")

    def find_module(name: str, path: list[str] | None = None):
        search_paths = path if path is not None else sys.path
        for base in search_paths:
            candidate = os.path.join(base, name + ".py")
            if os.path.exists(candidate):
                return open(candidate, "rb"), candidate, (".py", "rb", 1)
        raise ImportError(name)

    def load_module(name: str, fp, pathname: str, description):
        loader = importlib.machinery.SourceFileLoader(name, pathname)
        spec = importlib.util.spec_from_file_location(name, pathname, loader=loader)
        if spec is None:
            raise ImportError(name)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        loader.exec_module(module)
        return module

    imp.find_module = find_module  # type: ignore[attr-defined]
    imp.load_module = load_module  # type: ignore[attr-defined]
    sys.modules["imp"] = imp


def _load_protocol():
    _install_imp_compat()
    import mpyq  # type: ignore
    from s2protocol import versions  # type: ignore
    return mpyq, versions


def clean_name(value: Any, fallback: str = "Unknown") -> str:
    if value is None:
        return fallback
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    text = html.unescape(text).replace("<sp/>", " ").replace("<sp />", " ")
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def safe_str(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def loops_to_seconds(loop: int | None) -> int | None:
    if loop is None:
        return None
    return int(round(int(loop) / 16))


def has_any(text: str, hints: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(h.lower() in t for h in hints)


def category_for_unit(unit_type: str) -> dict[str, int]:
    return {
        "is_structure": int(has_any(unit_type, STRUCTURE_HINTS)),
        "is_static_defense": int(has_any(unit_type, STATIC_DEFENSE_HINTS)),
        "is_wall_gate": int(has_any(unit_type, WALL_GATE_HINTS)),
        "is_castle": int(has_any(unit_type, CASTLE_HINTS)),
        "is_cavalry": int(has_any(unit_type, CAVALRY_HINTS)),
        "is_ranged": int(has_any(unit_type, RANGED_HINTS)),
        "is_infantry": int(has_any(unit_type, INFANTRY_HINTS)),
        "is_siege": int(has_any(unit_type, SIEGE_HINTS)),
        "is_econ": int(has_any(unit_type, ECON_HINTS)),
        "is_production": int(has_any(unit_type, PROD_HINTS)),
        "is_noise": int(has_any(unit_type, NON_COMBAT_HINTS)),
    }


def tag_from_event(event: dict[str, Any]) -> tuple[int, int] | None:
    idx = event.get("m_unitTagIndex")
    rec = event.get("m_unitTagRecycle")
    if idx is None or rec is None:
        return None
    return int(idx), int(rec)


@dataclass
class ExtractedReplay:
    replay_id: str
    source_name: str
    map_name: str | None = None
    game_version: str | None = None
    duration_seconds: int | None = None
    parser_ok: bool = False
    warnings: list[str] = field(default_factory=list)
    replays: list[dict[str, Any]] = field(default_factory=list)
    players: list[dict[str, Any]] = field(default_factory=list)
    unit_events: list[dict[str, Any]] = field(default_factory=list)
    player_stats: list[dict[str, Any]] = field(default_factory=list)
    team_stats: list[dict[str, Any]] = field(default_factory=list)
    timeline_snapshots: list[dict[str, Any]] = field(default_factory=list)


def _pid_to_index(pid: Any, n: int) -> int | None:
    if pid is None:
        return None
    try:
        i = int(pid) - 1
    except Exception:
        return None
    if 0 <= i < n:
        return i
    return None


def _uid_to_index(uid: Any, n: int) -> int | None:
    if uid is None:
        return None
    try:
        i = int(uid)
    except Exception:
        return None
    if 0 <= i < n:
        return i
    return None


def parse_replay_file(path: Path, source_name: str | None = None) -> ExtractedReplay:
    data = path.read_bytes()
    replay_id = hashlib.sha256(data).hexdigest()[:16]
    source = source_name or path.name
    ex = ExtractedReplay(replay_id=replay_id, source_name=source)

    try:
        mpyq, versions = _load_protocol()
        archive = mpyq.MPQArchive(str(path))
        header_content = archive.header["user_data_header"]["content"]
        header = versions.latest().decode_replay_header(header_content)
        base_build = header["m_version"]["m_baseBuild"]
        protocol = versions.build(base_build)
        ex.game_version = str(base_build)
        details = protocol.decode_replay_details(archive.read_file("replay.details"))
        ex.map_name = clean_name(details.get("m_title"), fallback="Unknown")

        players = []
        for idx, p in enumerate(details.get("m_playerList", [])):
            result = {1: "Win", 2: "Loss", 3: "Tie", 0: "Undecided"}.get(p.get("m_result"), p.get("m_result"))
            players.append({
                "replay_id": replay_id,
                "player_index": idx,
                "player_id": idx + 1,
                "name": clean_name(p.get("m_name"), f"Player {idx + 1}"),
                "team_id": p.get("m_teamId"),
                "result": result,
            })
        ex.players = players

        command_counts = Counter()
        control_counts = Counter()
        camera_counts = Counter()
        chat_counts = Counter()
        ping_counts = Counter()
        leave_seconds: dict[int, int] = {}
        max_loop = 0
        try:
            for ev in protocol.decode_replay_game_events(archive.read_file("replay.game.events")):
                loop = int(ev.get("_gameloop", 0) or 0)
                max_loop = max(max_loop, loop)
                uid = _uid_to_index(ev.get("_userid", {}).get("m_userId"), len(players))
                if uid is None:
                    continue
                name = ev.get("_event")
                if name == "NNet.Game.SCmdEvent":
                    command_counts[uid] += 1
                elif name == "NNet.Game.SControlGroupUpdateEvent":
                    control_counts[uid] += 1
                elif name == "NNet.Game.SCameraUpdateEvent":
                    camera_counts[uid] += 1
                elif name == "NNet.Game.STriggerChatMessageEvent":
                    chat_counts[uid] += 1
                elif name == "NNet.Game.STriggerPingEvent":
                    ping_counts[uid] += 1
                elif name == "NNet.Game.SGameUserLeaveEvent":
                    s = loops_to_seconds(loop)
                    if s is not None:
                        leave_seconds[uid] = s
        except Exception as exc:
            ex.warnings.append(f"game events decode failed: {type(exc).__name__}: {exc}")

        tag_owner: dict[tuple[int, int], int] = {}
        tag_type: dict[tuple[int, int], str] = {}
        pending_init: dict[tuple[int, int], tuple[int, str, int]] = {}
        max_tracker_loop = 0
        unit_events: list[dict[str, Any]] = []
        try:
            for ev in protocol.decode_replay_tracker_events(archive.read_file("replay.tracker.events")):
                loop = int(ev.get("_gameloop", 0) or 0)
                max_tracker_loop = max(max_tracker_loop, loop)
                seconds = loops_to_seconds(loop)
                minute = round((seconds or 0) / 60, 3)
                evname = ev.get("_event")
                if evname == "NNet.Replay.Tracker.SUnitBornEvent":
                    unit = safe_str(ev.get("m_unitTypeName"), "UnknownUnit")
                    pid = ev.get("m_controlPlayerId") or ev.get("m_upkeepPlayerId")
                    idx = _pid_to_index(pid, len(players))
                    tag = tag_from_event(ev)
                    if tag and pid:
                        tag_owner[tag] = int(pid)
                        tag_type[tag] = unit
                    if idx is not None and not category_for_unit(unit)["is_noise"]:
                        unit_events.append({
                            "replay_id": replay_id, "source_name": source, "event_type": "unit_born",
                            "loop": loop, "seconds": seconds, "minute": minute,
                            "player_index": idx, "player_id": idx + 1, "player_name": players[idx]["name"],
                            "team_id": players[idx]["team_id"], "unit_type": unit,
                            **category_for_unit(unit),
                        })
                elif evname == "NNet.Replay.Tracker.SUnitInitEvent":
                    unit = safe_str(ev.get("m_unitTypeName"), "UnknownUnit")
                    pid = ev.get("m_controlPlayerId") or ev.get("m_upkeepPlayerId")
                    tag = tag_from_event(ev)
                    if tag and pid:
                        tag_owner[tag] = int(pid)
                        tag_type[tag] = unit
                        pending_init[tag] = (int(pid), unit, loop)
                elif evname == "NNet.Replay.Tracker.SUnitDoneEvent":
                    tag = tag_from_event(ev)
                    if tag and tag in pending_init:
                        pid, unit, init_loop = pending_init[tag]
                        idx = _pid_to_index(pid, len(players))
                        if idx is not None and category_for_unit(unit)["is_structure"]:
                            unit_events.append({
                                "replay_id": replay_id, "source_name": source, "event_type": "structure_done",
                                "loop": loop, "seconds": seconds, "minute": minute,
                                "init_loop": init_loop, "build_seconds": loops_to_seconds(loop - init_loop),
                                "player_index": idx, "player_id": idx + 1, "player_name": players[idx]["name"],
                                "team_id": players[idx]["team_id"], "unit_type": unit,
                                **category_for_unit(unit),
                            })
                elif evname == "NNet.Replay.Tracker.SUnitTypeChangeEvent":
                    tag = tag_from_event(ev)
                    unit = safe_str(ev.get("m_unitTypeName"), "UnknownUnit")
                    if tag:
                        tag_type[tag] = unit
                elif evname == "NNet.Replay.Tracker.SUnitDiedEvent":
                    tag = tag_from_event(ev)
                    unit = safe_str(ev.get("m_unitTypeName"), "UnknownUnit")
                    if unit == "UnknownUnit" and tag in tag_type:
                        unit = tag_type[tag]  # type: ignore[index]
                    owner_pid = ev.get("m_unitOwnerPlayerId") or (tag_owner.get(tag) if tag else None)
                    killer_pid = ev.get("m_killerPlayerId")
                    owner_idx = _pid_to_index(owner_pid, len(players))
                    killer_idx = _pid_to_index(killer_pid, len(players))
                    if owner_idx is not None and not category_for_unit(unit)["is_noise"]:
                        unit_events.append({
                            "replay_id": replay_id, "source_name": source, "event_type": "unit_died",
                            "loop": loop, "seconds": seconds, "minute": minute,
                            "player_index": owner_idx, "player_id": owner_idx + 1, "player_name": players[owner_idx]["name"],
                            "team_id": players[owner_idx]["team_id"], "unit_type": unit,
                            "killer_player_index": killer_idx, "killer_player_name": players[killer_idx]["name"] if killer_idx is not None else None,
                            "killer_team_id": players[killer_idx]["team_id"] if killer_idx is not None else None,
                            **category_for_unit(unit),
                        })
                elif evname == "NNet.Replay.Tracker.SUpgradeEvent":
                    pid = ev.get("m_playerId")
                    idx = _pid_to_index(pid, len(players))
                    if idx is not None:
                        upg = safe_str(ev.get("m_upgradeTypeName"), "UnknownUpgrade")
                        unit_events.append({
                            "replay_id": replay_id, "source_name": source, "event_type": "upgrade",
                            "loop": loop, "seconds": seconds, "minute": minute,
                            "player_index": idx, "player_id": idx + 1, "player_name": players[idx]["name"],
                            "team_id": players[idx]["team_id"], "unit_type": upg,
                            **{k: 0 for k in category_for_unit("").keys()},
                        })
        except Exception as exc:
            ex.warnings.append(f"tracker events decode failed: {type(exc).__name__}: {exc}")

        ex.unit_events = unit_events
        duration = loops_to_seconds(max(max_loop, max_tracker_loop))
        ex.duration_seconds = duration

        stats_by_player: dict[int, dict[str, Any]] = {}
        for p in players:
            idx = p["player_index"]
            stats_by_player[idx] = {**p,
                "source_name": source,
                "map_name": ex.map_name,
                "duration_seconds": duration,
                "commands": int(command_counts[idx]),
                "control_groups": int(control_counts[idx]),
                "camera_events": int(camera_counts[idx]),
                "chat_messages": int(chat_counts[idx]),
                "pings": int(ping_counts[idx]),
                "leave_seconds": leave_seconds.get(idx),
                "apm": round(command_counts[idx] / max(1, (duration or 1) / 60), 1) if duration else None,
                "kills": 0, "losses": 0, "units_born": 0, "structures_done": 0,
                "static_defense": 0, "walls_gates": 0, "castles": 0,
                "cavalry_units": 0, "ranged_units": 0, "infantry_units": 0, "siege_units": 0,
                "econ_structures": 0, "production_structures": 0, "upgrades": 0,
            }
        for ev in unit_events:
            idx = ev.get("player_index")
            if idx is None or idx not in stats_by_player:
                continue
            s = stats_by_player[idx]
            if ev["event_type"] == "unit_born":
                s["units_born"] += 1
                s["cavalry_units"] += int(ev["is_cavalry"])
                s["ranged_units"] += int(ev["is_ranged"])
                s["infantry_units"] += int(ev["is_infantry"])
                s["siege_units"] += int(ev["is_siege"])
                s["static_defense"] += int(ev["is_static_defense"])
                s["walls_gates"] += int(ev["is_wall_gate"])
                s["castles"] += int(ev["is_castle"])
            elif ev["event_type"] == "structure_done":
                s["structures_done"] += 1
                s["static_defense"] += int(ev["is_static_defense"])
                s["walls_gates"] += int(ev["is_wall_gate"])
                s["castles"] += int(ev["is_castle"])
                s["econ_structures"] += int(ev["is_econ"])
                s["production_structures"] += int(ev["is_production"])
            elif ev["event_type"] == "unit_died":
                s["losses"] += 1
                killer_idx = ev.get("killer_player_index")
                if killer_idx is not None and killer_idx != idx and killer_idx in stats_by_player:
                    stats_by_player[killer_idx]["kills"] += 1
            elif ev["event_type"] == "upgrade":
                s["upgrades"] += 1

        # First timing features for guide/mining.
        firsts: dict[int, dict[str, float | None]] = {idx: {} for idx in stats_by_player}
        first_keys = {
            "first_static_defense_minute": lambda e: e["event_type"] in {"unit_born", "structure_done"} and e["is_static_defense"],
            "first_wall_gate_minute": lambda e: e["event_type"] in {"unit_born", "structure_done"} and e["is_wall_gate"],
            "first_castle_minute": lambda e: e["event_type"] in {"unit_born", "structure_done"} and e["is_castle"],
            "first_cavalry_minute": lambda e: e["event_type"] == "unit_born" and e["is_cavalry"],
            "first_ranged_minute": lambda e: e["event_type"] == "unit_born" and e["is_ranged"],
            "first_infantry_minute": lambda e: e["event_type"] == "unit_born" and e["is_infantry"],
            "first_siege_minute": lambda e: e["event_type"] == "unit_born" and e["is_siege"],
            "first_econ_structure_minute": lambda e: e["event_type"] == "structure_done" and e["is_econ"],
            "first_prod_structure_minute": lambda e: e["event_type"] == "structure_done" and e["is_production"],
            "first_upgrade_minute": lambda e: e["event_type"] == "upgrade",
        }
        for idx in stats_by_player:
            evs = sorted([e for e in unit_events if e.get("player_index") == idx], key=lambda e: e["minute"])
            for key, pred in first_keys.items():
                val = next((float(e["minute"]) for e in evs if pred(e)), None)
                firsts[idx][key] = round(val, 3) if val is not None else None
            stats_by_player[idx].update(firsts[idx])

        for s in stats_by_player.values():
            s["kl_ratio"] = round(s["kills"] / s["losses"], 3) if s["losses"] else None
            s["role_label"] = classify_role(s)
        ex.player_stats = list(stats_by_player.values())

        team_acc: dict[int, dict[str, Any]] = {}
        for s in ex.player_stats:
            tid = s.get("team_id")
            if tid is None:
                continue
            tid = int(tid)
            acc = team_acc.setdefault(tid, {
                "replay_id": replay_id, "source_name": source, "map_name": ex.map_name,
                "team_id": tid, "players": [], "result": None, "duration_seconds": duration,
                "kills": 0, "losses": 0, "units_born": 0, "structures_done": 0,
                "static_defense": 0, "walls_gates": 0, "castles": 0, "cavalry_units": 0,
                "ranged_units": 0, "infantry_units": 0, "siege_units": 0,
                "econ_structures": 0, "production_structures": 0, "commands": 0, "upgrades": 0,
            })
            acc["players"].append(s["name"])
            if s.get("result") == "Win": acc["result"] = "Win"
            elif acc["result"] != "Win" and s.get("result"): acc["result"] = s.get("result")
            for k in ["kills","losses","units_born","structures_done","static_defense","walls_gates","castles","cavalry_units","ranged_units","infantry_units","siege_units","econ_structures","production_structures","commands","upgrades"]:
                acc[k] += int(s.get(k) or 0)
        for acc in team_acc.values():
            acc["players"] = ", ".join(acc["players"])
            acc["kl_ratio"] = round(acc["kills"] / acc["losses"], 3) if acc["losses"] else None
            acc["style_label"] = classify_team(acc)
        ex.team_stats = list(team_acc.values())

        ex.timeline_snapshots = build_snapshots(ex)
        ex.replays = [{
            "replay_id": replay_id, "source_name": source, "map_name": ex.map_name,
            "game_version": ex.game_version, "duration_seconds": ex.duration_seconds,
            "players": len(ex.players), "parser_ok": True, "warnings": "; ".join(ex.warnings),
        }]
        ex.parser_ok = True
        return ex
    except Exception as exc:
        ex.warnings.append(f"parse failed: {type(exc).__name__}: {exc}")
        ex.replays = [{"replay_id": replay_id, "source_name": source, "parser_ok": False, "warnings": "; ".join(ex.warnings)}]
        return ex


def classify_role(s: dict[str, Any]) -> str:
    units = max(1, int(s.get("cavalry_units",0)) + int(s.get("ranged_units",0)) + int(s.get("infantry_units",0)) + int(s.get("siege_units",0)))
    static = int(s.get("static_defense",0)); wg = int(s.get("walls_gates",0))
    if wg >= 60 or static >= 150 or (static / max(1, int(s.get("units_born",0)) + int(s.get("structures_done",0))) >= 0.22 and static >= 40):
        return "Defensive anchor / wall player"
    if int(s.get("cavalry_units",0)) >= 80 and int(s.get("cavalry_units",0)) / units >= 0.25:
        return "Cavalry pressure / mobile carry"
    if int(s.get("kills",0)) >= 800:
        return "Main combat carry / pressure leader"
    if int(s.get("ranged_units",0)) >= 150 and int(s.get("cavalry_units",0)) >= 100:
        return "Mixed firepower + mobile pressure"
    if int(s.get("ranged_units",0)) >= 150 and int(s.get("ranged_units",0)) / units >= 0.25:
        return "Ranged firepower/support"
    if int(s.get("infantry_units",0)) >= 250 and int(s.get("ranged_units",0)) >= 100:
        return "Infantry + hand-cannon frontline"
    if int(s.get("siege_units",0)) >= 40:
        return "Siege-support player"
    if int(s.get("units_born",0)) >= 300:
        return "Mass-production support"
    return "Mixed/support"


def classify_team(s: dict[str, Any]) -> str:
    total = max(1, int(s.get("cavalry_units",0)) + int(s.get("ranged_units",0)) + int(s.get("infantry_units",0)) + int(s.get("siege_units",0)))
    if int(s.get("walls_gates",0)) >= 100 or (int(s.get("static_defense",0)) >= 350 and int(s.get("walls_gates",0)) >= 70):
        return "Turtle / layered-defense team"
    if int(s.get("cavalry_units",0)) / total >= 0.30:
        return "Mobile cavalry-pressure team"
    if int(s.get("ranged_units",0)) / total >= 0.35:
        return "Ranged/firepower-heavy team"
    if int(s.get("infantry_units",0)) / total >= 0.40 and int(s.get("ranged_units",0)) / total >= 0.20:
        return "Infantry + firepower frontline team"
    if int(s.get("infantry_units",0)) / total >= 0.45:
        return "Infantry-frontline-heavy team"
    return "Mixed-composition team"


def build_snapshots(ex: ExtractedReplay) -> list[dict[str, Any]]:
    out = []
    for p in ex.players:
        idx = p["player_index"]
        evs = [e for e in ex.unit_events if e.get("player_index") == idx]
        for m in SNAPSHOT_MINUTES:
            cutoff = m
            prior = [e for e in evs if float(e.get("minute") or 0) <= cutoff]
            row = {
                "replay_id": ex.replay_id, "source_name": ex.source_name, "map_name": ex.map_name,
                "player_index": idx, "player_id": idx + 1, "player_name": p["name"], "team_id": p.get("team_id"),
                "result": p.get("result"), "snapshot_minute": m,
                "kills_to_now": 0, "losses_to_now": 0,
                "units_born_to_now": sum(1 for e in prior if e["event_type"] == "unit_born"),
                "structures_done_to_now": sum(1 for e in prior if e["event_type"] == "structure_done"),
                "static_defense_to_now": sum(int(e["is_static_defense"]) for e in prior if e["event_type"] in {"unit_born","structure_done"}),
                "walls_gates_to_now": sum(int(e["is_wall_gate"]) for e in prior if e["event_type"] in {"unit_born","structure_done"}),
                "cavalry_to_now": sum(int(e["is_cavalry"]) for e in prior if e["event_type"] == "unit_born"),
                "ranged_to_now": sum(int(e["is_ranged"]) for e in prior if e["event_type"] == "unit_born"),
                "infantry_to_now": sum(int(e["is_infantry"]) for e in prior if e["event_type"] == "unit_born"),
                "siege_to_now": sum(int(e["is_siege"]) for e in prior if e["event_type"] == "unit_born"),
                "upgrades_to_now": sum(1 for e in prior if e["event_type"] == "upgrade"),
            }
            # Losses and kills up to now.
            for e in prior:
                if e["event_type"] == "unit_died":
                    row["losses_to_now"] += 1
                    if e.get("killer_player_index") == idx:
                        row["kills_to_now"] += 1
            out.append(row)
    return out


def iter_replay_inputs(paths: list[Path]) -> Iterable[tuple[str, Path]]:
    """Yield (source_name, temp_or_real_path) for .SC2Replay files and replay ZIPs."""
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for child in p.rglob("*.SC2Replay"):
                yield str(child.relative_to(p)), child
        elif p.suffix.lower() == ".sc2replay":
            yield p.name, p
        elif p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as zf:
                for info in zf.infolist():
                    if info.is_dir() or not info.filename.lower().endswith(".sc2replay"):
                        continue
                    data = zf.read(info)
                    tmp = Path(tempfile.gettempdir()) / f"aok_{hashlib.sha256(data).hexdigest()[:16]}.SC2Replay"
                    tmp.write_bytes(data)
                    yield f"{p.name}:{info.filename}", tmp
        else:
            continue


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = sorted({k for row in rows for k in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def parse_many(paths: list[Path], out_dir: Path, limit: int | None = None, write_events: bool = False) -> dict[str, int]:
    seen: set[str] = set()
    all_replays=[]; all_players=[]; all_events=[]; all_pstats=[]; all_tstats=[]; all_snaps=[]
    ok=0; failed=0; total=0
    for source_name, replay_path in iter_replay_inputs(paths):
        digest = hashlib.sha256(Path(replay_path).read_bytes()).hexdigest()[:16]
        if digest in seen:
            continue
        if limit and total >= limit:
            break
        seen.add(digest)
        total += 1
        ex = parse_replay_file(replay_path, source_name=source_name)
        ok += int(ex.parser_ok); failed += int(not ex.parser_ok)
        all_replays.extend(ex.replays); all_players.extend(ex.players)
        if write_events:
            all_events.extend(ex.unit_events)
        all_pstats.extend(ex.player_stats); all_tstats.extend(ex.team_stats); all_snaps.extend(ex.timeline_snapshots)
        if total % 25 == 0:
            print(f"parsed {total} unique replays ({ok} ok, {failed} failed)")
    datasets = out_dir / "datasets"
    write_csv(datasets / "replays.csv", all_replays)
    write_csv(datasets / "players.csv", all_players)
    if write_events:
        write_csv(datasets / "unit_events.csv", all_events)
    else:
        (datasets / "unit_events.README.txt").write_text("Full unit event CSV was skipped. Rerun ingest with --write-events to export it.\n", encoding="utf-8")
    write_csv(datasets / "player_match_stats.csv", all_pstats)
    write_csv(datasets / "team_match_stats.csv", all_tstats)
    write_csv(datasets / "timeline_snapshots.csv", all_snaps)
    return {"unique_replays": total, "parser_ok": ok, "parser_failed": failed, "unit_events": len(all_events), "player_rows": len(all_pstats)}


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

_BOT_SRC = Path(__file__).resolve().parents[3] / "discord_bot" / "src"
if str(_BOT_SRC) not in sys.path:
    sys.path.insert(0, str(_BOT_SRC))
from aok_bot.match_rules import classify_role as _shared_classify_role
from aok_bot.match_rules import classify_team as _shared_classify_team
from aok_bot.match_rules import is_neutral_player
from aok_bot.match_rules import normalize_match_groups
from aok_bot.match_rules import user_player_indices
from aok_bot.protocols import select_protocol

# Shared with the bot so both classify units the same way (exact mechanical
# names: HandCannoneer is ranged, not siege).
from aok_bot.replay_parser import (  # noqa: E402
    CASTLE_HINTS, CAVALRY_HINTS, ECON_HINTS, INFANTRY_HINTS, MECHANICAL_UNIT_LABELS,
    NON_COMBAT_HINTS, RANGED_HINTS, STATIC_DEFENSE_HINTS, STRUCTURE_HINTS, WALL_GATE_HINTS,
)

PROD_HINTS = ("Barracks", "Stable", "Archery", "Blacksmith", "Castle", "TownHall", "Town", "Hall", "Market", "Workshop")

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


# Same table as the bot (aok_bot.replay_parser): loops per real second by m_gameSpeed.
LOOPS_PER_SECOND_BY_SPEED = {0: 9.6, 1: 12.8, 2: 16.0, 3: 19.2, 4: 22.4}


def loops_to_seconds(loop: int | None, loops_per_second: float = 22.4) -> int | None:
    """Real seconds; AoK lobbies run at Faster speed (22.4 game loops per second)."""
    if loop is None:
        return None
    return int(round(int(loop) / loops_per_second))


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
        "is_siege": int(unit_type in MECHANICAL_UNIT_LABELS),
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
    decoder_build: str | None = field(default=None, kw_only=True)
    game_events_complete: bool | None = field(default=None, kw_only=True)
    tracker_events_complete: bool | None = field(default=None, kw_only=True)
    duration_seconds: int | None = None
    parser_ok: bool = False
    warnings: list[str] = field(default_factory=list)
    replays: list[dict[str, Any]] = field(default_factory=list)
    players: list[dict[str, Any]] = field(default_factory=list)
    unit_events: list[dict[str, Any]] = field(default_factory=list)
    player_stats: list[dict[str, Any]] = field(default_factory=list)
    team_stats: list[dict[str, Any]] = field(default_factory=list)
    timeline_snapshots: list[dict[str, Any]] = field(default_factory=list)
    match_mode: str = "Unknown"


def _attribute_death(stats_by_player: dict[int, dict[str, Any]], event: dict[str, Any]) -> None:
    """Keep neutral animal combat out of player-vs-player kill/loss totals."""
    owner_idx, killer_idx = event.get("player_index"), event.get("killer_player_index")
    owner_is_animal = int(event.get("player_id") or 0) == 15
    killer_is_animal = int(event.get("killer_player_id") or 0) == 15
    if owner_is_animal:
        if killer_idx is not None and not killer_is_animal and killer_idx in stats_by_player:
            stats_by_player[killer_idx]["animal_kills"] += 1
    elif owner_idx is not None and owner_idx in stats_by_player:
        owner = stats_by_player[owner_idx]
        if killer_is_animal:
            owner["deaths_to_animals"] += 1
        else:
            owner["losses"] += 1
            if killer_idx is not None and killer_idx != owner_idx and killer_idx in stats_by_player:
                stats_by_player[killer_idx]["kills"] += 1


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



def parse_replay_file(path: Path, source_name: str | None = None) -> ExtractedReplay:
    data = path.read_bytes()
    replay_id = hashlib.sha256(data).hexdigest()[:16]
    source = source_name or path.name
    ex = ExtractedReplay(replay_id=replay_id, source_name=source)
    replay_handle = None

    try:
        mpyq, versions = _load_protocol()
        replay_handle = path.open("rb")
        archive = mpyq.MPQArchive(replay_handle)
        header_content = archive.header["user_data_header"]["content"]
        header = versions.latest().decode_replay_header(header_content)
        base_build = header["m_version"]["m_baseBuild"]
        protocol, decoder_build = select_protocol(versions, base_build)
        ex.decoder_build = str(decoder_build)
        if decoder_build != base_build:
            ex.warnings.append(
                f"Compatibility decoder: replay base build {base_build} uses protocol {decoder_build}; "
                "mapping verified against the local replay corpus.")
        ex.game_version = str(base_build)
        details = protocol.decode_replay_details(archive.read_file("replay.details"))
        loops_per_second = LOOPS_PER_SECOND_BY_SPEED.get(details.get("m_gameSpeed"), 22.4)
        try:
            initdata = protocol.decode_replay_initdata(archive.read_file("replay.initData"))
        except Exception:
            initdata = None
        user_index = user_player_indices(details.get("m_playerList", []), initdata)
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
                "raw_team_id": p.get("m_teamId"),
                "result": result,
            })
        ex.match_mode, groups = normalize_match_groups(players)
        for player, group in zip(players, groups):
            player["team_id"] = group
            player["match_mode"] = ex.match_mode
        # SC2 marks everyone present at the end as Win, so only a replay with Win
        # on exactly one side has a usable label; its other sides lost. Anything
        # else (no Win, Win on several sides) is "Unknown" and excluded from
        # win/loss statistics.
        win_sides = {p["team_id"] for p in players if p.get("result") == "Win" and p.get("team_id") is not None}
        for player in players:
            player["raw_result"] = player.get("result")
            if len(win_sides) == 1 and player.get("team_id") is not None and not is_neutral_player(player):
                player["result"] = "Win" if player["team_id"] in win_sides else "Loss"
            else:
                player["result"] = "Unknown"
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
                uid = user_index.get(ev.get("_userid", {}).get("m_userId"))
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
                    s = loops_to_seconds(loop, loops_per_second)
                    if s is not None:
                        leave_seconds[uid] = s
        except Exception as exc:
            ex.game_events_complete = False
            ex.warnings.append(f"game events decode failed: {type(exc).__name__}: {exc}. Command counts are partial; APM is unavailable.")
        else:
            ex.game_events_complete = True

        tag_owner: dict[tuple[int, int], int] = {}
        tag_type: dict[tuple[int, int], str] = {}
        pending_init: dict[tuple[int, int], tuple[int, str, int]] = {}
        max_tracker_loop = 0
        unit_events: list[dict[str, Any]] = []
        try:
            for ev in protocol.decode_replay_tracker_events(archive.read_file("replay.tracker.events")):
                loop = int(ev.get("_gameloop", 0) or 0)
                max_tracker_loop = max(max_tracker_loop, loop)
                seconds = loops_to_seconds(loop, loops_per_second)
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
                                "init_loop": init_loop, "build_seconds": loops_to_seconds(loop - init_loop, loops_per_second),
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
                    if (owner_idx is not None or str(owner_pid) == "15") and not category_for_unit(unit)["is_noise"]:
                        unit_events.append({
                            "replay_id": replay_id, "source_name": source, "event_type": "unit_died",
                            "loop": loop, "seconds": seconds, "minute": minute,
                            "player_index": owner_idx, "player_id": int(owner_pid) if owner_pid is not None else None,
                            "player_name": players[owner_idx]["name"] if owner_idx is not None else "Animals / Player 15",
                            "team_id": players[owner_idx]["team_id"] if owner_idx is not None else None, "unit_type": unit,
                            "killer_player_index": killer_idx, "killer_player_name": players[killer_idx]["name"] if killer_idx is not None else None,
                            "killer_team_id": players[killer_idx]["team_id"] if killer_idx is not None else None,
                            "killer_player_id": int(killer_pid) if killer_pid is not None else None,
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
            ex.tracker_events_complete = False
            ex.warnings.append(f"tracker events decode failed: {type(exc).__name__}: {exc}")
            raise
        else:
            ex.tracker_events_complete = True

        ex.unit_events = unit_events
        duration = loops_to_seconds(max(max_loop, max_tracker_loop), loops_per_second)
        ex.duration_seconds = duration
        for event in unit_events:
            event["match_mode"] = ex.match_mode
            idx = event.get("player_index")
            if idx is not None:
                event["raw_team_id"] = players[idx]["raw_team_id"]
            killer_idx = event.get("killer_player_index")
            if killer_idx is not None:
                event["killer_team_id"] = players[killer_idx]["team_id"]
                event["killer_raw_team_id"] = players[killer_idx]["raw_team_id"]

        stats_by_player: dict[int, dict[str, Any]] = {}
        for p in players:
            if is_neutral_player(p):
                continue
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
                "game_events_complete": ex.game_events_complete,
                "apm": round(command_counts[idx] / max(1, (duration or 1) / 60), 1) if duration and ex.game_events_complete else None,
                "kills": 0, "losses": 0, "animal_kills": 0, "deaths_to_animals": 0,
                "units_born": 0, "structures_done": 0,
                "static_defense": 0, "walls_gates": 0, "castles": 0,
                "cavalry_units": 0, "ranged_units": 0, "infantry_units": 0, "siege_units": 0,
                "econ_structures": 0, "production_structures": 0, "upgrades": 0,
            }
        for ev in unit_events:
            idx = ev.get("player_index")
            if ev["event_type"] == "unit_died":
                _attribute_death(stats_by_player, ev)
                continue
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
                "team_id": tid, "match_mode": ex.match_mode, "players": [], "result": None, "duration_seconds": duration,
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
            "decoder_build": ex.decoder_build,
            "game_events_complete": ex.game_events_complete, "tracker_events_complete": ex.tracker_events_complete,
            "players": len(ex.players), "match_mode": ex.match_mode,
            "parser_ok": True, "warnings": "; ".join(ex.warnings),
        }]
        ex.parser_ok = True
        return ex
    except Exception as exc:
        ex.warnings.append(f"parse failed: {type(exc).__name__}: {exc}")
        ex.replays = [{"replay_id": replay_id, "source_name": source, "match_mode": ex.match_mode,
                       "decoder_build": ex.decoder_build, "game_events_complete": ex.game_events_complete,
                       "tracker_events_complete": ex.tracker_events_complete,
                       "parser_ok": False, "warnings": "; ".join(ex.warnings)}]
        return ex
    finally:
        if replay_handle is not None:
            replay_handle.close()


def classify_role(s: dict[str, Any]) -> str:
    return _shared_classify_role(s)


def classify_team(s: dict[str, Any]) -> str:
    return _shared_classify_team(s)


def build_snapshots(ex: ExtractedReplay) -> list[dict[str, Any]]:
    out = []
    for p in ex.players:
        if is_neutral_player(p):
            continue
        idx = p["player_index"]
        evs = [e for e in ex.unit_events if e.get("player_index") == idx
               or (e["event_type"] == "unit_died" and e.get("killer_player_index") == idx)]
        for m in SNAPSHOT_MINUTES:
            if ex.duration_seconds is not None and m * 60 > ex.duration_seconds:
                break  # no snapshots after the replay ended
            cutoff = m
            prior = [e for e in evs if float(e.get("minute") or 0) <= cutoff]
            row = {
                "replay_id": ex.replay_id, "source_name": ex.source_name, "map_name": ex.map_name,
                "player_index": idx, "player_id": idx + 1, "player_name": p["name"], "team_id": p.get("team_id"),
                "raw_team_id": p.get("raw_team_id"), "match_mode": ex.match_mode,
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
                    if int(e.get("player_id") or 0) == 15 or int(e.get("killer_player_id") or 0) == 15:
                        continue
                    if e.get("player_index") == idx:
                        row["losses_to_now"] += 1
                    if e.get("killer_player_index") == idx and e.get("player_index") not in (None, idx):
                        row["kills_to_now"] += 1
            out.append(row)
    return out


MAX_ZIP_MEMBER_BYTES = 25 * 1024 * 1024


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
            with zipfile.ZipFile(p) as zf, tempfile.TemporaryDirectory(prefix="aok_zip_") as tmp_dir:
                for info in zf.infolist():
                    if info.is_dir() or not info.filename.lower().endswith(".sc2replay"):
                        continue
                    if not 0 < info.file_size <= MAX_ZIP_MEMBER_BYTES:
                        continue  # same per-replay cap as the bot's upload path
                    with zf.open(info) as fh:
                        data = fh.read(MAX_ZIP_MEMBER_BYTES + 1)
                    if len(data) > MAX_ZIP_MEMBER_BYTES:
                        continue
                    tmp = Path(tmp_dir) / f"{hashlib.sha256(data).hexdigest()[:16]}.SC2Replay"
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


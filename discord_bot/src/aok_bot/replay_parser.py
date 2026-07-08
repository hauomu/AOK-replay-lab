from __future__ import annotations

import hashlib
import html
import importlib.machinery
import importlib.util
import os
import re
import sys
import types
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .models import PlayerStats, ReplaySummary, TeamStats


class ReplayParserError(RuntimeError):
    pass


STRUCTURE_HINTS = (
    "House", "Farm", "Barracks", "Stable", "Archery", "Blacksmith", "Market", "Mill",
    "Lumber", "Mine", "Tower", "Castle", "Gate", "Wall", "Post", "Keep", "Town", "Hall",
)
STATIC_DEFENSE_HINTS = (
    "Wall", "Gate", "Tower", "WatchPost", "GuardPost", "GuardTower", "Castle", "Keep",
)
WALL_GATE_HINTS = ("Wall", "Gate")
CASTLE_HINTS = ("Castle", "Keep")
CAVALRY_HINTS = ("Horse", "Knight", "Cavalry", "Mounted", "Rider")
RANGED_HINTS = ("Archer", "Crossbow", "HandCannoneer", "Gun", "Rifle", "Musk", "Bow")
INFANTRY_HINTS = ("Swordsman", "Spearman", "Militia", "Pikeman", "Footman", "Infantry", "ManAtArms")
SIEGE_HINTS = ("Ballista", "Bombard", "Catapult", "Trebuchet", "Siege", "Cannon")
ECON_HINTS = ("House", "Farm", "Market", "Mill", "Lumber", "Mine", "TownHall", "Town", "Hall")
NON_COMBAT_HINTS = ("Beacon", "Dummy", "Path", "Marker", "Cursor", "Camera", "Missile", "Projectile")


def stable_copy_name(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    safe_stem = ''.join(ch if ch.isalnum() or ch in '._- ' else '_' for ch in path.stem)
    return f"{safe_stem}__{digest}{path.suffix}"


def extract_replay_paths(input_path: Path, replays_dir: Path) -> list[Path]:
    """Copy/extract a .SC2Replay or .zip to the bot replay folder and return replay paths."""
    replays_dir.mkdir(parents=True, exist_ok=True)
    suffix = input_path.suffix.lower()

    if suffix == ".sc2replay":
        out = replays_dir / stable_copy_name(input_path)
        out.write_bytes(input_path.read_bytes())
        return [out]

    if suffix == ".zip":
        found: list[Path] = []
        with zipfile.ZipFile(input_path) as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                if not member.filename.lower().endswith(".sc2replay"):
                    continue
                raw_name = Path(member.filename).name
                with zf.open(member) as src:
                    data = src.read()
                digest = hashlib.sha256(data).hexdigest()[:16]
                safe_name = ''.join(ch if ch.isalnum() or ch in '._- ' else '_' for ch in raw_name)
                out = replays_dir / f"{Path(safe_name).stem}__{digest}.SC2Replay"
                out.write_bytes(data)
                found.append(out)
        return found

    raise ReplayParserError(f"Unsupported upload type: {input_path.name}")


def _install_imp_compat() -> None:
    """s2protocol still imports the removed `imp` module on newer Python versions.

    Python 3.11 is still recommended, but this small compatibility shim prevents
    a confusing `ModuleNotFoundError: No module named 'imp'` on 3.12+.
    """
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


def _load_s2protocol():
    try:
        _install_imp_compat()
        import mpyq  # type: ignore
        from s2protocol import versions  # type: ignore
        return mpyq, versions
    except Exception as exc:  # pragma: no cover - depends on optional package
        raise ReplayParserError(
            "Full replay parsing requires Blizzard s2protocol + mpyq. "
            "Use the project venv, then run: pip install mpyq; "
            "git clone https://github.com/Blizzard/s2protocol.git external/s2protocol; "
            "pip install -e external/s2protocol. "
            f"Actual import error: {type(exc).__name__}: {exc}"
        ) from exc


def _safe_decode_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _clean_player_name(value: Any, fallback: str) -> str:
    raw = _safe_decode_string(value) or fallback
    text = html.unescape(raw)
    text = text.replace("<sp/>", " ").replace("<sp />", " ")
    # Remove SC2 rich-text/color/clan-ish tags such as <QNTlt>, <GodAge>, <c val=...>.
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def _decode_unit_type(value: Any) -> str:
    return (_safe_decode_string(value) or "UnknownUnit").strip() or "UnknownUnit"


def _seconds_from_loops(game_loop: int | None) -> int | None:
    if game_loop is None:
        return None
    # SC2 replays commonly use 16 game loops per game second.
    return int(round(game_loop / 16))


def _tag(event: dict[str, Any]) -> tuple[int, int] | None:
    index = event.get("m_unitTagIndex")
    recycle = event.get("m_unitTagRecycle")
    if index is None or recycle is None:
        return None
    return int(index), int(recycle)


def _pid_to_player(players: list[PlayerStats], pid: Any) -> PlayerStats | None:
    if pid is None:
        return None
    try:
        idx = int(pid) - 1  # tracker player IDs are normally 1-based.
    except Exception:
        return None
    if 0 <= idx < len(players):
        return players[idx]
    return None


def _increment(counter: dict[str, int], key: str, amount: int = 1) -> None:
    counter[key] = counter.get(key, 0) + amount


def _has_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint.lower() in text.lower() for hint in hints)


def _is_structure(unit_type: str) -> bool:
    return _has_any(unit_type, STRUCTURE_HINTS)


def _is_noise_unit(unit_type: str) -> bool:
    return _has_any(unit_type, NON_COMBAT_HINTS)


def _apply_unit_category(player: PlayerStats, unit_type: str, amount: int = 1, *, completed_structure: bool = False) -> None:
    if _has_any(unit_type, STATIC_DEFENSE_HINTS):
        player.static_defense += amount
    if _has_any(unit_type, WALL_GATE_HINTS):
        player.walls_gates += amount
    if _has_any(unit_type, CASTLE_HINTS):
        player.castles += amount
    if _has_any(unit_type, CAVALRY_HINTS):
        player.cavalry_units += amount
    if _has_any(unit_type, RANGED_HINTS):
        player.ranged_units += amount
    if _has_any(unit_type, INFANTRY_HINTS):
        player.infantry_units += amount
    if _has_any(unit_type, SIEGE_HINTS):
        player.siege_units += amount
    if completed_structure and _has_any(unit_type, ECON_HINTS):
        player.economic_structures += amount


def _classify_player_role(player: PlayerStats) -> str:
    total_combatish = max(1, player.cavalry_units + player.ranged_units + player.infantry_units + player.siege_units)
    static_ratio = player.static_defense / max(1, player.units_born + player.structures_done)
    cavalry_ratio = player.cavalry_units / total_combatish
    ranged_ratio = player.ranged_units / total_combatish
    infantry_ratio = player.infantry_units / total_combatish

    # Extreme walls/gates/static structures are a very distinct AoK fingerprint.
    if player.walls_gates >= 60 or player.static_defense >= 150 or (static_ratio >= 0.22 and player.static_defense >= 40):
        return "Defensive anchor / wall player"
    if player.cavalry_units >= 80 and cavalry_ratio >= 0.25:
        return "Cavalry pressure / mobile carry"
    if player.kills >= 800:
        return "Main combat carry / pressure leader"
    if player.ranged_units >= 150 and player.cavalry_units >= 100:
        return "Mixed firepower + mobile pressure"
    if player.ranged_units >= 150 and ranged_ratio >= 0.25:
        return "Ranged firepower/support"
    if player.infantry_units >= 250 and player.ranged_units >= 100:
        return "Infantry + hand-cannon frontline"
    if player.infantry_units >= 250 and infantry_ratio >= 0.40:
        return "Infantry frontline/mass army"
    if player.siege_units >= 40:
        return "Siege-support player"
    if player.units_born >= 300:
        return "Mass-production support"
    return "Mixed/support"


def _team_style(team: TeamStats) -> str:
    total = max(1, team.cavalry_units + team.ranged_units + team.infantry_units + team.siege_units)
    if team.walls_gates >= 100 or (team.static_defense >= 350 and team.walls_gates >= 70):
        return "Turtle / layered-defense team"
    if team.cavalry_units / total >= 0.30:
        return "Mobile cavalry-pressure team"
    if team.ranged_units / total >= 0.35:
        return "Ranged/firepower-heavy team"
    if team.infantry_units / total >= 0.40 and team.ranged_units / total >= 0.20:
        return "Infantry + firepower frontline team"
    if team.infantry_units / total >= 0.45:
        return "Infantry-frontline-heavy team"
    return "Mixed-composition team"


def _build_team_stats(summary: ReplaySummary) -> None:
    teams: dict[int, TeamStats] = {}
    for p in summary.players:
        if p.team_id is None:
            continue
        team = teams.setdefault(int(p.team_id), TeamStats(team_id=int(p.team_id)))
        team.players.append(p.name)
        if p.result == "Win":
            team.result = "Win"
        elif team.result != "Win" and p.result:
            team.result = p.result
        team.kills += p.kills
        team.losses += p.losses
        team.units_born += p.units_born
        team.commands += p.commands
        team.static_defense += p.static_defense
        team.walls_gates += p.walls_gates
        team.castles += p.castles
        team.cavalry_units += p.cavalry_units
        team.ranged_units += p.ranged_units
        team.infantry_units += p.infantry_units
        team.siege_units += p.siege_units
        team.structures_done += p.structures_done
        team.upgrades += p.upgrades

    for team in teams.values():
        team.style_label = _team_style(team)
    summary.teams = sorted(teams.values(), key=lambda t: t.team_id)


def _build_match_story(summary: ReplaySummary) -> None:
    players = summary.players
    if not players:
        return

    top_killer = max(players, key=lambda p: p.kills, default=None)
    top_producer = max(players, key=lambda p: p.units_born, default=None)
    top_defender = max(players, key=lambda p: p.static_defense, default=None)
    top_cavalry = max(players, key=lambda p: p.cavalry_units, default=None)
    efficient = [p for p in players if p.losses > 0 and p.kills >= 50]
    top_eff = max(efficient, key=lambda p: p.kills / max(1, p.losses), default=None)

    findings: list[str] = []
    story: list[str] = []

    if summary.teams:
        team_bits = []
        for t in summary.teams:
            ratio = t.kill_loss_ratio()
            ratio_label = f"{ratio:.2f}" if ratio is not None else "N/A"
            team_bits.append(
                f"Team {t.team_id}: {t.style_label}, K/L {t.kills}/{t.losses} ({ratio_label}), "
                f"units {t.units_born}, static defense {t.static_defense}."
            )
        story.extend(team_bits)

    if top_killer:
        findings.append(f"Main kill leader: {top_killer.name} with {top_killer.kills} credited kills.")
    if top_eff:
        findings.append(f"Most efficient major fighter: {top_eff.name} at K/L {top_eff.kills}/{top_eff.losses}.")
    if top_producer:
        findings.append(f"Largest production footprint: {top_producer.name} with {top_producer.units_born} units born.")
    if top_defender and top_defender.static_defense > 0:
        findings.append(f"Strongest defensive footprint: {top_defender.name} with {top_defender.static_defense} static-defense/wall/castle-style completions or spawns.")
    if top_cavalry and top_cavalry.cavalry_units > 0:
        findings.append(f"Largest cavalry/mobile footprint: {top_cavalry.name} with {top_cavalry.cavalry_units} cavalry-type units.")

    winners = summary.winner_label()
    if winners != "Unknown":
        story.insert(0, f"Winning side detected as {winners}.")

    # Add an interpretive sentence comparing teams where possible.
    if len(summary.teams) >= 2:
        ranked_by_static = sorted(summary.teams, key=lambda t: t.static_defense, reverse=True)
        ranked_by_ratio = sorted(
            [t for t in summary.teams if t.losses > 0],
            key=lambda t: t.kills / max(1, t.losses),
            reverse=True,
        )
        if ranked_by_static[0].static_defense >= ranked_by_static[-1].static_defense * 1.5 and ranked_by_static[0].static_defense >= 20:
            story.append(
                f"Team {ranked_by_static[0].team_id} was noticeably more defensive/static than the other side."
            )
        if ranked_by_ratio:
            story.append(
                f"Best team trade efficiency belongs to Team {ranked_by_ratio[0].team_id} "
                f"at K/L {ranked_by_ratio[0].kills}/{ranked_by_ratio[0].losses}."
            )

    summary.key_findings = findings
    summary.match_story = story


def parse_replay(path: Path) -> ReplaySummary:
    summary = ReplaySummary(source_path=path)

    try:
        mpyq, versions = _load_s2protocol()
    except ReplayParserError as exc:
        summary.warnings.append(str(exc))
        summary.map_name = "Unknown - parser dependency missing"
        return summary

    try:
        archive = mpyq.MPQArchive(str(path))
        header_content = archive.header["user_data_header"]["content"]
        header = versions.latest().decode_replay_header(header_content)
        base_build = header["m_version"]["m_baseBuild"]
        protocol = versions.build(base_build)
        summary.game_version = str(base_build)

        details = protocol.decode_replay_details(archive.read_file("replay.details"))
        try:
            protocol.decode_replay_initdata(archive.read_file("replay.initData"))
        except Exception:
            pass

        summary.map_name = _safe_decode_string(details.get("m_title"))
        if not summary.map_name:
            summary.map_name = _safe_decode_string(details.get("m_cacheHandles", [None])[0])
        if summary.map_name:
            summary.map_name = html.unescape(summary.map_name)

        players: list[PlayerStats] = []
        for idx, p in enumerate(details.get("m_playerList", [])):
            name = _clean_player_name(p.get("m_name"), f"Player {idx + 1}")
            team_id = p.get("m_teamId")
            result_code = p.get("m_result")
            result = {1: "Win", 2: "Loss", 3: "Tie", 0: "Undecided"}.get(
                result_code,
                str(result_code) if result_code is not None else None,
            )
            players.append(PlayerStats(name=name, team_id=team_id, result=result))
        summary.players = players

        # Game events: commands, APM-ish proxy, pings, chat, control groups, leave timings.
        game_event_count = 0
        command_counts: dict[int, int] = defaultdict(int)
        control_counts: dict[int, int] = defaultdict(int)
        camera_counts: dict[int, int] = defaultdict(int)
        chat_counts: dict[int, int] = defaultdict(int)
        ping_counts: dict[int, int] = defaultdict(int)
        max_loop = 0
        try:
            for event in protocol.decode_replay_game_events(archive.read_file("replay.game.events")):
                game_event_count += 1
                loop = int(event.get("_gameloop", 0) or 0)
                max_loop = max(max_loop, loop)
                uid_raw = event.get("_userid", {}).get("m_userId")
                try:
                    uid = int(uid_raw) if uid_raw is not None else None
                except Exception:
                    uid = None
                event_name = event.get("_event")
                if uid is not None and 0 <= uid < len(players):
                    if event_name == "NNet.Game.SCmdEvent":
                        command_counts[uid] += 1
                    elif event_name == "NNet.Game.SControlGroupUpdateEvent":
                        control_counts[uid] += 1
                    elif event_name == "NNet.Game.SCameraUpdateEvent":
                        camera_counts[uid] += 1
                    elif event_name == "NNet.Game.STriggerChatMessageEvent":
                        chat_counts[uid] += 1
                    elif event_name == "NNet.Game.STriggerPingEvent":
                        ping_counts[uid] += 1
                    elif event_name == "NNet.Game.SGameUserLeaveEvent":
                        players[uid].leave_time_seconds = _seconds_from_loops(loop)
        except Exception as exc:
            summary.warnings.append(f"Could not decode game events: {exc}")

        summary.raw_event_counts["game_events"] = game_event_count
        if max_loop:
            summary.duration_seconds = _seconds_from_loops(max_loop)

        for uid, player in enumerate(players):
            player.commands = int(command_counts.get(uid, 0))
            player.control_groups = int(control_counts.get(uid, 0))
            player.camera_events = int(camera_counts.get(uid, 0))
            player.chat_messages = int(chat_counts.get(uid, 0))
            player.pings = int(ping_counts.get(uid, 0))
            if summary.duration_seconds and summary.duration_seconds > 0:
                player.apm = int(round(player.commands / (summary.duration_seconds / 60)))

        # Tracker events: units, buildings, losses and kills.
        tracker_count = 0
        tag_owner: dict[tuple[int, int], int] = {}
        tag_type: dict[tuple[int, int], str] = {}
        pending_init: dict[tuple[int, int], tuple[int, str]] = {}
        max_tracker_loop = 0
        try:
            for event in protocol.decode_replay_tracker_events(archive.read_file("replay.tracker.events")):
                tracker_count += 1
                max_tracker_loop = max(max_tracker_loop, int(event.get("_gameloop", 0) or 0))
                event_name = event.get("_event")

                if event_name == "NNet.Replay.Tracker.SUnitBornEvent":
                    unit_type = _decode_unit_type(event.get("m_unitTypeName"))
                    pid = event.get("m_controlPlayerId") or event.get("m_upkeepPlayerId")
                    player = _pid_to_player(players, pid)
                    unit_tag = _tag(event)
                    if unit_tag and pid:
                        tag_owner[unit_tag] = int(pid)
                        tag_type[unit_tag] = unit_type
                    if player and not _is_noise_unit(unit_type):
                        player.units_born += 1
                        _increment(player.unit_type_counts, unit_type)
                        _apply_unit_category(player, unit_type)

                elif event_name == "NNet.Replay.Tracker.SUnitInitEvent":
                    unit_type = _decode_unit_type(event.get("m_unitTypeName"))
                    pid = event.get("m_controlPlayerId") or event.get("m_upkeepPlayerId")
                    unit_tag = _tag(event)
                    if unit_tag and pid:
                        pending_init[unit_tag] = (int(pid), unit_type)
                        tag_owner[unit_tag] = int(pid)
                        tag_type[unit_tag] = unit_type
                    player = _pid_to_player(players, pid)
                    if player and _is_structure(unit_type):
                        player.structures_started += 1

                elif event_name == "NNet.Replay.Tracker.SUnitDoneEvent":
                    unit_tag = _tag(event)
                    if unit_tag and unit_tag in pending_init:
                        pid, unit_type = pending_init[unit_tag]
                        player = _pid_to_player(players, pid)
                        if player:
                            player.structures_done += 1
                            _increment(player.structure_type_counts, unit_type)
                            _apply_unit_category(player, unit_type, completed_structure=True)

                elif event_name == "NNet.Replay.Tracker.SUnitTypeChangeEvent":
                    unit_tag = _tag(event)
                    new_type = _decode_unit_type(event.get("m_unitTypeName"))
                    if unit_tag:
                        tag_type[unit_tag] = new_type

                elif event_name == "NNet.Replay.Tracker.SUnitDiedEvent":
                    unit_tag = _tag(event)
                    owner_pid = event.get("m_unitOwnerPlayerId") or (tag_owner.get(unit_tag) if unit_tag else None)
                    unit_type = _decode_unit_type(event.get("m_unitTypeName"))
                    if unit_type == "UnknownUnit" and unit_tag in tag_type:
                        unit_type = tag_type[unit_tag]  # type: ignore[index]
                    owner = _pid_to_player(players, owner_pid)
                    if owner and not _is_noise_unit(unit_type):
                        owner.losses += 1
                        _increment(owner.unit_loss_counts, unit_type)
                    killer_pid = event.get("m_killerPlayerId")
                    killer = _pid_to_player(players, killer_pid)
                    # Avoid counting suicides/environment/no-player kills as player kills.
                    if killer and killer is not owner and not _is_noise_unit(unit_type):
                        killer.kills += 1

                elif event_name == "NNet.Replay.Tracker.SUpgradeEvent":
                    pid = event.get("m_playerId")
                    player = _pid_to_player(players, pid)
                    upgrade_name = _safe_decode_string(event.get("m_upgradeTypeName")) or "UnknownUpgrade"
                    if player:
                        player.upgrades += 1
                        _increment(player.upgrade_type_counts, upgrade_name)

                elif event_name == "NNet.Replay.Tracker.SPlayerStatsEvent":
                    pass
        except Exception as exc:
            summary.warnings.append(f"Could not decode tracker events: {exc}")

        summary.raw_event_counts["tracker_events"] = tracker_count
        if max_tracker_loop and (summary.duration_seconds is None or _seconds_from_loops(max_tracker_loop) > summary.duration_seconds):
            summary.duration_seconds = _seconds_from_loops(max_tracker_loop)

        try:
            msg_events = list(protocol.decode_replay_message_events(archive.read_file("replay.message.events")))
            summary.raw_event_counts["message_events"] = len(msg_events)
        except Exception as exc:
            summary.warnings.append(f"Could not decode message events: {exc}")

        for player in players:
            player.role_label = _classify_player_role(player)

        _build_team_stats(summary)
        _build_match_story(summary)
        summary.parser_ok = True
        return summary

    except Exception as exc:
        summary.warnings.append(f"Replay parse failed: {type(exc).__name__}: {exc}")
        summary.map_name = "Unknown - parse failed"
        return summary

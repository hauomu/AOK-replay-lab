from __future__ import annotations

import html
import importlib.machinery
import importlib.util
import os
import re
import sys
import types
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from .models import PlayerStats, ReplaySummary, TeamStats
from .protocols import UnsupportedReplayBuild, select_protocol
from .match_rules import classify_role, classify_team, normalize_match_groups, user_player_indices


class ReplayParserError(RuntimeError):
    pass


ANIMAL_PLAYER_ID = 15
ANIMAL_PLAYER_NAME = "Animals / Player 15"
SNAPSHOT_SECONDS = 5 * 60

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
ECON_HINTS = ("House", "Farm", "Market", "Mill", "Lumber", "Mine", "TownHall", "Town", "Hall")
NON_COMBAT_HINTS = ("Beacon", "Dummy", "Path", "Marker", "Cursor", "Camera", "Missile", "Projectile")

# v1.0 uses exact AoK protocol names. This avoids the old substring bug where
# HandCannoneer was treated as siege merely because it contains "Cannon".
MECHANICAL_UNIT_LABELS: dict[str, str] = {
    "Ballista": "Ballista",
    "BatteringRam": "Battering Ram",
    "BombardCannon": "Bombard Cannon",
    "Catapult": "Catapult",
    "ExplosiveWagon": "Explosives Wagon",
    "ExplosivesWagon": "Explosives Wagon",
    "TrebutchetMobile": "Trebuchet (Move Mode)",
    "TrebutchetSieged": "Trebuchet (Siege Mode)",
}
MECHANICAL_ATTACK_TYPES = {
    "Ballista", "BatteringRam", "BombardCannon", "Catapult",
    "ExplosiveWagon", "ExplosivesWagon", "TrebutchetSieged",
}
TREBUCHET_TYPES = {"TrebutchetMobile", "TrebutchetSieged"}

RESOURCE_PROTOCOL_LABELS = {
    "gold": "Minerals",
    "wood": "Vespene",
    "iron": "Terrazine",
}
RESOURCE_DISPLAY_LABELS = {
    "gold": "Gold",
    "wood": "Wood",
    "iron": "Iron",
}

AGE_UPGRADES: dict[str, str] = {
    "AgeIIDarkAge": "Dark Age",
    "AgeIIIFeudalAge2": "Feudal Age",
    "AgeIVCastleAge": "Castle Age",
    "AgeVImperialAge": "Imperial Age",
}
AGE_RANK = {
    "Starting age": 0,
    "Dark Age": 1,
    "Feudal Age": 2,
    "Castle Age": 3,
    "Imperial Age": 4,
}

TECH_STRUCTURE_RULES: dict[str, dict[str, str]] = {
    "Blacksmith": {"label": "Blacksmith", "category": "general combat tech", "inferred_age": "Feudal Age"},
    "FletchersWorkshop": {"label": "Fletcher's Workshop", "category": "ranged tech", "inferred_age": "Feudal Age"},
    "SiegeWorkshop": {"label": "Siege Workshop", "category": "mechanical production / tech", "inferred_age": "Castle Age"},
    "Castle": {"label": "Castle", "category": "late tech / defense / trebuchet access", "inferred_age": "Castle Age"},
    "AlchemistsLab": {"label": "Alchemist's Lab", "category": "advanced firepower tech", "inferred_age": "Imperial Age"},
}

KEY_UNLOCK_RULES: dict[str, dict[str, str]] = {
    "UnlockHandCannoneer": {
        "label": "Unlock Hand Cannoneer",
        "unit": "HandCannoneer",
        "category": "advanced ranged firepower unlock",
        "inferred_age": "Imperial Age",
        "likely_structure": "AlchemistsLab",
    },
    "UnlockBombardCannons": {
        "label": "Unlock Bombard Cannons",
        "unit": "BombardCannon",
        "category": "advanced mechanical firepower unlock",
        "inferred_age": "Imperial Age",
        "likely_structure": "AlchemistsLab",
    },
}

ADVANCED_UNIT_RULES: dict[str, dict[str, str]] = {
    "HandCannoneer": {"label": "Hand Cannoneer", "likely_unlock": "UnlockHandCannoneer", "likely_structure": "AlchemistsLab", "inferred_age": "Imperial Age"},
    "Ballista": {"label": "Ballista", "likely_unlock": "UpgradeBallistas", "likely_structure": "SiegeWorkshop", "inferred_age": "Castle Age"},
    "BatteringRam": {"label": "Battering Ram", "likely_unlock": "UpgradeBatteringRam01", "likely_structure": "SiegeWorkshop", "inferred_age": "Castle Age"},
    "Catapult": {"label": "Catapult", "likely_unlock": "UpgradeCatapult1", "likely_structure": "SiegeWorkshop", "inferred_age": "Castle Age"},
    "BombardCannon": {"label": "Bombard Cannon", "likely_unlock": "UnlockBombardCannons", "likely_structure": "AlchemistsLab", "inferred_age": "Imperial Age"},
    "TrebutchetMobile": {"label": "Trebuchet (Move Mode)", "likely_unlock": "Castle", "likely_structure": "Castle", "inferred_age": "Castle Age"},
    "TrebutchetSieged": {"label": "Trebuchet (Siege Mode)", "likely_unlock": "Castle", "likely_structure": "Castle", "inferred_age": "Castle Age"},
    "ExplosiveWagon": {"label": "Explosives Wagon", "likely_unlock": "unknown", "likely_structure": "SiegeWorkshop", "inferred_age": "Castle Age"},
    "ExplosivesWagon": {"label": "Explosives Wagon", "likely_unlock": "unknown", "likely_structure": "SiegeWorkshop", "inferred_age": "Castle Age"},
}

# Upgrade families observed in the replay corpus. We retain exact event names,
# then classify them by family for evaluation. Cosmetic/UI/meta events are excluded.
GAMEPLAY_UPGRADE_PREFIXES = (
    "Age", "ImprovedGathering", "TaxCollection", "MeleeDamageIncrease", "MeleeArmorIncrease",
    "RangerDamageIncrease", "RangerArmorIncrease", "Fortifications", "UpgradeUnitsSpeed",
    "UpgradeSwordsman", "UpgradeMilitia", "UpgradeSpearman", "UpgradeArchers",
    "UpgradeArchersto", "UpgradeCrossbowman", "UpgradeSkirmishers", "UnlockHandCannoneer",
    "UpgradeHandCannoneer", "UpgradeKnightstoCavaliers", "UpgradeHorseman", "UpgradeHorseArcher",
    "UpgradeMountedScout", "UpgradeMountedArcher", "UnlockBombardCannons", "UpgradeBatteringRam",
    "UpgradeCatapult", "UpgradeBallistas", "UpgradeBombardCannons",
)
IGNORED_UPGRADE_PREFIXES = (
    "RewardDance", "Spray", "DoubleQueueIconsChange", "GatherLabelVisible", "HotkeysUsable",
)


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


def _time_label(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _tag(event: dict[str, Any]) -> tuple[int, int] | None:
    index = event.get("m_unitTagIndex")
    recycle = event.get("m_unitTagRecycle")
    if index is None or recycle is None:
        return None
    return int(index), int(recycle)


def _killer_tag(event: dict[str, Any]) -> tuple[int, int] | None:
    index = event.get("m_killerUnitTagIndex")
    recycle = event.get("m_killerUnitTagRecycle")
    if index is None or recycle is None:
        return None
    return int(index), int(recycle)


def _is_animal_pid(pid: Any) -> bool:
    try:
        return int(pid) == ANIMAL_PLAYER_ID
    except Exception:
        return False


def _pid_to_player(players: list[PlayerStats], pid: Any) -> PlayerStats | None:
    if pid is None or _is_animal_pid(pid):
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


def _record_first(mapping: dict[str, int], key: str, seconds: int | None) -> None:
    if seconds is None:
        return
    if key not in mapping or seconds < mapping[key]:
        mapping[key] = int(seconds)


def _current_age(player: PlayerStats) -> str:
    return player.current_age()


def _is_gameplay_upgrade(upgrade_name: str) -> bool:
    if any(upgrade_name.startswith(prefix) for prefix in IGNORED_UPGRADE_PREFIXES):
        return False
    return any(upgrade_name.startswith(prefix) for prefix in GAMEPLAY_UPGRADE_PREFIXES)


def _upgrade_category(upgrade_name: str) -> str:
    if upgrade_name in AGE_UPGRADES:
        return "age progression"
    if upgrade_name in KEY_UNLOCK_RULES:
        return KEY_UNLOCK_RULES[upgrade_name]["category"]
    if upgrade_name.startswith(("ImprovedGathering", "TaxCollection")):
        return "economy"
    if upgrade_name.startswith(("UpgradeBatteringRam", "UpgradeCatapult", "UpgradeBallistas", "UpgradeBombardCannons")):
        return "mechanical"
    if upgrade_name.startswith(("UpgradeArchers", "UpgradeArchersto", "UpgradeCrossbowman", "UpgradeSkirmishers", "UpgradeHandCannoneer")):
        return "ranged"
    if upgrade_name.startswith(("UpgradeHorse", "UpgradeKnight", "UpgradeMounted")):
        return "cavalry"
    if upgrade_name.startswith(("UpgradeSwordsman", "UpgradeMilitia", "UpgradeSpearman")):
        return "infantry"
    if upgrade_name.startswith(("MeleeDamage", "MeleeArmor", "RangerDamage", "RangerArmor", "Fortifications", "UpgradeUnitsSpeed")):
        return "general combat"
    return "other gameplay tech"


def _calculate_tech_score(player: PlayerStats) -> int:
    # Transparent heuristic used only for relative report reads. It is not a
    # claim about exact AoK resource costs or official balance weights.
    age_points = player.age_stage() * 4
    structure_points = len(player.tech_structure_first_seconds) * 2
    unlock_points = len(player.tech_unlock_first_seconds) * 3
    upgrade_points = min(16, len(player.tech_upgrade_first_seconds))
    fielded_points = len(player.advanced_unit_first_seconds)
    player.tech_score = age_points + structure_points + unlock_points + upgrade_points + fielded_points
    return player.tech_score


def _calculate_team_tech_score(team: TeamStats) -> int:
    """Score the side's unique technology frontier, not duplicate player tech.

    Summing every player's score unfairly inflates larger teams (for example a
    4-player side against a 3-player side). The team score therefore uses the
    furthest age plus the side-wide unique structures, unlocks, upgrades, and
    advanced unit types that at least one teammate reached.
    """
    age_points = team.age_stage() * 4
    structure_points = len(team.tech_structure_first_seconds) * 2
    unlock_points = len(team.tech_unlock_first_seconds) * 3
    upgrade_points = min(16, len(team.tech_upgrade_first_seconds))
    fielded_points = len(team.advanced_unit_first_seconds)
    team.tech_score = age_points + structure_points + unlock_points + upgrade_points + fielded_points
    return team.tech_score


def _side_frontier_tech_score(players: list[PlayerStats]) -> int:
    """Return the same unique-frontier score while tracker events are streaming."""
    if not players:
        return 0
    age_stage = max((player.age_stage() for player in players), default=0)
    structures = {name for player in players for name in player.tech_structure_first_seconds}
    unlocks = {name for player in players for name in player.tech_unlock_first_seconds}
    upgrades = {name for player in players for name in player.tech_upgrade_first_seconds}
    advanced = {name for player in players for name in player.advanced_unit_first_seconds}
    return age_stage * 4 + len(structures) * 2 + len(unlocks) * 3 + min(16, len(upgrades)) + len(advanced)


def _record_tech_structure(player: PlayerStats, unit_type: str, seconds: int | None) -> None:
    if unit_type not in TECH_STRUCTURE_RULES:
        return
    _record_first(player.tech_structure_first_seconds, unit_type, seconds)
    observed_age = _current_age(player)
    if observed_age == "Starting age":
        observed_age = TECH_STRUCTURE_RULES[unit_type].get("inferred_age", observed_age)
    player.tech_structure_age_labels.setdefault(unit_type, observed_age)
    _calculate_tech_score(player)


def _record_upgrade(player: PlayerStats, upgrade_name: str, seconds: int | None) -> None:
    if upgrade_name in AGE_UPGRADES:
        _record_first(player.age_timing_seconds, AGE_UPGRADES[upgrade_name], seconds)
        _calculate_tech_score(player)
        return

    if not _is_gameplay_upgrade(upgrade_name):
        return

    _record_first(player.tech_upgrade_first_seconds, upgrade_name, seconds)
    player.tech_upgrade_age_labels.setdefault(upgrade_name, _current_age(player))
    if upgrade_name in KEY_UNLOCK_RULES:
        _record_first(player.tech_unlock_first_seconds, upgrade_name, seconds)
    _calculate_tech_score(player)


def _record_advanced_unit(player: PlayerStats, unit_type: str, seconds: int | None) -> None:
    if unit_type not in ADVANCED_UNIT_RULES:
        return
    _record_first(player.advanced_unit_first_seconds, unit_type, seconds)
    player.advanced_unit_age_labels.setdefault(unit_type, _current_age(player))
    _calculate_tech_score(player)


def _flatten_numeric_fields(value: Any, out: dict[str, int] | None = None) -> dict[str, int]:
    """Flatten decoded tracker stats into a simple numeric field dictionary."""
    if out is None:
        out = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, bool):
                out[str(key)] = int(child)
            elif isinstance(child, (int, float)):
                out[str(key)] = int(child)
            elif isinstance(child, (dict, list, tuple)):
                _flatten_numeric_fields(child, out)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _flatten_numeric_fields(child, out)
    return out


def _resource_sample_from_stats(stats: Any) -> tuple[dict[str, dict[str, int]], set[str], set[str]]:
    """Decode AoK resource channels from SPlayerStatsEvent.

    AoK labels the SC2 channels as Gold=Minerals, Wood=Vespene, Iron=Terrazine.
    The gathered figure is an estimate from current + used + lost score values;
    it is intentionally labelled as an estimate in reports.
    """
    flat = _flatten_numeric_fields(stats)
    samples: dict[str, dict[str, int]] = {}
    seen_channels: set[str] = set()
    seen_fields: set[str] = set()

    for resource, protocol_label in RESOURCE_PROTOCOL_LABELS.items():
        matching = {key: val for key, val in flat.items() if protocol_label.lower() in key.lower()}
        if not matching:
            continue
        seen_channels.add(resource)
        seen_fields.update(matching)

        current_key = f"m_scoreValue{protocol_label}Current"
        rate_key = f"m_scoreValue{protocol_label}CollectionRate"
        current = max(0, int(flat.get(current_key, 0) or 0))
        rate = max(0, int(flat.get(rate_key, 0) or 0))

        used = sum(
            max(0, int(value or 0))
            for key, value in matching.items()
            # UsedActiveForces already overlaps UsedCurrentArmy + UsedInProgressArmy.
            if f"{protocol_label}UsedCurrent" in key or f"{protocol_label}UsedInProgress" in key
        )
        lost = sum(
            abs(int(value or 0))
            for key, value in matching.items()
            if f"{protocol_label}Lost" in key
        )
        gathered_estimate = current + used + lost

        samples[resource] = {
            "current": current,
            "rate": rate,
            "gathered_estimate": max(0, gathered_estimate),
            "lost_value": max(0, lost),
        }

    return samples, seen_channels, seen_fields


RATE_WINDOW_SECONDS = 60
STARTING_STOCK_WINDOW_SECONDS = 240
STARTING_STOCK_MIN_JUMP = 600


def _remove_starting_stock(
    state: dict[str, dict[str, Any]],
    sample: dict[str, dict[str, int]],
    seconds: int | None,
) -> None:
    """Subtract map-granted starting stock from the gathered estimate.

    The first sample's stockpile is starting resources. AoK then spawns each
    player's starting units/buildings in one tick inside the first minutes
    (1,000-2,300 per resource on default settings, far more with lobby
    resource options); their value lands in UsedCurrent* without any
    gathering. Real early income stays well below STARTING_STOCK_MIN_JUMP
    per 10 s sample, so the first early jump that size is treated as the grant.
    """
    for resource, values in sample.items():
        raw = int(values.get("gathered_estimate", 0) or 0)
        st = state.setdefault(resource, {"prev": None, "offset": 0, "grant_seen": False})
        prev, st["prev"] = st["prev"], raw
        if prev is None:
            st["offset"] = raw
        elif (not st["grant_seen"] and seconds is not None
              and seconds <= STARTING_STOCK_WINDOW_SECONDS and raw - prev >= STARTING_STOCK_MIN_JUMP):
            st["offset"] += raw - prev
            st["grant_seen"] = True
        values["gathered_estimate"] = max(0, raw - st["offset"])


def _derive_gather_rates(
    history: dict[str, deque[tuple[int, int]]],
    sample: dict[str, dict[str, int]],
    seconds: int | None,
) -> None:
    """Fill per-minute rates from gathered-estimate deltas over the trailing window.

    AoK grants resources through triggers, so SC2's CollectionRate tracker
    field stays 0. A non-zero tracker rate is kept as-is.
    """
    if seconds is None:
        return
    for resource, values in sample.items():
        points = history.setdefault(resource, deque())
        gathered = int(values.get("gathered_estimate", 0) or 0)
        points.append((seconds, gathered))
        while len(points) > 1 and points[1][0] <= seconds - RATE_WINDOW_SECONDS:
            points.popleft()
        if int(values.get("rate", 0) or 0) > 0:
            continue
        start_seconds, start_gathered = points[0]
        elapsed = seconds - start_seconds
        values["rate"] = max(0, round((gathered - start_gathered) * 60 / elapsed)) if elapsed > 0 else 0


def _apply_resource_sample(
    player: PlayerStats, sample: dict[str, dict[str, int]], seconds: int | None = None,
) -> None:
    if not sample:
        return
    if seconds is not None and any(
        int(values.get("gathered_estimate", 0) or 0) > player.resource_gathered_estimate.get(resource, 0)
        for resource, values in sample.items()
    ):
        player.resource_last_gain_seconds = seconds
    player.resource_samples += 1
    for resource, values in sample.items():
        current = int(values.get("current", player.resource_current.get(resource, 0)) or 0)
        rate = int(values.get("rate", player.resource_collection_rate.get(resource, 0)) or 0)
        gathered = int(values.get("gathered_estimate", 0) or 0)
        lost = int(values.get("lost_value", 0) or 0)

        player.resource_current[resource] = current
        player.resource_collection_rate[resource] = rate
        player.resource_peak_current[resource] = max(player.resource_peak_current.get(resource, 0), current)
        player.resource_peak_collection_rate[resource] = max(player.resource_peak_collection_rate.get(resource, 0), rate)
        player.resource_gathered_estimate[resource] = max(player.resource_gathered_estimate.get(resource, 0), gathered)
        player.resource_lost_value[resource] = max(player.resource_lost_value.get(resource, 0), lost)


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
    if completed_structure and _has_any(unit_type, ECON_HINTS):
        player.economic_structures += amount


def _classify_player_role(player: PlayerStats) -> str:
    return classify_role(player)


def _team_style(team: TeamStats) -> str:
    return classify_team(team)


def _normalize_match_mode(summary: ReplaySummary) -> None:
    if not summary.players:
        return
    summary.match_mode, groups = normalize_match_groups(summary.players)
    for player, group in zip(summary.players, groups):
        player.team_id = group


def _team_brief(team: TeamStats) -> str:
    return team.label or f"Team {team.team_id}"


def _team_roster(team: TeamStats) -> str:
    return ", ".join(team.players) if team.players else "unknown players"


def _team_display(team: TeamStats, *, include_players: bool = True, match_mode: str | None = None) -> str:
    base = _team_brief(team)
    if not include_players:
        return base
    if match_mode in {"Free-for-all", "Duel"}:
        return base
    if team.players:
        return f"{base} ({_team_roster(team)})"
    return base


def _player_with_side(summary: ReplaySummary, player: PlayerStats | None) -> str:
    if player is None:
        return "Unknown player"
    if summary.match_mode == "Free-for-all":
        return f"{player.name} (FFA side)"
    if summary.match_mode == "Duel":
        return f"{player.name} (duel side)"

    team = next((t for t in summary.teams if t.team_id == player.team_id), None)
    if team is not None:
        return f"{player.name} ({_team_brief(team)})"
    if player.team_id is not None:
        return f"{player.name} (Team {player.team_id})"
    return player.name



def _result_rank(result: str | None) -> int:
    """Small helper for result precedence.

    Official `Win` remains authoritative. Leave-based logic is used mainly to
    turn replay-metadata `Undecided`/missing outcomes into useful losses/wins.
    """
    if result == "Win":
        return 3
    if result == "Tie":
        return 2
    if result == "Loss":
        return 1
    return 0


def _set_result_if_weaker(player: PlayerStats, result: str) -> None:
    if _result_rank(result) > _result_rank(player.result):
        player.result = result


END_EXIT_SECONDS = 15


def _apply_leave_based_results(summary: ReplaySummary) -> None:
    """Infer losses/wins from leave events.

    AoK displays often leave `m_result` as Undecided even though the practical
    result is obvious: in team games, a side is eliminated when every player on
    that side has left; in FFA/no-alliance games, a player who leaves has lost.

    This function does not demote an official replay `Win`. It only upgrades
    weak/undecided metadata into `Loss` or `Win` when leave events make the
    outcome clearer.
    """
    if not summary.players:
        return

    grouped: dict[int, list[PlayerStats]] = defaultdict(list)
    for player in summary.players:
        if player.team_id is not None:
            grouped[int(player.team_id)].append(player)

    if not grouped:
        return

    official_winners = [p for p in summary.players if p.result == "Win"]

    if summary.match_mode == "Free-for-all":
        for player in summary.players:
            if player.leave_time_seconds is not None and player.result != "Win":
                player.result = "Loss"

        if not official_winners:
            survivors = [p for p in summary.players if p.result != "Loss"]
            if len(survivors) == 1:
                survivors[0].result = "Win"
                summary.key_findings.append(
                    f"Leave-based result inference: {survivors[0].name} is the only FFA side that did not leave, so they are treated as the winner."
                )
            elif len(survivors) == 0:
                summary.key_findings.append(
                    "Leave-based result inference: every FFA side has a leave event, so the report keeps the official winner as unknown instead of inventing a winner."
                )
        return

    # SC2 marks every player still in the game at the end as Win, so an AoK
    # game ended with both sides present can record Win on opposing teams.
    # That metadata names no winner. Only a side that had fully left before
    # the closing exits (everyone quits in the last seconds) counts as beaten.
    win_sides = [tid for tid, ps in grouped.items() if any(p.result == "Win" for p in ps)]
    if len(win_sides) > 1:
        end = summary.duration_seconds
        cutoff = end - END_EXIT_SECONDS if end else None
        beaten = [
            tid for tid, ps in grouped.items()
            if all(p.leave_time_seconds is not None and (cutoff is None or p.leave_time_seconds < cutoff) for p in ps)
        ]
        for player in summary.players:
            player.result = "Undecided"
        if len(beaten) == len(grouped) - 1:
            for tid, ps in grouped.items():
                for player in ps:
                    player.result = "Loss" if tid in beaten else "Win"
            winner = next(tid for tid in grouped if tid not in beaten)
            summary.key_findings.append(
                "Replay metadata marks players on more than one side as Win; "
                f"Team {winner} is the only side not fully gone before the end, so it is treated as the winner."
            )
        else:
            summary.key_findings.append(
                "Replay metadata marks players on more than one side as Win (players still present at the end), "
                "so no winner is claimed."
            )
        return

    # Team/duel mode: a side loses once every player on that side has left.
    side_all_left: dict[int, bool] = {
        team_id: bool(players) and all(p.leave_time_seconds is not None for p in players)
        for team_id, players in grouped.items()
    }

    for team_id, all_left in side_all_left.items():
        if not all_left:
            continue
        team_players = grouped[team_id]
        if any(p.result == "Win" for p in team_players):
            continue
        for player in team_players:
            player.result = "Loss"
        summary.key_findings.append(
            f"Leave-based result inference: Team {team_id} ({', '.join(p.name for p in team_players)}) all left, so that side is treated as a loss."
        )

    if not official_winners:
        non_losing_team_ids = [
            team_id
            for team_id, players in grouped.items()
            if not all(p.result == "Loss" for p in players)
        ]
        if len(non_losing_team_ids) == 1:
            winning_team_id = non_losing_team_ids[0]
            for player in grouped[winning_team_id]:
                _set_result_if_weaker(player, "Win")
            summary.key_findings.append(
                f"Leave-based result inference: Team {winning_team_id} is the only side not fully eliminated by leave events, so it is treated as the winning side."
            )

def _merge_earliest(target: dict[str, int], source: dict[str, int]) -> None:
    for key, seconds in source.items():
        if key not in target or seconds < target[key]:
            target[key] = int(seconds)


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
        team.animal_kills += p.animal_kills
        team.deaths_to_animals += p.deaths_to_animals
        team.units_born += p.units_born
        team.commands += p.commands
        team.static_defense += p.static_defense
        team.walls_gates += p.walls_gates
        team.castles += p.castles
        team.cavalry_units += p.cavalry_units
        team.ranged_units += p.ranged_units
        team.infantry_units += p.infantry_units
        team.siege_units += p.siege_units
        team.mechanical_units += p.mechanical_units
        team.mechanical_kills += p.mechanical_kills
        team.mechanical_losses += p.mechanical_losses
        team.trebuchets_total += p.trebuchets_total
        team.trebuchets_sieged += p.trebuchets_sieged
        team.trebuchet_mobile_deaths += p.trebuchet_mobile_deaths
        team.trebuchet_sieged_deaths += p.trebuchet_sieged_deaths
        team.trebuchet_sieged_kills += p.trebuchet_sieged_kills
        team.structures_done += p.structures_done
        team.upgrades += p.upgrades
        _merge_earliest(team.age_timing_seconds, p.age_timing_seconds)
        _merge_earliest(team.tech_structure_first_seconds, p.tech_structure_first_seconds)
        _merge_earliest(team.tech_upgrade_first_seconds, p.tech_upgrade_first_seconds)
        _merge_earliest(team.tech_unlock_first_seconds, p.tech_unlock_first_seconds)
        _merge_earliest(team.advanced_unit_first_seconds, p.advanced_unit_first_seconds)
        for resource in ("gold", "wood", "iron"):
            team.resource_current[resource] += int(p.resource_current.get(resource, 0) or 0)
            team.resource_collection_rate[resource] += int(p.resource_collection_rate.get(resource, 0) or 0)
            team.resource_peak_current[resource] += int(p.resource_peak_current.get(resource, 0) or 0)
            team.resource_peak_collection_rate[resource] += int(p.resource_peak_collection_rate.get(resource, 0) or 0)
            team.resource_gathered_estimate[resource] += int(p.resource_gathered_estimate.get(resource, 0) or 0)
            # A leaver's slot can keep collecting (shared control), so average
            # over whichever is later: leaving or the last resource gain.
            active_seconds = max(p.leave_time_seconds or 0, p.resource_last_gain_seconds or 0)
            active_seconds = active_seconds or summary.duration_seconds or 0
            if active_seconds > 0:
                p.resource_average_rate[resource] = round(
                    int(p.resource_gathered_estimate.get(resource, 0) or 0) * 60 / active_seconds)
            team.resource_average_rate[resource] += p.resource_average_rate[resource]
            team.resource_lost_value[resource] += int(p.resource_lost_value.get(resource, 0) or 0)

    for team in teams.values():
        _calculate_team_tech_score(team)
        team.style_label = _team_style(team)
        if summary.match_mode in {"Free-for-all", "Duel"}:
            team.style_label = (team.style_label or "Mixed-composition team").replace(" team", " profile")
        if summary.match_mode in {"Free-for-all", "Duel"} and len(team.players) == 1:
            team.label = team.players[0]
        elif summary.match_mode == "Free-for-all":
            team.label = f"FFA group {team.team_id}"
        else:
            team.label = f"Team {team.team_id}"
    summary.teams = sorted(teams.values(), key=lambda t: t.team_id)


def _resource_total(values: dict[str, int]) -> int:
    return sum(int(values.get(key, 0) or 0) for key in ("gold", "wood", "iron"))


def _resource_triplet(values: dict[str, int], seen_channels: list[str] | set[str] | None = None) -> str:
    seen = set(seen_channels or ("gold", "wood", "iron"))
    def value(resource: str) -> str:
        if resource not in seen:
            return "n/a"
        return f"{int(values.get(resource, 0) or 0):,}"
    return f"Gold {value('gold')}, Wood {value('wood')}, Iron {value('iron')}"


def _first_timing_labels(mapping: dict[str, int], labels: dict[str, dict[str, str]], limit: int = 4) -> str:
    rows = sorted(mapping.items(), key=lambda kv: (kv[1], kv[0]))[:limit]
    if not rows:
        return "none recorded"
    return ", ".join(f"{labels.get(name, {}).get('label', name)} at {_time_label(seconds)}" for name, seconds in rows)


def _build_tech_evaluations(summary: ReplaySummary) -> list[str]:
    lines: list[str] = []
    resources_available = bool(summary.resource_channels_seen)
    for team in summary.teams:
        structures = _first_timing_labels(team.tech_structure_first_seconds, TECH_STRUCTURE_RULES)
        unlocks = _first_timing_labels(team.tech_unlock_first_seconds, KEY_UNLOCK_RULES)
        advanced_rows = sorted(team.advanced_unit_first_seconds.items(), key=lambda kv: (kv[1], kv[0]))[:4]
        advanced = ", ".join(
            f"{ADVANCED_UNIT_RULES.get(name, {}).get('label', name)} at {_time_label(seconds)}"
            for name, seconds in advanced_rows
        ) or "none recorded"
        resource_read = (
            f" Latest stockpile: {_resource_triplet(team.resource_current, summary.resource_channels_seen)}; "
            f"gather rate per minute: average {_resource_triplet(team.resource_average_rate, summary.resource_channels_seen)}, "
            f"peak {_resource_triplet(team.resource_peak_collection_rate, summary.resource_channels_seen)}; "
            f"gathered estimate: {_resource_triplet(team.resource_gathered_estimate, summary.resource_channels_seen)}."
            if resources_available else
            " Resource tracker fields were not available in this replay."
        )
        lines.append(
            f"{_team_display(team, match_mode=summary.match_mode)} — {team.current_age()}, tech score {team.tech_score}. "
            f"Key tech structures: {structures}. Key unlocks: {unlocks}. Advanced units first fielded: {advanced}. "
            f"Mechanical K/L {team.mechanical_kills}/{team.mechanical_losses}; trebuchets {team.trebuchets_total} total, "
            f"{team.trebuchets_sieged} reached siege mode, {team.trebuchet_mobile_deaths} died in move mode."
            + resource_read
        )
    return lines


def _team_strength_bits(team: TeamStats, others: list[TeamStats]) -> list[str]:
    bits: list[str] = []
    if not others:
        return bits
    other_max_units = max(o.units_born for o in others)
    other_max_commands = max(o.commands for o in others)
    other_best_ratio = max((o.kill_loss_ratio() or 0) for o in others)
    ratio = team.kill_loss_ratio() or 0
    if ratio > other_best_ratio + 0.10:
        bits.append("better trade conversion")
    if team.units_born >= other_max_units * 1.10:
        bits.append("larger production footprint")
    if team.commands >= other_max_commands * 1.10:
        bits.append("higher visible activity")
    if team.static_defense >= max(o.static_defense for o in others) * 1.25 and team.static_defense >= 30:
        bits.append("stronger defensive layer")
    if team.animal_kills >= max(o.animal_kills for o in others) * 1.25 and team.animal_kills >= 15:
        bits.append("more map/animal clearing")
    if team.tech_score >= max(o.tech_score for o in others) * 1.15 and team.tech_score >= 8:
        bits.append("deeper technology progression")
    other_economy = max((_resource_total(o.resource_gathered_estimate) for o in others), default=0)
    if other_economy > 0 and _resource_total(team.resource_gathered_estimate) >= other_economy * 1.10:
        bits.append("stronger tracked economy throughput")
    if team.mechanical_kills >= max(o.mechanical_kills for o in others) * 1.20 and team.mechanical_kills >= 10:
        bits.append("more converted mechanical firepower")
    return bits


def _team_risk_bits(team: TeamStats, others: list[TeamStats]) -> list[str]:
    bits: list[str] = []
    if not others:
        return bits
    if team.losses > max(o.losses for o in others) * 1.10:
        bits.append("higher attrition")
    if (team.kill_loss_ratio() or 0) + 0.10 < max((o.kill_loss_ratio() or 0) for o in others):
        bits.append("weaker fight conversion")
    if team.commands < max(o.commands for o in others) * 0.75:
        bits.append("lower visible command activity")
    if team.deaths_to_animals >= 10:
        bits.append("lost noticeable units to animals")
    if team.trebuchet_mobile_deaths >= 2:
        bits.append("lost trebuchets before they could fight in siege mode")
    if team.mechanical_losses > team.mechanical_kills * 1.25 and team.mechanical_losses >= 10:
        bits.append("poor mechanical trade conversion")
    other_tech = max((o.tech_score for o in others), default=0)
    if other_tech > 0 and team.tech_score + 3 < other_tech:
        bits.append("shallower technology progression")
    return bits


def _timeline_team_value(snapshot: dict[str, Any], team_id: int, key: str) -> int:
    teams = snapshot.get("teams", {})
    team = teams.get(str(team_id)) or teams.get(team_id) or {}
    return int(team.get(key, 0) or 0)


def _build_turning_points(summary: ReplaySummary) -> list[str]:
    if len(summary.teams) < 2 or len(summary.timeline_snapshots) < 2:
        return []
    winner = next((t for t in summary.teams if t.result == "Win"), None)
    subject = "recorded winner"
    if winner is None:
        winner = max(summary.teams, key=lambda t: (t.kill_loss_ratio() or 0, t.kills - t.losses))
        subject = "inferred statistical leader, not a recorded winner"
    opponents = [t for t in summary.teams if t.team_id != winner.team_id]
    if not opponents:
        return []
    opp = max(opponents, key=lambda t: t.kills + t.units_born)

    best: tuple[int, int, int] | None = None  # gain, start_sec, end_sec
    prev = summary.timeline_snapshots[0]
    prev_diff = (
        _timeline_team_value(prev, winner.team_id, "kills") - _timeline_team_value(prev, winner.team_id, "losses")
        - _timeline_team_value(prev, opp.team_id, "kills") + _timeline_team_value(prev, opp.team_id, "losses")
    )
    for snap in summary.timeline_snapshots[1:]:
        diff = (
            _timeline_team_value(snap, winner.team_id, "kills") - _timeline_team_value(snap, winner.team_id, "losses")
            - _timeline_team_value(snap, opp.team_id, "kills") + _timeline_team_value(snap, opp.team_id, "losses")
        )
        gain = diff - prev_diff
        if best is None or gain > best[0]:
            best = (gain, int(prev.get("seconds", 0) or 0), int(snap.get("seconds", 0) or 0))
        prev = snap
        prev_diff = diff

    if best and best[0] > 20:
        return [
            f"Largest detected fight swing is around {_time_label(best[1])}–{_time_label(best[2])}, "
            f"where {_team_display(winner, match_mode=summary.match_mode)} ({subject}) improved its relative kill/loss position by about {best[0]} units."
        ]
    return ["No timeline window shows a relative kill/loss swing above 20 units."]


def _build_match_story(summary: ReplaySummary) -> None:
    players = summary.players
    if not players:
        return

    top_killer = max(players, key=lambda p: p.kills, default=None)
    top_producer = max(players, key=lambda p: p.units_born, default=None)
    top_defender = max(players, key=lambda p: p.static_defense, default=None)
    top_animal_killer = max(players, key=lambda p: p.animal_kills, default=None)
    top_tech = max(players, key=lambda p: (p.tech_score, p.age_stage(), len(p.tech_unlock_first_seconds)), default=None)
    top_economy = max(players, key=lambda p: _resource_total(p.resource_gathered_estimate), default=None)
    top_mechanical = max(players, key=lambda p: (p.mechanical_kills - p.mechanical_losses, p.mechanical_kills), default=None)
    efficient = [p for p in players if p.losses > 0 and p.kills >= 50]
    top_eff = max(efficient, key=lambda p: p.kills / max(1, p.losses), default=None)

    # Preserve parser-level findings such as leave-based result inference.
    findings: list[str] = list(summary.key_findings)
    story: list[str] = []
    team_evals: list[str] = []
    tech_evals: list[str] = []
    animal_impact: list[str] = []
    takeaways: list[str] = []

    if summary.teams:
        winner = next((t for t in summary.teams if t.result == "Win"), None)
        if winner is not None:
            opponents = [t for t in summary.teams if t.team_id != winner.team_id]
            if summary.match_mode == "Free-for-all":
                summary.verdict = (
                    f"Free-for-all detected: {_team_display(winner, match_mode=summary.match_mode)} is the winning player. "
                    "Every non-animal player is treated as their own hostile side, so the analysis no longer merges the lobby into one team."
                )
            elif summary.match_mode == "Duel":
                summary.verdict = (
                    f"Duel/no-alliance match detected: {_team_display(winner, match_mode=summary.match_mode)} is the winning player. "
                    "The report compares individual sides instead of team aggregates."
                )
            elif opponents:
                # Recorded outcome plus measured sizes only; replay counters do not establish why a side won.
                biggest_opp = max(opponents, key=lambda t: len(t.players))
                summary.verdict = (
                    f"Recorded winner: {_team_display(winner, match_mode=summary.match_mode)} ({len(winner.players)} player(s) versus "
                    f"{len(biggest_opp.players)} on the largest opposing side; heuristic style label: "
                    f"{winner.style_label or 'mixed'}). The replay records the outcome, not its causes."
                )
            else:
                summary.verdict = f"{_team_display(winner, match_mode=summary.match_mode)} is detected as the winning side."
        else:
            if summary.match_mode == "Free-for-all":
                leader = max(
                    summary.teams,
                    key=lambda t: (
                        t.kills - t.losses,
                        t.kill_loss_ratio() or 0,
                        t.tech_score,
                        _resource_total(t.resource_gathered_estimate),
                        t.units_born,
                        t.commands,
                    ),
                    default=None,
                )
                if leader is not None:
                    summary.verdict = (
                        f"Free-for-all detected, but no clean official winner was found in replay metadata. "
                        f"The likely leader by PvP margin/conversion is {_team_display(leader, match_mode=summary.match_mode)}."
                    )
                else:
                    summary.verdict = "Free-for-all detected, but no clean winner was found in replay metadata; analysis is based on combat, survival, activity, and leave patterns."
            else:
                summary.verdict = "No clean winner was detected in replay metadata; analysis is based on combat, activity, and leave patterns."

        for t in summary.teams:
            others = [o for o in summary.teams if o.team_id != t.team_id]
            ratio = t.kill_loss_ratio()
            ratio_label = f"{ratio:.2f}" if ratio is not None else "N/A"
            strengths = _team_strength_bits(t, others)
            risks = _team_risk_bits(t, others)
            if t.result == "Win":
                result_word = "won"
            elif t.result == "Loss":
                result_word = "lost"
            else:
                result_word = "did not get a clear win result"
            eval_line = (
                f"{_team_display(t, match_mode=summary.match_mode)} {result_word}. It reads as a {t.style_label or 'mixed-composition profile'} "
                f"with {len(t.players)} player(s). Main strengths: {', '.join(strengths) if strengths else 'no single dominant advantage detected'}. "
                f"Main risks/problems: {', '.join(risks) if risks else 'no major weakness flagged by the heuristic read'}. "
                f"Evidence snapshot: PvP K/L {t.kills}/{t.losses} ({ratio_label}), units {t.units_born}, commands {t.commands}, "
                f"age {t.current_age()}, tech score {t.tech_score}, mechanical K/L {t.mechanical_kills}/{t.mechanical_losses}."
            )
            team_evals.append(eval_line)
            story.append(
                f"{_team_display(t, match_mode=summary.match_mode)}: {t.style_label}, PvP K/L {t.kills}/{t.losses} ({ratio_label}), "
                f"animal K/D {t.animal_kills}/{t.deaths_to_animals}, {t.current_age()}, tech score {t.tech_score}."
            )

        tech_evals = _build_tech_evaluations(summary)

    if summary.match_mode == "Free-for-all" and summary.teams:
        ranked = sorted(
            summary.teams,
            key=lambda t: (
                t.kills - t.losses,
                t.kill_loss_ratio() or 0,
                t.tech_score,
                _resource_total(t.resource_gathered_estimate),
                t.units_born,
                t.commands,
            ),
            reverse=True,
        )
        leader = ranked[0]
        findings.append(
            f"FFA leader by PvP margin/conversion: {_team_display(leader, match_mode=summary.match_mode)} at {leader.kills}/{leader.losses} "
            f"(margin {leader.kills - leader.losses}, K/L {leader.kill_loss_ratio() or 'N/A'})."
        )
        if len(ranked) > 1:
            runner = ranked[1]
            findings.append(
                f"Closest rival by the same heuristic: {_team_display(runner, match_mode=summary.match_mode)} at {runner.kills}/{runner.losses} "
                f"(margin {runner.kills - runner.losses})."
            )

    if top_killer:
        findings.append(f"Main PvP kill leader: {_player_with_side(summary, top_killer)} with {top_killer.kills} player-vs-player credited kills.")
    if top_eff:
        findings.append(f"Most efficient major fighter: {_player_with_side(summary, top_eff)} at PvP K/L {top_eff.kills}/{top_eff.losses}.")
    if top_producer:
        findings.append(f"Largest production footprint: {_player_with_side(summary, top_producer)} with {top_producer.units_born} units born.")
    if top_defender and top_defender.static_defense > 0:
        findings.append(f"Strongest defensive footprint: {_player_with_side(summary, top_defender)} with {top_defender.static_defense} static-defense/wall/castle-style completions or spawns.")
    if top_animal_killer and top_animal_killer.animal_kills > 0:
        findings.append(f"Most animal clearing: {_player_with_side(summary, top_animal_killer)} killed {top_animal_killer.animal_kills} Player 15 animal units.")
    if top_tech and top_tech.tech_score > 0:
        findings.append(
            f"Deepest inferred tech profile: {_player_with_side(summary, top_tech)} reached {top_tech.current_age()} "
            f"with tech score {top_tech.tech_score} and {len(top_tech.tech_unlock_first_seconds)} key unlock(s)."
        )
    if top_economy and summary.resource_channels_seen and _resource_total(top_economy.resource_gathered_estimate) > 0:
        findings.append(
            f"Largest tracked economy throughput: {_player_with_side(summary, top_economy)} at "
            f"{_resource_triplet(top_economy.resource_gathered_estimate, summary.resource_channels_seen)} gathered estimate."
        )
    if top_mechanical and top_mechanical.mechanical_kills > 0:
        findings.append(
            f"Best mechanical conversion: {_player_with_side(summary, top_mechanical)} at "
            f"{top_mechanical.mechanical_kills}/{top_mechanical.mechanical_losses} mechanical K/L."
        )

    animal = summary.animal_stats
    if animal and (animal.kills or animal.losses or animal.units_born):
        top_victim = max(players, key=lambda p: p.deaths_to_animals, default=None)
        animal_impact.append(
            f"Player 15 is tracked as Animals/Neutral. Animals killed {animal.kills} player units and lost {animal.losses} animal units."
        )
        if top_animal_killer and top_animal_killer.animal_kills > 0:
            animal_impact.append(f"Top animal clearer: {_player_with_side(summary, top_animal_killer)} with {top_animal_killer.animal_kills} animal kills.")
        if top_victim and top_victim.deaths_to_animals > 0:
            animal_impact.append(f"Most punished by animals: {_player_with_side(summary, top_victim)} with {top_victim.deaths_to_animals} deaths to Player 15.")
        if animal.top_losses():
            animal_impact.append("Most killed animal types: " + ", ".join(f"{name}×{count}" for name, count in animal.top_losses(5)) + ".")
        if animal.top_kill_units():
            animal_impact.append("Animal units doing the killing: " + ", ".join(f"{name}×{count}" for name, count in animal.top_kill_units(5)) + ".")

    summary.turning_points = _build_turning_points(summary)

    if summary.match_mode == "Free-for-all":
        takeaways.append(
            "In FFA, do not evaluate the replay as Team 0 vs Team 1. Every player is a separate hostile side, so survival timing, third-partying, map control, and individual replacement tempo matter more than team K/D."
        )

    if summary.teams and len(summary.teams) >= 2:
        winner = next((t for t in summary.teams if t.result == "Win"), None)
        if winner is not None:
            opps = [t for t in summary.teams if t.team_id != winner.team_id]
            if summary.match_mode == "Free-for-all":
                pass
            elif opps:
                opp = max(opps, key=lambda t: len(t.players))
                if len(winner.players) < len(opp.players):
                    takeaways.append(
                        "Review question: the recorded winner had fewer players; which fights and replacement decisions offset the numbers gap?"
                    )
                elif (winner.kill_loss_ratio() or 0) > (opp.kill_loss_ratio() or 0):
                    takeaways.append(
                        "Review question: the recorded winner also had the better PvP K/L; which engagements produced that trade difference?"
                    )
    if animal and animal.kills >= 20:
        takeaways.append(
            f"Player 15 animals killed {animal.kills} player units; review whether pathing, scouting and animal clearing exposed units."
        )
    if summary.teams and len(summary.teams) >= 2:
        tech_ranked = sorted(summary.teams, key=lambda t: (t.tech_score, _resource_total(t.resource_gathered_estimate)), reverse=True)
        if tech_ranked[0].tech_score >= tech_ranked[1].tech_score + 4:
            takeaways.append(
                f"{_team_display(tech_ranked[0], match_mode=summary.match_mode)} held the clearer tech lead; compare whether that lead became fielded units and mechanical kills rather than judging the tech score alone."
            )
    if not takeaways:
        takeaways.append("Use this replay as a role-coverage review: check who provides frontline, firepower, production, defense, and map control before judging only K/D.")

    winners = summary.winner_label()
    if winners != "Unknown":
        story.insert(0, f"Winning side detected as {winners}.")

    summary.key_findings = findings
    summary.match_story = story
    summary.team_evaluations = team_evals
    summary.tech_evaluations = tech_evals
    summary.animal_impact = animal_impact
    summary.player_takeaways = takeaways


def parse_replay(path: Path) -> ReplaySummary:
    summary = ReplaySummary(source_path=path)
    summary.animal_stats = PlayerStats(name=ANIMAL_PLAYER_NAME, result="Neutral")
    replay_handle = None

    try:
        mpyq, versions = _load_s2protocol()
    except ReplayParserError as exc:
        summary.warnings.append(str(exc))
        summary.map_name = "Unknown - parser dependency missing"
        return summary

    try:
        replay_handle = path.open("rb")
        archive = mpyq.MPQArchive(replay_handle)
        header_content = archive.header["user_data_header"]["content"]
        header = versions.latest().decode_replay_header(header_content)
        base_build = header["m_version"]["m_baseBuild"]
        protocol, decoder_build = select_protocol(versions, base_build)
        summary.decoder_build = str(decoder_build)
        if decoder_build != base_build:
            summary.warnings.append(
                f"Compatibility decoder: replay base build {base_build} uses protocol {decoder_build}; "
                "mapping verified against the local replay corpus.")
        summary.game_version = str(base_build)

        details = protocol.decode_replay_details(archive.read_file("replay.details"))
        try:
            initdata = protocol.decode_replay_initdata(archive.read_file("replay.initData"))
        except Exception:
            initdata = None
        user_index = user_player_indices(details.get("m_playerList", []), initdata)

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
        _normalize_match_mode(summary)

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
                uid = user_index.get(event.get("_userid", {}).get("m_userId"))
                event_name = event.get("_event")
                if uid is not None:
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
            summary.game_events_complete = False
            summary.warnings.append(f"Could not decode game events: {exc}. Command counts are partial; APM is unavailable.")
        else:
            summary.game_events_complete = True

        summary.raw_event_counts["game_events"] = game_event_count
        if max_loop:
            summary.duration_seconds = _seconds_from_loops(max_loop)

        for uid, player in enumerate(players):
            player.commands = int(command_counts.get(uid, 0))
            player.control_groups = int(control_counts.get(uid, 0))
            player.camera_events = int(camera_counts.get(uid, 0))
            player.chat_messages = int(chat_counts.get(uid, 0))
            player.pings = int(ping_counts.get(uid, 0))
            if summary.duration_seconds and summary.duration_seconds > 0 and summary.game_events_complete:
                player.apm = int(round(player.commands / (summary.duration_seconds / 60)))

        # Tracker events: units, buildings, losses, PvP kills, technology,
        # Player 15/animal interactions, and resource snapshots.
        tracker_count = 0
        tag_owner: dict[tuple[int, int], int] = {}
        tag_type: dict[tuple[int, int], str] = {}
        pending_init: dict[tuple[int, int], tuple[int, str]] = {}
        max_tracker_loop = 0

        mechanical_tags_by_pid: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trebuchet_tags_by_pid: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trebuchet_sieged_tags_by_pid: dict[int, set[tuple[int, int]]] = defaultdict(set)
        resource_channels_seen: set[str] = set()
        resource_fields_seen: set[str] = set()
        player_stats_event_count = 0
        gather_history: dict[int, dict[str, deque[tuple[int, int]]]] = defaultdict(dict)
        starting_stock: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
        team_peak_rate: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        team_timeline_state: dict[int, dict[str, Any]] = defaultdict(
            lambda: {
                "kills": 0,
                "losses": 0,
                "units_born": 0,
                "animal_kills": 0,
                "deaths_to_animals": 0,
                "gold": 0,
                "wood": 0,
                "iron": 0,
                "gold_rate": 0,
                "wood_rate": 0,
                "iron_rate": 0,
                "age": "Starting age",
                "tech_score": 0,
                "mechanical_units": 0,
                "mechanical_kills": 0,
                "mechanical_losses": 0,
            }
        )
        next_snapshot = SNAPSHOT_SECONDS

        def refresh_side_state(player: PlayerStats | None) -> None:
            if player is None or player.team_id is None:
                return
            team_id = int(player.team_id)
            members = [p for p in players if p.team_id is not None and int(p.team_id) == team_id]
            state = team_timeline_state[team_id]
            for resource in ("gold", "wood", "iron"):
                state[resource] = sum(int(p.resource_current.get(resource, 0) or 0) for p in members)
                state[f"{resource}_rate"] = sum(int(p.resource_collection_rate.get(resource, 0) or 0) for p in members)
                team_peak_rate[team_id][resource] = max(team_peak_rate[team_id][resource], state[f"{resource}_rate"])
            age_player = max(members, key=lambda p: p.age_stage(), default=None)
            state["age"] = age_player.current_age() if age_player else "Starting age"
            state["tech_score"] = _side_frontier_tech_score(members)
            state["mechanical_units"] = sum(p.mechanical_units for p in members)
            state["mechanical_kills"] = sum(p.mechanical_kills for p in members)
            state["mechanical_losses"] = sum(p.mechanical_losses for p in members)

        for initial_player in players:
            refresh_side_state(initial_player)

        def record_advanced_and_mechanical(
            player: PlayerStats | None,
            pid: Any,
            unit_tag: tuple[int, int] | None,
            unit_type: str,
            seconds: int | None,
        ) -> None:
            if player is None:
                return
            _record_advanced_unit(player, unit_type, seconds)

            if unit_type not in MECHANICAL_UNIT_LABELS:
                refresh_side_state(player)
                return

            try:
                pid_int = int(pid)
            except Exception:
                pid_int = 0

            is_new_asset = unit_tag is None or unit_tag not in mechanical_tags_by_pid[pid_int]
            if unit_tag is not None:
                mechanical_tags_by_pid[pid_int].add(unit_tag)

            if is_new_asset:
                player.mechanical_units += 1
                player.siege_units += 1  # compatibility alias; now exact mechanical count.
                _increment(player.mechanical_unit_counts, MECHANICAL_UNIT_LABELS[unit_type])

            if unit_type in TREBUCHET_TYPES:
                is_new_trebuchet = unit_tag is None or unit_tag not in trebuchet_tags_by_pid[pid_int]
                if unit_tag is not None:
                    trebuchet_tags_by_pid[pid_int].add(unit_tag)
                if is_new_trebuchet:
                    player.trebuchets_total += 1

            if unit_type == "TrebutchetSieged":
                is_first_siege = unit_tag is None or unit_tag not in trebuchet_sieged_tags_by_pid[pid_int]
                if unit_tag is not None:
                    trebuchet_sieged_tags_by_pid[pid_int].add(unit_tag)
                if is_first_siege:
                    player.trebuchets_sieged += 1

            refresh_side_state(player)

        def snapshot_until(seconds: int | None) -> None:
            nonlocal next_snapshot
            if seconds is None:
                return
            while next_snapshot <= seconds:
                summary.timeline_snapshots.append(
                    {
                        "seconds": next_snapshot,
                        "time": _time_label(next_snapshot),
                        "teams": {str(team_id): dict(values) for team_id, values in sorted(team_timeline_state.items())},
                    }
                )
                next_snapshot += SNAPSHOT_SECONDS

        try:
            for event in protocol.decode_replay_tracker_events(archive.read_file("replay.tracker.events")):
                tracker_count += 1
                loop = int(event.get("_gameloop", 0) or 0)
                max_tracker_loop = max(max_tracker_loop, loop)
                event_seconds = _seconds_from_loops(loop)
                snapshot_until(event_seconds)
                event_name = event.get("_event")

                if event_name == "NNet.Replay.Tracker.SUnitBornEvent":
                    unit_type = _decode_unit_type(event.get("m_unitTypeName"))
                    pid = event.get("m_controlPlayerId") or event.get("m_upkeepPlayerId")
                    unit_tag = _tag(event)
                    if unit_tag and pid:
                        tag_owner[unit_tag] = int(pid)
                        tag_type[unit_tag] = unit_type

                    if _is_animal_pid(pid):
                        animal = summary.animal_stats
                        if animal and not _is_noise_unit(unit_type):
                            animal.units_born += 1
                            _increment(animal.unit_type_counts, unit_type)
                        continue

                    player = _pid_to_player(players, pid)
                    if player and not _is_noise_unit(unit_type):
                        player.units_born += 1
                        if player.team_id is not None:
                            team_timeline_state[int(player.team_id)]["units_born"] += 1
                        _increment(player.unit_type_counts, unit_type)
                        _apply_unit_category(player, unit_type)
                        record_advanced_and_mechanical(player, pid, unit_tag, unit_type, event_seconds)

                elif event_name == "NNet.Replay.Tracker.SUnitInitEvent":
                    unit_type = _decode_unit_type(event.get("m_unitTypeName"))
                    pid = event.get("m_controlPlayerId") or event.get("m_upkeepPlayerId")
                    unit_tag = _tag(event)
                    if unit_tag and pid:
                        pending_init[unit_tag] = (int(pid), unit_type)
                        tag_owner[unit_tag] = int(pid)
                        tag_type[unit_tag] = unit_type
                    if _is_animal_pid(pid):
                        continue
                    player = _pid_to_player(players, pid)
                    if player and _is_structure(unit_type):
                        player.structures_started += 1

                elif event_name == "NNet.Replay.Tracker.SUnitDoneEvent":
                    unit_tag = _tag(event)
                    if unit_tag and unit_tag in pending_init:
                        pid, unit_type = pending_init[unit_tag]
                        if _is_animal_pid(pid):
                            continue
                        player = _pid_to_player(players, pid)
                        if player:
                            player.structures_done += 1
                            _increment(player.structure_type_counts, unit_type)
                            _apply_unit_category(player, unit_type, completed_structure=True)
                            _record_tech_structure(player, unit_type, event_seconds)
                            refresh_side_state(player)

                elif event_name == "NNet.Replay.Tracker.SUnitTypeChangeEvent":
                    unit_tag = _tag(event)
                    new_type = _decode_unit_type(event.get("m_unitTypeName"))
                    if unit_tag:
                        tag_type[unit_tag] = new_type
                        owner_pid = tag_owner.get(unit_tag)
                        owner = _pid_to_player(players, owner_pid)
                        record_advanced_and_mechanical(owner, owner_pid, unit_tag, new_type, event_seconds)

                elif event_name == "NNet.Replay.Tracker.SUnitDiedEvent":
                    unit_tag = _tag(event)
                    owner_pid = event.get("m_unitOwnerPlayerId") or (tag_owner.get(unit_tag) if unit_tag else None)
                    unit_type = _decode_unit_type(event.get("m_unitTypeName"))
                    if unit_type == "UnknownUnit" and unit_tag in tag_type:
                        unit_type = tag_type[unit_tag]  # type: ignore[index]
                    if _is_noise_unit(unit_type):
                        continue

                    killer_pid = event.get("m_killerPlayerId")

                    if _is_animal_pid(owner_pid):
                        animal = summary.animal_stats
                        if animal:
                            animal.losses += 1
                            _increment(animal.unit_loss_counts, unit_type)
                        killer = _pid_to_player(players, killer_pid)
                        if killer:
                            killer.animal_kills += 1
                            if killer.team_id is not None:
                                team_timeline_state[int(killer.team_id)]["animal_kills"] += 1
                        continue

                    owner = _pid_to_player(players, owner_pid)
                    if _is_animal_pid(killer_pid):
                        animal = summary.animal_stats
                        if animal:
                            animal.kills += 1
                            killer_unit_type = tag_type.get(_killer_tag(event), "UnknownAnimal")
                            _increment(animal.unit_kill_counts, killer_unit_type)
                        if owner:
                            owner.deaths_to_animals += 1
                            if owner.team_id is not None:
                                team_timeline_state[int(owner.team_id)]["deaths_to_animals"] += 1
                        continue

                    if owner:
                        owner.losses += 1
                        _increment(owner.unit_loss_counts, unit_type)
                        if unit_type in MECHANICAL_UNIT_LABELS:
                            owner.mechanical_losses += 1
                            _increment(owner.mechanical_loss_counts, MECHANICAL_UNIT_LABELS[unit_type])
                            if unit_type == "TrebutchetMobile":
                                owner.trebuchet_mobile_deaths += 1
                            elif unit_type == "TrebutchetSieged":
                                owner.trebuchet_sieged_deaths += 1
                        if owner.team_id is not None:
                            team_timeline_state[int(owner.team_id)]["losses"] += 1
                        refresh_side_state(owner)

                    killer = _pid_to_player(players, killer_pid)
                    # Avoid counting suicides/environment/no-player/animal kills as PvP kills.
                    if killer and owner and killer is not owner:
                        killer.kills += 1
                        killer_unit_type = tag_type.get(_killer_tag(event), "UnknownKillerUnit")
                        _increment(killer.unit_kill_counts, killer_unit_type)
                        if killer_unit_type in MECHANICAL_ATTACK_TYPES:
                            killer.mechanical_kills += 1
                            _increment(killer.mechanical_kill_counts, MECHANICAL_UNIT_LABELS[killer_unit_type])
                            if killer_unit_type == "TrebutchetSieged":
                                killer.trebuchet_sieged_kills += 1
                        if killer.team_id is not None:
                            team_timeline_state[int(killer.team_id)]["kills"] += 1
                        refresh_side_state(killer)

                elif event_name == "NNet.Replay.Tracker.SUpgradeEvent":
                    pid = event.get("m_playerId")
                    if _is_animal_pid(pid):
                        continue
                    player = _pid_to_player(players, pid)
                    upgrade_name = _safe_decode_string(event.get("m_upgradeTypeName")) or "UnknownUpgrade"
                    if player:
                        player.upgrades += 1
                        _increment(player.upgrade_type_counts, upgrade_name)
                        _record_upgrade(player, upgrade_name, event_seconds)
                        refresh_side_state(player)

                elif event_name == "NNet.Replay.Tracker.SPlayerStatsEvent":
                    player_stats_event_count += 1
                    pid = event.get("m_playerId")
                    if _is_animal_pid(pid):
                        continue
                    player = _pid_to_player(players, pid)
                    if player:
                        sample, seen_channels, seen_fields = _resource_sample_from_stats(event.get("m_stats", {}))
                        resource_channels_seen.update(seen_channels)
                        resource_fields_seen.update(seen_fields)
                        sample_seconds = _seconds_from_loops(event.get("_gameloop"))
                        _remove_starting_stock(starting_stock[id(player)], sample, sample_seconds)
                        _derive_gather_rates(gather_history[id(player)], sample, sample_seconds)
                        _apply_resource_sample(player, sample, sample_seconds)
                        refresh_side_state(player)
        except Exception as exc:
            summary.warnings.append(f"Could not decode tracker events: {exc}")
            raise

        summary.raw_event_counts["tracker_events"] = tracker_count
        summary.raw_event_counts["player_stats_events"] = player_stats_event_count
        summary.raw_event_counts["resource_fields_seen"] = len(resource_fields_seen)
        if max_tracker_loop and (summary.duration_seconds is None or _seconds_from_loops(max_tracker_loop) > summary.duration_seconds):
            summary.duration_seconds = _seconds_from_loops(max_tracker_loop)
        snapshot_until(summary.duration_seconds)

        summary.resource_channels_seen = sorted(resource_channels_seen, key=lambda key: ("gold", "wood", "iron").index(key))
        summary.resource_tracking_notes.append(
            "AoK resource labels use Gold=SC2 Minerals, Wood=SC2 Vespene, and Iron=SC2 Terrazine."
        )
        if resource_channels_seen:
            summary.resource_tracking_notes.append(
                "Current stockpile comes directly from SPlayerStatsEvent; gathered/lost totals are score-value estimates, and gather rates per minute are derived from them."
            )
        else:
            summary.resource_tracking_notes.append(
                "This replay exposed no supported SPlayerStatsEvent resource fields, so resource values are unavailable rather than zero."
            )
        if "iron" not in resource_channels_seen:
            summary.resource_tracking_notes.append(
                "No Terrazine tracker fields were exposed in this replay/build; Iron is reported as unavailable, not as a confirmed zero."
            )
        summary.tech_inference_notes.extend([
            "Age and upgrade event names are exact replay-protocol observations.",
            "Tech-structure completion timings are exact; structure-to-unit requirements and age placement remain inferred until confirmed from map data or TwoDie.",
            "Trebuchet move mode cannot attack; move-mode deaths are tracked as asset losses, while kills are credited only from attack-capable mechanical states.",
        ])

        try:
            msg_events = list(protocol.decode_replay_message_events(archive.read_file("replay.message.events")))
            summary.raw_event_counts["message_events"] = len(msg_events)
        except Exception as exc:
            summary.warnings.append(f"Could not decode message events: {exc}")

        for player in players:
            player.role_label = _classify_player_role(player)

        if summary.animal_stats and not (
            summary.animal_stats.kills or summary.animal_stats.losses or summary.animal_stats.units_born
        ):
            summary.animal_stats = None

        _apply_leave_based_results(summary)
        _build_team_stats(summary)
        for team in summary.teams:
            if team.team_id in team_peak_rate:
                # Best simultaneous 60 s window, not the sum of each player's own best.
                team.resource_peak_collection_rate.update(team_peak_rate[team.team_id])
        _build_match_story(summary)
        summary.parser_ok = True
        return summary

    except UnsupportedReplayBuild as exc:
        summary.game_version = str(exc.base_build)
        summary.warnings.append(
            f"Replay is from StarCraft II build {exc.base_build}, which this bot's s2protocol "
            "decoder does not support yet. The bot needs an s2protocol update and redeploy.")
        summary.map_name = f"Unknown - unsupported SC2 build {exc.base_build}"
        return summary
    except Exception as exc:
        summary.warnings.append(f"Replay parse failed: {type(exc).__name__}: {exc}")
        summary.map_name = "Unknown - parse failed"
        return summary
    finally:
        if replay_handle is not None:
            replay_handle.close()

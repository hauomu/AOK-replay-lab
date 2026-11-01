"""Dependency-free match rules shared by the replay parser and miner."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _get(value: Any, key: str, default: Any = 0) -> Any:
    return value.get(key, default) if isinstance(value, Mapping) else getattr(value, key, default)


def _int(value: Any, key: str) -> int:
    try:
        return int(_get(value, key) or 0)
    except (TypeError, ValueError):
        return 0


def classify_role(stats: Any) -> str:
    cavalry, ranged = _int(stats, "cavalry_units"), _int(stats, "ranged_units")
    infantry, siege = _int(stats, "infantry_units"), _int(stats, "siege_units")
    total = max(1, cavalry + ranged + infantry + siege)
    static, walls = _int(stats, "static_defense"), _int(stats, "walls_gates")
    if walls >= 60 or static >= 150 or (static / max(1, _int(stats, "units_born") + _int(stats, "structures_done")) >= 0.22 and static >= 40):
        return "Defensive anchor / wall player"
    if cavalry >= 80 and cavalry / total >= 0.25:
        return "Cavalry pressure / mobile carry"
    if _int(stats, "kills") >= 800:
        return "Main combat carry / pressure leader"
    if ranged >= 150 and cavalry >= 100:
        return "Mixed firepower + mobile pressure"
    if ranged >= 150 and ranged / total >= 0.25:
        return "Ranged firepower/support"
    if infantry >= 250 and ranged >= 100:
        return "Infantry + hand-cannon frontline"
    if infantry >= 250 and infantry / total >= 0.40:
        return "Infantry frontline/mass army"
    if siege >= 40:
        return "Mechanical-support player"
    if _int(stats, "units_born") >= 300:
        return "Mass-production support"
    if _int(stats, "animal_kills") >= 30:
        return "Map-control / animal-clear support"
    return "Mixed/support"


def classify_team(stats: Any) -> str:
    cavalry, ranged = _int(stats, "cavalry_units"), _int(stats, "ranged_units")
    infantry, siege = _int(stats, "infantry_units"), _int(stats, "siege_units")
    total = max(1, cavalry + ranged + infantry + siege)
    walls, static = _int(stats, "walls_gates"), _int(stats, "static_defense")
    if walls >= 100 or (static >= 350 and walls >= 70):
        return "Turtle / layered-defense team"
    if cavalry / total >= 0.30:
        return "Mobile cavalry-pressure team"
    if ranged / total >= 0.35:
        return "Ranged/firepower-heavy team"
    if infantry / total >= 0.40 and ranged / total >= 0.20:
        return "Infantry + firepower frontline team"
    if infantry / total >= 0.45:
        return "Infantry-frontline-heavy team"
    return "Mixed-composition team"


def is_neutral_player(player: Any) -> bool:
    name = str(_get(player, "name", "") or "")
    try:
        player_id = int(_get(player, "player_id", 0) or 0)
    except (TypeError, ValueError):
        player_id = 0
    return player_id == 15 or name.startswith("Player 15") or name == "Animals / Player 15"


def user_player_indices(player_list: Sequence[Any], initdata: Any) -> dict[int, int]:
    """Map game-event user IDs to replay.details player indices.

    User IDs are lobby user slots, not player-list positions; AI players and
    observers shift them. Falls back to identity when initData has no usable slots.
    """
    try:
        slots = initdata["m_syncLobbyState"]["m_lobbyState"]["m_slots"]
    except (KeyError, TypeError):
        slots = []
    mapping: dict[int, int] = {}
    for index, player in enumerate(player_list):
        slot = _get(player, "m_workingSetSlotId", None)
        if isinstance(slot, int) and 0 <= slot < len(slots):
            user_id = _get(slots[slot], "m_userId", None)
            if isinstance(user_id, int):
                mapping[user_id] = index
    return mapping or {index: index for index in range(len(player_list))}


def normalize_match_groups(players: Sequence[Any]) -> tuple[str, list[Any]]:
    """Return the bot's mode label and per-player analysis team IDs."""
    raw_ids = [_get(player, "team_id", None) for player in players]
    human_indices = [i for i, player in enumerate(players) if _get(player, "name", "") and not is_neutral_player(player)]
    human_ids = [raw_ids[i] for i in human_indices]
    ffa = False
    if len(human_indices) >= 3 and all(team_id is not None for team_id in human_ids):
        distinct = set(human_ids)
        ffa = len(distinct) <= 1 or len(distinct) == len(human_indices)
    groups = list(raw_ids)
    if ffa:
        if len(set(human_ids)) <= 1:
            for group, player_index in enumerate(human_indices, 1):
                groups[player_index] = group
        return "Free-for-all", groups
    distinct = {raw_ids[i] for i in human_indices if raw_ids[i] is not None}
    mode = "Duel" if len(human_indices) == 2 and len(distinct) == 2 else "Team"
    return mode, groups

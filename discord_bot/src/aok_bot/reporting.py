from __future__ import annotations

from pathlib import Path
from typing import Any

import discord

from .models import PlayerStats, ReplaySummary, TeamStats

try:  # v0.6: Jinja2 gives us a cleaner, template-driven Markdown report layout.
    from jinja2 import Environment
except Exception:  # pragma: no cover - dependency may not be installed in older venvs yet.
    Environment = None  # type: ignore[assignment]


TECH_STRUCTURE_LABELS = {
    "Blacksmith": "Blacksmith",
    "FletchersWorkshop": "Fletcher's Workshop",
    "SiegeWorkshop": "Siege Workshop",
    "Castle": "Castle",
    "AlchemistsLab": "Alchemist's Lab",
}
UNLOCK_LABELS = {
    "UnlockHandCannoneer": "Unlock Hand Cannoneer",
    "UnlockBombardCannons": "Unlock Bombard Cannons",
}
ADVANCED_UNIT_LABELS = {
    "HandCannoneer": "Hand Cannoneer",
    "Ballista": "Ballista",
    "BatteringRam": "Battering Ram",
    "Catapult": "Catapult",
    "BombardCannon": "Bombard Cannon",
    "TrebutchetMobile": "Trebuchet (Move Mode)",
    "TrebutchetSieged": "Trebuchet (Siege Mode)",
    "ExplosiveWagon": "Explosives Wagon",
    "ExplosivesWagon": "Explosives Wagon",
}
ADVANCED_UNIT_REQUIREMENTS = {
    "HandCannoneer": "Unlock Hand Cannoneer; likely Alchemist's Lab + Imperial Age",
    "Ballista": "likely Siege Workshop + Castle Age",
    "BatteringRam": "likely Siege Workshop + Castle Age",
    "Catapult": "likely Siege Workshop + Castle Age",
    "BombardCannon": "Unlock Bombard Cannons; likely Alchemist's Lab + Imperial Age",
    "TrebutchetMobile": "likely Castle + Castle Age; move mode cannot attack",
    "TrebutchetSieged": "same trebuchet asset after entering attack-capable siege mode",
    "ExplosiveWagon": "likely Siege Workshop; exact unlock unconfirmed",
    "ExplosivesWagon": "likely Siege Workshop; exact unlock unconfirmed",
}
RESOURCE_LABELS = {"gold": "Gold", "wood": "Wood", "iron": "Iron"}


def _ratio(kills: int, losses: int) -> str:
    if losses <= 0:
        return "N/A"
    return f"{kills / losses:.2f}"


def _leave_label(seconds: int | None) -> str:
    if seconds is None:
        return ""
    m, s = divmod(int(seconds), 60)
    return f" left {m}:{s:02d}"


def _left_time(seconds: int | None) -> str:
    return _leave_label(seconds).replace(" left ", "")


def _top_items(items: list[tuple[str, int]], empty: str = "none") -> str:
    if not items:
        return empty
    return ", ".join(f"{name}×{count}" for name, count in items)


def _time_label(seconds: int | None) -> str:
    if seconds is None:
        return "n/a"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _resource_cell(summary: ReplaySummary, resource: str, value: int | None) -> str:
    if resource not in set(summary.resource_channels_seen):
        return "n/a"
    return f"{int(value or 0):,}"


def _resource_triplet(summary: ReplaySummary, values: dict[str, int]) -> str:
    return ", ".join(
        f"{RESOURCE_LABELS[key]} {_resource_cell(summary, key, values.get(key, 0))}"
        for key in ("gold", "wood", "iron")
    )


def _timed_items(mapping: dict[str, int], labels: dict[str, str], limit: int = 5) -> str:
    items = sorted(mapping.items(), key=lambda kv: (kv[1], kv[0]))[:limit]
    if not items:
        return "none recorded"
    return ", ".join(f"{labels.get(name, name)} at {_time_label(seconds)}" for name, seconds in items)


def _timed_items_with_age(
    mapping: dict[str, int],
    labels: dict[str, str],
    ages: dict[str, str],
    limit: int = 8,
) -> str:
    items = sorted(mapping.items(), key=lambda kv: (kv[1], kv[0]))[:limit]
    if not items:
        return "none recorded"
    parts: list[str] = []
    for name, seconds in items:
        age = ages.get(name)
        age_part = f" [{age}]" if age else ""
        parts.append(f"{labels.get(name, name)} at {_time_label(seconds)}{age_part}")
    return ", ".join(parts)


def _age_timing_items(player: PlayerStats) -> str:
    items = sorted(player.age_timing_seconds.items(), key=lambda kv: (kv[1], kv[0]))
    if not items:
        return "none recorded"
    return ", ".join(f"{age} at {_time_label(seconds)}" for age, seconds in items)


def _advanced_requirement_items(player: PlayerStats) -> str:
    items = sorted(player.advanced_unit_first_seconds.items(), key=lambda kv: (kv[1], kv[0]))
    if not items:
        return "none recorded"
    return "; ".join(
        f"{ADVANCED_UNIT_LABELS.get(name, name)} → {ADVANCED_UNIT_REQUIREMENTS.get(name, 'requirement unconfirmed')}"
        for name, _ in items
    )


def _tech_economy_embed_lines(summary: ReplaySummary) -> list[str]:
    lines: list[str] = []
    for team in _sort_teams_for_report(summary):
        resources = (
            f"; stockpile {_resource_triplet(summary, team.resource_current)}"
            if summary.resource_channels_seen else ""
        )
        lines.append(
            f"{_team_label_with_players(team, summary.match_mode)} — {team.current_age()}, tech {team.tech_score}, "
            f"mechanical {team.mechanical_kills}/{team.mechanical_losses}{resources}."
        )
    return lines


def _team_label(team: TeamStats) -> str:
    return team.label or f"Team {team.team_id}"


def _team_label_with_players(team: TeamStats, match_mode: str | None = None) -> str:
    base = _team_label(team)
    if match_mode in {"Free-for-all", "Duel"}:
        return base
    if team.players:
        return f"{base} ({', '.join(team.players)})"
    return base


def _team_by_id(summary: ReplaySummary, team_id: int | None) -> TeamStats | None:
    if team_id is None:
        return None
    return next((t for t in summary.teams if t.team_id == team_id), None)


def _side_label_for_player(summary: ReplaySummary, player: PlayerStats) -> str:
    if summary.match_mode == "Free-for-all":
        return "FFA side"
    if summary.match_mode == "Duel":
        return "Duel side"
    team = _team_by_id(summary, player.team_id)
    if team is not None:
        return _team_label(team)
    if player.team_id is not None:
        return f"Team {player.team_id}"
    return ""


def _player_with_side(summary: ReplaySummary, player: PlayerStats) -> str:
    side = _side_label_for_player(summary, player)
    return f"{player.name} ({side})" if side else player.name


def _team_line_summary(team: TeamStats, match_mode: str | None = None) -> str:
    if team.result == "Win":
        result = "won"
    elif team.result == "Loss":
        result = "lost"
    else:
        result = "no clear win result"
    return (
        f"**{_team_label_with_players(team, match_mode)}** — {result}; {team.style_label or 'mixed style'}. "
        f"PvP K/L {team.kills}/{team.losses} ({_ratio(team.kills, team.losses)}); "
        f"animal K/D {team.animal_kills}/{team.deaths_to_animals}; "
        f"{team.current_age()}, tech {team.tech_score}, mechanical {team.mechanical_kills}/{team.mechanical_losses}."
    )


def _player_line(player: PlayerStats) -> str:
    extras: list[str] = []
    if player.animal_kills or player.deaths_to_animals:
        extras.append(f"animals {player.animal_kills}/{player.deaths_to_animals}")
    if player.leave_time_seconds is not None:
        extras.append(_leave_label(player.leave_time_seconds).strip())
    extra = f"; {'; '.join(extras)}" if extras else ""
    return (
        f"**{player.name}** — {player.role_label or 'Mixed/support'}; "
        f"PvP K/L {player.kills}/{player.losses} ({_ratio(player.kills, player.losses)}), "
        f"units {player.units_born}{extra}"
    )


def _section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.append(f"## {title}")
    lines.append("")
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _md_cell(value: Any) -> str:
    """Escape a value so Markdown tables remain readable even with clan tags/pipes."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    return text.replace("|", r"\|")


def _markdown_table(
    headers: list[str],
    rows: list[list[Any]],
    *,
    right: set[int] | None = None,
) -> str:
    """Create padded Markdown tables that are readable both raw and rendered."""
    if not rows:
        return "_No rows._"

    right = right or set()
    clean_headers = [_md_cell(h) for h in headers]
    clean_rows = [[_md_cell(cell) for cell in row] for row in rows]
    widths = [len(h) for h in clean_headers]
    for row in clean_rows:
        for idx, cell in enumerate(row):
            if idx >= len(widths):
                widths.append(0)
            widths[idx] = max(widths[idx], len(cell))

    def fmt_row(row: list[str]) -> str:
        padded: list[str] = []
        for idx, cell in enumerate(row):
            width = widths[idx]
            padded.append(cell.rjust(width) if idx in right else cell.ljust(width))
        return "| " + " | ".join(padded) + " |"

    separators: list[str] = []
    for idx, width in enumerate(widths):
        if idx in right:
            separators.append(("-" * max(3, width - 1)) + ":")
        else:
            separators.append("-" * max(3, width))

    return "\n".join([fmt_row(clean_headers), fmt_row(separators), *[fmt_row(row) for row in clean_rows]])


def _sort_teams_for_report(summary: ReplaySummary) -> list[TeamStats]:
    if summary.match_mode == "Free-for-all":
        return sorted(
            summary.teams,
            key=lambda t: (
                t.kills - t.losses,
                t.kill_loss_ratio() or 0,
                t.tech_score,
                sum(t.resource_gathered_estimate.values()),
                t.units_born,
                t.commands,
            ),
            reverse=True,
        )
    return sorted(summary.teams, key=lambda t: t.team_id)


def _sort_players_for_report(summary: ReplaySummary) -> list[PlayerStats]:
    if summary.match_mode == "Free-for-all":
        return sorted(
            summary.players,
            key=lambda p: (p.kills - p.losses, p.kills, p.tech_score, sum(p.resource_gathered_estimate.values()), p.units_born),
            reverse=True,
        )
    return sorted(summary.players, key=lambda p: (p.team_id if p.team_id is not None else 99, -p.kills, p.name.lower()))


def _side_roster_lines(summary: ReplaySummary) -> list[str]:
    """Human-readable side labels for Discord embeds."""
    if not summary.teams:
        return []
    if summary.match_mode == "Free-for-all":
        return [f"{_team_label(t)} = FFA side" for t in _sort_teams_for_report(summary)]
    if summary.match_mode == "Duel":
        return [f"{_team_label(t)} = duel side" for t in _sort_teams_for_report(summary)]
    return [f"{_team_label(t)} = {', '.join(t.players) if t.players else 'unknown players'}" for t in _sort_teams_for_report(summary)]


def _player_group_label(summary: ReplaySummary, team: TeamStats | None, players: list[PlayerStats]) -> str:
    if summary.match_mode == "Free-for-all":
        if players:
            return f"{players[0].name} (FFA side)"
        return "FFA side"
    if summary.match_mode == "Duel":
        if players:
            return f"{players[0].name} (duel side)"
        return "Duel side"
    if team is not None:
        return _team_label_with_players(team, summary.match_mode)
    return "Unknown side"


def _build_player_table_groups(summary: ReplaySummary) -> list[dict[str, Any]]:
    """Group player tables by team/side so large reports are easier to scan.

    Team games get one section per team. FFA/duel games still use the same
    side grouping, but each player is its own side so the output does not imply
    fake alliances.
    """
    players_by_team: dict[int | None, list[PlayerStats]] = {}
    for player in _sort_players_for_report(summary):
        players_by_team.setdefault(player.team_id, []).append(player)

    team_lookup = {team.team_id: team for team in summary.teams}

    def sort_key(item: tuple[int | None, list[PlayerStats]]) -> tuple[int, int]:
        team_id, group_players = item
        if summary.match_mode == "Free-for-all":
            # Strongest FFA side first.
            best = max(
                group_players,
                key=lambda p: (p.kills - p.losses, p.kills, p.tech_score, sum(p.resource_gathered_estimate.values()), p.units_born),
                default=None,
            )
            return (0, -((best.kills - best.losses) if best else 0))
        return (team_id is None, team_id if team_id is not None else 999)

    groups: list[dict[str, Any]] = []
    for team_id, group_players in sorted(players_by_team.items(), key=sort_key):
        team = team_lookup.get(team_id) if team_id is not None else None
        combat_rows = [
            [
                p.name,
                f"{p.kills}/{p.losses} ({_ratio(p.kills, p.losses)})",
                f"{p.animal_kills}/{p.deaths_to_animals} ({_ratio(p.animal_kills, p.deaths_to_animals)})",
                p.units_born,
                p.structures_done,
                p.commands,
                p.apm if p.apm is not None else "",
            ]
            for p in group_players
        ]
        army_rows = [
            [
                p.name,
                p.static_defense,
                p.cavalry_units,
                p.ranged_units,
                p.infantry_units,
                p.mechanical_units,
                _top_items(p.top_units(4)),
            ]
            for p in group_players
        ]
        resource_rows = [
            [
                p.name,
                _resource_cell(summary, "gold", p.resource_current.get("gold", 0)),
                _resource_cell(summary, "wood", p.resource_current.get("wood", 0)),
                _resource_cell(summary, "iron", p.resource_current.get("iron", 0)),
                _resource_cell(summary, "gold", p.resource_collection_rate.get("gold", 0)),
                _resource_cell(summary, "wood", p.resource_collection_rate.get("wood", 0)),
                _resource_cell(summary, "iron", p.resource_collection_rate.get("iron", 0)),
                _resource_triplet(summary, p.resource_gathered_estimate),
            ]
            for p in group_players
        ]
        tech_rows = [
            [
                p.name,
                p.current_age(),
                p.tech_score,
                _timed_items(p.tech_structure_first_seconds, TECH_STRUCTURE_LABELS, 3),
                _timed_items(p.tech_unlock_first_seconds, UNLOCK_LABELS, 3),
                _timed_items(p.advanced_unit_first_seconds, ADVANCED_UNIT_LABELS, 3),
                f"{p.mechanical_kills}/{p.mechanical_losses}",
                f"{p.trebuchets_total}/{p.trebuchets_sieged}/{p.trebuchet_mobile_deaths}",
            ]
            for p in group_players
        ]
        groups.append({
            "label": _player_group_label(summary, team, group_players),
            "combat_rows": combat_rows,
            "army_rows": army_rows,
            "resource_rows": resource_rows,
            "tech_rows": tech_rows,
        })
    return groups


def _timeline_group_label(summary: ReplaySummary, team: TeamStats) -> str:
    """Label timeline groups without implying fake alliances in FFA/duel games."""
    if summary.match_mode == "Free-for-all":
        return f"{_team_label(team)} (FFA side)"
    if summary.match_mode == "Duel":
        return f"{_team_label(team)} (duel side)"
    return _team_label_with_players(team, summary.match_mode)


def _build_timeline_table_groups(summary: ReplaySummary) -> list[dict[str, Any]]:
    """Group cumulative timeline snapshots by team/side, then sort each group by time.

    Earlier versions alternated rows by timestamp, for example Team 0 then Team 1
    at 5:00, then Team 0 then Team 1 at 10:00. That was good for point-in-time
    comparison, but hard to scan as a progression. This groups the table as:

        Team 0 -> 5:00, 10:00, 15:00...
        Team 1 -> 5:00, 10:00, 15:00...

    FFA/duel modes use the same side grouping but label sides as FFA/duel sides
    so the report does not imply alliances.
    """
    if not summary.timeline_snapshots:
        return []

    # Keep the same side ordering as the rest of the report.
    teams = _sort_teams_for_report(summary)
    groups: list[dict[str, Any]] = []

    for team in teams:
        rows: list[list[Any]] = []
        tech_resource_rows: list[list[Any]] = []
        for snap in sorted(summary.timeline_snapshots, key=lambda s: int(s.get("seconds", 0) or 0)):
            teams_dict = snap.get("teams", {})
            values = teams_dict.get(str(team.team_id)) or teams_dict.get(team.team_id)
            if not values:
                continue
            rows.append([
                snap.get("time"),
                f"{values.get('kills', 0)}/{values.get('losses', 0)}",
                values.get("units_born", 0),
                f"{values.get('animal_kills', 0)}/{values.get('deaths_to_animals', 0)}",
            ])
            tech_resource_rows.append([
                snap.get("time"),
                values.get("age", "Starting age"),
                values.get("tech_score", 0),
                f"{values.get('mechanical_kills', 0)}/{values.get('mechanical_losses', 0)}",
                _resource_cell(summary, "gold", values.get("gold", 0)),
                _resource_cell(summary, "wood", values.get("wood", 0)),
                _resource_cell(summary, "iron", values.get("iron", 0)),
                _resource_cell(summary, "gold", values.get("gold_rate", 0)),
                _resource_cell(summary, "wood", values.get("wood_rate", 0)),
                _resource_cell(summary, "iron", values.get("iron_rate", 0)),
            ])
        if rows:
            groups.append({
                "label": _timeline_group_label(summary, team),
                "rows": rows,
                "tech_resource_rows": tech_resource_rows,
            })

    return groups


def _embed_key_findings(summary: ReplaySummary) -> list[str]:
    """Rebuild the most important evidence lines with guaranteed side labels."""
    players = summary.players
    if not players:
        return summary.key_findings

    findings: list[str] = []
    if summary.match_mode == "Free-for-all" and summary.teams:
        ranked = sorted(
            summary.teams,
            key=lambda t: (
                t.kills - t.losses,
                t.kill_loss_ratio() or 0,
                t.tech_score,
                sum(t.resource_gathered_estimate.values()),
                t.units_born,
                t.commands,
            ),
            reverse=True,
        )
        leader = ranked[0]
        findings.append(
            f"FFA leader by PvP margin/conversion: {_team_label(leader)} (FFA side) at {leader.kills}/{leader.losses} "
            f"(margin {leader.kills - leader.losses}, K/L {leader.kill_loss_ratio() or 'N/A'})."
        )
        if len(ranked) > 1:
            runner = ranked[1]
            findings.append(
                f"Closest rival by the same heuristic: {_team_label(runner)} (FFA side) at {runner.kills}/{runner.losses} "
                f"(margin {runner.kills - runner.losses})."
            )

    top_killer = max(players, key=lambda p: p.kills, default=None)
    top_producer = max(players, key=lambda p: p.units_born, default=None)
    top_defender = max(players, key=lambda p: p.static_defense, default=None)
    top_animal_killer = max(players, key=lambda p: p.animal_kills, default=None)
    top_tech = max(players, key=lambda p: (p.tech_score, p.age_stage()), default=None)
    top_economy = max(players, key=lambda p: sum(p.resource_gathered_estimate.values()), default=None)
    top_mechanical = max(players, key=lambda p: (p.mechanical_kills - p.mechanical_losses, p.mechanical_kills), default=None)
    efficient = [p for p in players if p.losses > 0 and p.kills >= 50]
    top_eff = max(efficient, key=lambda p: p.kills / max(1, p.losses), default=None)

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
            f"Tech leader: {_player_with_side(summary, top_tech)} — {top_tech.current_age()}, tech score {top_tech.tech_score}."
        )
    if top_economy and summary.resource_channels_seen and sum(top_economy.resource_gathered_estimate.values()) > 0:
        findings.append(
            f"Tracked economy leader: {_player_with_side(summary, top_economy)} — {_resource_triplet(summary, top_economy.resource_gathered_estimate)} gathered estimate."
        )
    if top_mechanical and top_mechanical.mechanical_kills > 0:
        findings.append(
            f"Mechanical leader: {_player_with_side(summary, top_mechanical)} — {top_mechanical.mechanical_kills}/{top_mechanical.mechanical_losses} mechanical K/L."
        )

    return findings or summary.key_findings


def _build_report_tables(summary: ReplaySummary) -> dict[str, list[list[Any]]]:
    teams = _sort_teams_for_report(summary)
    players = _sort_players_for_report(summary)

    side_overview_rows = [
        [
            _team_label_with_players(t, summary.match_mode),
            t.result or "",
            t.style_label or "",
        ]
        for t in teams
    ]

    side_combat_rows = [
        [
            _team_label_with_players(t, summary.match_mode),
            f"{t.kills}/{t.losses} ({_ratio(t.kills, t.losses)})",
            f"{t.animal_kills}/{t.deaths_to_animals} ({_ratio(t.animal_kills, t.deaths_to_animals)})",
            t.units_born,
            t.commands,
        ]
        for t in teams
    ]

    side_footprint_rows = [
        [
            _team_label_with_players(t, summary.match_mode),
            t.static_defense,
            t.walls_gates,
            t.castles,
            t.cavalry_units,
            t.ranged_units,
            t.infantry_units,
            t.mechanical_units,
        ]
        for t in teams
    ]

    side_tech_rows = [
        [
            _team_label_with_players(t, summary.match_mode),
            t.current_age(),
            t.tech_score,
            len(t.tech_structure_first_seconds),
            len(t.tech_unlock_first_seconds),
            len(t.advanced_unit_first_seconds),
            f"{t.mechanical_kills}/{t.mechanical_losses}",
            f"{t.trebuchets_total}/{t.trebuchets_sieged}/{t.trebuchet_mobile_deaths}",
        ]
        for t in teams
    ]

    side_resource_rows = [
        [
            _team_label_with_players(t, summary.match_mode),
            _resource_cell(summary, "gold", t.resource_current.get("gold", 0)),
            _resource_cell(summary, "wood", t.resource_current.get("wood", 0)),
            _resource_cell(summary, "iron", t.resource_current.get("iron", 0)),
            _resource_cell(summary, "gold", t.resource_collection_rate.get("gold", 0)),
            _resource_cell(summary, "wood", t.resource_collection_rate.get("wood", 0)),
            _resource_cell(summary, "iron", t.resource_collection_rate.get("iron", 0)),
            _resource_triplet(summary, t.resource_gathered_estimate),
        ]
        for t in teams
    ]

    player_overview_rows = [
        [
            p.name,
            _side_label_for_player(summary, p),
            p.result or "",
            p.role_label or "",
            _left_time(p.leave_time_seconds),
        ]
        for p in players
    ]

    player_combat_rows = [
        [
            p.name,
            f"{p.kills}/{p.losses} ({_ratio(p.kills, p.losses)})",
            f"{p.animal_kills}/{p.deaths_to_animals} ({_ratio(p.animal_kills, p.deaths_to_animals)})",
            p.units_born,
            p.structures_done,
            p.commands,
            p.apm if p.apm is not None else "",
        ]
        for p in players
    ]

    player_army_rows = [
        [
            p.name,
            p.static_defense,
            p.cavalry_units,
            p.ranged_units,
            p.infantry_units,
            p.mechanical_units,
            _top_items(p.top_units(4)),
        ]
        for p in players
    ]

    animal_rows = [
        [
            p.name,
            _side_label_for_player(summary, p),
            p.animal_kills,
            p.deaths_to_animals,
            _ratio(p.animal_kills, p.deaths_to_animals),
        ]
        for p in sorted(summary.players, key=lambda p: (p.deaths_to_animals + p.animal_kills, p.animal_kills), reverse=True)
        if p.animal_kills or p.deaths_to_animals
    ]

    # v0.8: timeline rows are sorted by side first, then time, so progression is easier to scan.
    team_labels = {str(t.team_id): _timeline_group_label(summary, t) for t in summary.teams}
    timeline_rows: list[list[Any]] = []
    for group in _build_timeline_table_groups(summary):
        for row in group["rows"]:
            timeline_rows.append([row[0], group["label"], row[1], row[2], row[3]])

    raw_event_rows = [[key, value] for key, value in summary.raw_event_counts.items()]

    return {
        "side_overview": side_overview_rows,
        "side_combat": side_combat_rows,
        "side_footprint": side_footprint_rows,
        "side_tech": side_tech_rows,
        "side_resources": side_resource_rows,
        "player_overview": player_overview_rows,
        "player_combat": player_combat_rows,
        "player_army": player_army_rows,
        "animal_rows": animal_rows,
        "timeline_rows": timeline_rows,
        "raw_event_rows": raw_event_rows,
    }


REPORT_TEMPLATE = r"""# AoK Replay Analysis

| Field | Value |
| ----- | ----- |
| File | `{{ summary.source_path.name | md }}` |
| Map | {{ (summary.map_name or 'Unknown') | md }} |
| Duration | {{ summary.duration_label() | md }} |
| Match mode | {{ summary.match_mode | md }} |
| Winning side | {{ summary.winner_label() | md }} |
| Game version/build | {{ (summary.game_version or 'Unknown') | md }} |
| Parser OK | {{ summary.parser_ok }} |
| Report format | Jinja2 compact table layout |

{% if summary.verdict %}
## Short verdict

{{ summary.verdict }}
{% endif %}

{% if summary.turning_points %}
## Turning point

{% for item in summary.turning_points -%}
- {{ item }}
{% endfor %}
{% endif %}

{% if summary.team_evaluations %}
## {{ 'FFA/player evaluations' if summary.match_mode == 'Free-for-all' else 'Team evaluations' }}

{% for item in summary.team_evaluations -%}
- {{ item }}
{% endfor %}
{% endif %}

{% if summary.tech_evaluations %}
## Technology + economy evaluation

{% for item in summary.tech_evaluations -%}
- {{ item }}
{% endfor %}
{% endif %}

{% if summary.animal_impact %}
## Player 15 / Animals impact

{% for item in summary.animal_impact -%}
- {{ item }}
{% endfor %}
{% endif %}

{% if summary.player_takeaways %}
## Most useful player takeaway

{% for item in summary.player_takeaways -%}
- {{ item }}
{% endfor %}
{% endif %}

{% if summary.key_findings %}
## Evidence highlights

{% for item in summary.key_findings -%}
- {{ item }}
{% endfor %}
{% endif %}

{% if summary.match_story %}
## Match story notes

{% for item in summary.match_story -%}
- {{ item }}
{% endfor %}
{% endif %}

{% if tables.side_overview %}
## {{ 'FFA/player side overview' if summary.match_mode == 'Free-for-all' else 'Team overview' }}

{{ table(['Side', 'Result', 'Style'], tables.side_overview) }}

## Side combat + activity

{{ table(['Side', 'PvP K/L', 'Animal K/D', 'Units', 'Cmds'], tables.side_combat, right=[3, 4]) }}

## Side army / defense footprint

{{ table(['Side', 'Static', 'Walls/gates', 'Castles', 'Cavalry', 'Ranged', 'Infantry', 'Mechanical'], tables.side_footprint, right=[1, 2, 3, 4, 5, 6, 7]) }}

## Side technology overview

Trebuchets are shown as **total assets / reached siege mode / died in move mode**.

{{ table(['Side', 'Age', 'Tech score', 'Tech structures', 'Key unlocks', 'Advanced unit types', 'Mechanical K/L', 'Trebs T/S/M-loss'], tables.side_tech, right=[2, 3, 4, 5]) }}

## Side resource overview

AoK labels the replay channels as **Gold = minerals**, **Wood = vespene**, and **Iron = terrazine**. `n/a` means the replay protocol did not expose that channel; it is not a confirmed zero.

{{ table(['Side', 'Gold', 'Wood', 'Iron', 'Gold rate', 'Wood rate', 'Iron rate', 'Gathered estimate'], tables.side_resources, right=[1, 2, 3, 4, 5, 6]) }}
{% endif %}

{% if summary.animal_stats %}
## Player 15 / Animals evidence

- **Animal K/D:** {{ summary.animal_stats.kills }} kills caused / {{ summary.animal_stats.losses }} animal deaths
- **Animal units seen/born:** {{ summary.animal_stats.units_born }}
- **Most killed animal types:** {{ top_items(summary.animal_stats.top_losses(10)) }}
- **Animal units credited with kills:** {{ top_items(summary.animal_stats.top_kill_units(10)) }}

### Player vs Animals table

{{ table(['Player', 'Side', 'Animal kills', 'Deaths to animals', 'Animal K/D'], tables.animal_rows, right=[2, 3, 4]) }}
{% endif %}

{% if summary.timeline_snapshots %}
## Timeline snapshots

These are cumulative 5-minute snapshots. They support the turning-point read but should be treated as replay-protocol evidence, not visual map observation.

{% for group in timeline_table_groups -%}
### {{ group.label }} — combat

{{ table(['Time', 'PvP K/L', 'Units born', 'Animal K/D'], group.rows, right=[2]) }}

### {{ group.label }} — technology + resources

{{ table(['Time', 'Age', 'Tech', 'Mechanical K/L', 'Gold', 'Wood', 'Iron', 'Gold rate', 'Wood rate', 'Iron rate'], group.tech_resource_rows, right=[2, 4, 5, 6, 7, 8, 9]) }}

{% endfor -%}
{% endif %}

{% if summary.players %}
## Player overview

{{ table(['Player', 'Side', 'Result', 'Role read', 'Left'], tables.player_overview) }}

## Player combat + activity

{% for group in player_table_groups -%}
### {{ group.label }}

{{ table(['Player', 'PvP K/L', 'Animal K/D', 'Units', 'Structures', 'Cmds', 'APM'], group.combat_rows, right=[3, 4, 5, 6]) }}

{% endfor -%}

## Player army profile

{% for group in player_table_groups -%}
### {{ group.label }}

{{ table(['Player', 'Static', 'Cavalry', 'Ranged', 'Infantry', 'Mechanical', 'Top units'], group.army_rows, right=[1, 2, 3, 4, 5]) }}

{% endfor -%}

## Player resource tracking

{% for group in player_table_groups -%}
### {{ group.label }}

{{ table(['Player', 'Gold', 'Wood', 'Iron', 'Gold rate', 'Wood rate', 'Iron rate', 'Gathered estimate'], group.resource_rows, right=[1, 2, 3, 4, 5, 6]) }}

{% endfor -%}

## Player technology profiles

Trebuchets are shown as **total assets / reached siege mode / died in move mode**.

{% for group in player_table_groups -%}
### {{ group.label }}

{{ table(['Player', 'Age', 'Tech score', 'Tech structures', 'Key unlocks', 'Advanced units', 'Mechanical K/L', 'Trebs T/S/M-loss'], group.tech_rows, right=[2]) }}

{% endfor -%}

## Player composition detail

{% for p in players_by_combat %}
### {{ player_with_side(summary, p) }}

- **Role read:** {{ p.role_label or 'Unknown' }}
- **PvP combat:** {{ p.kills }} kills / {{ p.losses }} losses, K/L {{ ratio(p.kills, p.losses) }}
- **Animal interaction:** {{ p.animal_kills }} animal kills / {{ p.deaths_to_animals }} deaths to animals
- **Activity:** {{ p.commands }} commands, {{ p.control_groups }} control-group events, {{ p.pings }} pings, {{ p.chat_messages }} chat messages
- **Production:** {{ p.units_born }} units born, {{ p.structures_done }} completed structures, {{ p.upgrades }} raw upgrade events
- **Technology:** {{ p.current_age() }}, tech score {{ p.tech_score }}
- **Age progression:** {{ age_timing_items(p) }}
- **Tech structures by age:** {{ timed_items_with_age(p.tech_structure_first_seconds, tech_structure_labels, p.tech_structure_age_labels, 6) }}
- **Key unlocks:** {{ timed_items_with_age(p.tech_unlock_first_seconds, unlock_labels, p.tech_upgrade_age_labels, 6) }}
- **Gameplay upgrades by observed age:** {{ timed_items_with_age(p.tech_upgrade_first_seconds, empty_labels, p.tech_upgrade_age_labels, 10) }}
- **Advanced units:** {{ timed_items_with_age(p.advanced_unit_first_seconds, advanced_unit_labels, p.advanced_unit_age_labels, 8) }}
- **Inferred unit requirements:** {{ advanced_requirement_items(p) }}
- **Resources:** current {{ resource_triplet(summary, p.resource_current) }}; rates {{ resource_triplet(summary, p.resource_collection_rate) }}; gathered estimate {{ resource_triplet(summary, p.resource_gathered_estimate) }}
- **Mechanical:** {{ p.mechanical_units }} assets, {{ p.mechanical_kills }}/{{ p.mechanical_losses }} K/L; trebuchets {{ p.trebuchets_total }} total, {{ p.trebuchets_sieged }} reached siege mode, {{ p.trebuchet_mobile_deaths }} move-mode deaths, {{ p.trebuchet_sieged_deaths }} siege-mode deaths
- **Top units:** {{ top_items(p.top_units(8)) }}
{% if p.top_structures() -%}
- **Top structures:** {{ top_items(p.top_structures(8)) }}
{% endif -%}
{% if p.top_losses() -%}
- **Most lost unit types:** {{ top_items(p.top_losses(8)) }}
{% endif -%}
{% if p.top_kill_units() -%}
- **Unit types credited with kills:** {{ top_items(p.top_kill_units(8)) }}
{% endif -%}
{% if p.leave_time_seconds is not none -%}
- **Leave time:** {{ left_time(p.leave_time_seconds) }}
{% endif %}
{% endfor %}
{% endif %}

{% if summary.resource_tracking_notes %}
## Resource tracking notes

{% for note in summary.resource_tracking_notes -%}
- {{ note }}
{% endfor %}
{% endif %}

{% if summary.tech_inference_notes %}
## Technology inference notes

{% for note in summary.tech_inference_notes -%}
- {{ note }}
{% endfor %}
{% endif %}

{% if summary.raw_event_counts %}
## Raw event counts

{{ table(['Event type', 'Count'], tables.raw_event_rows, right=[1]) }}
{% endif %}

{% if summary.warnings %}
## Warnings

{% for warning in summary.warnings -%}
- {{ warning }}
{% endfor %}
{% endif %}

## Known limitations

- This reads replay protocol events, not a video recording.
- Player 15 is treated as Animals/Neutral because AoK assigns animals to that player slot.
- PvP K/L excludes animal kills; animal K/D is tracked separately.
- Exact age costs and hard prerequisite chains still need AoK map metadata or TwoDie confirmation; inferred relationships are labelled as such.
- FFA/no-alliance games are split into one analysis side per player; team games still aggregate allied players.
- Resource gathered/lost totals are score-value estimates; current stockpile and collection rate are direct tracker fields when exposed.
- Iron is shown as `n/a` when Terrazine fields are absent, rather than being silently treated as zero.
- Role and tech-lead labels are heuristic reads based on observed events, timings, resources, units, structures, and combat conversion.
"""


def make_match_embed(summary: ReplaySummary) -> discord.Embed:
    title = summary.map_name or "AoK Replay Analysis"
    colour = discord.Colour.green() if summary.parser_ok else discord.Colour.orange()
    embed = discord.Embed(title=title, colour=colour)
    embed.add_field(name="Duration", value=summary.duration_label(), inline=True)
    embed.add_field(name="Players", value=str(len(summary.players)) if summary.players else "unknown", inline=True)
    embed.add_field(name="Mode", value=summary.match_mode, inline=True)
    embed.add_field(name="Winner", value=summary.winner_label(), inline=True)
    embed.add_field(name="Parser", value="OK" if summary.parser_ok else "limited", inline=True)

    side_rosters = _side_roster_lines(summary)
    if side_rosters:
        embed.add_field(
            name="Side labels" if summary.match_mode == "Free-for-all" else "Team labels",
            value="\n".join(f"• {line}" for line in side_rosters[:8])[:1024],
            inline=False,
        )

    if summary.verdict:
        embed.add_field(name="Verdict", value=summary.verdict[:1024], inline=False)

    if summary.turning_points:
        embed.add_field(
            name="Turning point",
            value="\n".join(f"• {line}" for line in summary.turning_points[:2])[:1024],
            inline=False,
        )

    if summary.team_evaluations:
        # Keep the embed summary-first. The full numeric evidence lives in the Markdown attachment.
        embed.add_field(
            name="FFA/player evaluations" if summary.match_mode == "Free-for-all" else "Team evaluations",
            value="\n".join(f"• {line}" for line in summary.team_evaluations[:3 if summary.match_mode == "Free-for-all" else 2])[:1024],
            inline=False,
        )
    elif summary.teams:
        embed.add_field(
            name="FFA/player evaluations" if summary.match_mode == "Free-for-all" else "Team evaluations",
            value="\n".join(_team_line_summary(t, summary.match_mode) for t in summary.teams)[:1024],
            inline=False,
        )

    tech_economy_lines = _tech_economy_embed_lines(summary)
    if tech_economy_lines:
        embed.add_field(
            name="Technology + resources",
            value="\n".join(f"• {line}" for line in tech_economy_lines[:4])[:1024],
            inline=False,
        )

    if summary.animal_impact:
        embed.add_field(
            name="Player 15 / Animals",
            value="\n".join(f"• {line}" for line in summary.animal_impact[:4])[:1024],
            inline=False,
        )

    if summary.player_takeaways:
        embed.add_field(
            name="Most useful player takeaway",
            value="\n".join(f"• {line}" for line in summary.player_takeaways[:2])[:1024],
            inline=False,
        )

    embed_findings = _embed_key_findings(summary)
    if embed_findings:
        embed.add_field(
            name="Evidence highlights",
            value="\n".join(f"• {line}" for line in embed_findings[:5])[:1024],
            inline=False,
        )

    if summary.warnings:
        embed.add_field(name="Warnings", value="\n".join(summary.warnings[:3])[:1024], inline=False)

    return embed


def markdown_report(summary: ReplaySummary) -> str:
    tables = _build_report_tables(summary)

    if Environment is not None:
        env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
        env.filters["md"] = _md_cell
        template = env.from_string(REPORT_TEMPLATE)
        rendered = template.render(
            summary=summary,
            tables=tables,
            table=_markdown_table,
            ratio=_ratio,
            top_items=_top_items,
            left_time=_left_time,
            player_with_side=_player_with_side,
            player_table_groups=_build_player_table_groups(summary),
            timeline_table_groups=_build_timeline_table_groups(summary),
            players_by_combat=sorted(summary.players, key=lambda p: (p.kills, p.animal_kills, p.tech_score, p.units_born), reverse=True),
            timed_items=_timed_items,
            timed_items_with_age=_timed_items_with_age,
            age_timing_items=_age_timing_items,
            advanced_requirement_items=_advanced_requirement_items,
            resource_triplet=_resource_triplet,
            empty_labels={},
            tech_structure_labels=TECH_STRUCTURE_LABELS,
            unlock_labels=UNLOCK_LABELS,
            advanced_unit_labels=ADVANCED_UNIT_LABELS,
        )
        return rendered.strip() + "\n"

    # Fallback keeps the bot usable if an existing venv has not installed Jinja2 yet.
    lines: list[str] = []
    lines.append("# AoK Replay Analysis")
    lines.append("")
    lines.append(_markdown_table(
        ["Field", "Value"],
        [
            ["File", f"`{summary.source_path.name}`"],
            ["Map", summary.map_name or "Unknown"],
            ["Duration", summary.duration_label()],
            ["Match mode", summary.match_mode],
            ["Winning side", summary.winner_label()],
            ["Game version/build", summary.game_version or "Unknown"],
            ["Parser OK", summary.parser_ok],
            ["Report format", "compact table layout; install Jinja2 for template rendering"],
        ],
    ))
    lines.append("")

    if summary.verdict:
        lines.extend(["## Short verdict", "", summary.verdict, ""])
    _section(lines, "Turning point", summary.turning_points)
    _section(lines, "FFA/player evaluations" if summary.match_mode == "Free-for-all" else "Team evaluations", summary.team_evaluations)
    _section(lines, "Technology + economy evaluation", summary.tech_evaluations)
    _section(lines, "Player 15 / Animals impact", summary.animal_impact)
    _section(lines, "Most useful player takeaway", summary.player_takeaways)
    _section(lines, "Evidence highlights", summary.key_findings)
    _section(lines, "Match story notes", summary.match_story)

    if tables["side_overview"]:
        lines.extend(["## FFA/player side overview" if summary.match_mode == "Free-for-all" else "## Team overview", ""])
        lines.append(_markdown_table(["Side", "Result", "Style"], tables["side_overview"]))
        lines.extend(["", "## Side combat + activity", ""])
        lines.append(_markdown_table(["Side", "PvP K/L", "Animal K/D", "Units", "Cmds"], tables["side_combat"], right=[3, 4]))
        lines.extend(["", "## Side army / defense footprint", ""])
        lines.append(_markdown_table(["Side", "Static", "Walls/gates", "Castles", "Cavalry", "Ranged", "Infantry", "Mechanical"], tables["side_footprint"], right=[1, 2, 3, 4, 5, 6, 7]))
        lines.extend(["", "## Side technology overview", ""])
        lines.append(_markdown_table(["Side", "Age", "Tech score", "Tech structures", "Key unlocks", "Advanced unit types", "Mechanical K/L", "Trebs T/S/M-loss"], tables["side_tech"], right=[2, 3, 4, 5]))
        lines.extend(["", "## Side resource overview", ""])
        lines.append(_markdown_table(["Side", "Gold", "Wood", "Iron", "Gold rate", "Wood rate", "Iron rate", "Gathered estimate"], tables["side_resources"], right=[1, 2, 3, 4, 5, 6]))
        lines.append("")

    if summary.animal_stats:
        animal = summary.animal_stats
        lines.extend(["## Player 15 / Animals evidence", ""])
        lines.append(f"- **Animal K/D:** {animal.kills} kills caused / {animal.losses} animal deaths")
        lines.append(f"- **Animal units seen/born:** {animal.units_born}")
        lines.append(f"- **Most killed animal types:** {_top_items(animal.top_losses(10))}")
        lines.append(f"- **Animal units credited with kills:** {_top_items(animal.top_kill_units(10))}")
        lines.extend(["", "### Player vs Animals table", ""])
        lines.append(_markdown_table(["Player", "Side", "Animal kills", "Deaths to animals", "Animal K/D"], tables["animal_rows"], right=[2, 3, 4]))
        lines.append("")

    if summary.timeline_snapshots:
        lines.extend(["## Timeline snapshots", "", "These are cumulative 5-minute snapshots. They support the turning-point read but should be treated as replay-protocol evidence, not visual map observation.", ""])
        for group in _build_timeline_table_groups(summary):
            lines.extend([f"### {group['label']}", ""])
            lines.append(_markdown_table(["Time", "PvP K/L", "Units born", "Animal K/D"], group["rows"], right=[2]))
            lines.extend(["", f"### {group['label']} — technology + resources", ""])
            lines.append(_markdown_table(["Time", "Age", "Tech", "Mechanical K/L", "Gold", "Wood", "Iron", "Gold rate", "Wood rate", "Iron rate"], group["tech_resource_rows"], right=[2, 4, 5, 6, 7, 8, 9]))
            lines.append("")

    if summary.players:
        lines.extend(["## Player overview", ""])
        lines.append(_markdown_table(["Player", "Side", "Result", "Role read", "Left"], tables["player_overview"]))
        lines.extend(["", "## Player combat + activity", ""])
        for group in _build_player_table_groups(summary):
            lines.extend([f"### {group['label']}", ""])
            lines.append(_markdown_table(["Player", "PvP K/L", "Animal K/D", "Units", "Structures", "Cmds", "APM"], group["combat_rows"], right=[3, 4, 5, 6]))
            lines.append("")
        lines.extend(["## Player army profile", ""])
        for group in _build_player_table_groups(summary):
            lines.extend([f"### {group['label']}", ""])
            lines.append(_markdown_table(["Player", "Static", "Cavalry", "Ranged", "Infantry", "Mechanical", "Top units"], group["army_rows"], right=[1, 2, 3, 4, 5]))
            lines.append("")
        lines.extend(["## Player resource tracking", ""])
        for group in _build_player_table_groups(summary):
            lines.extend([f"### {group['label']}", ""])
            lines.append(_markdown_table(["Player", "Gold", "Wood", "Iron", "Gold rate", "Wood rate", "Iron rate", "Gathered estimate"], group["resource_rows"], right=[1, 2, 3, 4, 5, 6]))
            lines.append("")
        lines.extend(["## Player technology profiles", ""])
        for group in _build_player_table_groups(summary):
            lines.extend([f"### {group['label']}", ""])
            lines.append(_markdown_table(["Player", "Age", "Tech score", "Tech structures", "Key unlocks", "Advanced units", "Mechanical K/L", "Trebs T/S/M-loss"], group["tech_rows"], right=[2]))
            lines.append("")

    _section(lines, "Resource tracking notes", summary.resource_tracking_notes)
    _section(lines, "Technology inference notes", summary.tech_inference_notes)

    if summary.raw_event_counts:
        lines.extend(["## Raw event counts", ""])
        lines.append(_markdown_table(["Event type", "Count"], tables["raw_event_rows"], right=[1]))
        lines.append("")

    if summary.warnings:
        _section(lines, "Warnings", summary.warnings)

    lines.extend([
        "## Known limitations",
        "",
        "- This reads replay protocol events, not a video recording.",
        "- Player 15 is treated as Animals/Neutral because AoK assigns animals to that player slot.",
        "- PvP K/L excludes animal kills; animal K/D is tracked separately.",
        "- Exact age costs and hard prerequisite chains still need AoK map metadata or TwoDie confirmation; inferred relationships are labelled as such.",
        "- FFA/no-alliance games are split into one analysis side per player; team games still aggregate allied players.",
        "- Resource gathered/lost totals are score-value estimates; current stockpile and collection rate are direct tracker fields when exposed.",
        "- Iron is shown as `n/a` when Terrazine fields are absent, rather than being silently treated as zero.",
        "- Role and tech-lead labels are heuristic reads based on observed events, timings, resources, units, structures, and combat conversion.",
    ])
    return "\n".join(lines).strip() + "\n"


def save_markdown_report(summary: ReplaySummary, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_name = ''.join(ch if ch.isalnum() or ch in '._- ' else '_' for ch in summary.source_path.stem)
    path = reports_dir / f"{safe_name}.md"
    path.write_text(markdown_report(summary), encoding="utf-8")
    return path

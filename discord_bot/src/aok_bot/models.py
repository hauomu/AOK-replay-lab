from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PlayerStats:
    name: str
    team_id: int | None = None
    result: str | None = None
    apm: int | None = None
    commands: int = 0
    control_groups: int = 0
    camera_events: int = 0
    chat_messages: int = 0
    pings: int = 0
    kills: int = 0
    losses: int = 0
    units_born: int = 0
    structures_started: int = 0
    structures_done: int = 0
    static_defense: int = 0
    walls_gates: int = 0
    castles: int = 0
    cavalry_units: int = 0
    ranged_units: int = 0
    infantry_units: int = 0
    siege_units: int = 0
    economic_structures: int = 0
    upgrades: int = 0
    leave_time_seconds: int | None = None
    role_label: str | None = None
    unit_type_counts: dict[str, int] = field(default_factory=dict)
    structure_type_counts: dict[str, int] = field(default_factory=dict)
    unit_loss_counts: dict[str, int] = field(default_factory=dict)
    upgrade_type_counts: dict[str, int] = field(default_factory=dict)

    def kill_loss_ratio(self) -> float | None:
        if self.losses <= 0:
            return None
        return round(self.kills / self.losses, 3)

    def top_units(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.unit_type_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    def top_structures(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.structure_type_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


@dataclass
class TeamStats:
    team_id: int
    result: str | None = None
    players: list[str] = field(default_factory=list)
    kills: int = 0
    losses: int = 0
    units_born: int = 0
    commands: int = 0
    static_defense: int = 0
    walls_gates: int = 0
    castles: int = 0
    cavalry_units: int = 0
    ranged_units: int = 0
    infantry_units: int = 0
    siege_units: int = 0
    structures_done: int = 0
    upgrades: int = 0
    style_label: str | None = None

    def kill_loss_ratio(self) -> float | None:
        if self.losses <= 0:
            return None
        return round(self.kills / self.losses, 3)


@dataclass
class ReplaySummary:
    source_path: Path
    map_name: str | None = None
    duration_seconds: int | None = None
    game_version: str | None = None
    players: list[PlayerStats] = field(default_factory=list)
    teams: list[TeamStats] = field(default_factory=list)
    raw_event_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    parser_ok: bool = False
    match_story: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)

    def duration_label(self) -> str:
        if self.duration_seconds is None:
            return "unknown"
        minutes, seconds = divmod(int(self.duration_seconds), 60)
        return f"{minutes}:{seconds:02d}"

    def player_names(self) -> str:
        if not self.players:
            return "unknown"
        return ", ".join(p.name for p in self.players)

    def winner_label(self) -> str:
        winners = sorted({p.team_id for p in self.players if p.result == "Win" and p.team_id is not None})
        if winners:
            return ", ".join(f"Team {team}" for team in winners)
        return "Unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "map_name": self.map_name,
            "duration_seconds": self.duration_seconds,
            "duration_label": self.duration_label(),
            "game_version": self.game_version,
            "players": [p.__dict__ for p in self.players],
            "teams": [t.__dict__ for t in self.teams],
            "raw_event_counts": self.raw_event_counts,
            "warnings": self.warnings,
            "parser_ok": self.parser_ok,
            "match_story": self.match_story,
            "key_findings": self.key_findings,
        }

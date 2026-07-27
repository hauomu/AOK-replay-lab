from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


RESOURCE_CHANNELS = ("gold", "wood", "iron")
AGE_ORDER = {
    "Starting age": 0,
    "Dark Age": 1,
    "Feudal Age": 2,
    "Castle Age": 3,
    "Imperial Age": 4,
}


def _resource_dict() -> dict[str, int]:
    return {name: 0 for name in RESOURCE_CHANNELS}


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

    # Human-vs-human / team-combat kills. Animal kills are tracked separately so
    # the combat read does not get inflated by clearing neutral camps.
    kills: int = 0
    losses: int = 0

    # Player 15 / neutral-animal interaction stats.
    animal_kills: int = 0
    deaths_to_animals: int = 0

    units_born: int = 0
    structures_started: int = 0
    structures_done: int = 0
    static_defense: int = 0
    walls_gates: int = 0
    castles: int = 0
    cavalry_units: int = 0
    ranged_units: int = 0
    infantry_units: int = 0

    # Retained for database/report compatibility. v1.0 now fills this with the
    # exact AoK mechanical allowlist rather than loose "Cannon" substring logic.
    siege_units: int = 0
    mechanical_units: int = 0
    mechanical_kills: int = 0
    mechanical_losses: int = 0
    trebuchets_total: int = 0
    trebuchets_sieged: int = 0
    trebuchet_mobile_deaths: int = 0
    trebuchet_sieged_deaths: int = 0
    trebuchet_sieged_kills: int = 0

    economic_structures: int = 0
    upgrades: int = 0
    leave_time_seconds: int | None = None
    role_label: str | None = None

    unit_type_counts: dict[str, int] = field(default_factory=dict)
    structure_type_counts: dict[str, int] = field(default_factory=dict)
    unit_loss_counts: dict[str, int] = field(default_factory=dict)
    unit_kill_counts: dict[str, int] = field(default_factory=dict)
    upgrade_type_counts: dict[str, int] = field(default_factory=dict)

    mechanical_unit_counts: dict[str, int] = field(default_factory=dict)
    mechanical_loss_counts: dict[str, int] = field(default_factory=dict)
    mechanical_kill_counts: dict[str, int] = field(default_factory=dict)

    # Inferred tech-tree state. Timings are replay seconds from game start.
    age_timing_seconds: dict[str, int] = field(default_factory=dict)
    tech_structure_first_seconds: dict[str, int] = field(default_factory=dict)
    tech_structure_age_labels: dict[str, str] = field(default_factory=dict)
    tech_upgrade_first_seconds: dict[str, int] = field(default_factory=dict)
    tech_upgrade_age_labels: dict[str, str] = field(default_factory=dict)
    tech_unlock_first_seconds: dict[str, int] = field(default_factory=dict)
    advanced_unit_first_seconds: dict[str, int] = field(default_factory=dict)
    advanced_unit_age_labels: dict[str, str] = field(default_factory=dict)
    tech_score: int = 0

    # AoK labels: Gold=SC2 minerals, Wood=SC2 vespene, Iron=SC2 terrazine.
    # Current/rate are the latest observed tracker values. Gathered/lost are
    # score-value estimates derived from SPlayerStatsEvent fields.
    resource_current: dict[str, int] = field(default_factory=_resource_dict)
    resource_collection_rate: dict[str, int] = field(default_factory=_resource_dict)
    resource_peak_current: dict[str, int] = field(default_factory=_resource_dict)
    resource_peak_collection_rate: dict[str, int] = field(default_factory=_resource_dict)
    resource_gathered_estimate: dict[str, int] = field(default_factory=_resource_dict)
    resource_lost_value: dict[str, int] = field(default_factory=_resource_dict)
    resource_samples: int = 0

    def kill_loss_ratio(self) -> float | None:
        if self.losses <= 0:
            return None
        return round(self.kills / self.losses, 3)

    def animal_kill_loss_ratio(self) -> float | None:
        if self.deaths_to_animals <= 0:
            return None
        return round(self.animal_kills / self.deaths_to_animals, 3)

    def top_units(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.unit_type_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    def top_structures(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.structure_type_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    def top_losses(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.unit_loss_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    def top_kill_units(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.unit_kill_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    def current_age(self) -> str:
        if not self.age_timing_seconds:
            return "Starting age"
        return max(
            self.age_timing_seconds,
            key=lambda age: (AGE_ORDER.get(age, -1), self.age_timing_seconds.get(age, -1)),
        )

    def age_stage(self) -> int:
        return AGE_ORDER.get(self.current_age(), 0)

    def resource_total_current(self) -> int:
        return sum(int(self.resource_current.get(key, 0) or 0) for key in RESOURCE_CHANNELS)

    def top_mechanical_units(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.mechanical_unit_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


@dataclass
class TeamStats:
    team_id: int
    label: str | None = None
    result: str | None = None
    players: list[str] = field(default_factory=list)
    kills: int = 0
    losses: int = 0
    animal_kills: int = 0
    deaths_to_animals: int = 0
    units_born: int = 0
    commands: int = 0
    static_defense: int = 0
    walls_gates: int = 0
    castles: int = 0
    cavalry_units: int = 0
    ranged_units: int = 0
    infantry_units: int = 0
    siege_units: int = 0
    mechanical_units: int = 0
    mechanical_kills: int = 0
    mechanical_losses: int = 0
    trebuchets_total: int = 0
    trebuchets_sieged: int = 0
    trebuchet_mobile_deaths: int = 0
    trebuchet_sieged_deaths: int = 0
    trebuchet_sieged_kills: int = 0
    structures_done: int = 0
    upgrades: int = 0
    style_label: str | None = None

    age_timing_seconds: dict[str, int] = field(default_factory=dict)
    tech_structure_first_seconds: dict[str, int] = field(default_factory=dict)
    tech_structure_age_labels: dict[str, str] = field(default_factory=dict)
    tech_upgrade_first_seconds: dict[str, int] = field(default_factory=dict)
    tech_unlock_first_seconds: dict[str, int] = field(default_factory=dict)
    advanced_unit_first_seconds: dict[str, int] = field(default_factory=dict)
    tech_score: int = 0

    resource_current: dict[str, int] = field(default_factory=_resource_dict)
    resource_collection_rate: dict[str, int] = field(default_factory=_resource_dict)
    resource_peak_current: dict[str, int] = field(default_factory=_resource_dict)
    resource_peak_collection_rate: dict[str, int] = field(default_factory=_resource_dict)
    resource_gathered_estimate: dict[str, int] = field(default_factory=_resource_dict)
    resource_lost_value: dict[str, int] = field(default_factory=_resource_dict)

    def kill_loss_ratio(self) -> float | None:
        if self.losses <= 0:
            return None
        return round(self.kills / self.losses, 3)

    def animal_kill_loss_ratio(self) -> float | None:
        if self.deaths_to_animals <= 0:
            return None
        return round(self.animal_kills / self.deaths_to_animals, 3)

    def current_age(self) -> str:
        if not self.age_timing_seconds:
            return "Starting age"
        return max(
            self.age_timing_seconds,
            key=lambda age: (AGE_ORDER.get(age, -1), self.age_timing_seconds.get(age, -1)),
        )

    def age_stage(self) -> int:
        return AGE_ORDER.get(self.current_age(), 0)


@dataclass
class ReplaySummary:
    source_path: Path
    match_mode: str = "Team"
    map_name: str | None = None
    duration_seconds: int | None = None
    game_version: str | None = None
    players: list[PlayerStats] = field(default_factory=list)
    teams: list[TeamStats] = field(default_factory=list)
    animal_stats: PlayerStats | None = None
    timeline_snapshots: list[dict[str, Any]] = field(default_factory=list)
    raw_event_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    parser_ok: bool = False

    # v1.0 resource/tech provenance.
    resource_channels_seen: list[str] = field(default_factory=list)
    resource_tracking_notes: list[str] = field(default_factory=list)
    tech_inference_notes: list[str] = field(default_factory=list)
    tech_evaluations: list[str] = field(default_factory=list)

    # Summary-first analysis fields used by /aok_analyze.
    verdict: str | None = None
    turning_points: list[str] = field(default_factory=list)
    team_evaluations: list[str] = field(default_factory=list)
    animal_impact: list[str] = field(default_factory=list)
    player_takeaways: list[str] = field(default_factory=list)
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
        if self.match_mode in {"Free-for-all", "Duel"}:
            winner_names = [p.name for p in self.players if p.result == "Win"]
            if winner_names:
                return ", ".join(winner_names)

        if self.teams:
            def side_name(team: TeamStats) -> str:
                base = team.label or f"Team {team.team_id}"
                if self.match_mode not in {"Free-for-all", "Duel"} and team.players:
                    return f"{base} ({', '.join(team.players)})"
                return base

            winners = [side_name(t) for t in self.teams if t.result == "Win"]
            if winners:
                return ", ".join(winners)
            if self.match_mode == "Free-for-all":
                leader = max(
                    self.teams,
                    key=lambda t: (
                        t.kills - t.losses,
                        t.kill_loss_ratio() or 0,
                        t.tech_score,
                        t.resource_gathered_estimate.get("gold", 0)
                        + t.resource_gathered_estimate.get("wood", 0)
                        + t.resource_gathered_estimate.get("iron", 0),
                        t.units_born,
                        t.commands,
                    ),
                    default=None,
                )
                if leader is not None:
                    return f"Not recorded; likely leader: {side_name(leader)}"

        winners = sorted({p.team_id for p in self.players if p.result == "Win" and p.team_id is not None})
        if winners:
            return ", ".join(f"Team {team}" for team in winners)
        return "Unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "match_mode": self.match_mode,
            "map_name": self.map_name,
            "duration_seconds": self.duration_seconds,
            "duration_label": self.duration_label(),
            "game_version": self.game_version,
            "players": [p.__dict__ for p in self.players],
            "teams": [t.__dict__ for t in self.teams],
            "animal_stats": self.animal_stats.__dict__ if self.animal_stats else None,
            "timeline_snapshots": self.timeline_snapshots,
            "raw_event_counts": self.raw_event_counts,
            "warnings": self.warnings,
            "parser_ok": self.parser_ok,
            "resource_channels_seen": self.resource_channels_seen,
            "resource_tracking_notes": self.resource_tracking_notes,
            "tech_inference_notes": self.tech_inference_notes,
            "tech_evaluations": self.tech_evaluations,
            "verdict": self.verdict,
            "turning_points": self.turning_points,
            "team_evaluations": self.team_evaluations,
            "animal_impact": self.animal_impact,
            "player_takeaways": self.player_takeaways,
            "match_story": self.match_story,
            "key_findings": self.key_findings,
        }

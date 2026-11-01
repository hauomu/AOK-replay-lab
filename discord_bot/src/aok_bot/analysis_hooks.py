"""Summary-only replay analysis modes; these hooks never read replay files."""
from __future__ import annotations

from typing import Any, Callable

from .models import PlayerStats, ReplaySummary


Analysis = dict[str, Any]


def _result(summary: ReplaySummary, mode: str, items: list[dict[str, Any]], limitations: list[str]) -> Analysis:
    warnings = list(summary.warnings)
    if summary.parser_ok and len(summary.teams) < 2:
        warnings.append("Fewer than two sides were identified; this may be an incomplete or lobby recording.")
    if not summary.parser_ok:
        warnings.append("Replay parsing did not complete; no analysis advice is available.")
        return {"mode": mode, "available": False, "warnings": warnings, "items": [], "limitations": limitations}
    return {"mode": mode, "available": True, "warnings": warnings, "items": items, "limitations": limitations}


def _item(subject: str, observations: list[str], review_questions: list[str] | None = None) -> dict[str, Any]:
    return {"subject": subject, "observations": observations, "review_questions": review_questions or []}


def _role_observation(player: PlayerStats) -> list[str]:
    return [f"Heuristic role label: {player.role_label}."] if player.role_label else []


def analyze_stats(summary: ReplaySummary) -> Analysis:
    items = []
    for player in summary.players:
        observations = [f"PvP kills: {player.kills}; PvP losses: {player.losses}.",
                        f"Animal kills: {player.animal_kills}; deaths to animals: {player.deaths_to_animals}."]
        observations.extend(_role_observation(player))
        items.append(_item(player.name, observations))
    if summary.animal_stats:
        animal = summary.animal_stats
        items.append(_item("Animals / neutral", [f"Kills caused: {animal.kills}; animal deaths: {animal.losses}.",
                                                  f"Units seen or born: {animal.units_born}."]))
    return _result(summary, "stats", items, [
        "Role labels and match mode are inferred; roles are heuristic.",
        "Unit counts do not measure value, and APM does not measure decision quality.",
    ])


def analyze_coaching(summary: ReplaySummary) -> Analysis:
    items = []
    for player in summary.players:
        observations, questions = [], []
        if player.losses > player.kills:
            observations.append(f"Observed attrition: {player.losses} PvP losses versus {player.kills} PvP kills.")
            questions.append("Which engagements account for the losses, and what was visible before committing?")
        if player.animal_kills or player.deaths_to_animals:
            observations.append(f"Animal encounters recorded: {player.animal_kills} kills and {player.deaths_to_animals} deaths.")
            questions.append("Were the animal encounters intentional, and were any units exposed while taking them?")
        if player.commands:
            observations.append(f"Recorded command activity: {player.commands} commands" + (f" ({player.apm} APM estimate)." if player.apm is not None else "."))
            questions.append("Which commands changed the game state, and where could commands have been more purposeful?")
        if player.leave_time_seconds is not None:
            observations.append(f"Recorded departure time: {player.leave_time_seconds} seconds.")
            questions.append("What was happening around the recorded departure time?")
        if observations:
            items.append(_item(player.name, observations, questions))
    return _result(summary, "coaching", items, [
        "Questions refer only to metrics present in the parsed summary; event-level causes are not established.",
        "Unit counts do not measure value, and APM does not measure decision quality.",
    ])


def analyze_team(summary: ReplaySummary) -> Analysis:
    if len(summary.teams) < 2:
        result = _result(summary, "team", [], ["At least two identified sides are needed for a team comparison."])
        result["available"] = False
        result["warnings"].append("Team comparison unavailable: opposing-side evidence is missing.")
        return result
    items = []
    teams = summary.teams
    if teams:
        observations = []
        for team in teams:
            label = team.label or f"Side {team.team_id}"
            players = [p for p in summary.players if p.team_id == team.team_id]
            roles: dict[str, int] = {}
            for player in players:
                if player.role_label:
                    roles[player.role_label] = roles.get(player.role_label, 0) + 1
            role_text = ", ".join(f"{name}: {count}" for name, count in sorted(roles.items())) or "no role labels recorded"
            observations.append(f"{label}: {team.kills} PvP kills, {team.losses} PvP losses; role distribution: {role_text}.")
        items.append(_item("Side comparison", observations))
    timed = [p.leave_time_seconds for p in summary.players if p.leave_time_seconds is not None]
    if len(timed) >= 2:
        items.append(_item("Departure timing", [f"Recorded player departure times span {min(timed)}–{max(timed)} seconds (spread {max(timed) - min(timed)} seconds)."]))
    limitations = ["Role labels and match mode are inferred; role distribution uses heuristic labels.",
                   "Unit counts do not measure value, and APM does not measure decision quality."]
    if summary.match_mode == "Free-for-all":
        limitations.append("FFA entries are individual sides; this comparison does not infer team coordination.")
    return _result(summary, "team", items, limitations)


ANALYSIS_HOOKS: dict[str, Callable[[ReplaySummary], Analysis]] = {
    "stats": analyze_stats,
    "coaching": analyze_coaching,
    "team": analyze_team,
}


def analyze(summary: ReplaySummary, mode: str = "stats") -> Analysis:
    try:
        hook = ANALYSIS_HOOKS[mode]
    except (KeyError, TypeError):
        raise ValueError(f"Unsupported analysis mode: {mode!r}") from None
    return hook(summary)

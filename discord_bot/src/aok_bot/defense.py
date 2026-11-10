"""Defensive structures and their denial, from replay tracker events.

Tracks castles, guard towers, watch towers (outposts: vision, no attack),
walls, gates and barricades per player:

- built: placed and completed; standing at the end; lost to enemies after
  completion (removed by the owner counts as neither standing nor lost);
- denied: cancelled by the owner, destroyed by an enemy while still being
  built, or never finished by the end of the game;
- builder kills: an enemy kills one of the owner's workers right next to a
  site that is still under construction. The replay does not say which worker
  was building or when building pauses, so this is an inference ("builder
  likely killed"). Its outcome is followed: the build resumed and finished
  (with its extra build time), was cancelled, was destroyed (straight away or
  in a later push), or never finished;
- denial inflicted: the same events credited to the enemy who caused them.

Cancelled and destroyed are exact: the replay records who killed a structure
(no killer, or the owner, means it was cancelled or removed).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Callable

DEFENSE_KINDS = ("Castle", "Guard tower", "Watch tower", "Wall", "Gate", "Barricade")
WORKER_HINTS = ("Peasant", "Villager")
# A builder stands next to its site; walls are thin, castles are big.
BUILDER_RADIUS = {"Castle": 5.0, "Guard tower": 3.5, "Watch tower": 3.5}
DEFAULT_BUILDER_RADIUS = 3.0
# A site destroyed this long after its builder died fell to a later push.
LATER_PUSH_SECONDS = 20
NOTABLE_KINDS = ("Castle", "Guard tower", "Watch tower")
MAX_EVENTS = 12


def defense_kind(unit_type: str) -> str | None:
    name = unit_type.lower()
    if "castle" in name:
        return "Castle"
    if "guardtower" in name:
        return "Guard tower"
    if "watchtower" in name or "outpost" in name or "watchpost" in name:
        return "Watch tower"
    if "gate" in name:
        return "Gate"
    if "wall" in name:
        return "Wall"
    if "barricade" in name:
        return "Barricade"
    return None


def _is_worker(unit_type: str) -> bool:
    return any(hint.lower() in unit_type.lower() for hint in WORKER_HINTS)


@dataclass
class Site:
    pid: int
    kind: str
    unit_type: str
    start: int
    x: float
    y: float
    value: int
    done_at: int | None = None
    died_at: int | None = None
    killer: int | None = None
    builder_kills: list[tuple[int, int]] = field(default_factory=list)  # (seconds, killer pid)


def _tag(event: dict[str, Any]) -> tuple[int, int] | None:
    index, recycle = event.get("m_unitTagIndex"), event.get("m_unitTagRecycle")
    if index is None or recycle is None:
        return None
    return int(index), int(recycle)


class DefenseTracker:
    """Feed it every tracker event in order, then call finish()."""

    def __init__(self, team_of: Callable[[int], int | None], value_of: Callable[[str], int]):
        self._team_of = team_of
        self._value_of = value_of
        self.sites: dict[tuple[int, int], Site] = {}
        self._workers: dict[tuple[int, int], int] = {}
        self._standing_value: dict[int, int] = {}

    def hostile(self, a: int | None, b: int | None) -> bool:
        if not a or not b or a == b:
            return False
        ta, tb = self._team_of(a), self._team_of(b)
        return ta is None or tb is None or ta != tb

    def standing_value(self, pids: list[int]) -> int:
        return sum(self._standing_value.get(pid, 0) for pid in pids)

    def _complete(self, site: Site, seconds: int) -> None:
        site.done_at = seconds
        self._standing_value[site.pid] = self._standing_value.get(site.pid, 0) + site.value

    def on_event(self, event: dict[str, Any], seconds: int) -> None:
        name = event.get("_event", "")
        tag = _tag(event)
        if tag is None:
            return
        if name.endswith("SUnitInitEvent") or name.endswith("SUnitBornEvent"):
            raw = event.get("m_unitTypeName")
            unit_type = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw or "")
            pid = int(event.get("m_controlPlayerId") or event.get("m_upkeepPlayerId") or 0)
            if not pid:
                return
            kind = defense_kind(unit_type)
            if kind:
                site = Site(pid, kind, unit_type, seconds, float(event.get("m_x") or 0), float(event.get("m_y") or 0),
                            self._value_of(unit_type))
                self.sites[tag] = site
                if name.endswith("SUnitBornEvent"):  # placed whole (map or trigger): already complete
                    self._complete(site, seconds)
            elif name.endswith("SUnitBornEvent") and _is_worker(unit_type):
                self._workers[tag] = pid
        elif name.endswith("SUnitDoneEvent"):
            site = self.sites.get(tag)
            if site and site.done_at is None and site.died_at is None:
                self._complete(site, seconds)
        elif name.endswith("SUnitDiedEvent"):
            killer = event.get("m_killerPlayerId")
            killer = int(killer) if killer is not None else None
            site = self.sites.get(tag)
            if site and site.died_at is None:
                site.died_at, site.killer = seconds, killer
                if site.done_at is not None:
                    self._standing_value[site.pid] = max(0, self._standing_value.get(site.pid, 0) - site.value)
                return
            owner = self._workers.pop(tag, None)
            if owner and self.hostile(owner, killer):
                self._builder_killed(owner, killer, seconds, float(event.get("m_x") or 0), float(event.get("m_y") or 0))

    def _builder_killed(self, owner: int, killer: int, seconds: int, x: float, y: float) -> None:
        best, best_distance = None, None
        for site in self.sites.values():
            if site.pid != owner or site.done_at is not None or site.died_at is not None or site.start > seconds:
                continue
            distance = math.hypot(site.x - x, site.y - y)
            if distance <= BUILDER_RADIUS.get(site.kind, DEFAULT_BUILDER_RADIUS) and (best_distance is None or distance < best_distance):
                best, best_distance = site, distance
        if best is not None:
            best.builder_kills.append((seconds, killer))

    def finish(self, players: list[Any], pid_to_player: Callable[[int], Any]) -> list[dict[str, Any]]:
        """Write per-player stats onto the players; return the notable denial events."""
        for player in players:
            player.defense = {}
            player.defense_builder_kills = {}
            player.denial_inflicted = {}
            player.defense_value_standing = 0
        typical: dict[str, float] = {}
        clean: dict[str, list[int]] = {}
        for site in self.sites.values():
            if site.done_at is not None and not site.builder_kills and site.done_at > site.start:
                clean.setdefault(site.unit_type, []).append(site.done_at - site.start)
        for unit_type, durations in clean.items():
            typical[unit_type] = median(durations)

        events: list[dict[str, Any]] = []
        for site in sorted(self.sites.values(), key=lambda s: s.start):
            owner = pid_to_player(site.pid)
            if owner is None:
                continue
            counts = owner.defense.setdefault(site.kind, {})
            bump = lambda key, n=1: counts.__setitem__(key, counts.get(key, 0) + n)  # noqa: E731
            hostile_kill = self.hostile(site.pid, site.killer)
            attacker = pid_to_player(site.killer) if hostile_kill and site.killer else None
            bump("placed")
            if site.done_at is not None:
                bump("completed")
                if site.died_at is None:
                    bump("standing")
                    owner.defense_value_standing += site.value
                elif hostile_kill:
                    bump("lost")
                    if attacker is not None:
                        _add(attacker.denial_inflicted, "defenses_destroyed")
                outcome = "completed"
            elif site.died_at is None:
                bump("unfinished")
                outcome = "never finished"
            elif hostile_kill:
                bump("destroyed_building")
                if attacker is not None:
                    _add(attacker.denial_inflicted, "builds_destroyed")
                outcome = "destroyed while being built"
            else:
                bump("cancelled")
                outcome = "cancelled"

            if not site.builder_kills:
                if outcome == "destroyed while being built" and site.kind in NOTABLE_KINDS:
                    events.append(_event(site, owner, attacker, outcome, None))
                continue
            first_kill, first_killer = site.builder_kills[0]
            for _, killer_pid in site.builder_kills:
                credited = pid_to_player(killer_pid)
                if credited is not None:
                    _add(credited.denial_inflicted, "builders_killed")
            stats = owner.defense_builder_kills
            _add(stats, "sites")
            _add(stats, "workers", len(site.builder_kills))
            delay = None
            if outcome == "completed":
                _add(stats, "resumed")
                expected = typical.get(site.unit_type)
                if expected is not None:
                    delay = max(0, int(round((site.done_at - site.start) - expected)))
                    _add(stats, "delay_seconds", delay)
            elif outcome == "destroyed while being built":
                later = site.died_at - first_kill >= LATER_PUSH_SECONDS
                _add(stats, "destroyed_later" if later else "destroyed")
                if later:
                    outcome = "stalled, then destroyed in a later push"
            elif outcome == "cancelled":
                _add(stats, "cancelled")
            else:
                _add(stats, "never_finished")
            if site.kind in NOTABLE_KINDS or outcome != "completed":
                events.append(_event(site, owner, attacker or pid_to_player(first_killer), outcome, delay))

        # Castles and towers first, then by time; keep the list short.
        order = {kind: i for i, kind in enumerate(DEFENSE_KINDS)}
        events.sort(key=lambda e: (order.get(e["kind"], 9), e["start"]))
        events = sorted(events[:MAX_EVENTS], key=lambda e: e["start"])
        return events


def _add(mapping: dict[str, int], key: str, amount: int = 1) -> None:
    mapping[key] = mapping.get(key, 0) + amount


def _event(site: Site, owner: Any, attacker: Any, outcome: str, delay: int | None) -> dict[str, Any]:
    return {
        "kind": site.kind,
        "owner": owner.name,
        "attacker": attacker.name if attacker is not None else None,
        "start": site.start,
        "builder_killed_at": site.builder_kills[0][0] if site.builder_kills else None,
        "workers_killed": len(site.builder_kills),
        "end": site.done_at if site.done_at is not None else site.died_at,
        "outcome": outcome,
        "delay": delay,
    }


def side_totals(players: list[Any]) -> dict[str, Any]:
    """Sum the per-player defense stats for a side."""
    kinds: dict[str, dict[str, int]] = {}
    builder: dict[str, int] = {}
    inflicted: dict[str, int] = {}
    value = 0
    for p in players:
        for kind, counts in (getattr(p, "defense", None) or {}).items():
            target = kinds.setdefault(kind, {})
            for key, n in counts.items():
                target[key] = target.get(key, 0) + n
        for key, n in (getattr(p, "defense_builder_kills", None) or {}).items():
            builder[key] = builder.get(key, 0) + n
        for key, n in (getattr(p, "denial_inflicted", None) or {}).items():
            inflicted[key] = inflicted.get(key, 0) + n
        value += int(getattr(p, "defense_value_standing", 0) or 0)
    return {"kinds": kinds, "builder": builder, "inflicted": inflicted, "value": value}


def denied_count(kinds: dict[str, dict[str, int]]) -> int:
    return sum(c.get("cancelled", 0) + c.get("destroyed_building", 0) + c.get("unfinished", 0) for c in kinds.values())


def _kind_list(kinds: dict[str, dict[str, int]], key: str, only: tuple[str, ...] = NOTABLE_KINDS) -> str:
    parts = [f"{kinds[k][key]} {k.lower()}{'s' if kinds[k][key] != 1 else ''}"
             for k in only if kinds.get(k, {}).get(key)]
    return ", ".join(parts) or "none"


def defense_findings(summary: Any) -> list[str]:
    """Plain-language map-control and denial reads for the report and embed."""
    players = [p for p in summary.players if getattr(p, "defense", None) or getattr(p, "denial_inflicted", None)]
    if not players:
        return []
    lines: list[str] = []
    last = summary.economy_series[-1]["teams"] if summary.economy_series else {}
    if summary.teams and summary.match_mode != "Free-for-all":
        for team in summary.teams:
            members = [p for p in summary.players if p.team_id == team.team_id]
            totals = side_totals(members)
            if not totals["kinds"]:
                continue
            army = (last.get(str(team.team_id)) or {}).get("army_value")
            versus = f"; army alive {army}" if army is not None else ""
            lines.append(
                f"{team.label or f'Team {team.team_id}'} ended holding {_kind_list(totals['kinds'], 'standing')} "
                f"(defense worth {totals['value']}{versus}).")

    def standing_key(p: Any) -> tuple[int, int]:
        kinds = p.defense or {}
        return (sum(kinds.get(k, {}).get("standing", 0) for k in NOTABLE_KINDS), p.defense_value_standing)

    holder = max(summary.players, key=standing_key, default=None)
    if holder is not None and standing_key(holder)[0] > 0:
        lines.append(f"Strongest map-control footprint: {holder.name}, holding {_kind_list(holder.defense, 'standing')} "
                     f"at the end (built {_kind_list(holder.defense, 'completed')}).")

    denier = max(summary.players, key=lambda p: (sum((p.denial_inflicted or {}).values()), p.name), default=None)
    if denier is not None and denier.denial_inflicted:
        d = denier.denial_inflicted
        lines.append(f"Most denial: {denier.name} destroyed {d.get('defenses_destroyed', 0)} enemy defenses, "
                     f"{d.get('builds_destroyed', 0)} still under construction, and likely killed {d.get('builders_killed', 0)} builders at defense sites.")

    def denied_of(p: Any) -> int:
        return denied_count(p.defense or {})

    pressured = max(summary.players, key=lambda p: (denied_of(p), p.name), default=None)
    if pressured is not None and denied_of(pressured):
        kinds = pressured.defense
        placed = sum(c.get("placed", 0) for c in kinds.values())
        cancelled = sum(c.get("cancelled", 0) for c in kinds.values())
        destroyed = sum(c.get("destroyed_building", 0) for c in kinds.values())
        unfinished = sum(c.get("unfinished", 0) for c in kinds.values())
        lines.append(f"Most defenses denied: {pressured.name} lost {denied_of(pressured)} of {placed} placed before completion "
                     f"({destroyed} destroyed while being built, {cancelled} cancelled, {unfinished} never finished).")

    builder = side_totals(summary.players)["builder"]
    if builder.get("sites"):
        resumed = builder.get("resumed", 0)
        delay = f", on average {round(builder.get('delay_seconds', 0) / resumed)} s late" if resumed and builder.get("delay_seconds") else ""
        lines.append(
            f"Builder kills (inferred): {builder['sites']} defense sites had a builder likely killed; "
            f"{resumed} resumed and finished{delay}, {builder.get('cancelled', 0)} cancelled, "
            f"{builder.get('destroyed', 0)} destroyed on the spot, {builder.get('destroyed_later', 0)} destroyed in a later push, "
            f"{builder.get('never_finished', 0)} never finished.")
    return lines

from __future__ import annotations

from pathlib import Path

import discord

from .models import PlayerStats, ReplaySummary, TeamStats


def _ratio(kills: int, losses: int) -> str:
    if losses <= 0:
        return "N/A"
    return f"{kills / losses:.2f}"


def _leave_label(seconds: int | None) -> str:
    if seconds is None:
        return ""
    m, s = divmod(int(seconds), 60)
    return f" left {m}:{s:02d}"


def _top_items(items: list[tuple[str, int]], empty: str = "none") -> str:
    if not items:
        return empty
    return ", ".join(f"{name}×{count}" for name, count in items)


def _team_line(team: TeamStats) -> str:
    result = f" {team.result}" if team.result else ""
    return (
        f"**Team {team.team_id}{result}** — {team.style_label or 'Unknown style'}; "
        f"K/L **{team.kills}/{team.losses}** ({_ratio(team.kills, team.losses)}), "
        f"units **{team.units_born}**, static defense **{team.static_defense}**, "
        f"cavalry **{team.cavalry_units}**, ranged **{team.ranged_units}**, siege **{team.siege_units}**"
    )


def _player_line(player: PlayerStats) -> str:
    top_units = _top_items(player.top_units(3))
    return (
        f"**{player.name}** — {player.role_label or 'Mixed/support'}; "
        f"K/L {player.kills}/{player.losses} ({_ratio(player.kills, player.losses)}), "
        f"units {player.units_born}, APM {player.apm if player.apm is not None else 'N/A'}, "
        f"top: {top_units}{_leave_label(player.leave_time_seconds)}"
    )


def make_match_embed(summary: ReplaySummary) -> discord.Embed:
    title = summary.map_name or "AoK Replay Analysis"
    colour = discord.Colour.green() if summary.parser_ok else discord.Colour.orange()
    embed = discord.Embed(title=title, colour=colour)
    embed.add_field(name="Duration", value=summary.duration_label(), inline=True)
    embed.add_field(name="Players", value=str(len(summary.players)) if summary.players else "unknown", inline=True)
    embed.add_field(name="Winner", value=summary.winner_label(), inline=True)
    embed.add_field(name="Parser", value="OK" if summary.parser_ok else "limited", inline=True)

    if summary.key_findings:
        embed.add_field(
            name="Key findings",
            value="\n".join(f"• {line}" for line in summary.key_findings[:5])[:1024],
            inline=False,
        )

    if summary.teams:
        embed.add_field(
            name="Team read",
            value="\n".join(_team_line(t) for t in summary.teams)[:1024],
            inline=False,
        )

    if summary.players:
        ordered = sorted(summary.players, key=lambda p: (p.kills, p.units_born, p.commands), reverse=True)
        embed.add_field(
            name="Player roles / snapshots",
            value="\n".join(_player_line(p) for p in ordered[:8])[:1024],
            inline=False,
        )

    if summary.match_story:
        embed.add_field(
            name="Match story",
            value="\n".join(f"• {line}" for line in summary.match_story[:4])[:1024],
            inline=False,
        )

    if summary.warnings:
        embed.add_field(name="Warnings", value="\n".join(summary.warnings[:3])[:1024], inline=False)

    return embed


def markdown_report(summary: ReplaySummary) -> str:
    lines: list[str] = []
    lines.append("# AoK Replay Report")
    lines.append("")
    lines.append(f"**File:** `{summary.source_path.name}`")
    lines.append(f"**Map:** {summary.map_name or 'Unknown'}")
    lines.append(f"**Duration:** {summary.duration_label()}")
    lines.append(f"**Winning side:** {summary.winner_label()}")
    lines.append(f"**Game version/build:** {summary.game_version or 'Unknown'}")
    lines.append(f"**Parser OK:** {summary.parser_ok}")
    lines.append("")

    if summary.key_findings:
        lines.append("## Key findings")
        lines.append("")
        for finding in summary.key_findings:
            lines.append(f"- {finding}")
        lines.append("")

    if summary.match_story:
        lines.append("## Match story")
        lines.append("")
        for item in summary.match_story:
            lines.append(f"- {item}")
        lines.append("")

    if summary.teams:
        lines.append("## Team comparison")
        lines.append("")
        lines.append("| Team | Result | Players | Style | Kills | Losses | K/L | Units | Static defense | Walls/gates | Castles | Cavalry | Ranged | Infantry | Siege |")
        lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for t in summary.teams:
            lines.append(
                f"| {t.team_id} | {t.result or ''} | {', '.join(t.players)} | {t.style_label or ''} | "
                f"{t.kills} | {t.losses} | {_ratio(t.kills, t.losses)} | {t.units_born} | "
                f"{t.static_defense} | {t.walls_gates} | {t.castles} | {t.cavalry_units} | "
                f"{t.ranged_units} | {t.infantry_units} | {t.siege_units} |"
            )
        lines.append("")

    if summary.players:
        lines.append("## Player table")
        lines.append("")
        lines.append("| Player | Team | Result | Role read | APM | Cmds | Ctrl groups | Kills | Losses | K/L | Units | Static def. | Cavalry | Ranged | Infantry | Siege | Left |")
        lines.append("|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for p in sorted(summary.players, key=lambda p: (p.team_id if p.team_id is not None else 99, -p.kills)):
            left = _leave_label(p.leave_time_seconds).replace(" left ", "")
            lines.append(
                f"| {p.name} | {p.team_id if p.team_id is not None else ''} | {p.result or ''} | {p.role_label or ''} | "
                f"{p.apm if p.apm is not None else ''} | {p.commands} | {p.control_groups} | "
                f"{p.kills} | {p.losses} | {_ratio(p.kills, p.losses)} | {p.units_born} | "
                f"{p.static_defense} | {p.cavalry_units} | {p.ranged_units} | {p.infantry_units} | {p.siege_units} | {left} |"
            )
        lines.append("")

        lines.append("## Player composition detail")
        lines.append("")
        for p in sorted(summary.players, key=lambda p: p.kills, reverse=True):
            lines.append(f"### {p.name}")
            lines.append("")
            lines.append(f"- **Role read:** {p.role_label or 'Unknown'}")
            lines.append(f"- **Combat:** {p.kills} kills / {p.losses} losses, K/L {_ratio(p.kills, p.losses)}")
            lines.append(f"- **Activity:** {p.commands} commands, {p.control_groups} control-group events, {p.pings} pings, {p.chat_messages} chat messages")
            lines.append(f"- **Production:** {p.units_born} units born, {p.structures_done} completed structures, {p.upgrades} upgrades")
            lines.append(f"- **Top units:** {_top_items(p.top_units(8))}")
            if p.top_structures():
                lines.append(f"- **Top structures:** {_top_items(p.top_structures(8))}")
            if p.unit_loss_counts:
                losses = sorted(p.unit_loss_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
                lines.append(f"- **Most lost unit types:** {_top_items(losses)}")
            if p.leave_time_seconds is not None:
                lines.append(f"- **Leave time:** {_leave_label(p.leave_time_seconds).replace(' left ', '')}")
            lines.append("")

    if summary.raw_event_counts:
        lines.append("## Raw event counts")
        lines.append("")
        for key, value in summary.raw_event_counts.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    if summary.warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in summary.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("## Known limitations")
    lines.append("")
    lines.append("- This reads replay protocol events, not a video recording.")
    lines.append("- Ability/button IDs still need AoK map metadata for perfect build/research/action names.")
    lines.append("- Role labels are heuristic reads based on units, structures, kills/losses, and activity.")
    return "\n".join(lines)


def save_markdown_report(summary: ReplaySummary, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_name = ''.join(ch if ch.isalnum() or ch in '._- ' else '_' for ch in summary.source_path.stem)
    path = reports_dir / f"{safe_name}.md"
    path.write_text(markdown_report(summary), encoding="utf-8")
    return path

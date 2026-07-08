from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import discord
from discord import app_commands

from .config import load_settings
from .replay_parser import ReplayParserError, extract_replay_paths, parse_replay
from .reporting import make_match_embed, save_markdown_report
from .sc2arcade_client import SC2ArcadeClient
from .storage import Storage

settings = load_settings()
storage = Storage(settings.database_path)
arcade = SC2ArcadeClient()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def guild_object() -> discord.Object | None:
    if settings.guild_id is None:
        return None
    return discord.Object(id=settings.guild_id)


async def save_attachment(attachment: discord.Attachment) -> Path:
    safe_name = ''.join(ch if ch.isalnum() or ch in '._-()[]' else '_' for ch in attachment.filename)
    out_path = settings.uploads_dir / safe_name
    await attachment.save(out_path)
    return out_path


@client.event
async def on_ready():
    guild = guild_object()
    if guild is not None:
        tree.copy_global_to(guild=guild)
        synced = await tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to guild {settings.guild_id}")
    else:
        synced = await tree.sync()
        print(f"Synced {len(synced)} global commands")
    print(f"Logged in as {client.user}")


@tree.command(name="aok_recent", description="Show recent Age of Knights sessions from SC2Arcade.")
@app_commands.describe(limit="Number of recent sessions to show")
async def aok_recent(interaction: discord.Interaction, limit: int = 5):
    await interaction.response.defer(thinking=True)
    limit = max(1, min(limit, 10))
    try:
        lobbies = await arcade.get_recent_lobbies(
            settings.sc2arcade_region_id,
            settings.sc2arcade_map_id,
            limit=limit,
        )
    except Exception as exc:
        await interaction.followup.send(f"SC2Arcade request failed: `{exc}`")
        return

    if not lobbies:
        await interaction.followup.send("No recent AoK sessions returned by SC2Arcade.")
        return

    lines = []
    for idx, lobby in enumerate(lobbies[:limit], start=1):
        title = lobby.get("map", {}).get("name") or lobby.get("mapName") or "Age of Knights"
        status = lobby.get("status") or lobby.get("extModStatus") or "unknown"
        opened = lobby.get("createdAt") or lobby.get("openedAt") or lobby.get("startedAt") or "unknown time"
        closed = lobby.get("closedAt") or lobby.get("completedAt") or ""
        lines.append(f"**{idx}. {title}** — {status} — {opened}{' → ' + closed if closed else ''}")

    await interaction.followup.send("\n".join(lines)[:1900])


@tree.command(name="aok_analyze", description="Analyze an uploaded AoK .SC2Replay or ZIP of replays.")
@app_commands.describe(replay="Attach a .SC2Replay file or a .zip containing replays")
async def aok_analyze(interaction: discord.Interaction, replay: discord.Attachment):
    await interaction.response.defer(thinking=True)

    filename_lower = replay.filename.lower()
    if not (filename_lower.endswith(".sc2replay") or filename_lower.endswith(".zip")):
        await interaction.followup.send("Please upload a `.SC2Replay` file or a `.zip` containing replay files.")
        return

    try:
        upload_path = await save_attachment(replay)
        replay_paths = extract_replay_paths(upload_path, settings.replays_dir)
    except Exception as exc:
        await interaction.followup.send(f"Could not read upload: `{exc}`")
        return

    if not replay_paths:
        await interaction.followup.send("No `.SC2Replay` files were found in that upload.")
        return

    summaries = []
    report_paths = []
    for path in replay_paths:
        summary = parse_replay(path)
        storage.save_replay(summary)
        report_path = save_markdown_report(summary, settings.reports_dir)
        summaries.append(summary)
        report_paths.append(report_path)

    first = summaries[0]
    embed = make_match_embed(first)

    if len(summaries) == 1:
        await interaction.followup.send(embed=embed, file=discord.File(report_paths[0]))
        return

    ok_count = sum(1 for s in summaries if s.parser_ok)
    message = (
        f"Processed **{len(summaries)}** replay(s). "
        f"Full parser OK for **{ok_count}**. Showing first replay snapshot below."
    )
    # For many reports, avoid attaching dozens of files to Discord. Attach only first report.
    await interaction.followup.send(message, embed=embed, file=discord.File(report_paths[0]))


@tree.command(name="aok_player", description="Show local profile stats for a player from uploaded replays.")
@app_commands.describe(name="Player name or partial name")
async def aok_player(interaction: discord.Interaction, name: str):
    profile = storage.player_profile(name)
    if profile["games"] == 0:
        await interaction.response.send_message(f"No local replay stats found for `{name}` yet.")
        return

    lines = [
        f"**{profile['name']} AoK profile**",
        f"Games in local database: **{profile['games']}**",
        f"Kills/losses: **{profile['kills']} / {profile['losses']}**",
        f"K/L ratio: **{profile['kill_loss_ratio']}**",
        f"Units born: **{profile['units_born']}**",
        f"Commands: **{profile['commands']}**",
        f"Avg APM: **{profile['avg_apm']}**",
        f"Results: `{profile['results']}`",
    ]
    await interaction.response.send_message("\n".join(lines))


@tree.command(name="aok_leaderboard", description="Show local leaderboard from uploaded replays.")
async def aok_leaderboard(interaction: discord.Interaction):
    rows = storage.leaderboard(limit=10)
    if not rows:
        await interaction.response.send_message("No local replay stats yet. Upload replays with `/aok_analyze`.")
        return

    lines = ["**AoK local replay leaderboard**"]
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"{i}. **{r['name']}** — games {r['games']}, "
            f"kills {r['kills']}, losses {r['losses']}, K/L {r['klr']}, avg APM {r['avg_apm']}"
        )
    await interaction.response.send_message("\n".join(lines)[:1900])


def main() -> None:
    if not settings.discord_token or settings.discord_token == "replace_me":
        raise SystemExit("Set DISCORD_TOKEN in .env before running the bot.")
    client.run(settings.discord_token)


if __name__ == "__main__":
    main()

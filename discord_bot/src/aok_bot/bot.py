from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import replace

import aiohttp
from pathlib import Path

import discord
from discord import app_commands

from .retention import sweep
from .config import load_settings
from .replay_inputs import extract_replay_paths
from .replay_worker import parse_replay_isolated
from .reporting import make_match_embed, save_markdown_report, validate_mode
from .sc2arcade_client import SC2ArcadeClient
from .storage import Storage

settings = None
storage = None
arcade = SC2ArcadeClient()

intents = discord.Intents.default()
client = discord.Client(intents=intents, allowed_mentions=discord.AllowedMentions.none())
tree = app_commands.CommandTree(client)


def guild_object() -> discord.Object | None:
    if settings.guild_id is None:
        return None
    return discord.Object(id=settings.guild_id)


class JobAdmission:
    def __init__(self, capacity=2):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Invalid job capacity")
        self.capacity = capacity
        self.jobs = set()

    def submit(self, factory):
        if len(self.jobs) >= self.capacity:
            return None
        task = asyncio.create_task(factory())
        self.jobs.add(task)
        def finished(job):
            self.jobs.discard(job)
            if not job.cancelled():
                job.exception()  # Retrieve errors even after the interaction disconnects.
        task.add_done_callback(finished)
        return task


admission = JobAdmission()


async def owned_thread(function, *args):
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            break
    if cancelled:
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


async def save_attachment(attachment: discord.Attachment) -> Path:
    limits = settings.input_limits
    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in {".zip", ".sc2replay"}:
        raise ValueError("Unsupported upload type")
    if not 0 < attachment.size <= limits.upload_bytes:
        raise ValueError("Invalid upload size")
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="request-", suffix=suffix, dir=settings.uploads_dir)
    os.close(fd)
    out_path = Path(name)
    try:
        timeout = aiohttp.ClientTimeout(total=settings.download_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(attachment.url) as response:
                response.raise_for_status()
                if response.content_length is not None and response.content_length > limits.upload_bytes:
                    raise ValueError("Upload limit exceeded")
                total = 0
                with out_path.open("wb") as dst:
                    async for chunk in response.content.iter_chunked(65536):
                        total += len(chunk)
                        if total > limits.upload_bytes:
                            raise ValueError("Upload limit exceeded")
                        dst.write(chunk)
                if not total or total != attachment.size:
                    raise ValueError("Incomplete upload")
        return out_path
    except BaseException:
        out_path.unlink(missing_ok=True)
        raise


@client.event
async def on_ready():
    await _sweep_scratch()
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
    except Exception:
        await interaction.followup.send("SC2Arcade request failed. Please try again later.")
        return

    if not lobbies:
        await interaction.followup.send("No recent AoK sessions returned by SC2Arcade.")
        return

    lines = []
    for idx, lobby in enumerate(lobbies[:limit], start=1):
        if not isinstance(lobby, dict):
            continue
        title = (lobby.get("map") or {}).get("name") or lobby.get("mapName") or "Age of Knights"
        status = lobby.get("status") or lobby.get("extModStatus") or "unknown"
        opened = lobby.get("createdAt") or lobby.get("openedAt") or lobby.get("startedAt") or "unknown time"
        closed = lobby.get("closedAt") or lobby.get("completedAt") or ""
        lines.append(f"**{idx}. {title}** — {status} — {opened}{' → ' + closed if closed else ''}")

    await interaction.followup.send(discord.utils.escape_mentions("\n".join(lines))[:1900])


@tree.command(name="aok_analyze", description="Analyze an uploaded AoK .SC2Replay or ZIP of replays.")
@app_commands.describe(replay="Attach a .SC2Replay file or a .zip containing replays", mode="Report mode")
@app_commands.choices(mode=[
    app_commands.Choice(name="Stats", value="stats"),
    app_commands.Choice(name="Coaching", value="coaching"),
    app_commands.Choice(name="Team", value="team"),
])
async def aok_analyze(interaction: discord.Interaction, replay: discord.Attachment, mode: str = "stats"):
    try:
        validate_mode(mode)
        if Path(replay.filename).suffix.lower() not in {".sc2replay", ".zip"}:
            raise ValueError("Unsupported upload")
    except ValueError:
        await interaction.response.send_message("Choose a supported report mode and a replay or ZIP file.", ephemeral=True)
        return
    task = admission.submit(lambda: _analyze_job(interaction, replay, mode))
    if task is None:
        await interaction.response.send_message("Replay analysis is busy. Please try again later.", ephemeral=True)
        return
    await asyncio.shield(task)


MAX_ATTACHMENTS = 10  # Discord's per-message file limit.
# Interaction tokens expire after 15 minutes; stop starting new replays well before.
JOB_BUDGET_SECONDS = 12 * 60

PUBLIC_WARNINGS = (
    ("Compatibility decoder:", "A corpus-validated compatibility decoder was used."),
    ("Could not decode game events:", "Command counts are partial; APM is unavailable."),
    ("Could not decode message events:", "Message events could not be decoded."),
)


def _public_warning(warning: str) -> str:
    """Replace parser diagnostics, which may hold paths or untrusted text, with fixed wording."""
    for prefix, public in PUBLIC_WARNINGS:
        if warning.startswith(prefix):
            return public
    return "Some replay data could not be analyzed reliably."


async def _sweep_scratch() -> None:
    try:
        result = await asyncio.to_thread(
            sweep, settings.uploads_dir, settings.reports_dir, settings.replays_dir, settings.replay_cache_days)
        if result.total():
            print(f"Cleanup: removed {result.uploads} upload(s), {result.reports} report(s), "
                  f"{result.replays} cached replay(s)")
    except Exception as exc:  # cleanup must never break the bot
        print(f"Cleanup failed: {type(exc).__name__}")


async def _analyze_job(interaction, replay, mode):
    upload_path = None
    completed = []
    try:
        await interaction.response.defer(thinking=True)
        upload_path = await save_attachment(replay)
        paths = await owned_thread(extract_replay_paths, upload_path, settings.replays_dir, settings.input_limits)
        completed, failed, unsaved, skipped = [], 0, 0, 0
        loop = asyncio.get_running_loop()
        started = loop.time()
        for path in paths:
            if loop.time() - started > JOB_BUDGET_SECONDS:
                skipped += 1
                continue
            try:
                summary = await owned_thread(parse_replay_isolated, path)
                public_warnings = list(dict.fromkeys(_public_warning(w) for w in summary.warnings))
                public = replace(summary, warnings=public_warnings)
                report = save_markdown_report(public, settings.reports_dir, mode)
            except Exception:
                failed += 1
                continue
            try:
                await asyncio.to_thread(storage.save_replay, summary)
            except Exception:
                unsaved += 1
            completed.append((public, report))
        if not completed:
            await interaction.followup.send("No replay reports could be generated. The upload may be invalid or exceed analysis limits.")
            return
        # The snapshot embed uses public warnings only; embed text never pings anyone.
        embed = make_match_embed(completed[0][0])
        ok = sum(s.parser_ok for s, _ in completed)
        message = f"Generated {len(completed)} report(s); {ok} analyzed successfully; {failed} failed."
        if unsaved:
            message += f" {unsaved} report(s) could not be saved to history."
        if skipped:
            message += f" {skipped} replay(s) were skipped to stay within Discord's time limit; upload them separately."
        if len(completed) > MAX_ATTACHMENTS:
            message += f" Only the first {MAX_ATTACHMENTS} reports are attached."
        reports = [report for _, report in completed[:MAX_ATTACHMENTS]]
        attachments = [discord.File(report) for report in reports]
        try:
            await interaction.followup.send(message, embed=embed, files=attachments,
                                            allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            # A rejected embed must not cost the user the reports: resend without it.
            for attachment in attachments:
                attachment.close()
            attachments = [discord.File(report) for report in reports]
            await interaction.followup.send(message, files=attachments,
                                            allowed_mentions=discord.AllowedMentions.none())
        finally:
            for attachment in attachments:
                attachment.close()
    except Exception:
        await interaction.followup.send("Could not process this upload. Please check the file and try again.", allowed_mentions=discord.AllowedMentions.none())
    finally:
        if upload_path is not None:
            upload_path.unlink(missing_ok=True)
        # Reports live on in the Discord message; the local copies are not needed.
        for _, report in completed:
            try:
                Path(report).unlink(missing_ok=True)
            except OSError:
                pass
        await _sweep_scratch()


@tree.command(name="aok_player", description="Show local profile stats for a player from uploaded replays.")
@app_commands.describe(name="Player name or partial name")
async def aok_player(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    try:
        profile = await asyncio.to_thread(storage.player_profile, name)
    except Exception:
        await interaction.followup.send("Could not read the replay history. Please try again later.")
        return
    if profile["games"] == 0:
        matches = profile.get("matches") or []
        if len(matches) > 1:
            shown = ", ".join(matches[:10]) + (", …" if len(matches) > 10 else "")
            message = f"Several players match that name; use the full name: {shown}"
        else:
            message = "No local replay stats found for that player yet."
        await interaction.followup.send(discord.utils.escape_mentions(message)[:1900])
        return

    lines = [
        f"**{profile['name']} AoK profile**",
        f"Games in local database: **{profile['games']}**",
        f"PvP kills/losses: **{profile['kills']} / {profile['losses']}**",
        f"PvP K/L ratio: **{profile['kill_loss_ratio']}**",
        f"Animal K/D: **{profile.get('animal_kills', 0)} / {profile.get('deaths_to_animals', 0)}**",
        f"Animal K/D ratio: **{profile.get('animal_kill_loss_ratio')}**",
        f"Units born: **{profile['units_born']}**",
        f"Commands: **{profile['commands']}**",
        f"Avg APM: **{profile['avg_apm']}**",
        f"Results: `{profile['results']}`",
    ]
    await interaction.followup.send(discord.utils.escape_mentions("\n".join(lines))[:1900])


@tree.command(name="aok_leaderboard", description="Show local leaderboard from uploaded replays.")
async def aok_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        rows = await asyncio.to_thread(storage.leaderboard, 10)
    except Exception:
        await interaction.followup.send("Could not read the replay history. Please try again later.")
        return
    if not rows:
        await interaction.followup.send("No local replay stats yet. Upload replays with `/aok_analyze`.")
        return

    lines = ["**AoK local replay leaderboard**"]
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"{i}. **{r['name']}** — games {r['games']}, "
            f"PvP {r['kills']}/{r['losses']} K/L {r['klr']}, "
            f"animals {r.get('animal_kills', 0)}/{r.get('deaths_to_animals', 0)}, "
            f"avg APM {r['avg_apm']}"
        )
    await interaction.followup.send(discord.utils.escape_mentions("\n".join(lines))[:1900])


def main() -> None:
    global settings, storage, admission
    settings = load_settings()
    storage = Storage(settings.database_path)
    admission = JobAdmission(settings.max_active_jobs)
    if not settings.discord_token or settings.discord_token == "replace_me":
        raise SystemExit("Set DISCORD_TOKEN in .env before running the bot.")
    client.run(settings.discord_token)


if __name__ == "__main__":
    main()

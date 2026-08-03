from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import tasks

from .config import load_settings
from .patch_note_storage import PatchNoteStorage
from .patch_notes import PatchNote, extract_patch_notes, format_patch_note_body
from .replay_parser import extract_replay_paths, parse_replay
from .reporting import make_match_embed, save_markdown_report
from .sc2arcade_client import SC2ArcadeClient
from .storage import Storage

settings = load_settings()
storage = Storage(settings.database_path)
patch_note_storage = PatchNoteStorage(settings.database_path)
arcade = SC2ArcadeClient()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
patch_sync_lock = asyncio.Lock()


@dataclass
class PatchWatcherStatus:
    last_checked_at: str | None = None
    last_success_at: str | None = None
    latest_version: str | None = None
    notes_seen: int = 0
    posts_created: int = 0
    posts_updated: int = 0
    last_error: str | None = None


patch_watcher_status = PatchWatcherStatus()


def guild_object() -> discord.Object | None:
    if settings.guild_id is None:
        return None
    return discord.Object(id=settings.guild_id)


async def save_attachment(attachment: discord.Attachment) -> Path:
    safe_name = "".join(
        ch if ch.isalnum() or ch in "._-()[]" else "_"
        for ch in attachment.filename
    )
    out_path = settings.uploads_dir / safe_name
    await attachment.save(out_path)
    return out_path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _patch_source_url() -> str:
    return (
        "https://sc2arcade.com/map/"
        f"{settings.patch_notes_region_id}/{settings.patch_notes_map_id}/"
    )


def _patch_thread_name(note: PatchNote) -> str:
    name = f"Discuss Age of Knights v{note.version}"
    return name[:100]


def make_patch_note_embed(note: PatchNote) -> discord.Embed:
    body = format_patch_note_body(note)
    if len(body) > 3900:
        body = (
            body[:3850].rstrip()
            + "\n\n_Notes truncated to fit Discord. The source remains linked above._"
        )

    embed = discord.Embed(
        title=f"⚔️ Age of Knights v{note.version}",
        url=_patch_source_url(),
        description=body,
        colour=discord.Colour.blue(),
    )
    embed.add_field(
        name="Published",
        value=note.published_at or "Date not supplied",
        inline=True,
    )
    embed.add_field(
        name="Source",
        value="StarCraft II Arcade update notes",
        inline=True,
    )
    embed.set_footer(
        text="Automatically mirrored by the AoK FourDie Companion Bot."
    )
    return embed


def _allowed_mentions() -> discord.AllowedMentions:
    return discord.AllowedMentions(
        everyone=False,
        users=False,
        roles=True,
        replied_user=False,
    )


def _patch_mention(enabled: bool) -> str | None:
    if not enabled or settings.patch_notes_mention_role_id is None:
        return None
    return f"<@&{settings.patch_notes_mention_role_id}>"


async def _resolve_channel(channel_id: int) -> Any:
    channel = client.get_channel(channel_id)
    if channel is None:
        channel = await client.fetch_channel(channel_id)
    return channel


async def publish_patch_note(
    note: PatchNote,
    *,
    mention_role: bool,
) -> tuple[int, int, int | None]:
    if settings.patch_notes_channel_id is None:
        raise RuntimeError("PATCH_NOTES_CHANNEL_ID is not configured")

    channel = await _resolve_channel(settings.patch_notes_channel_id)
    embed = make_patch_note_embed(note)
    content = _patch_mention(mention_role)
    allowed_mentions = _allowed_mentions()

    if isinstance(channel, discord.ForumChannel):
        result = await channel.create_thread(
            name=f"Age of Knights v{note.version}"[:100],
            content=content,
            embed=embed,
            auto_archive_duration=1440,
            allowed_mentions=allowed_mentions,
            reason="Automatic Age of Knights patch-note mirror",
        )
        thread = getattr(result, "thread", result)
        message = getattr(result, "message", None)
        if message is None:
            message = await thread.fetch_message(thread.id)
        return channel.id, message.id, thread.id

    if not isinstance(channel, discord.TextChannel):
        raise RuntimeError(
            "PATCH_NOTES_CHANNEL_ID must refer to a text, announcement, or forum channel"
        )

    message = await channel.send(
        content=content,
        embed=embed,
        allowed_mentions=allowed_mentions,
    )
    thread_id: int | None = None

    if settings.patch_notes_create_discussion_thread:
        try:
            thread = await message.create_thread(
                name=_patch_thread_name(note),
                auto_archive_duration=1440,
                reason="Age of Knights patch-note discussion",
            )
            thread_id = thread.id
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(
                "Patch note posted, but discussion thread creation failed: "
                f"version={note.version}, error={exc}"
            )

    return channel.id, message.id, thread_id


async def edit_patch_note(row: dict[str, Any], note: PatchNote) -> None:
    message_id = int(row["discord_message_id"])
    parent = await _resolve_channel(int(row["discord_channel_id"]))

    # A forum post's starter message lives inside the created thread. A normal
    # text-channel announcement remains in its parent even when it has an
    # attached discussion thread.
    if isinstance(parent, discord.ForumChannel):
        thread_id = row.get("discord_thread_id")
        if thread_id is None:
            raise RuntimeError(f"Forum publication for v{note.version} has no thread ID")
        destination = await _resolve_channel(int(thread_id))
    else:
        destination = parent

    if not isinstance(destination, (discord.TextChannel, discord.Thread)):
        raise RuntimeError(
            f"Could not resolve a message-bearing Discord channel for v{note.version}"
        )

    message = await destination.fetch_message(message_id)
    await message.edit(embed=make_patch_note_embed(note))


async def sync_patch_notes() -> dict[str, int]:
    """Fetch, persist, publish, and update SC2 Arcade patch notes."""

    async with patch_sync_lock:
        patch_watcher_status.last_checked_at = _utc_now()
        patch_watcher_status.last_error = None

        try:
            payload = await arcade.get_map_details(
                settings.patch_notes_region_id,
                settings.patch_notes_map_id,
                locale=settings.patch_notes_locale,
            )
            notes = extract_patch_notes(payload)
            if not notes:
                raise RuntimeError(
                    "SC2Arcade returned no patch-note sections for the configured map"
                )

            initial_import = not patch_note_storage.has_any(
                settings.patch_notes_region_id,
                settings.patch_notes_map_id,
            )
            latest_version = notes[0].version

            for note in notes:
                existing = patch_note_storage.get(
                    settings.patch_notes_region_id,
                    settings.patch_notes_map_id,
                    note.version,
                )

                suppressed = False
                if existing is None and initial_import:
                    if settings.patch_notes_first_run_mode == "baseline":
                        suppressed = True
                    elif settings.patch_notes_first_run_mode == "latest":
                        suppressed = note.version != latest_version
                    elif settings.patch_notes_first_run_mode == "all":
                        suppressed = False

                patch_note_storage.upsert_source(
                    settings.patch_notes_region_id,
                    settings.patch_notes_map_id,
                    note,
                    suppressed_on_insert=suppressed,
                )

            created = 0
            updated = 0
            unsynced = patch_note_storage.list_unsynced(
                settings.patch_notes_region_id,
                settings.patch_notes_map_id,
            )

            for row in unsynced:
                note = patch_note_storage.note_from_row(row)
                try:
                    if row.get("discord_message_id") is None:
                        mention_role = (
                            not initial_import
                            or settings.patch_notes_mention_on_first_import
                        )
                        channel_id, message_id, thread_id = await publish_patch_note(
                            note,
                            mention_role=mention_role,
                        )
                        patch_note_storage.mark_posted(
                            settings.patch_notes_region_id,
                            settings.patch_notes_map_id,
                            note.version,
                            channel_id=channel_id,
                            message_id=message_id,
                            thread_id=thread_id,
                            posted_hash=note.content_hash,
                        )
                        created += 1
                    elif settings.patch_notes_edit_existing_posts:
                        await edit_patch_note(row, note)
                        patch_note_storage.mark_edited(
                            settings.patch_notes_region_id,
                            settings.patch_notes_map_id,
                            note.version,
                            posted_hash=note.content_hash,
                        )
                        updated += 1
                    else:
                        # Acknowledge the source revision without editing Discord,
                        # preventing the watcher from retrying forever.
                        patch_note_storage.mark_edited(
                            settings.patch_notes_region_id,
                            settings.patch_notes_map_id,
                            note.version,
                            posted_hash=note.content_hash,
                        )
                except Exception as exc:
                    patch_note_storage.mark_error(
                        settings.patch_notes_region_id,
                        settings.patch_notes_map_id,
                        note.version,
                        str(exc),
                    )
                    print(
                        "Patch-note Discord sync failed: "
                        f"version={note.version}, error={exc}"
                    )

            patch_watcher_status.last_success_at = _utc_now()
            patch_watcher_status.latest_version = latest_version
            patch_watcher_status.notes_seen = len(notes)
            patch_watcher_status.posts_created += created
            patch_watcher_status.posts_updated += updated

            print(
                "Patch-note sync complete: "
                f"latest={latest_version}, notes={len(notes)}, "
                f"created={created}, updated={updated}"
            )
            return {"notes": len(notes), "created": created, "updated": updated}
        except Exception as exc:
            patch_watcher_status.last_error = str(exc)
            print(f"Patch-note sync failed: {exc}")
            raise


@tasks.loop(minutes=60)
async def patch_note_loop() -> None:
    try:
        await sync_patch_notes()
    except Exception:
        # sync_patch_notes records and logs the specific error. Keeping the
        # loop alive lets a temporary upstream or Discord outage self-recover.
        pass


@patch_note_loop.before_loop
async def before_patch_note_loop() -> None:
    await client.wait_until_ready()


@client.event
async def on_ready() -> None:
    guild = guild_object()
    if guild is not None:
        tree.copy_global_to(guild=guild)
        synced = await tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to guild {settings.guild_id}")
    else:
        synced = await tree.sync()
        print(f"Synced {len(synced)} global commands")

    if settings.patch_notes_enabled and not patch_note_loop.is_running():
        patch_note_loop.change_interval(minutes=settings.patch_notes_poll_minutes)
        patch_note_loop.start()
        print(
            "Patch-note watcher enabled: "
            f"channel={settings.patch_notes_channel_id}, "
            f"interval={settings.patch_notes_poll_minutes}m, "
            f"first_run={settings.patch_notes_first_run_mode}"
        )

    print(f"Logged in as {client.user}")


@tree.command(name="aok_recent", description="Show recent Age of Knights sessions from SC2Arcade.")
@app_commands.describe(limit="Number of recent sessions to show")
async def aok_recent(interaction: discord.Interaction, limit: int = 5) -> None:
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
        lines.append(
            f"**{idx}. {title}** — {status} — {opened}"
            f"{' → ' + closed if closed else ''}"
        )

    await interaction.followup.send("\n".join(lines)[:1900])


@tree.command(name="aok_analyze", description="Analyze an uploaded AoK .SC2Replay or ZIP of replays.")
@app_commands.describe(replay="Attach a .SC2Replay file or a .zip containing replays")
async def aok_analyze(
    interaction: discord.Interaction,
    replay: discord.Attachment,
) -> None:
    await interaction.response.defer(thinking=True)

    filename_lower = replay.filename.lower()
    if not (filename_lower.endswith(".sc2replay") or filename_lower.endswith(".zip")):
        await interaction.followup.send(
            "Please upload a `.SC2Replay` file or a `.zip` containing replay files."
        )
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
        await interaction.followup.send(
            embed=embed,
            file=discord.File(report_paths[0]),
        )
        return

    ok_count = sum(1 for summary in summaries if summary.parser_ok)
    message = (
        f"Processed **{len(summaries)}** replay(s). "
        f"Full parser OK for **{ok_count}**. Showing first replay snapshot below."
    )
    await interaction.followup.send(
        message,
        embed=embed,
        file=discord.File(report_paths[0]),
    )


@tree.command(name="aok_player", description="Show local profile stats for a player from uploaded replays.")
@app_commands.describe(name="Player name or partial name")
async def aok_player(interaction: discord.Interaction, name: str) -> None:
    profile = storage.player_profile(name)
    if profile["games"] == 0:
        await interaction.response.send_message(
            f"No local replay stats found for `{name}` yet."
        )
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
    await interaction.response.send_message("\n".join(lines))


@tree.command(name="aok_leaderboard", description="Show local leaderboard from uploaded replays.")
async def aok_leaderboard(interaction: discord.Interaction) -> None:
    rows = storage.leaderboard(limit=10)
    if not rows:
        await interaction.response.send_message(
            "No local replay stats yet. Upload replays with `/aok_analyze`."
        )
        return

    lines = ["**AoK local replay leaderboard**"]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"{index}. **{row['name']}** — games {row['games']}, "
            f"PvP {row['kills']}/{row['losses']} K/L {row['klr']}, "
            f"animals {row.get('animal_kills', 0)}/{row.get('deaths_to_animals', 0)}, "
            f"avg APM {row['avg_apm']}"
        )
    await interaction.response.send_message("\n".join(lines)[:1900])


@tree.command(name="aok_patchnotes", description="Show the latest mirrored Age of Knights patch notes.")
async def aok_patchnotes(interaction: discord.Interaction) -> None:
    row = patch_note_storage.latest(
        settings.patch_notes_region_id,
        settings.patch_notes_map_id,
    )
    if row is None:
        await interaction.response.send_message(
            "No patch notes have been mirrored yet.",
            ephemeral=True,
        )
        return

    note = patch_note_storage.note_from_row(row)
    await interaction.response.send_message(embed=make_patch_note_embed(note))


@tree.command(name="aok_patchnotes_status", description="Show patch-note watcher status.")
async def aok_patchnotes_status(interaction: discord.Interaction) -> None:
    lines = [
        "**AoK patch-note watcher**",
        f"Enabled: **{settings.patch_notes_enabled}**",
        f"Target channel: `{settings.patch_notes_channel_id or 'not configured'}`",
        f"Polling interval: **{settings.patch_notes_poll_minutes} minutes**",
        f"Latest version seen: **{patch_watcher_status.latest_version or 'none'}**",
        f"Last successful check: `{patch_watcher_status.last_success_at or 'never'}`",
        f"Posts created this process: **{patch_watcher_status.posts_created}**",
        f"Posts updated this process: **{patch_watcher_status.posts_updated}**",
    ]
    if patch_watcher_status.last_error:
        lines.append(f"Last error: `{patch_watcher_status.last_error[:500]}`")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@tree.command(name="aok_patchnotes_sync", description="Check SC2 Arcade for patch-note updates now.")
@app_commands.default_permissions(manage_guild=True)
async def aok_patchnotes_sync(interaction: discord.Interaction) -> None:
    member = interaction.user
    if not isinstance(member, discord.Member) or not member.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "You need **Manage Server** to run this command.",
            ephemeral=True,
        )
        return

    if settings.patch_notes_channel_id is None:
        await interaction.response.send_message(
            "`PATCH_NOTES_CHANNEL_ID` is not configured.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        result = await sync_patch_notes()
    except Exception as exc:
        await interaction.followup.send(
            f"Patch-note sync failed: `{str(exc)[:1500]}`",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        "Patch-note sync complete: "
        f"**{result['notes']}** source entries, "
        f"**{result['created']}** posts created, "
        f"**{result['updated']}** posts updated.",
        ephemeral=True,
    )


def main() -> None:
    if not settings.discord_token or settings.discord_token == "replace_me":
        raise SystemExit("Set DISCORD_TOKEN in .env before running the bot.")
    client.run(settings.discord_token)


if __name__ == "__main__":
    main()

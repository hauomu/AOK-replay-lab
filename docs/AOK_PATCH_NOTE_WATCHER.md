# AoK automatic patch-note mirror

The Discord bot can poll the public SC2Arcade map-details endpoint and mirror the patch notes that are already embedded in **Age of Knights**. TwoDie does not need to paste a second copy into Discord.

## Behaviour

- Polls the configured map every 60 minutes by default.
- Stores source notes and Discord publication IDs in the existing SQLite database.
- Posts only genuinely new versions.
- Edits an existing Discord post when the source text changes for the same version.
- Supports a normal text/announcement channel or a Discord forum channel.
- Creates a discussion thread automatically for text-channel announcements.
- Preserves the source wording instead of rewriting patch notes.
- Adds `/aok_patchnotes`, `/aok_patchnotes_status`, and maintainer-only `/aok_patchnotes_sync` commands.

## Discord permissions

For a normal `#patch-notes` text or announcement channel, allow the bot:

- View Channel
- Send Messages
- Embed Links
- Read Message History
- Create Public Threads
- Send Messages in Threads

For a forum channel, allow the bot to view the forum and create/send posts. Discord may display this as **Send Messages** or **Create Posts**, depending on the client UI.

Members can be denied `Send Messages` in the parent text channel while still being allowed `Send Messages in Threads` for discussion.

## Configuration

Add the following to the repository-root `.env` used by Docker Compose:

```env
ENABLE_PATCH_NOTE_WATCHER=true
PATCH_NOTES_CHANNEL_ID=PASTE_DISCORD_CHANNEL_OR_FORUM_ID
PATCH_NOTES_REGION_ID=2
PATCH_NOTES_MAP_ID=131901
PATCH_NOTES_LOCALE=enUS
PATCH_NOTES_POLL_MINUTES=60
PATCH_NOTES_CREATE_DISCUSSION_THREAD=true
PATCH_NOTES_MENTION_ROLE_ID=
PATCH_NOTES_MENTION_ON_FIRST_IMPORT=false
PATCH_NOTES_EDIT_EXISTING_POSTS=true
PATCH_NOTES_FIRST_RUN_MODE=latest
```

`PATCH_NOTES_FIRST_RUN_MODE` accepts:

- `baseline`: record existing notes and wait for the next new version.
- `latest`: post only the latest existing version on first startup. This is the default.
- `all`: post all existing versions. Use carefully because this can flood the channel.

`PATCH_NOTES_MENTION_ROLE_ID` is optional. When present, newly detected updates mention that role. The first import does not mention it unless `PATCH_NOTES_MENTION_ON_FIRST_IMPORT=true`.

## Deploy on Tomo

After merging the update:

```bash
ssh sherman@100.84.104.62
cd ~/aok-bot
bash scripts/deploy_tomo.sh
```

Check startup and watcher logs:

```bash
docker logs --tail 150 aok-replay-bot
```

Expected output includes:

```text
Patch-note watcher enabled: channel=..., interval=60m, first_run=latest
Patch-note sync complete: latest=..., notes=..., created=..., updated=...
```

Run an immediate check from Discord with:

```text
/aok_patchnotes_sync
```

The command requires **Manage Server**.

## Failure behaviour

A temporary SC2Arcade or Discord failure is logged and retried on the next poll. An unsent or unedited publication remains marked as pending in SQLite, so a container restart does not lose it or create duplicates.

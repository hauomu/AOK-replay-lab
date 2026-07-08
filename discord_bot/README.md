# AoK Companion Bot MVP

A Discord bot for **StarCraft II Arcade: Age of Knights** replay analysis and SC2Arcade session tracking.

This MVP is designed to work in layers:

1. **SC2Arcade metadata watcher**: tracks AoK lobbies/match history without replay files.
2. **Replay upload analyzer**: accepts `.SC2Replay` or `.zip` uploads in Discord and generates post-game reports.
3. **Player profile database**: stores parsed replay stats for leaderboards and player summaries.
4. **AoK metadata bridge**: later uses AoK map/dependency metadata to translate raw unit/ability IDs into readable AoK terms.

## Current status

This is the v0.2 MVP. It can parse uploaded AoK replay files, clean SC2 rich-text player names, extract tracker-event unit/combat data, generate team/player role reads, and store local leaderboard stats. The parser expects Blizzard's `s2protocol`/`mpyq` libraries to be installed. If those are missing, the bot still runs, but replay analysis falls back to file metadata and tells you what dependency is missing.

## Quick start

### 1. Create a Discord bot

Create a bot application in the Discord Developer Portal, invite it to your server, and enable:

- Message Content Intent, if you also want message attachment watching later.
- Bot permissions: Send Messages, Attach Files, Read Message History.
- Slash commands through the OAuth2 `applications.commands` scope.

### 2. Install Python dependencies

Python 3.11 is recommended. Newer Python versions may work because this project includes a small compatibility shim for `s2protocol`, but Python 3.11 is still the safest option.

```powershell
cd aok_discord_bot_mvp
$Py311 = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
& $Py311 -m venv .venv311
$Python = "$PWD\.venv311\Scripts\python.exe"
& $Python -m pip install --upgrade pip setuptools wheel
& $Python -m pip install -r requirements.txt
```

### 3. Install replay parser dependencies

The bot can start without these, but full `.SC2Replay` parsing needs them.

Recommended:

```powershell
if (!(Test-Path external)) { mkdir external }
if (!(Test-Path external\s2protocol)) { git clone https://github.com/Blizzard/s2protocol.git external\s2protocol }
& $Python -m & $Python -m pip install mpyq
& $Python -m pip install -e external\s2protocol
```

If `mpyq` is not installed automatically:

```powershell
& $Python -m pip install mpyq
```

### 4. Configure `.env`

Copy:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```text
DISCORD_TOKEN=your_bot_token_here
AOK_GUILD_ID=optional_test_server_id
SC2ARCADE_REGION_ID=2
SC2ARCADE_MAP_ID=131901
```

For fast command registration during testing, set `AOK_GUILD_ID` to your Discord server ID. For global commands, leave it blank.

### 5. Run the bot

```powershell
$Project = "$PWD"
$Python = "$Project\.venv311\Scripts\python.exe"
& $Python -m src.aok_bot.bot
```

## Main commands

### `/aok_recent`

Fetches recent Age of Knights sessions from SC2Arcade metadata.

### `/aok_analyze replay:<attachment>`

Upload either:

- a single `.SC2Replay`
- or a `.zip` containing many `.SC2Replay` files

The bot stores the upload, parses each replay it can, saves reports, and replies with a summary.

### `/aok_player name:<player>`

Shows a simple player profile from the local SQLite database.

### `/aok_leaderboard`

Shows leaderboard-style stats from uploaded/parsed replays.

## Data folders

```text
data/
├── uploads/        # original Discord uploads
├── replays/        # extracted replay files
├── reports/        # generated Markdown reports
├── dependencies/   # AoK map/mod metadata files, optional for now
├── cache/          # temporary files
└── aok_bot.sqlite3 # local database, created automatically
```

## How to use your AoK dependency files

Copy your downloaded/cached AoK files into:

```text
data/dependencies/
```

Expected useful files include:

```text
Age of Knights Replayable v20 PubFix.SC2Map
AoK assets 2021 rev.SC2Mod
VoidMulti.SC2Mod
manifest.json
```

The MVP does not fully extract SC2 map MPQ data yet, but it reserves this folder and database structure for the next step: translating replay IDs into AoK unit/ability/upgrade names.

## Roadmap

### v0.1

- Discord slash commands
- Replay/ZIP upload handling
- Basic replay metadata extraction
- Player summary database
- SC2Arcade recent match query

### v0.2

- Better tracker-event extraction
- Unit birth/death/kill tables
- Team summaries
- Discord-friendly match recap embeds
- Clean SC2 rich-text player names
- Heuristic player role labels: defensive anchor, cavalry pressure, ranged support, infantry frontline, mixed carry
- SC2Arcade API host fix: uses `https://api.sc2arcade.com` first, then falls back to website proxy

### v0.3

- AoK metadata dictionary from map/dependency files
- Custom unit/building/ability/upgrades translation
- Role classifier: turtle, cavalry carry, infantry/firepower, support, mixed pressure

### v0.4

- SC2Arcade watcher loop
- Auto-post when an AoK match finishes
- Link replay upload to SC2Arcade session

### v0.5

- Player profile pages
- Balance dashboard
- ML-assisted coach/recommendations

## Notes

- SC2Arcade is used only for public lobby/match metadata.
- Full gameplay reconstruction still needs actual `.SC2Replay` files.
- The bot is intentionally framed as a replay/statistics/coach bot, not an automation or cheat bot.

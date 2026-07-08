# AoK Replay Lab

AoK Replay Lab is a community tooling project for **StarCraft II Arcade: Age of Knights**.

It currently has two independent workflows:

1. **Discord replay analyzer bot** — accepts AoK `.SC2Replay` files or ZIPs, parses replay metadata/events, stores local stats, and generates Discord-friendly match summaries.
2. **Offline strategy mining pipeline** — batch-processes replay archives to discover team roles, timing windows, win signals, and guide-writing material.

The project is intentionally split so the Discord bot can stay lightweight while the heavier ML/statistics work runs offline.

## Repository layout

```text
aok-replay-lab/
├── discord_bot/        # Discord slash-command bot MVP v0.2
├── strategy_mining/    # Offline strategy mining / guide pipeline v0.1
└── docs/               # Context, roadmap, handoff notes, sample outputs
```

## Current status

- Discord bot shell works in a private test server.
- `/aok_analyze` parses Age of Knights replays using `mpyq` + Blizzard `s2protocol`.
- `/aok_leaderboard` and `/aok_player` use locally stored replay stats.
- Replay summaries have been upgraded from basic K/D into role/style/team composition reads.
- Offline strategy mining pipeline can generate CSV datasets, timing-window analysis, decision-tree-style win signals, and draft guide material.

## Important Python version note

Use **Python 3.11** for the Discord bot and strategy pipeline.

Blizzard `s2protocol` currently breaks on newer Python versions such as Python 3.14 because it imports the removed `imp` module. On Windows, create a dedicated Python 3.11 environment.

## Discord bot quick start

```powershell
cd .\discord_bot

$Python311 = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
& $Python311 -m venv .venv311
$Python = "$PWD\.venv311\Scripts\python.exe"

& $Python -m pip install --upgrade pip setuptools wheel
& $Python -m pip install -r requirements.txt

mkdir external -ErrorAction SilentlyContinue
git clone https://github.com/Blizzard/s2protocol.git external\s2protocol
& $Python -m pip install -e external\s2protocol
& $Python -m pip install mpyq

Copy-Item .env.example .env
notepad .env
```

Fill `.env` with your bot token and private test server ID:

```env
DISCORD_TOKEN=PASTE_YOUR_BOT_TOKEN_HERE
AOK_GUILD_ID=PASTE_YOUR_PRIVATE_TEST_SERVER_ID_HERE
SC2ARCADE_REGION_ID=2
SC2ARCADE_MAP_ID=131901
DATABASE_PATH=data/aok_bot.sqlite3
```

Run the bot:

```powershell
& $Python -m src.aok_bot.bot
```

Test in Discord:

```text
/aok_analyze
/aok_leaderboard
/aok_player player_name
/aok_recent
```

`/aok_recent` may need future API/header patching depending on SC2Arcade response behavior. Replay upload analysis is the priority feature.

## Strategy mining quick start

```powershell
cd .\strategy_mining

$Python311 = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
& $Python311 -m venv .venv311
$Python = "$PWD\.venv311\Scripts\python.exe"

& $Python -m pip install --upgrade pip setuptools wheel
& $Python -m pip install -r requirements.txt

mkdir external -ErrorAction SilentlyContinue
git clone https://github.com/Blizzard/s2protocol.git external\s2protocol
& $Python -m pip install -e external\s2protocol
& $Python -m pip install mpyq

.\scripts\run_strategy_mining.ps1 `
  -Inputs "$env:USERPROFILE\Desktop\sherman_aok_replays.zip" `
  -OutDir "output" `
  -Limit 10
```

Remove `-Limit 10` for a full run.

## What is deliberately not committed

Do not commit:

- Discord bot tokens or `.env` files
- `.SC2Replay` files
- recovered AoK `.SC2Map`, `.SC2Mod`, or `.s2ma` files
- local SQLite databases
- generated output folders unless intentionally copied into docs/sample_outputs

Game assets/replays should stay local unless permission is clear.

## Near-term roadmap

1. Harden replay parsing and error messages.
2. Improve team/result resolution across older AoK versions.
3. Extract AoK-specific map metadata from recovered map/mod files.
4. Upgrade reports from generic “structure/unit types” into real AoK names and tech timings.
5. Generate first player guide from the offline strategy mining pipeline.
6. Add optional Discord commands for published guide snippets.
7. Keep anti-spam/onboarding as a separate future module, not part of replay MVP.

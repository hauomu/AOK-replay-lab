# AoK Replay Lab

AoK Replay Lab is a community tooling project for **StarCraft II Arcade: Age of Knights**.

It currently has two independent workflows:

1. **Discord replay analyzer bot** — accepts AoK `.SC2Replay` files or ZIPs, parses replay metadata/events, stores local stats, and generates Discord-friendly match summaries.
2. **Offline strategy mining pipeline** — batch-processes replay archives to discover team roles, timing windows, win signals, and guide-writing material.

The project is intentionally split so the Discord bot can stay lightweight while the heavier ML/statistics work runs offline.

## Repository layout

```text
aok-replay-lab/
├── discord_bot/        # Discord slash-command bot MVP v0.4
├── strategy_mining/    # Offline strategy mining / guide pipeline v0.1
└── docs/               # Context, roadmap, handoff notes, sample outputs
```

## Current status

- Discord bot shell works in a private test server.
- `/aok_analyze` parses Age of Knights replays using `mpyq` + Blizzard `s2protocol`.
- `/aok_analyze` now supports team games, FFA/no-alliance games, duel-style games, and Player 15 / Animals tracking.
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

## v0.3 note

The Discord bot tracks **Player 15 as Animals / Neutral** inside `/aok_analyze`, separates animal K/D from human combat K/D, and produces a more summary-first report with team evaluations and player takeaways.

## v0.4 note

`/aok_analyze` adds **Free For All / no-alliance support**. FFA games are no longer collapsed into fake teams. Each active human player is evaluated as their own hostile side, while Player 15 remains a special Animals / Neutral actor. The report format now switches between team evaluation mode and FFA/player evaluation mode depending on the replay.

## v1.0 update

The Discord replay analyzer is now at **v1.0**. In addition to the earlier team, FFA, duel, and Player 15 support, reports now include:

- leave-based result inference when official replay metadata is unclear
- readable grouped player and timeline tables
- exact mechanical-unit tracking, including trebuchet move/siege state
- observed and inferred age, technology-structure, upgrade, and unit-unlock progression
- resource snapshots using **Gold = Minerals, Wood = Vespene, Iron = Terrazine**
- current stockpile and collection-rate data when exposed by `SPlayerStatsEvent`
- clearly labelled estimated gathered/lost resource values

When a replay build omits Terrazine fields, Iron is reported as `n/a`, not zero. Technology prerequisites and age placement remain explicitly labelled as inferred until confirmed from AoK map data.

See [`docs/AOK_ANALYZE_V1_0_TECH_RESOURCES.md`](docs/AOK_ANALYZE_V1_0_TECH_RESOURCES.md) and the versioned implementation notes under `docs/` for the complete progression from v0.3 through v1.0.

## Docker deployment

The repository includes a Docker Compose deployment for the Discord bot. Runtime
configuration and data stay outside the image:

- `.env` at the repository root contains the Discord configuration and is ignored by Git.
- `data/` at the repository root contains the SQLite database, uploads, replays, and reports.
- the container restarts automatically unless it was explicitly stopped.
- Blizzard `s2protocol` is pinned to a specific upstream commit for reproducible builds.

Initial deployment:

```bash
git clone https://github.com/hauomu/AOK-replay-lab.git ~/aok-bot
cd ~/aok-bot
cp discord_bot/.env.example .env
mkdir -p data
# Edit .env before starting the bot.
GIT_COMMIT="$(git rev-parse HEAD)" docker compose up --detach --build
```

Subsequent Tomo updates can be run from the repository root:

```bash
bash scripts/deploy_tomo.sh
```

The update script creates a timestamped SQLite backup, fast-forwards `main`,
rebuilds the image, recreates the bot container, and prints the deployed Git
revision and recent logs.

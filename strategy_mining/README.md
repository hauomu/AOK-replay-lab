# AoK Strategy Mining Pipeline v0.1

Offline replay-mining pipeline for **StarCraft II Arcade: Age of Knights**.

This is intentionally separate from the Discord bot. The bot can collect/analyze replays, but this pipeline is for slower offline analysis: strategy discovery, timing-window mining, player-guide drafting, and eventually ML-based recommendations.

## What this does now

Given `.SC2Replay` files or ZIPs containing replays, it exports:

```text
output/
├── datasets/
│   ├── replays.csv
│   ├── players.csv
│   ├── player_match_stats.csv
│   ├── team_match_stats.csv
│   ├── timeline_snapshots.csv
│   └── unit_events.csv                 optional; can be very large
├── analysis/
│   ├── player_profiles.csv
│   ├── player_role_summary.csv
│   ├── team_style_summary.csv
│   ├── timing_windows.csv
│   ├── snapshot_win_signals.csv
│   ├── ml_feature_importances.csv
│   ├── ml_decision_rules.txt
│   └── ml_model_report.md
└── guides/
    └── aok_team_roles_and_timing_windows_guide.md
```

The first generated guide focuses on role patterns and timing windows, not exact build-order prescriptions yet. Exact claims like “skip building X to gain resources at only a 5 minute tech delay” need AoK-specific map metadata: building costs, ability IDs, upgrade IDs, and resource/bank keys.

## Recommended workflow for our current project

```text
1. Keep testing the Discord bot in your private test server.
2. Use the bot or this pipeline to parse replay batches.
3. Generate CSVs + guide drafts offline.
4. Use the guide output as evidence for a player guide / Discord post.
5. Later, after TwoDie approves/test-deploys the bot, expose selected guide commands in Discord.
```

## Important Python note

Use Python 3.11 if possible. Blizzard `s2protocol` has compatibility issues with newer Python versions. This pipeline includes a small compatibility shim, but Python 3.11 is still the least painful option on Windows.

## Quick run on Windows PowerShell

From this project folder:

```powershell
.\scripts\run_strategy_mining.ps1 `
  -Inputs "$env:USERPROFILE\Desktop\sherman_aok_replays.zip" `
  -OutDir "output"
```

For a quick test run:

```powershell
.\scripts\run_strategy_mining.ps1 `
  -Inputs "$env:USERPROFILE\Desktop\sherman_aok_replays.zip" `
  -OutDir "output_test" `
  -Limit 10
```

To export the full raw event table, add `-WriteEvents`. Be warned: `unit_events.csv` can become very large for hundreds of replays.

## Manual run

```powershell
$Project = "$env:USERPROFILE\Desktop\aok_strategy_mining_v0_1"
$Py311 = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
Set-Location $Project

& $Py311 -m venv .venv_ml
$Python = "$Project\.venv_ml\Scripts\python.exe"

& $Python -m pip install --upgrade pip setuptools wheel
& $Python -m pip install -r requirements.txt

if (!(Test-Path external)) { mkdir external }
if (!(Test-Path external\s2protocol)) {
    git clone https://github.com/Blizzard/s2protocol.git external\s2protocol
}
& $Python -m pip install -e external\s2protocol

$env:PYTHONPATH = "$Project\src"
& $Python -m aok_ml.ingest_replays "$env:USERPROFILE\Desktop\sherman_aok_replays.zip" --out output
& $Python -m aok_ml.strategy_miner --out output
& $Python -m aok_ml.train_models --out output
```

## Commands

### Parse replays

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv_ml\Scripts\python.exe -m aok_ml.ingest_replays path\to\replays.zip --out output
```

Supported inputs:

```text
.SC2Replay file
folder containing .SC2Replay files
ZIP containing .SC2Replay files
```

### Generate strategy summaries and guide

```powershell
.\.venv_ml\Scripts\python.exe -m aok_ml.strategy_miner --out output
```

### Train readable ML model

```powershell
.\.venv_ml\Scripts\python.exe -m aok_ml.train_models --out output
```

This creates:

```text
output/analysis/ml_model_report.md
output/analysis/ml_feature_importances.csv
output/analysis/ml_decision_rules.txt
```

Treat this as a guide-discovery tool, not a final predictor. The first model is deliberately readable: small decision tree + random forest feature importances.

## How to interpret the outputs

### `timing_windows.csv`

Compares median first timings between winners and non-winners:

```text
first production structure
first static defense
first wall/gate
first cavalry
first ranged
first siege
first upgrade
```

Positive difference means non-winners reached that timing later than winners. Negative difference means winners delayed it, which can suggest a greedier or alternative path.

### `snapshot_win_signals.csv`

Compares winners vs non-winners at fixed minutes:

```text
5, 10, 15, 20, 25, 30, 45, 60
```

Useful for guide statements like:

```text
By 20 minutes, winning players in this corpus tended to have more ranged units and higher total production.
```

### `player_role_summary.csv`

Groups players into heuristic roles:

```text
Cavalry pressure / mobile carry
Defensive anchor / wall player
Ranged firepower/support
Infantry + hand-cannon frontline
Mass-production support
```

### `ml_model_report.md`

A first pass at ML-based win-signal discovery. Use it to find candidate patterns, then manually inspect the matching replays before writing guide rules.

## Known limitations

- This reads replay protocol events, not video.
- Old replay builds may fail depending on protocol availability.
- Current unit/building classification is heuristic based on unit names.
- Ability/button IDs still need AoK map metadata for exact build/research/action names.
- Resource/bank/economy reasoning is not exact until AoK metadata extraction is added.
- The first ML model is exploratory and can be biased by player skill, team stacking, old map versions, and small sample sizes.

## Next planned upgrade

1. Extract AoK-specific unit/building/ability/upgrade dictionaries from the recovered `.SC2Map` / `.SC2Mod` files.
2. Add exact building/tech/cost timing analysis.
3. Generate guide pages by strategy type:
   - Fast pressure / all-in
   - Greedy economy
   - Cavalry pressure
   - Turtle defense
   - Anti-turtle response
4. Feed selected guide summaries back into the Discord bot as commands like `/aok_guide anti_turtle`.

# Roadmap

## v0.2 current baseline

- Discord slash command bot works locally.
- Replay parser works with Python 3.11 + `mpyq` + Blizzard `s2protocol`.
- Detailed match summaries are available for uploaded replays.
- Offline strategy mining pipeline exists as a separate project.

## v0.3 replay analyzer

- Better error surfacing in Discord for parser failures.
- Stronger team/result detection across variants and older replay protocols.
- Report attachment cleanup and size handling.
- Batch upload UX for ZIPs.

## v0.4 AoK metadata extraction

- Extract GameData XML/String data from recovered map/mod dependencies.
- Build `units.csv`, `abilities.csv`, `upgrades.csv`, `buildings.csv` mappings.
- Translate raw replay IDs into AoK-specific terms.

## v0.5 strategy guide pipeline

- Run the full replay corpus through the offline pipeline.
- Generate first public guide draft:
  - team roles
  - timing windows
  - anti-turtle advice
  - cavalry pressure signals
  - defensive overinvestment signals

## Later: Discord guide commands

- `/aok_guide anti_turtle`
- `/aok_guide cavalry`
- `/aok_player_style <name>`
- `/aok_timing_windows`

## Later: anti-spam/onboarding module

Keep this isolated from the replay bot until the MVP is stable.

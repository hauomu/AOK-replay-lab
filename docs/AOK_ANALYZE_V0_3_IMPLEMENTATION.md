# `/aok_analyze` v0.3 implementation notes

This version changes `/aok_analyze` from a mostly numeric replay parser into a summary-first replay evaluation feature.

## Implemented features

### 1. Player 15 / Animals tracking

AoK assigns neutral animals to **Player 15**. The parser now treats `m_playerId == 15`, `m_controlPlayerId == 15`, `m_unitOwnerPlayerId == 15`, or `m_killerPlayerId == 15` as a special actor:

```text
Animals / Player 15
```

The bot now tracks:

- animal units seen/born
- animal deaths
- animal kills caused against real players
- player animal kills
- player deaths to animals
- top killed animal types
- animal unit types credited with kills
- team-level animal K/D

Animal kills are separated from human/team combat kills so ordinary leaderboard/team K/D does not get inflated by clearing neutral camps.

### 2. Summary-first Discord embed

The Discord embed is now less number-heavy. It prioritizes:

- short verdict
- turning point
- Team 0 / Team 1 evaluations
- Player 15 / Animals impact
- most useful player takeaway
- only a few evidence highlights

The full evidence stays in the attached Markdown report.

### 3. Full Markdown report

The attached Markdown report now includes:

- short verdict
- turning point
- team evaluations
- Player 15 / Animals impact
- most useful player takeaway
- evidence highlights
- team evidence table
- Player 15 / Animals evidence table
- player-vs-animals table
- 5-minute timeline snapshots
- player evidence table
- player composition detail
- raw event counts and limitations

### 4. Timeline-based turning point heuristic

The parser builds cumulative 5-minute team snapshots from tracker events. The report uses these to identify the largest detected fight swing.

This is still replay-protocol analysis, not visual map observation.

### 5. Local DB migration

The local SQLite table `replay_players` now stores:

- `animal_kills`
- `deaths_to_animals`

Existing v0.1/v0.2 databases are migrated with `ALTER TABLE` when the bot starts.

## Files changed

```text
discord_bot/src/aok_bot/models.py
discord_bot/src/aok_bot/replay_parser.py
discord_bot/src/aok_bot/reporting.py
discord_bot/src/aok_bot/storage.py
discord_bot/src/aok_bot/bot.py
```

## Known limitations

- This reads SC2 replay protocol data, not visual camera footage.
- `Player 15` is treated as animals/neutral based on TwoDie's AoK-specific clarification.
- Some deaths may still have no clean player killer in replay metadata.
- Ability/button IDs still need AoK map metadata for perfect build-order and tech names.
- Role/style labels are heuristic guide-writing aids, not final competitive truth.

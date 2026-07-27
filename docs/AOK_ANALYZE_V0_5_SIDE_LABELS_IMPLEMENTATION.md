# AoK `/aok_analyze` v0.5 — Team Rosters + Player Side Labels

## Purpose

The `/aok_analyze` Discord summary now makes team membership explicit in the human-readable output.

Before this patch, the summary could say:

```text
Team 0 did not get a clear win result...
Main PvP kill leader: TwoDie...
```

That was hard to read because users had to infer who belonged to each team.

## New behavior

For team games, team evaluation lines now include the team roster directly beside the team label:

```text
Team 0 (TwoDie, phantom, Sebda) won...
Team 1 (Monstr, пендальф, АРТАНИС, Makak) did not get a clear win result...
```

Evidence highlights now show the side for individual player callouts:

```text
Main PvP kill leader: TwoDie (Team 0) with 568 player-vs-player credited kills.
Largest production footprint: TwoDie (Team 0) with 709 units born.
```

## FFA behavior

In Free For All / no-alliance mode, players are not assigned fake teams in the summary.

Player callouts use:

```text
GWWolf (FFA side)
shermanator (FFA side)
```

This keeps FFA reports clear and avoids implying that FFA players are allied.

## Markdown report updates

The full attached Markdown report now also uses readable side labels in:

- team/player evidence table
- player-vs-animals table
- player evidence table
- timeline snapshots

## Files changed

```text
discord_bot/src/aok_bot/models.py
discord_bot/src/aok_bot/replay_parser.py
discord_bot/src/aok_bot/reporting.py
```

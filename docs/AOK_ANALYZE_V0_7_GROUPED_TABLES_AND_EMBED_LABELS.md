# AoK `/aok_analyze` v0.7 — Grouped Player Tables + Embed Side Labels

## Purpose

v0.7 improves readability in both the Markdown report and the Discord embed summary.

The previous v0.6 report had readable Markdown tables, but the player tables were still one long list. This made it hard to immediately see which players belonged to which team. The Discord embed also needed explicit team/side labels so evidence lines are easier to interpret without opening the attached Markdown report.

## Markdown report changes

The following sections are now grouped by side:

- `Player combat + activity`
- `Player army profile`

For team games, each section gets subheaders such as:

```text
### Team 0 (TwoDie, phantom, Sebda)
### Team 1 (Monstr, пендальф, АРТАНИС, Makak)
```

For FFA/no-alliance games, each player remains their own hostile side, so the report uses FFA-safe labels such as:

```text
### GWWolf (FFA side)
### shermanator (FFA side)
```

This avoids implying fake alliances in Free For All mode.

## Discord embed changes

The embed now adds a compact side-label field:

```text
Team labels
• Team 0 = TwoDie, phantom, Sebda
• Team 1 = Monstr, пендальф, АРТАНИС, Makak
```

For FFA:

```text
Side labels
• GWWolf = FFA side
• shermanator = FFA side
```

Evidence highlights are also regenerated with side labels, for example:

```text
Main PvP kill leader: TwoDie (Team 0) with 568 player-vs-player credited kills.
Most efficient major fighter: Sebda (Team 0) at PvP K/L 205/143.
Largest production footprint: shermanator (FFA side) with 1275 units born.
```

## Files changed

```text
discord_bot/src/aok_bot/reporting.py
```

## Notes

This patch does not change replay parsing. It only changes summary/report presentation.

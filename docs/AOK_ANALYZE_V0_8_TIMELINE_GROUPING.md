# AoK `/aok_analyze` v0.8 — Timeline Snapshots Grouped by Side

## Purpose

v0.8 improves the Markdown report timeline layout.

Earlier reports listed cumulative timeline snapshots in alternating timestamp order:

```text
5:00  Team 0
5:00  Team 1
10:00 Team 0
10:00 Team 1
```

That made point-in-time comparison possible, but it was harder to read each side's progression across the match.

v0.8 groups timeline snapshots by team/side first, then sorts each side by time:

```text
Team 0
5:00
10:00
15:00
...

Team 1
5:00
10:00
15:00
...
```

## Behavior

For team games, the report now shows:

```text
### Team 0 (player names)
### Team 1 (player names)
```

For FFA/no-alliance games, the report avoids fake teams and shows:

```text
### PlayerName (FFA side)
```

For duel-style games, the report shows:

```text
### PlayerName (duel side)
```

## Scope

This is a presentation-only change in `reporting.py`.

It does not change replay parsing, storage, animal tracking, FFA detection, or combat calculations.

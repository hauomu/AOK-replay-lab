# AoK `/aok_analyze` v0.4 — FFA / No-Alliance Support

## Purpose

The analyzer previously assumed that Age of Knights displays were mostly team games. This caused Free For All / no-alliance games to be summarized incorrectly as if all players belonged to the same team.

v0.4 adds explicit match-mode detection and FFA reporting.

## Required behavior

`/aok_analyze` should detect whether a replay is:

- Team game
- Free-for-all / no-alliance
- Duel-style game
- Team game with Player 15 animals / neutral units

For FFA games, do **not** merge players into one team. Each player should be treated as their own hostile side.

## FFA output shape

For FFA/no-alliance games, the Discord summary should prioritize:

- Match mode: Free-for-all
- Winner if recorded, otherwise likely leader / strongest conversion profile
- Per-player combat conversion
- PvP kills and losses
- Animal interaction if Player 15 exists
- Turning point / collapse window if detectable
- Most useful player takeaway

## Implementation notes

The parser should infer FFA when alliance/team metadata does not produce meaningful teams, or when every active human player appears hostile/unallied.

Avoid presenting fake teams in FFA mode. Use player-centric analysis instead.

## Player 15 / animals

Player 15 remains a special neutral actor:

```text
Player 15 = Animals / Neutral
```

Animal kills, animal deaths, and deaths caused by animals should still be tracked in both team and FFA modes.

## Guide value

FFA reports are especially useful for detecting:

- strongest individual macro/combat profile
- inefficient aggression
- who fed units into static defenses or animals
- who survived longest
- who converted production into effective kills
- when the match became one-sided

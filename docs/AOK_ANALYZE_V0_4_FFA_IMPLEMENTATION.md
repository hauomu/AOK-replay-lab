# `/aok_analyze` v0.4: Free-for-all / no-alliance support

## Problem fixed

Older analyzer versions assumed that an AoK replay should be evaluated as a team game. In Free For All/no-alliance displays, the replay can encode all human players under the same `m_teamId`, which caused the bot to merge every player into one side.

That made these reports wrong for FFA:

- winner/side detection
- team evidence table
- turning-point read
- player/team K/L aggregation
- verdict and player takeaway

## v0.4 behavior

The analyzer now detects FFA-like displays and treats every human player as their own hostile side.

Detection rules:

- 3+ players and all players have the same `m_teamId` → `Free-for-all`
- 3+ players and every player already has a unique `m_teamId` → `Free-for-all`
- 2 players with unique team IDs → `Duel`
- otherwise → `Team`

When the replay stores all FFA players under one team id, v0.4 rewrites analysis groups internally so each player gets their own side. This affects analysis only; it does not modify the replay.

## Reporting changes

The report now includes:

- `Match mode: Free-for-all`
- FFA/player evaluations instead of team-only evaluation
- side labels using player names rather than `Team 0` / `Team 1`
- FFA-aware turning point text
- FFA-aware player takeaway
- likely leader inference when the replay metadata does not record a clean winner

## Winner handling

Some AoK FFA displays do not mark a clean `Win` result in replay metadata. In those cases, v0.4 does not pretend there is an official winner. It reports:

```text
Not recorded; likely leader: <player>
```

The likely leader heuristic is based on:

1. PvP kill/loss margin
2. PvP K/L ratio
3. units born
4. command activity

This is intentionally labelled as likely/inferred, not official.

## Compatibility

Team games still use the previous team aggregation behavior.

Player 15 / Animals tracking from v0.3 is still preserved.

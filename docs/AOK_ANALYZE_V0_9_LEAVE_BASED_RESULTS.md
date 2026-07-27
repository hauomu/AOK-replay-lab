# AoK `/aok_analyze` v0.9 — Leave-Based Result Inference

## Purpose

Some Age of Knights replays do not store a clean winner/loss result in replay metadata. The bot now uses leave events as a result signal.

## Team games

In team mode:

```text
If every player on a team leaves, that team is treated as losing.
```

If exactly one team remains not fully eliminated by leave events and no official replay winner was recorded, that remaining team is treated as the winning side.

Example:

```text
Team 0: TwoDie, phantom — did not fully leave
Team 1: Monstr, Makak — all left

Result inference:
Team 1 = Loss
Team 0 = Win
```

## FFA / no-alliance games

In FFA mode:

```text
If a player leaves, that player is treated as losing.
```

If exactly one FFA side/player does not leave and no official winner was recorded, that player is treated as the winner.

If every FFA side has a leave event, the bot keeps the official winner as unknown instead of inventing a winner.

## Official winner metadata

The bot does not demote an official replay `Win`. Leave-based inference is mainly used to resolve `Undecided` / missing metadata into useful practical results.

## Report behavior

Leave-based inference appears in evidence highlights, for example:

```text
Leave-based result inference: Team 1 (Monstr, Makak) all left, so that side is treated as a loss.
Leave-based result inference: Team 0 is the only side not fully eliminated by leave events, so it is treated as the winning side.
```

Team/player evaluation language now distinguishes:

```text
won
lost
did not get a clear win result
```

rather than treating every non-win as ambiguous.

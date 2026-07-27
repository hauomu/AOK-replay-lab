# `/aok_analyze` v1.0 — Technology, Mechanical, and Resource Evaluation

## Purpose

This update adds technology-tree inference and replay resource tracking to the detailed AoK analysis. It also replaces the old loose siege category with an exact mechanical-unit model.

## Resource labels

The replay parser maps SC2 tracker channels to AoK terminology:

```text
Gold = Minerals
Wood = Vespene
Iron = Terrazine
```

### Direct values

When present in `SPlayerStatsEvent`, the bot records:

- latest current stockpile
- latest collection rate
- peak observed stockpile
- peak observed collection rate

### Estimated values

The bot also creates best-effort gathered and lost-value estimates from current, used, and lost score-value fields. Every report labels these values as estimates. They are not treated as an exact transaction ledger.

If the replay exposes no Terrazine fields, Iron is shown as `n/a`; absence is never silently converted to a confirmed zero.

## Technology events

### Exact observed age markers

```text
AgeIIDarkAge       -> Dark Age
AgeIIIFeudalAge2  -> Feudal Age
AgeIVCastleAge    -> Castle Age
AgeVImperialAge  -> Imperial Age
```

### Exact observed tech structures

```text
Blacksmith
FletchersWorkshop
SiegeWorkshop
Castle
AlchemistsLab
```

### Explicit key unlocks

```text
UnlockHandCannoneer
UnlockBombardCannons
```

### Gameplay upgrade families

The parser retains gameplay-relevant economy, infantry, ranged, cavalry, general-combat, fortification, and mechanical upgrades. Cosmetic/UI/meta events such as dances and sprays are ignored.

## Inferred unit requirements

First appearance of advanced units is linked to the most likely structure, unlock, and age. These links are displayed as **inferred**, not official prerequisites. Exact costs and hard gates require map data or TwoDie confirmation.

Examples:

```text
Hand Cannoneer -> Unlock Hand Cannoneer; likely Alchemist's Lab + Imperial Age
Bombard Cannon -> Unlock Bombard Cannons; likely Alchemist's Lab + Imperial Age
Ballista/Ram/Catapult -> likely Siege Workshop + Castle Age
Trebuchet -> likely Castle + Castle Age
```

## Exact mechanical model

```text
Ballista
BatteringRam
BombardCannon
Catapult
ExplosiveWagon / ExplosivesWagon
TrebutchetMobile
TrebutchetSieged
```

Important rules:

- `HandCannoneer` is not mechanical.
- A trebuchet is counted once by unique unit tag even when it changes mode.
- `TrebutchetMobile` cannot attack.
- move-mode deaths are still recorded as mechanical asset losses.
- only attack-capable types, including `TrebutchetSieged`, receive mechanical kill credit.

## Technology score

The score is a transparent relative heuristic:

```text
age frontier
+ unique completed tech structures
+ unique key unlocks
+ unique gameplay upgrades, capped
+ unique advanced unit types fielded
```

For a team, the score uses the side's **unique technology frontier**, not the sum of every player's score. This avoids automatically inflating a four-player team over a three-player team because both sides researched duplicate baseline technologies.

## Report additions

The Discord summary now includes a compact `Technology + resources` field. The Markdown report adds:

- side technology overview
- side resource overview
- player technology profiles
- player resource tables
- grouped tech/resource timeline snapshots
- inferred advanced-unit requirements
- mechanical production, kills, and losses
- trebuchet state-specific evidence
- resource and inference provenance notes

## Evaluation use

Technology and resources are supporting evidence, not standalone proof of victory. The bot combines them with:

- PvP combat conversion
- recent timeline swing
- unit production/replacement capability
- mechanical conversion
- defensive footprint
- activity
- leave-based result logic

## Validation status

- Python source compilation: passed
- synthetic team/FFA report rendering: passed
- SQLite migration/save/profile smoke test: passed
- direct resource-field mapping smoke test: passed
- real replay validation: must be run in an environment with `mpyq` and Blizzard `s2protocol` installed

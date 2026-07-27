# AoK Replay Analysis

| Field | Value |
| ----- | ----- |
| File | `Age of Knights (144).SC2Replay` |
| Map | Age of Knights |
| Duration | 80:24 |
| Match mode | Free-for-all |
| Winning side | Not recorded; likely leader: GWWolf |
| Game version/build | 97425 |
| Parser OK | True |
| Report format | Jinja2 compact table layout |

## Short verdict

Free-for-all detected, but no clean official winner was found in replay metadata. The likely leader by PvP margin/conversion is GWWolf.

## Turning point

- Largest detected fight swing is around 45:00–50:00, where GWWolf improved its relative kill/loss position by about 206 units.

## FFA/player evaluations

- GWWolf did not get a clear win result. It reads as a Infantry + firepower frontline profile with 1 player(s). Main strengths: better trade conversion. Main risks/problems: no major weakness flagged by the heuristic read. Evidence snapshot: PvP K/L 1385/1004 (1.38), units 1175, commands 700.
- Ynosyn did not get a clear win result. It reads as a Infantry + firepower frontline profile with 1 player(s). Main strengths: no single dominant advantage detected. Main risks/problems: weaker fight conversion, lower visible command activity. Evidence snapshot: PvP K/L 156/265 (0.59), units 253, commands 140.
- shermanator did not get a clear win result. It reads as a Ranged/firepower-heavy profile with 1 player(s). Main strengths: stronger defensive layer. Main risks/problems: higher attrition, weaker fight conversion. Evidence snapshot: PvP K/L 990/1262 (0.78), units 1275, commands 760.
- FatalEStoned did not get a clear win result. It reads as a Mobile cavalry-pressure profile with 1 player(s). Main strengths: no single dominant advantage detected. Main risks/problems: weaker fight conversion, lower visible command activity. Evidence snapshot: PvP K/L 157/327 (0.48), units 295, commands 146.


## Most useful player takeaway

- In FFA, do not evaluate the replay as Team 0 vs Team 1. Every player is a separate hostile side, so survival timing, third-partying, map control, and individual replacement tempo matter more than team K/D.

## Evidence highlights

- FFA leader by PvP margin/conversion: GWWolf at 1385/1004 (margin 381, K/L 1.379).
- Closest rival by the same heuristic: Ynosyn at 156/265 (margin -109).
- Main PvP kill leader: GWWolf (FFA side) with 1385 player-vs-player credited kills.
- Most efficient major fighter: GWWolf (FFA side) at PvP K/L 1385/1004.
- Largest production footprint: shermanator (FFA side) with 1275 units born.
- Strongest defensive footprint: shermanator (FFA side) with 100 static-defense/wall/castle-style completions or spawns.

## Match story notes

- Not recorded; likely leader: GWWolf.
- GWWolf: Infantry + firepower frontline profile, PvP K/L 1385/1004 (1.38), animal K/D 0/0.
- Ynosyn: Infantry + firepower frontline profile, PvP K/L 156/265 (0.59), animal K/D 0/0.
- shermanator: Ranged/firepower-heavy profile, PvP K/L 990/1262 (0.78), animal K/D 0/0.
- FatalEStoned: Mobile cavalry-pressure profile, PvP K/L 157/327 (0.48), animal K/D 0/0.

## FFA/player side overview

| Side         | Result    | Style                                  |
| ------------ | --------- | -------------------------------------- |
| GWWolf       | Undecided | Infantry + firepower frontline profile |
| Ynosyn       | Undecided | Infantry + firepower frontline profile |
| FatalEStoned | Undecided | Mobile cavalry-pressure profile        |
| shermanator  | Undecided | Ranged/firepower-heavy profile         |

## Side combat + activity

| Side         | PvP K/L          | Animal K/D | Units | Cmds |
| ------------ | ---------------- | ---------- | ----: | ---: |
| GWWolf       | 1385/1004 (1.38) | 0/0 (N/A)  |  1175 |  700 |
| Ynosyn       | 156/265 (0.59)   | 0/0 (N/A)  |   253 |  140 |
| FatalEStoned | 157/327 (0.48)   | 0/0 (N/A)  |   295 |  146 |
| shermanator  | 990/1262 (0.78)  | 0/0 (N/A)  |  1275 |  760 |

## Side army / defense footprint

| Side         | Static | Walls/gates | Castles | Cavalry | Ranged | Infantry | Siege |
| ------------ | -----: | ----------: | ------: | ------: | -----: | -------: | ----: |
| GWWolf       |     79 |           4 |       2 |       1 |    375 |      664 |   395 |
| Ynosyn       |     53 |           0 |       0 |      17 |     33 |      112 |     3 |
| FatalEStoned |     29 |           0 |       2 |     143 |     65 |       58 |     0 |
| shermanator  |    100 |           8 |       9 |     117 |    545 |      446 |   370 |


## Timeline snapshots

These are cumulative 5-minute snapshots. They support the turning-point read but should be treated as replay-protocol evidence, not visual map observation.

| Time  | Side         | PvP K/L  | Units born | Animal K/D |
| ----- | ------------ | -------- | ---------: | ---------- |
| 5:00  | GWWolf       | 1/57     |         81 | 0/0        |
| 5:00  | Ynosyn       | 0/50     |         82 | 0/0        |
| 5:00  | shermanator  | 0/39     |         66 | 0/0        |
| 5:00  | FatalEStoned | 0/23     |         47 | 0/0        |
| 10:00 | GWWolf       | 1/57     |         88 | 0/0        |
| 10:00 | Ynosyn       | 0/50     |        107 | 0/0        |
| 10:00 | shermanator  | 0/39     |         82 | 0/0        |
| 10:00 | FatalEStoned | 0/23     |         70 | 0/0        |
| 15:00 | GWWolf       | 1/57     |        101 | 0/0        |
| 15:00 | Ynosyn       | 2/69     |        144 | 0/0        |
| 15:00 | shermanator  | 19/41    |        113 | 0/0        |
| 15:00 | FatalEStoned | 0/23     |         91 | 0/0        |
| 20:00 | GWWolf       | 1/57     |        116 | 0/0        |
| 20:00 | Ynosyn       | 2/69     |        176 | 0/0        |
| 20:00 | shermanator  | 19/41    |        149 | 0/0        |
| 20:00 | FatalEStoned | 0/23     |        108 | 0/0        |
| 25:00 | GWWolf       | 1/57     |        158 | 0/0        |
| 25:00 | Ynosyn       | 79/189   |        232 | 0/0        |
| 25:00 | shermanator  | 140/118  |        224 | 0/0        |
| 25:00 | FatalEStoned | 0/24     |        143 | 0/0        |
| 30:00 | GWWolf       | 11/58    |        219 | 0/0        |
| 30:00 | Ynosyn       | 152/252  |        253 | 0/0        |
| 30:00 | shermanator  | 196/194  |        322 | 0/0        |
| 30:00 | FatalEStoned | 1/25     |        170 | 0/0        |
| 35:00 | GWWolf       | 121/152  |        323 | 0/0        |
| 35:00 | Ynosyn       | 156/263  |        253 | 0/0        |
| 35:00 | shermanator  | 197/202  |        379 | 0/0        |
| 35:00 | FatalEStoned | 95/122   |        188 | 0/0        |
| 40:00 | GWWolf       | 236/212  |        399 | 0/0        |
| 40:00 | Ynosyn       | 156/263  |        253 | 0/0        |
| 40:00 | shermanator  | 197/202  |        390 | 0/0        |
| 40:00 | FatalEStoned | 155/237  |        295 | 0/0        |
| 45:00 | GWWolf       | 345/222  |        400 | 0/0        |
| 45:00 | Ynosyn       | 156/263  |        253 | 0/0        |
| 45:00 | shermanator  | 206/222  |        402 | 0/0        |
| 45:00 | FatalEStoned | 157/327  |        295 | 0/0        |
| 50:00 | GWWolf       | 519/293  |        441 | 0/0        |
| 50:00 | Ynosyn       | 156/263  |        253 | 0/0        |
| 50:00 | shermanator  | 277/396  |        533 | 0/0        |
| 50:00 | FatalEStoned | 157/327  |        295 | 0/0        |
| 55:00 | GWWolf       | 655/386  |        485 | 0/0        |
| 55:00 | Ynosyn       | 156/263  |        253 | 0/0        |
| 55:00 | shermanator  | 370/532  |        660 | 0/0        |
| 55:00 | FatalEStoned | 157/327  |        295 | 0/0        |
| 60:00 | GWWolf       | 748/513  |        583 | 0/0        |
| 60:00 | Ynosyn       | 156/265  |        253 | 0/0        |
| 60:00 | shermanator  | 499/625  |        750 | 0/0        |
| 60:00 | FatalEStoned | 157/327  |        295 | 0/0        |
| 65:00 | GWWolf       | 862/596  |        712 | 0/0        |
| 65:00 | Ynosyn       | 156/265  |        253 | 0/0        |
| 65:00 | shermanator  | 582/739  |        817 | 0/0        |
| 65:00 | FatalEStoned | 157/327  |        295 | 0/0        |
| 70:00 | GWWolf       | 1104/754 |        906 | 0/0        |
| 70:00 | Ynosyn       | 156/265  |        253 | 0/0        |
| 70:00 | shermanator  | 740/981  |       1055 | 0/0        |
| 70:00 | FatalEStoned | 157/327  |        295 | 0/0        |
| 75:00 | GWWolf       | 1208/842 |        983 | 0/0        |
| 75:00 | Ynosyn       | 156/265  |        253 | 0/0        |
| 75:00 | shermanator  | 828/1085 |       1189 | 0/0        |
| 75:00 | FatalEStoned | 157/327  |        295 | 0/0        |
| 80:00 | GWWolf       | 1362/991 |       1155 | 0/0        |
| 80:00 | Ynosyn       | 156/265  |        253 | 0/0        |
| 80:00 | shermanator  | 977/1239 |       1273 | 0/0        |
| 80:00 | FatalEStoned | 157/327  |        295 | 0/0        |

## Player overview

| Player       | Side     | Result    | Role read                           | Left  |
| ------------ | -------- | --------- | ----------------------------------- | ----- |
| GWWolf       | FFA side | Undecided | Main combat carry / pressure leader |       |
| Ynosyn       | FFA side | Undecided | Mixed/support                       | 30:16 |
| FatalEStoned | FFA side | Undecided | Cavalry pressure / mobile carry     | 38:29 |
| shermanator  | FFA side | Undecided | Main combat carry / pressure leader | 80:24 |

## Player combat + activity

### GWWolf (FFA side)

| Player | PvP K/L          | Animal K/D | Units | Structures | Cmds | APM |
| ------ | ---------------- | ---------- | ----: | ---------: | ---: | ---: |
| GWWolf | 1385/1004 (1.38) | 0/0 (N/A)  |  1175 |         94 |  700 |   9 |

### Ynosyn (FFA side)

| Player | PvP K/L        | Animal K/D | Units | Structures | Cmds | APM |
| ------ | -------------- | ---------- | ----: | ---------: | ---: | ---: |
| Ynosyn | 156/265 (0.59) | 0/0 (N/A)  |   253 |         17 |  140 |   2 |

### FatalEStoned (FFA side)

| Player       | PvP K/L        | Animal K/D | Units | Structures | Cmds | APM |
| ------------ | -------------- | ---------- | ----: | ---------: | ---: | ---: |
| FatalEStoned | 157/327 (0.48) | 0/0 (N/A)  |   295 |         37 |  146 |   2 |

### shermanator (FFA side)

| Player      | PvP K/L         | Animal K/D | Units | Structures | Cmds | APM |
| ----------- | --------------- | ---------- | ----: | ---------: | ---: | ---: |
| shermanator | 990/1262 (0.78) | 0/0 (N/A)  |  1275 |        108 |  760 |   9 |

## Player army profile

### GWWolf (FFA side)

| Player | Static | Cavalry | Ranged | Infantry | Siege | Top units                                                    |
| ------ | -----: | ------: | -----: | -------: | ----: | ------------------------------------------------------------ |
| GWWolf |     79 |       1 |    375 |      664 |   395 | Swordsman×422, HandCannoneer×354, Spearman×242, GuardPost×60 |

### Ynosyn (FFA side)

| Player | Static | Cavalry | Ranged | Infantry | Siege | Top units                                          |
| ------ | -----: | ------: | -----: | -------: | ----: | -------------------------------------------------- |
| Ynosyn |     53 |      17 |     33 |      112 |     3 | Swordsman×82, GuardPost×53, Peasant3×41, Archer×20 |

### FatalEStoned (FFA side)

| Player       | Static | Cavalry | Ranged | Infantry | Siege | Top units                                            |
| ------------ | -----: | ------: | -----: | -------: | ----: | ---------------------------------------------------- |
| FatalEStoned |     29 |     143 |     65 |       58 |     0 | Knight×80, Swordsman×58, HorseArcher×52, Peasant3×51 |

### shermanator (FFA side)

| Player      | Static | Cavalry | Ranged | Infantry | Siege | Top units                                                      |
| ----------- | -----: | ------: | -----: | -------: | ----: | -------------------------------------------------------------- |
| shermanator |    100 |     117 |    545 |      446 |   370 | HandCannoneer×338, Militia×302, Crossbowman×178, Swordsman×142 |

## Player composition detail

### GWWolf (FFA side)

- **Role read:** Main combat carry / pressure leader
- **PvP combat:** 1385 kills / 1004 losses, K/L 1.38
- **Animal interaction:** 0 animal kills / 0 deaths to animals
- **Activity:** 700 commands, 193 control-group events, 0 pings, 5 chat messages
- **Production:** 1175 units born, 94 completed structures, 47 upgrades
- **Top units:** Swordsman×422, HandCannoneer×354, Spearman×242, GuardPost×60, Peasant3×59, BombardCannon×35, AgeResearchCenter×1, MountedScout×1
- **Top structures:** ArcheryRange×21, House1×20, BarracksAoK×16, WatchPost×12, SiegeWorkshop×6, GoldMine×5, Castle×2, GateClosedVertical×2
- **Most lost unit types:** Swordsman×403, HandCannoneer×300, Spearman×206, GuardPost×57, BombardCannon×28, Peasant3×5, ArcheryRange×3, SiegeWorkshop×1
- **Unit types credited with kills:** HandCannoneer×836, Swordsman×283, BombardCannon×134, Spearman×129, Peasant3×2, UnknownKillerUnit×1
### shermanator (FFA side)

- **Role read:** Main combat carry / pressure leader
- **PvP combat:** 990 kills / 1262 losses, K/L 0.78
- **Animal interaction:** 0 animal kills / 0 deaths to animals
- **Activity:** 760 commands, 457 control-group events, 0 pings, 6 chat messages
- **Production:** 1275 units born, 108 completed structures, 50 upgrades
- **Top units:** HandCannoneer×338, Militia×302, Crossbowman×178, Swordsman×142, Horseman×116, Peasant3×90, GuardPost×41, Archer×20
- **Top structures:** GuardTower×27, WatchPost×15, House1×11, ArcheryRange×9, BarracksAoK×9, Castle×9, GoldMine×5, GateClosedVertical×4
- **Most lost unit types:** HandCannoneer×335, Militia×302, Crossbowman×178, Swordsman×142, Horseman×114, GuardPost×40, Peasant3×36, Archer×20
- **Unit types credited with kills:** HandCannoneer×473, Crossbowman×164, Castle×67, Swordsman×66, Militia×54, GuardTower×47, Peasant3×38, Archer×34
- **Leave time:** 80:24
### FatalEStoned (FFA side)

- **Role read:** Cavalry pressure / mobile carry
- **PvP combat:** 157 kills / 327 losses, K/L 0.48
- **Animal interaction:** 0 animal kills / 0 deaths to animals
- **Activity:** 146 commands, 0 control-group events, 0 pings, 0 chat messages
- **Production:** 295 units born, 37 completed structures, 26 upgrades
- **Top units:** Knight×80, Swordsman×58, HorseArcher×52, Peasant3×51, GuardPost×27, Crossbowman×10, Horseman×10, Archer×2
- **Top structures:** House1×13, GoldMine×7, Stable×5, BarracksAoK×3, Castle×2, AlchemistsLab×1, ArcheryRange×1, Blacksmith×1
- **Most lost unit types:** Knight×80, Swordsman×56, Peasant3×51, HorseArcher×50, GuardPost×27, House1×13, Crossbowman×10, Horseman×10
- **Unit types credited with kills:** Knight×72, HorseArcher×54, Peasant3×14, Swordsman×8, Crossbowman×3, Archer×2, Horseman×2, Castle×1
- **Leave time:** 38:29
### Ynosyn (FFA side)

- **Role read:** Mixed/support
- **PvP combat:** 156 kills / 265 losses, K/L 0.59
- **Animal interaction:** 0 animal kills / 0 deaths to animals
- **Activity:** 140 commands, 5 control-group events, 0 pings, 3 chat messages
- **Production:** 253 units born, 17 completed structures, 28 upgrades
- **Top units:** Swordsman×82, GuardPost×53, Peasant3×41, Archer×20, Militia×18, Spearman×12, Horseman×10, Crossbowman×6
- **Top structures:** House1×6, BarracksAoK×2, ArcheryRange×1, Blacksmith×1, FletchersWorkshop×1, GoldMine×1, Market×1, SiegeWorkshop×1
- **Most lost unit types:** Swordsman×79, GuardPost×53, Peasant3×41, Archer×20, Militia×18, Spearman×12, Horseman×8, HorseArcher×6
- **Unit types credited with kills:** Swordsman×95, Archer×30, Crossbowman×16, HorseArcher×6, Catapult×3, Spearman×3, Peasant3×2, Horseman×1
- **Leave time:** 30:16

## Raw event counts

| Event type     | Count |
| -------------- | ----: |
| game_events    | 34078 |
| tracker_events | 12758 |
| message_events |    37 |


## Known limitations

- This reads replay protocol events, not a video recording.
- Player 15 is treated as Animals/Neutral because AoK assigns animals to that player slot.
- PvP K/L excludes animal kills; animal K/D is tracked separately.
- Ability/button IDs still need AoK map metadata for perfect build/research/action names.
- FFA/no-alliance games are split into one analysis side per player; team games still aggregate allied players.
- Role labels are heuristic reads based on units, structures, kills/losses, animal interaction, and activity.

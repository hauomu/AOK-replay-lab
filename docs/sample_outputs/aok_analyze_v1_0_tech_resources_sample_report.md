# AoK Replay Analysis

| Field | Value |
| ----- | ----- |
| File | `synthetic_v1.SC2Replay` |
| Map | Age of Knights |
| Duration | 40:00 |
| Match mode | Team |
| Winning side | Team 1 (TwoDie, phantom) |
| Game version/build | synthetic |
| Parser OK | True |
| Report format | Jinja2 compact table layout |

## Short verdict

Team 1 (TwoDie, phantom) won through a Mixed-composition team profile, with the strongest evidence coming from fight conversion, production/remax, and role coverage.

## Turning point

- Largest detected fight swing is around 5:00–20:00, where Team 1 (TwoDie, phantom) improved its relative kill/loss position by about 104 units.

## Team evaluations

- Team 1 (TwoDie, phantom) won. It reads as a Mixed-composition team with 2 player(s). Main strengths: better trade conversion, higher visible activity, more map/animal clearing, deeper technology progression, stronger tracked economy throughput, more converted mechanical firepower. Main risks/problems: no major weakness flagged by the heuristic read. Evidence snapshot: PvP K/L 290/220 (1.32), units 780, commands 1050, age Imperial Age, tech score 36, mechanical K/L 80/6.
- Team 2 (Makak, Monstr) lost. It reads as a Mixed-composition team with 2 player(s). Main strengths: no single dominant advantage detected. Main risks/problems: higher attrition, weaker fight conversion, lower visible command activity, shallower technology progression. Evidence snapshot: PvP K/L 240/380 (0.63), units 720, commands 670, age Castle Age, tech score 17, mechanical K/L 25/11.

## Technology + economy evaluation

- Team 1 (TwoDie, phantom) — Imperial Age, tech score 36. Key tech structures: Blacksmith at 7:00, Fletcher's Workshop at 8:00, Siege Workshop at 16:00, Castle at 16:40. Key unlocks: Unlock Bombard Cannons at 28:50. Advanced units first fielded: Battering Ram at 17:20, Catapult at 18:20, Bombard Cannon at 29:40, Trebuchet (Move Mode) at 30:20. Mechanical K/L 80/6; trebuchets 2 total, 2 reached siege mode, 1 died in move mode. Latest stockpile: Gold 1,800, Wood 1,300, Iron 210; collection-rate snapshot: Gold 5,500, Wood 3,700, Iron 500; gathered estimate: Gold 10,500, Wood 7,500, Iron 1,010.
- Team 2 (Makak, Monstr) — Castle Age, tech score 17. Key tech structures: Blacksmith at 7:30, Siege Workshop at 18:20. Key unlocks: none recorded. Advanced units first fielded: Ballista at 19:50. Mechanical K/L 25/11; trebuchets 0 total, 0 reached siege mode, 0 died in move mode. Latest stockpile: Gold 1,200, Wood 900, Iron 0; collection-rate snapshot: Gold 4,200, Wood 2,600, Iron 0; gathered estimate: Gold 7,200, Wood 4,500, Iron 0.

## Player 15 / Animals impact

- Player 15 is tracked as Animals/Neutral. Animals killed 11 player units and lost 50 animal units.
- Top animal clearer: TwoDie (Team 1) with 20 animal kills.
- Most punished by animals: Makak (Team 2) with 9 deaths to Player 15.
- Most killed animal types: Boar×20, Wolf×18, Bear×12.
- Animal units doing the killing: Wolf×8, Bear×3.

## Most useful player takeaway

- Do not judge a push only by army count; replacement tempo and trade conversion are often more predictive than raw numbers.
- Team 1 (TwoDie, phantom) held the clearer tech lead; compare whether that lead became fielded units and mechanical kills rather than judging the tech score alone.

## Evidence highlights

- Main PvP kill leader: TwoDie (Team 1) with 200 player-vs-player credited kills.
- Most efficient major fighter: TwoDie (Team 1) at PvP K/L 200/120.
- Largest production footprint: TwoDie (Team 1) with 500 units born.
- Most animal clearing: TwoDie (Team 1) killed 20 Player 15 animal units.
- Deepest inferred tech profile: TwoDie (Team 1) reached Imperial Age with tech score 36 and 1 key unlock(s).
- Largest tracked economy throughput: TwoDie (Team 1) at Gold 6,900, Wood 5,250, Iron 1,010 gathered estimate.
- Best mechanical conversion: TwoDie (Team 1) at 80/6 mechanical K/L.

## Match story notes

- Winning side detected as Team 1 (TwoDie, phantom).
- Team 1 (TwoDie, phantom): Mixed-composition team, PvP K/L 290/220 (1.32), animal K/D 20/2, Imperial Age, tech score 36.
- Team 2 (Makak, Monstr): Mixed-composition team, PvP K/L 240/380 (0.63), animal K/D 8/9, Castle Age, tech score 17.

## Team overview

| Side                     | Result | Style                  |
| ------------------------ | ------ | ---------------------- |
| Team 1 (TwoDie, phantom) | Win    | Mixed-composition team |
| Team 2 (Makak, Monstr)   | Loss   | Mixed-composition team |

## Side combat + activity

| Side                     | PvP K/L        | Animal K/D   | Units | Cmds |
| ------------------------ | -------------- | ------------ | ----: | ---: |
| Team 1 (TwoDie, phantom) | 290/220 (1.32) | 20/2 (10.00) |   780 | 1050 |
| Team 2 (Makak, Monstr)   | 240/380 (0.63) | 8/9 (0.89)   |   720 |  670 |

## Side army / defense footprint

| Side                     | Static | Walls/gates | Castles | Cavalry | Ranged | Infantry | Mechanical |
| ------------------------ | -----: | ----------: | ------: | ------: | -----: | -------: | ---------: |
| Team 1 (TwoDie, phantom) |      0 |           0 |       0 |       0 |      0 |        0 |         15 |
| Team 2 (Makak, Monstr)   |      0 |           0 |       0 |       0 |      0 |        0 |          9 |

## Side technology overview

Trebuchets are shown as **total assets / reached siege mode / died in move mode**.

| Side                     | Age          | Tech score | Tech structures | Key unlocks | Advanced unit types | Mechanical K/L | Trebs T/S/M-loss |
| ------------------------ | ------------ | ---------: | --------------: | ----------: | ------------------: | -------------- | ---------------- |
| Team 1 (TwoDie, phantom) | Imperial Age |         36 |               5 |           1 |                   5 | 80/6           | 2/2/1            |
| Team 2 (Makak, Monstr)   | Castle Age   |         17 |               2 |           0 |                   1 | 25/11          | 0/0/0            |

## Side resource overview

AoK labels the replay channels as **Gold = minerals**, **Wood = vespene**, and **Iron = terrazine**. `n/a` means the replay protocol did not expose that channel; it is not a confirmed zero.

| Side                     |  Gold |  Wood | Iron | Gold rate | Wood rate | Iron rate | Gathered estimate                   |
| ------------------------ | ----: | ----: | ---: | --------: | --------: | --------: | ----------------------------------- |
| Team 1 (TwoDie, phantom) | 1,800 | 1,300 |  210 |     5,500 |     3,700 |       500 | Gold 10,500, Wood 7,500, Iron 1,010 |
| Team 2 (Makak, Monstr)   | 1,200 |   900 |    0 |     4,200 |     2,600 |         0 | Gold 7,200, Wood 4,500, Iron 0      |

## Player 15 / Animals evidence

- **Animal K/D:** 11 kills caused / 50 animal deaths
- **Animal units seen/born:** 80
- **Most killed animal types:** Boar×20, Wolf×18, Bear×12
- **Animal units credited with kills:** Wolf×8, Bear×3

### Player vs Animals table

| Player | Side   | Animal kills | Deaths to animals | Animal K/D |
| ------ | ------ | -----------: | ----------------: | ---------: |
| TwoDie | Team 1 |           20 |                 2 |      10.00 |
| Makak  | Team 2 |            8 |                 9 |       0.89 |

## Timeline snapshots

These are cumulative 5-minute snapshots. They support the turning-point read but should be treated as replay-protocol evidence, not visual map observation.

### Team 1 (TwoDie, phantom) — combat

| Time  | PvP K/L | Units born | Animal K/D |
| ----- | ------- | ---------: | ---------- |
| 5:00  | 10/8    |        100 | 4/1        |
| 20:00 | 150/100 |        430 | 16/2       |

### Team 1 (TwoDie, phantom) — technology + resources

| Time  | Age        | Tech | Mechanical K/L |  Gold |  Wood | Iron | Gold rate | Wood rate | Iron rate |
| ----- | ---------- | ---: | -------------- | ----: | ----: | ---: | --------: | --------: | --------: |
| 5:00  | Feudal Age |    8 | 0/0            |   500 |   300 |    0 |     1,200 |       700 |         0 |
| 20:00 | Castle Age |   20 | 42/3           | 1,800 | 1,300 |  210 |     5,500 |     3,700 |       500 |

### Team 2 (Makak, Monstr) — combat

| Time  | PvP K/L | Units born | Animal K/D |
| ----- | ------- | ---------: | ---------- |
| 5:00  | 8/12    |         95 | 2/2        |
| 20:00 | 110/170 |        390 | 6/7        |

### Team 2 (Makak, Monstr) — technology + resources

| Time  | Age        | Tech | Mechanical K/L |  Gold | Wood | Iron | Gold rate | Wood rate | Iron rate |
| ----- | ---------- | ---: | -------------- | ----: | ---: | ---: | --------: | --------: | --------: |
| 5:00  | Feudal Age |    6 | 0/0            |   400 |  250 |    0 |     1,050 |       650 |         0 |
| 20:00 | Castle Age |   14 | 15/8           | 1,200 |  900 |    0 |     4,100 |     2,600 |         0 |


## Player overview

| Player  | Side   | Result | Role read          | Left |
| ------- | ------ | ------ | ------------------ | ---- |
| TwoDie  | Team 1 | Win    | Mixed carry        |      |
| phantom | Team 1 | Win    | Mechanical support |      |
| Makak   | Team 2 | Loss   | Ranged firepower   |      |
| Monstr  | Team 2 | Loss   | Infantry frontline |      |

## Player combat + activity

### Team 1 (TwoDie, phantom)

| Player  | PvP K/L        | Animal K/D   | Units | Structures | Cmds | APM |
| ------- | -------------- | ------------ | ----: | ---------: | ---: | ---: |
| TwoDie  | 200/120 (1.67) | 20/2 (10.00) |   500 |         80 |  700 |     |
| phantom | 90/100 (0.90)  | 0/0 (N/A)    |   280 |         40 |  350 |     |

### Team 2 (Makak, Monstr)

| Player | PvP K/L        | Animal K/D | Units | Structures | Cmds | APM |
| ------ | -------------- | ---------- | ----: | ---------: | ---: | ---: |
| Makak  | 170/240 (0.71) | 8/9 (0.89) |   460 |         60 |  420 |     |
| Monstr | 70/140 (0.50)  | 0/0 (N/A)  |   260 |         35 |  250 |     |

## Player army profile

### Team 1 (TwoDie, phantom)

| Player  | Static | Cavalry | Ranged | Infantry | Mechanical | Top units |
| ------- | -----: | ------: | -----: | -------: | ---------: | --------- |
| TwoDie  |      0 |       0 |      0 |        0 |         15 | none      |
| phantom |      0 |       0 |      0 |        0 |          0 | none      |

### Team 2 (Makak, Monstr)

| Player | Static | Cavalry | Ranged | Infantry | Mechanical | Top units |
| ------ | -----: | ------: | -----: | -------: | ---------: | --------- |
| Makak  |      0 |       0 |      0 |        0 |          9 | none      |
| Monstr |      0 |       0 |      0 |        0 |          0 | none      |

## Player resource tracking

### Team 1 (TwoDie, phantom)

| Player  |  Gold | Wood | Iron | Gold rate | Wood rate | Iron rate | Gathered estimate                  |
| ------- | ----: | ---: | ---: | --------: | --------: | --------: | ---------------------------------- |
| TwoDie  | 1,200 |  850 |  210 |     3,400 |     2,400 |       500 | Gold 6,900, Wood 5,250, Iron 1,010 |
| phantom |   600 |  450 |    0 |     2,100 |     1,300 |         0 | Gold 3,600, Wood 2,250, Iron 0     |

### Team 2 (Makak, Monstr)

| Player | Gold | Wood | Iron | Gold rate | Wood rate | Iron rate | Gathered estimate              |
| ------ | ---: | ---: | ---: | --------: | --------: | --------: | ------------------------------ |
| Makak  |  600 |  450 |    0 |     2,100 |     1,300 |         0 | Gold 3,600, Wood 2,250, Iron 0 |
| Monstr |  600 |  450 |    0 |     2,100 |     1,300 |         0 | Gold 3,600, Wood 2,250, Iron 0 |

## Player technology profiles

Trebuchets are shown as **total assets / reached siege mode / died in move mode**.

### Team 1 (TwoDie, phantom)

| Player  | Age          | Tech score | Tech structures                                                          | Key unlocks                     | Advanced units                                                     | Mechanical K/L | Trebs T/S/M-loss |
| ------- | ------------ | ---------: | ------------------------------------------------------------------------ | ------------------------------- | ------------------------------------------------------------------ | -------------- | ---------------- |
| TwoDie  | Imperial Age |         36 | Blacksmith at 7:00, Fletcher's Workshop at 8:00, Siege Workshop at 16:00 | Unlock Bombard Cannons at 28:50 | Battering Ram at 17:20, Catapult at 18:20, Bombard Cannon at 29:40 | 80/6           | 2/2/1            |
| phantom | Feudal Age   |         12 | Blacksmith at 7:00, Fletcher's Workshop at 8:00                          | none recorded                   | none recorded                                                      | 0/0            | 0/0/0            |

### Team 2 (Makak, Monstr)

| Player | Age        | Tech score | Tech structures                             | Key unlocks   | Advanced units    | Mechanical K/L | Trebs T/S/M-loss |
| ------ | ---------- | ---------: | ------------------------------------------- | ------------- | ----------------- | -------------- | ---------------- |
| Makak  | Castle Age |         17 | Blacksmith at 7:30, Siege Workshop at 18:20 | none recorded | Ballista at 19:50 | 25/11          | 0/0/0            |
| Monstr | Feudal Age |         10 | Blacksmith at 7:30                          | none recorded | none recorded     | 0/0            | 0/0/0            |

## Player composition detail

### TwoDie (Team 1)

- **Role read:** Mixed carry
- **PvP combat:** 200 kills / 120 losses, K/L 1.67
- **Animal interaction:** 20 animal kills / 2 deaths to animals
- **Activity:** 700 commands, 0 control-group events, 0 pings, 0 chat messages
- **Production:** 500 units born, 80 completed structures, 0 raw upgrade events
- **Technology:** Imperial Age, tech score 36
- **Age progression:** Dark Age at 2:30, Feudal Age at 5:00, Castle Age at 15:00, Imperial Age at 27:30
- **Tech structures by age:** Blacksmith at 7:00 [Feudal Age], Fletcher's Workshop at 8:00 [Feudal Age], Siege Workshop at 16:00 [Castle Age], Castle at 16:40 [Castle Age], Alchemist's Lab at 28:20 [Imperial Age]
- **Key unlocks:** Unlock Bombard Cannons at 28:50 [Imperial Age]
- **Gameplay upgrades by observed age:** UpgradeCatapult1 at 18:40 [Castle Age], UnlockBombardCannons at 28:50 [Imperial Age]
- **Advanced units:** Battering Ram at 17:20 [Castle Age], Catapult at 18:20 [Castle Age], Bombard Cannon at 29:40 [Imperial Age], Trebuchet (Move Mode) at 30:20 [Imperial Age], Trebuchet (Siege Mode) at 30:50 [Imperial Age]
- **Inferred unit requirements:** Battering Ram → likely Siege Workshop + Castle Age; Catapult → likely Siege Workshop + Castle Age; Bombard Cannon → Unlock Bombard Cannons; likely Alchemist's Lab + Imperial Age; Trebuchet (Move Mode) → likely Castle + Castle Age; move mode cannot attack; Trebuchet (Siege Mode) → same trebuchet asset after entering attack-capable siege mode
- **Resources:** current Gold 1,200, Wood 850, Iron 210; rates Gold 3,400, Wood 2,400, Iron 500; gathered estimate Gold 6,900, Wood 5,250, Iron 1,010
- **Mechanical:** 15 assets, 80/6 K/L; trebuchets 2 total, 2 reached siege mode, 1 move-mode deaths, 0 siege-mode deaths
- **Top units:** none
### Makak (Team 2)

- **Role read:** Ranged firepower
- **PvP combat:** 170 kills / 240 losses, K/L 0.71
- **Animal interaction:** 8 animal kills / 9 deaths to animals
- **Activity:** 420 commands, 0 control-group events, 0 pings, 0 chat messages
- **Production:** 460 units born, 60 completed structures, 0 raw upgrade events
- **Technology:** Castle Age, tech score 17
- **Age progression:** Dark Age at 2:40, Feudal Age at 5:20, Castle Age at 17:00
- **Tech structures by age:** Blacksmith at 7:30 [Feudal Age], Siege Workshop at 18:20 [Castle Age]
- **Key unlocks:** none recorded
- **Gameplay upgrades by observed age:** none recorded
- **Advanced units:** Ballista at 19:50 [Castle Age]
- **Inferred unit requirements:** Ballista → likely Siege Workshop + Castle Age
- **Resources:** current Gold 600, Wood 450, Iron 0; rates Gold 2,100, Wood 1,300, Iron 0; gathered estimate Gold 3,600, Wood 2,250, Iron 0
- **Mechanical:** 9 assets, 25/11 K/L; trebuchets 0 total, 0 reached siege mode, 0 move-mode deaths, 0 siege-mode deaths
- **Top units:** none
### phantom (Team 1)

- **Role read:** Mechanical support
- **PvP combat:** 90 kills / 100 losses, K/L 0.90
- **Animal interaction:** 0 animal kills / 0 deaths to animals
- **Activity:** 350 commands, 0 control-group events, 0 pings, 0 chat messages
- **Production:** 280 units born, 40 completed structures, 0 raw upgrade events
- **Technology:** Feudal Age, tech score 12
- **Age progression:** Dark Age at 2:30, Feudal Age at 5:00
- **Tech structures by age:** Blacksmith at 7:00 [Feudal Age], Fletcher's Workshop at 8:00 [Feudal Age]
- **Key unlocks:** none recorded
- **Gameplay upgrades by observed age:** none recorded
- **Advanced units:** none recorded
- **Inferred unit requirements:** none recorded
- **Resources:** current Gold 600, Wood 450, Iron 0; rates Gold 2,100, Wood 1,300, Iron 0; gathered estimate Gold 3,600, Wood 2,250, Iron 0
- **Mechanical:** 0 assets, 0/0 K/L; trebuchets 0 total, 0 reached siege mode, 0 move-mode deaths, 0 siege-mode deaths
- **Top units:** none
### Monstr (Team 2)

- **Role read:** Infantry frontline
- **PvP combat:** 70 kills / 140 losses, K/L 0.50
- **Animal interaction:** 0 animal kills / 0 deaths to animals
- **Activity:** 250 commands, 0 control-group events, 0 pings, 0 chat messages
- **Production:** 260 units born, 35 completed structures, 0 raw upgrade events
- **Technology:** Feudal Age, tech score 10
- **Age progression:** Dark Age at 2:40, Feudal Age at 5:20
- **Tech structures by age:** Blacksmith at 7:30 [Feudal Age]
- **Key unlocks:** none recorded
- **Gameplay upgrades by observed age:** none recorded
- **Advanced units:** none recorded
- **Inferred unit requirements:** none recorded
- **Resources:** current Gold 600, Wood 450, Iron 0; rates Gold 2,100, Wood 1,300, Iron 0; gathered estimate Gold 3,600, Wood 2,250, Iron 0
- **Mechanical:** 0 assets, 0/0 K/L; trebuchets 0 total, 0 reached siege mode, 0 move-mode deaths, 0 siege-mode deaths
- **Top units:** none

## Resource tracking notes

- AoK resource labels use Gold=SC2 Minerals, Wood=SC2 Vespene, and Iron=SC2 Terrazine.
- Synthetic validation: gathered totals are estimates.

## Technology inference notes

- Synthetic validation: requirements are inferred.



## Known limitations

- This reads replay protocol events, not a video recording.
- Player 15 is treated as Animals/Neutral because AoK assigns animals to that player slot.
- PvP K/L excludes animal kills; animal K/D is tracked separately.
- Exact age costs and hard prerequisite chains still need AoK map metadata or TwoDie confirmation; inferred relationships are labelled as such.
- FFA/no-alliance games are split into one analysis side per player; team games still aggregate allied players.
- Resource gathered/lost totals are score-value estimates; current stockpile and collection rate are direct tracker fields when exposed.
- Iron is shown as `n/a` when Terrazine fields are absent, rather than being silently treated as zero.
- Role and tech-lead labels are heuristic reads based on observed events, timings, resources, units, structures, and combat conversion.

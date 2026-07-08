# Age of Knights Strategy Mining Guide

Generated from **40 attempted unique replay(s)**, with **23 parser-ok replay(s)** producing **156 player-match row(s)**.

> Treat this as replay-derived evidence, not final balance truth. These findings show correlations and common patterns in the replay corpus; they should be validated by players before becoming hard guide rules.

## Timing windows worth testing

Median first-timing comparison between winners and non-winners:

| Signal | Winner median | Non-winner median | Difference | Winner 25–75% window |
|---|---:|---:|---:|---|
| first castle | 20.67 | 20.43 | -0.23 | 17.80–22.82 |
| first cavalry | 1.02 | 1.02 | 0.00 | 0.54–1.15 |
| first econ structure | 2.02 | 2.23 | 0.22 | 1.42–2.40 |
| first infantry | 7.55 | 7.35 | -0.20 | 6.22–9.63 |
| first prod structure | 5.30 | 5.69 | 0.39 | 4.22–5.93 |
| first ranged | 12.17 | 13.74 | 1.57 | 11.06–17.65 |
| first siege | 30.61 | 25.55 | -5.06 | 25.19–35.71 |
| first static defense | 8.41 | 9.63 | 1.22 | 5.30–12.08 |
| first upgrade | 0.00 | 0.00 | 0.00 | 0.00–0.48 |
| first wall gate | 8.98 | 13.15 | 4.17 | 6.43–10.75 |

**How to use this:** positive difference means non-winners tended to reach that timing later than winners. Negative difference means winners tended to delay it, which may indicate a greedier or alternative path.

## Player role patterns

| Role | Samples | Win rate | Avg K/L proxy | Avg units | Median first production | Median first upgrade |
|---|---:|---:|---:|---:|---:|---:|
| Mixed/support | 99 | 0.15 | 0.84 | 123.38 | 5.77 | 0.00 |
| Mass-production support | 20 | 0.25 | 0.62 | 550.65 | 5.22 | 1.17 |
| Cavalry pressure / mobile carry | 16 | 0.56 | 1.19 | 326.56 | 5.84 | 0.00 |
| Siege-support player | 7 | 0.43 | 1.01 | 450.43 | 5.20 | 1.02 |
| Ranged firepower/support | 6 | 0.50 | 0.77 | 585.00 | 5.36 | 0.00 |
| Main combat carry / pressure leader | 4 | 0.25 | 1.11 | 866.25 | 4.16 | 0.30 |
| Defensive anchor / wall player | 2 | 0.00 | 2.02 | 269.00 | 4.66 | 0.78 |
| Infantry + hand-cannon frontline | 1 | 0.00 | 0.92 | 586.00 | 5.60 | 1.37 |
| Mixed firepower + mobile pressure | 1 | 0.00 | 0.69 | 899.00 | 7.28 | 0.00 |

## Team style patterns

| Team style | Samples | Win rate | Avg K/L proxy | Avg static defense | Avg cavalry | Avg ranged | Avg siege |
|---|---:|---:|---:|---:|---:|---:|---:|
| Infantry-frontline-heavy team | 28 | 0.11 | 0.78 | 24.11 | 39.11 | 72.68 | 33.89 |
| Infantry + firepower frontline team | 9 | 0.33 | 0.90 | 39.56 | 61.89 | 165.00 | 42.11 |
| Mobile cavalry-pressure team | 9 | 0.22 | 0.96 | 22.33 | 152.89 | 62.67 | 29.89 |
| Mixed-composition team | 7 | 0.43 | 0.89 | 27.29 | 133.86 | 209.14 | 111.57 |
| Ranged/firepower-heavy team | 5 | 0.20 | 1.22 | 17.40 | 100.00 | 178.80 | 87.60 |
| Turtle / layered-defense team | 1 | 0.00 | 1.92 | 168.00 | 10.00 | 68.00 | 29.00 |

## Snapshot signals

These are median differences between winning and non-winning players at fixed timestamps. Larger positive values mean winners tended to have more of that feature by that time.

| Minute | Feature | Winner median | Non-winner median | Difference |
|---:|---|---:|---:|---:|
| 5 | upgrades | 6.00 | 5.00 | 1.00 |
| 5 | kills | 0.00 | 0.00 | 0.00 |
| 5 | units born | 18.50 | 19.00 | -0.50 |
| 10 | units born | 36.00 | 34.00 | 2.00 |
| 10 | static defense | 1.00 | 0.00 | 1.00 |
| 10 | losses | 3.00 | 4.00 | -1.00 |
| 15 | units born | 60.00 | 58.50 | 1.50 |
| 15 | ranged | 1.50 | 0.00 | 1.50 |
| 15 | infantry | 7.50 | 10.00 | -2.50 |
| 20 | units born | 92.50 | 81.00 | 11.50 |
| 20 | ranged | 8.00 | 1.50 | 6.50 |
| 20 | infantry | 16.50 | 19.00 | -2.50 |
| 25 | units born | 128.00 | 102.00 | 26.00 |
| 25 | ranged | 9.00 | 4.00 | 5.00 |
| 25 | losses | 45.00 | 51.00 | -6.00 |
| 30 | units born | 163.50 | 119.50 | 44.00 |
| 30 | losses | 91.50 | 77.50 | 14.00 |
| 30 | infantry | 34.00 | 39.00 | -5.00 |
| 45 | units born | 241.00 | 142.50 | 98.50 |
| 45 | ranged | 32.00 | 7.00 | 25.00 |
| 45 | walls gates | 0.00 | 0.00 | 0.00 |
| 60 | units born | 265.00 | 142.50 | 122.50 |
| 60 | losses | 165.50 | 124.00 | 41.50 |
| 60 | walls gates | 0.00 | 0.00 | 0.00 |

## Draft guide rules to test in-game

### 1. Early production timing
Use the `timing_windows.csv` median first-production structure timing as the first candidate benchmark. If winners consistently complete production earlier, test an opening that hits that window; if winners delay it, that may indicate a viable greedier/economy path.

### 2. Anti-turtle response
If the enemy team shows rapid wall/gate/static-defense growth by the 15–25 minute snapshots, avoid feeding infantry into the same choke. Test siege/firepower support or multi-front pressure instead.

### 3. All-in pressure detection
Look for games where winners have a kill spike and higher units-born by 10–20 minutes. Those should be manually reviewed as candidate all-in or timing-attack replays.

### 4. Greedy/economy route detection
Look for winning players who delay first production or first upgrade but have higher unit count, economy-structure count, or lower early losses by 20–30 minutes. These are candidate greedy builds.

## Next upgrade needed

To produce exact statements like ‘skip Building X and you gain resources but delay Tech Y by 5 minutes’, the pipeline needs AoK map metadata: ability IDs, building costs, upgrade IDs, and resource/bank key meanings. The recovered AoK map/mod files are the right place to extract that later.

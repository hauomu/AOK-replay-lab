# AoK ML Model Report

This is a small, readable model for strategy mining. Treat it as a guide-discovery tool, not a final predictor.

Rows: 1248 timeline snapshots
Features: snapshot_minute, kills_to_now, losses_to_now, units_born_to_now, structures_done_to_now, static_defense_to_now, walls_gates_to_now, cavalry_to_now, ranged_to_now, infantry_to_now, siege_to_now, upgrades_to_now

Decision tree holdout accuracy: 0.782
Random forest holdout accuracy: 0.801

## Top feature importances

| Feature | Importance |
|---|---:|
| cavalry_to_now | 0.1272 |
| ranged_to_now | 0.1158 |
| static_defense_to_now | 0.1133 |
| walls_gates_to_now | 0.1079 |
| upgrades_to_now | 0.1072 |
| losses_to_now | 0.1022 |
| structures_done_to_now | 0.0809 |
| units_born_to_now | 0.0721 |
| infantry_to_now | 0.0632 |
| siege_to_now | 0.0443 |
| snapshot_minute | 0.0337 |
| kills_to_now | 0.0323 |

## Readable decision tree rules

```text
|--- cavalry_to_now <= 22.50
|   |--- ranged_to_now <= 14.50
|   |   |--- losses_to_now <= 43.50
|   |   |   |--- ranged_to_now <= 6.50
|   |   |   |   |--- class: 0
|   |   |   |--- ranged_to_now >  6.50
|   |   |   |   |--- class: 0
|   |   |--- losses_to_now >  43.50
|   |   |   |--- static_defense_to_now <= 32.00
|   |   |   |   |--- class: 0
|   |   |   |--- static_defense_to_now >  32.00
|   |   |   |   |--- class: 0
|   |--- ranged_to_now >  14.50
|   |   |--- structures_done_to_now <= 27.50
|   |   |   |--- upgrades_to_now <= 35.00
|   |   |   |   |--- class: 0
|   |   |   |--- upgrades_to_now >  35.00
|   |   |   |   |--- class: 1
|   |   |--- structures_done_to_now >  27.50
|   |   |   |--- static_defense_to_now <= 5.50
|   |   |   |   |--- class: 1
|   |   |   |--- static_defense_to_now >  5.50
|   |   |   |   |--- class: 0
|--- cavalry_to_now >  22.50
|   |--- walls_gates_to_now <= 19.00
|   |   |--- static_defense_to_now <= 18.50
|   |   |   |--- upgrades_to_now <= 31.50
|   |   |   |   |--- class: 0
|   |   |   |--- upgrades_to_now >  31.50
|   |   |   |   |--- class: 1
|   |   |--- static_defense_to_now >  18.50
|   |   |   |--- static_defense_to_now <= 26.00
|   |   |   |   |--- class: 0
|   |   |   |--- static_defense_to_now >  26.00
|   |   |   |   |--- class: 0
|   |--- walls_gates_to_now >  19.00
|   |   |--- class: 1

```

## Classification report

```text
              precision    recall  f1-score   support

           0       0.79      0.98      0.87       240
           1       0.67      0.11      0.19        72

    accuracy                           0.78       312
   macro avg       0.73      0.55      0.53       312
weighted avg       0.76      0.78      0.72       312

```
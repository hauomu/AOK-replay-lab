from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

FEATURES = [
    "snapshot_minute",
    "kills_to_now", "losses_to_now", "units_born_to_now", "structures_done_to_now",
    "static_defense_to_now", "walls_gates_to_now", "cavalry_to_now", "ranged_to_now",
    "infantry_to_now", "siege_to_now", "upgrades_to_now",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Train small, readable AoK strategy models from timeline snapshots.")
    ap.add_argument("--out", default="output", help="Output directory containing datasets/")
    ap.add_argument("--max-depth", type=int, default=4)
    args = ap.parse_args()
    out = Path(args.out)
    datasets = out / "datasets"
    analysis = out / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)

    try:
        from sklearn.tree import DecisionTreeClassifier, export_text
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report, accuracy_score
    except Exception as exc:
        raise SystemExit(
            "scikit-learn is required for model training. Install with: pip install scikit-learn\n"
            f"Actual import error: {type(exc).__name__}: {exc}"
        )

    snap_path = datasets / "timeline_snapshots.csv"
    if not snap_path.exists() or snap_path.stat().st_size == 0:
        raise SystemExit(f"Missing {snap_path}. Run ingest first.")
    df = pd.read_csv(snap_path)
    df = df[df["result"].notna()].copy()
    df["is_win"] = (df["result"] == "Win").astype(int)
    features = [f for f in FEATURES if f in df.columns]
    X = df[features].fillna(0)
    y = df["is_win"]

    if len(df) < 30 or y.nunique() < 2:
        raise SystemExit("Not enough parsed labeled snapshot rows to train a useful model yet.")

    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=stratify)

    tree = DecisionTreeClassifier(max_depth=args.max_depth, min_samples_leaf=8, random_state=42)
    tree.fit(X_train, y_train)
    pred = tree.predict(X_test)

    rf = RandomForestClassifier(n_estimators=200, max_depth=6, min_samples_leaf=5, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)

    importances = pd.DataFrame({"feature": features, "importance": rf.feature_importances_}).sort_values("importance", ascending=False)
    importances.to_csv(analysis / "ml_feature_importances.csv", index=False)

    rules = export_text(tree, feature_names=features)
    (analysis / "ml_decision_rules.txt").write_text(rules, encoding="utf-8")

    report_lines = []
    report_lines.append("# AoK ML Model Report")
    report_lines.append("")
    report_lines.append("This is a small, readable model for strategy mining. Treat it as a guide-discovery tool, not a final predictor.")
    report_lines.append("")
    report_lines.append(f"Rows: {len(df)} timeline snapshots")
    report_lines.append(f"Features: {', '.join(features)}")
    report_lines.append("")
    report_lines.append(f"Decision tree holdout accuracy: {accuracy_score(y_test, pred):.3f}")
    report_lines.append(f"Random forest holdout accuracy: {accuracy_score(y_test, rf_pred):.3f}")
    report_lines.append("")
    report_lines.append("## Top feature importances")
    report_lines.append("")
    report_lines.append("| Feature | Importance |")
    report_lines.append("|---|---:|")
    for _, r in importances.head(12).iterrows():
        report_lines.append(f"| {r['feature']} | {r['importance']:.4f} |")
    report_lines.append("")
    report_lines.append("## Readable decision tree rules")
    report_lines.append("")
    report_lines.append("```text")
    report_lines.append(rules)
    report_lines.append("```")
    report_lines.append("")
    report_lines.append("## Classification report")
    report_lines.append("")
    report_lines.append("```text")
    report_lines.append(classification_report(y_test, pred, zero_division=0))
    report_lines.append("```")
    (analysis / "ml_model_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Wrote {analysis / 'ml_model_report.md'}")
    print(f"Wrote {analysis / 'ml_feature_importances.csv'}")
    print(f"Wrote {analysis / 'ml_decision_rules.txt'}")

if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from pathlib import Path
import math
import pandas as pd


def _safe_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return float('nan')
    return round((series == 'Win').mean(), 3)


def _fmt(x, digits=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def mine_strategies(output_dir: Path) -> dict[str, Path]:
    datasets = output_dir / "datasets"
    analysis = output_dir / "analysis"
    guides = output_dir / "guides"
    analysis.mkdir(parents=True, exist_ok=True)
    guides.mkdir(parents=True, exist_ok=True)

    pstats = _read_csv(datasets / "player_match_stats.csv")
    tstats = _read_csv(datasets / "team_match_stats.csv")
    snaps = _read_csv(datasets / "timeline_snapshots.csv")
    replays = _read_csv(datasets / "replays.csv")

    written: dict[str, Path] = {}

    if not pstats.empty:
        pstats["is_win"] = (pstats["result"] == "Win").astype(int)
        role_summary = pstats.groupby("role_label", dropna=False).agg(
            samples=("replay_id", "count"),
            win_rate=("is_win", "mean"),
            avg_kills=("kills", "mean"),
            avg_losses=("losses", "mean"),
            avg_units=("units_born", "mean"),
            avg_static=("static_defense", "mean"),
            avg_cavalry=("cavalry_units", "mean"),
            avg_ranged=("ranged_units", "mean"),
            avg_infantry=("infantry_units", "mean"),
            avg_siege=("siege_units", "mean"),
            median_first_prod=("first_prod_structure_minute", "median"),
            median_first_static=("first_static_defense_minute", "median"),
            median_first_cavalry=("first_cavalry_minute", "median"),
            median_first_ranged=("first_ranged_minute", "median"),
            median_first_siege=("first_siege_minute", "median"),
            median_first_upgrade=("first_upgrade_minute", "median"),
        ).reset_index().sort_values(["samples", "win_rate"], ascending=[False, False])
        role_summary["win_rate"] = role_summary["win_rate"].round(3)
        path = analysis / "player_role_summary.csv"
        role_summary.to_csv(path, index=False)
        written["player_role_summary"] = path

        player_profiles = pstats.groupby("name", dropna=False).agg(
            games=("replay_id", "count"),
            win_rate=("is_win", "mean"),
            kills=("kills", "sum"),
            losses=("losses", "sum"),
            avg_apm=("apm", "mean"),
            avg_units=("units_born", "mean"),
            avg_static=("static_defense", "mean"),
            avg_cavalry=("cavalry_units", "mean"),
            avg_ranged=("ranged_units", "mean"),
            avg_infantry=("infantry_units", "mean"),
            avg_siege=("siege_units", "mean"),
        ).reset_index()
        player_profiles["kl_ratio"] = player_profiles.apply(lambda r: round(r["kills"] / r["losses"], 3) if r["losses"] else None, axis=1)
        # most common role per player
        role_mode = pstats.groupby("name")["role_label"].agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "")
        player_profiles["common_role"] = player_profiles["name"].map(role_mode)
        player_profiles["win_rate"] = player_profiles["win_rate"].round(3)
        player_profiles = player_profiles.sort_values(["games", "kills"], ascending=[False, False])
        path = analysis / "player_profiles.csv"
        player_profiles.to_csv(path, index=False)
        written["player_profiles"] = path

        timing_cols = [c for c in pstats.columns if c.startswith("first_") and c.endswith("_minute")]
        timing_rows = []
        for col in timing_cols:
            win_vals = pstats.loc[pstats["is_win"] == 1, col].dropna()
            lose_vals = pstats.loc[pstats["is_win"] == 0, col].dropna()
            timing_rows.append({
                "timing_feature": col,
                "winner_samples": len(win_vals),
                "nonwinner_samples": len(lose_vals),
                "winner_median_minute": round(float(win_vals.median()), 2) if len(win_vals) else None,
                "nonwinner_median_minute": round(float(lose_vals.median()), 2) if len(lose_vals) else None,
                "winner_25pct": round(float(win_vals.quantile(0.25)), 2) if len(win_vals) else None,
                "winner_75pct": round(float(win_vals.quantile(0.75)), 2) if len(win_vals) else None,
                "difference_nonwinner_minus_winner": round(float(lose_vals.median() - win_vals.median()), 2) if len(win_vals) and len(lose_vals) else None,
            })
        timing = pd.DataFrame(timing_rows).sort_values("timing_feature")
        path = analysis / "timing_windows.csv"
        timing.to_csv(path, index=False)
        written["timing_windows"] = path

    if not tstats.empty:
        tstats["is_win"] = (tstats["result"] == "Win").astype(int)
        team_style = tstats.groupby("style_label", dropna=False).agg(
            samples=("replay_id", "count"),
            win_rate=("is_win", "mean"),
            avg_kills=("kills", "mean"),
            avg_losses=("losses", "mean"),
            avg_units=("units_born", "mean"),
            avg_static=("static_defense", "mean"),
            avg_walls=("walls_gates", "mean"),
            avg_cavalry=("cavalry_units", "mean"),
            avg_ranged=("ranged_units", "mean"),
            avg_infantry=("infantry_units", "mean"),
            avg_siege=("siege_units", "mean"),
        ).reset_index().sort_values(["samples", "win_rate"], ascending=[False, False])
        team_style["win_rate"] = team_style["win_rate"].round(3)
        path = analysis / "team_style_summary.csv"
        team_style.to_csv(path, index=False)
        written["team_style_summary"] = path

    if not snaps.empty:
        snaps["is_win"] = (snaps["result"] == "Win").astype(int)
        features = [
            "kills_to_now", "losses_to_now", "units_born_to_now", "structures_done_to_now",
            "static_defense_to_now", "walls_gates_to_now", "cavalry_to_now", "ranged_to_now",
            "infantry_to_now", "siege_to_now", "upgrades_to_now",
        ]
        rows = []
        for minute, g in snaps.groupby("snapshot_minute"):
            for feature in features:
                if feature not in g: continue
                winners = g.loc[g["is_win"] == 1, feature].dropna()
                others = g.loc[g["is_win"] == 0, feature].dropna()
                if len(winners) == 0 or len(others) == 0: continue
                rows.append({
                    "snapshot_minute": minute,
                    "feature": feature,
                    "winner_median": round(float(winners.median()), 2),
                    "nonwinner_median": round(float(others.median()), 2),
                    "difference_winner_minus_nonwinner": round(float(winners.median() - others.median()), 2),
                    "winner_75pct": round(float(winners.quantile(0.75)), 2),
                    "nonwinner_75pct": round(float(others.quantile(0.75)), 2),
                })
        snap_signals = pd.DataFrame(rows).sort_values(["snapshot_minute", "difference_winner_minus_nonwinner"], ascending=[True, False])
        path = analysis / "snapshot_win_signals.csv"
        snap_signals.to_csv(path, index=False)
        written["snapshot_win_signals"] = path

    guide_path = guides / "aok_team_roles_and_timing_windows_guide.md"
    guide_path.write_text(generate_guide(output_dir), encoding="utf-8")
    written["guide"] = guide_path

    return written


def generate_guide(output_dir: Path) -> str:
    analysis = output_dir / "analysis"
    datasets = output_dir / "datasets"
    pstats = _read_csv(datasets / "player_match_stats.csv")
    replays = _read_csv(datasets / "replays.csv")
    role = _read_csv(analysis / "player_role_summary.csv")
    team = _read_csv(analysis / "team_style_summary.csv")
    timing = _read_csv(analysis / "timing_windows.csv")
    snap = _read_csv(analysis / "snapshot_win_signals.csv")

    total_replays = int(replays["replay_id"].nunique()) if not replays.empty and "replay_id" in replays else 0
    parsed_ok = int(replays["parser_ok"].sum()) if not replays.empty and "parser_ok" in replays else total_replays
    total_players = len(pstats) if not pstats.empty else 0
    lines = []
    lines.append("# Age of Knights Strategy Mining Guide")
    lines.append("")
    lines.append(f"Generated from **{total_replays} attempted unique replay(s)**, with **{parsed_ok} parser-ok replay(s)** producing **{total_players} player-match row(s)**.")
    lines.append("")
    lines.append("> Treat this as replay-derived evidence, not final balance truth. These findings show correlations and common patterns in the replay corpus; they should be validated by players before becoming hard guide rules.")
    lines.append("")

    if not timing.empty:
        lines.append("## Timing windows worth testing")
        lines.append("")
        lines.append("Median first-timing comparison between winners and non-winners:")
        lines.append("")
        lines.append("| Signal | Winner median | Non-winner median | Difference | Winner 25–75% window |")
        lines.append("|---|---:|---:|---:|---|")
        for _, r in timing.iterrows():
            nice = r["timing_feature"].replace("first_", "first ").replace("_minute", "").replace("_", " ")
            diff = r.get("difference_nonwinner_minus_winner")
            lines.append(f"| {nice} | {_fmt(r.get('winner_median_minute'))} | {_fmt(r.get('nonwinner_median_minute'))} | {_fmt(diff)} | {_fmt(r.get('winner_25pct'))}–{_fmt(r.get('winner_75pct'))} |")
        lines.append("")
        lines.append("**How to use this:** positive difference means non-winners tended to reach that timing later than winners. Negative difference means winners tended to delay it, which may indicate a greedier or alternative path.")
        lines.append("")

    if not role.empty:
        lines.append("## Player role patterns")
        lines.append("")
        lines.append("| Role | Samples | Win rate | Avg K/L proxy | Avg units | Median first production | Median first upgrade |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for _, r in role.head(10).iterrows():
            kl = (r.get("avg_kills") / r.get("avg_losses")) if r.get("avg_losses") else None
            lines.append(f"| {r.get('role_label')} | {int(r.get('samples', 0))} | {_fmt(r.get('win_rate'))} | {_fmt(kl)} | {_fmt(r.get('avg_units'))} | {_fmt(r.get('median_first_prod'))} | {_fmt(r.get('median_first_upgrade'))} |")
        lines.append("")

    if not team.empty:
        lines.append("## Team style patterns")
        lines.append("")
        lines.append("| Team style | Samples | Win rate | Avg K/L proxy | Avg static defense | Avg cavalry | Avg ranged | Avg siege |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in team.iterrows():
            kl = (r.get("avg_kills") / r.get("avg_losses")) if r.get("avg_losses") else None
            lines.append(f"| {r.get('style_label')} | {int(r.get('samples', 0))} | {_fmt(r.get('win_rate'))} | {_fmt(kl)} | {_fmt(r.get('avg_static'))} | {_fmt(r.get('avg_cavalry'))} | {_fmt(r.get('avg_ranged'))} | {_fmt(r.get('avg_siege'))} |")
        lines.append("")

    if not snap.empty:
        lines.append("## Snapshot signals")
        lines.append("")
        lines.append("These are median differences between winning and non-winning players at fixed timestamps. Larger positive values mean winners tended to have more of that feature by that time.")
        lines.append("")
        lines.append("| Minute | Feature | Winner median | Non-winner median | Difference |")
        lines.append("|---:|---|---:|---:|---:|")
        # Show top two positive and top negative per snapshot.
        selected = []
        for m, g in snap.groupby("snapshot_minute"):
            selected.extend(g.sort_values("difference_winner_minus_nonwinner", ascending=False).head(2).to_dict("records"))
            selected.extend(g.sort_values("difference_winner_minus_nonwinner", ascending=True).head(1).to_dict("records"))
        for r in selected[:36]:
            nice = r["feature"].replace("_to_now", "").replace("_", " ")
            lines.append(f"| {int(r['snapshot_minute'])} | {nice} | {_fmt(r['winner_median'])} | {_fmt(r['nonwinner_median'])} | {_fmt(r['difference_winner_minus_nonwinner'])} |")
        lines.append("")

    lines.append("## Draft guide rules to test in-game")
    lines.append("")
    lines.append("### 1. Early production timing")
    lines.append("Use the `timing_windows.csv` median first-production structure timing as the first candidate benchmark. If winners consistently complete production earlier, test an opening that hits that window; if winners delay it, that may indicate a viable greedier/economy path.")
    lines.append("")
    lines.append("### 2. Anti-turtle response")
    lines.append("If the enemy team shows rapid wall/gate/static-defense growth by the 15–25 minute snapshots, avoid feeding infantry into the same choke. Test siege/firepower support or multi-front pressure instead.")
    lines.append("")
    lines.append("### 3. All-in pressure detection")
    lines.append("Look for games where winners have a kill spike and higher units-born by 10–20 minutes. Those should be manually reviewed as candidate all-in or timing-attack replays.")
    lines.append("")
    lines.append("### 4. Greedy/economy route detection")
    lines.append("Look for winning players who delay first production or first upgrade but have higher unit count, economy-structure count, or lower early losses by 20–30 minutes. These are candidate greedy builds.")
    lines.append("")
    lines.append("## Next upgrade needed")
    lines.append("")
    lines.append("To produce exact statements like ‘skip Building X and you gain resources but delay Tech Y by 5 minutes’, the pipeline needs AoK map metadata: ability IDs, building costs, upgrade IDs, and resource/bank key meanings. The recovered AoK map/mod files are the right place to extract that later.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Mine AoK replay CSVs into strategy summaries and guide drafts.")
    ap.add_argument("--out", default="output", help="Output directory containing datasets/")
    args = ap.parse_args()
    written = mine_strategies(Path(args.out))
    for name, path in written.items():
        print(f"{name}: {path}")

if __name__ == "__main__":
    main()

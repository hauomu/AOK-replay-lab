"""Economy and army timeline chart for one replay (PNG, attached to the report).

Panels: each side's gather rate (gold + wood per minute, from the replay's
resource stats) and iron spent per minute (priced from the map's costs; the
replay holds no iron stockpile). Second panel: army value alive (gold + wood +
iron cost of living army units) and the value of defenses still standing.
Third: food (supply) in use vs the cap from houses. The biggest fights are shaded and numbered.
matplotlib is optional: without it no chart is produced and reports still work.
"""
from __future__ import annotations

from pathlib import Path

from .models import ReplaySummary

TEAM_COLOURS = ("#2b6cb0", "#c53030", "#2f855a", "#b7791f", "#6b46c1", "#319795", "#d53f8c", "#4a5568")
SHADED_FIGHTS = 3


def render_timeline_chart(summary: ReplaySummary, out_path: Path) -> Path | None:
    series = summary.economy_series or []
    if not summary.parser_ok or len(series) < 3:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    team_ids = sorted({tid for point in series for tid in point["teams"]}, key=lambda t: int(t))
    labels = {str(t.team_id): f"Team {t.team_id}" for t in summary.teams}
    minutes = [point["t"] / 60 for point in series]

    fig, (eco, army, food) = plt.subplots(3, 1, figsize=(10, 8.4), sharex=True, dpi=110,
                                          gridspec_kw={"height_ratios": [3, 3, 2]})
    for index, tid in enumerate(team_ids):
        colour = TEAM_COLOURS[index % len(TEAM_COLOURS)]
        name = labels.get(tid, f"Team {tid}")
        gather = [p["teams"].get(tid, {}).get("gold_rate", 0) + p["teams"].get(tid, {}).get("wood_rate", 0) for p in series]
        iron_cum = [p["teams"].get(tid, {}).get("iron_spent", 0) for p in series]
        iron_rate = [0.0]
        for i in range(1, len(series)):
            dt = (series[i]["t"] - series[i - 1]["t"]) / 60 or 1
            iron_rate.append(max(0.0, (iron_cum[i] - iron_cum[i - 1]) / dt))
        eco.plot(minutes, gather, color=colour, linewidth=1.8, label=f"{name} gold+wood gathered/min")
        eco.plot(minutes, iron_rate, color=colour, linewidth=1.2, linestyle="--", label=f"{name} iron spent/min")
        army.plot(minutes, [p["teams"].get(tid, {}).get("army_value", 0) for p in series],
                  color=colour, linewidth=1.8, label=f"{name} army alive")
        army.plot(minutes, [p["teams"].get(tid, {}).get("defense_value", 0) for p in series],
                  color=colour, linewidth=1.2, linestyle="--", label=f"{name} defenses standing")
        food.plot(minutes, [p["teams"].get(tid, {}).get("food_used", 0) for p in series],
                  color=colour, linewidth=1.6, label=f"{name} food used")
        food.plot(minutes, [p["teams"].get(tid, {}).get("food_cap", 0) for p in series],
                  color=colour, linewidth=1.0, linestyle=":", label=f"{name} food cap (houses)")

    for fight in sorted(summary.fights, key=lambda f: f.get("rank", 99))[:SHADED_FIGHTS]:
        start, end = fight["start"] / 60, max(fight["end"], fight["start"] + 10) / 60
        for axis in (eco, army, food):
            axis.axvspan(start, end, color="#718096", alpha=0.15, linewidth=0)
        army.annotate(f"#{fight['rank']}", xy=(start, 0), xycoords=("data", "axes fraction"),
                      xytext=(2, 3 + 11 * ((fight["rank"] - 1) % 2)), textcoords="offset points",
                      fontsize=8, color="#2d3748")

    eco.set_title(f"{summary.map_name or 'AoK'} | {summary.duration_label()} | {summary.winner_display()[:70]}", fontsize=10)
    eco.set_ylabel("per minute")
    eco.legend(fontsize=7, loc="upper left", ncol=2, frameon=False)
    army.set_ylabel("value (gold+wood+iron)")
    army.legend(fontsize=7, loc="upper left", ncol=2, frameon=False)
    food.set_ylabel("food (supply)")
    food.set_xlabel("game time (minutes); shaded = biggest fights")
    food.legend(fontsize=7, loc="upper left", ncol=2, frameon=False)
    for axis in (eco, army, food):
        axis.grid(alpha=0.25)
        axis.set_ylim(bottom=0)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path

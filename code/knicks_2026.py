"""
2025-26 Knicks Championship Run -- chart module + script.

Charts:
  1. Where the shots came from      (half-court hexbin heatmap)
  2. Shot type                      (bar chart: attempts + FG%)
  3. Efficiency throughout the game (eFG% by game minute)
  4. Leaderboards                   (points, rebounds, assists, 3PM)

Run as a script:   python code/knicks_2026.py   -> saves PNGs to code/charts/ and shows them
Used by the site:  python code/build_site.py    -> writes site/index.html (deployed on Render)

Data: data/nyk_2026.csv (Knicks rows only, small enough for git). If it's missing,
it is created automatically from the full archive (1)/pbp2026.csv.
"""

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Arc, Circle, Rectangle

# ---------------------------------------------------------------- config
TEAM = "NYK"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SMALL_DATA = ROOT / "data" / "nyk_2026.csv"
FULL_DATA = ROOT / "archive (1)" / "pbp2026.csv"

BLUE = "#2a78d6"     # primary series color
ORANGE = "#eb6834"   # secondary series color
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "font.size": 10,
    "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
})


# ---------------------------------------------------------------- data
def load_team_rows() -> pd.DataFrame:
    """Knicks play-by-play rows. Builds the small CSV from the full archive once."""
    if SMALL_DATA.exists():
        return pd.read_csv(SMALL_DATA, dtype={"gameid": str})
    df = pd.read_csv(FULL_DATA, dtype={"gameid": str})
    nyk = df[df["team"] == TEAM].copy()
    SMALL_DATA.parent.mkdir(exist_ok=True)
    nyk.to_csv(SMALL_DATA, index=False)
    print(f"Wrote {SMALL_DATA} ({len(nyk):,} rows)")
    return nyk


def prepare(nyk: pd.DataFrame):
    shots = nyk[nyk["type"].isin(["Made Shot", "Missed Shot"])].copy()
    shots["made"] = shots["type"].eq("Made Shot")
    shots["is3"] = shots["desc"].str.contains("3PT", na=False)
    shots["family"] = shots["subtype"].map(shot_family)
    return shots


def clock_to_sec(c: str) -> float:
    m = re.match(r"PT(\d+)M([\d.]+)S", str(c))
    return int(m.group(1)) * 60 + float(m.group(2)) if m else np.nan


def shot_family(sub: str) -> str:
    s = str(sub).lower()
    if "dunk" in s:
        return "Dunk"
    if "layup" in s or "finger roll" in s:
        return "Layup"
    if "float" in s:
        return "Floater"
    if "hook" in s:
        return "Hook"
    if "step back" in s:
        return "Step-back"
    if "fadeaway" in s or "turnaround" in s:
        return "Fadeaway / turnaround"
    if "pull" in s:
        return "Pull-up"
    if "jump" in s:
        return "Catch & shoot / other jumper"
    return "Other"


def efg(made: pd.Series, is3: pd.Series) -> float:
    return (made.sum() + 0.5 * (made & is3).sum()) / len(made)


# ---------------------------------------------------------------- 1. heatmap
def draw_court(ax, color=INK_2, lw=1.2):
    """Half court in the data's units (tenths of a foot, hoop at 0,0)."""
    parts = [
        Circle((0, 0), 7.5, lw=lw, color=color, fill=False),                 # hoop
        Rectangle((-30, -7.5), 60, -1, lw=lw, color=color),                  # backboard
        Rectangle((-80, -47.5), 160, 190, lw=lw, color=color, fill=False),   # paint
        Arc((0, 142.5), 120, 120, theta1=0, theta2=180, lw=lw, color=color), # FT circle
        Arc((0, 0), 80, 80, theta1=0, theta2=180, lw=lw, color=color),       # restricted
        Rectangle((-220, -47.5), 0, 140, lw=lw, color=color),                # corner 3 L
        Rectangle((220, -47.5), 0, 140, lw=lw, color=color),                 # corner 3 R
        Arc((0, 0), 475, 475, theta1=22, theta2=158, lw=lw, color=color),    # 3pt arc
        Rectangle((-250, -47.5), 500, 470, lw=lw, color=color, fill=False),  # outline
    ]
    for p in parts:
        ax.add_patch(p)
    ax.set_xlim(-250, 250)
    ax.set_ylim(-47.5, 422.5)
    ax.set_aspect("equal")
    ax.axis("off")


def chart_heatmap(shots):
    fig, ax = plt.subplots(figsize=(7, 6.6))
    xy = shots[(shots["y"] < 422) & (shots["x"].abs() <= 250)]
    hb = ax.hexbin(xy["x"], xy["y"], gridsize=28, extent=(-250, 250, -47.5, 422.5),
                   cmap="Blues", mincnt=1, bins="log", linewidths=0.2, edgecolors=SURFACE)
    draw_court(ax)
    cb = fig.colorbar(hb, ax=ax, shrink=0.7, pad=0.01)
    cb.set_label("Shot attempts (log scale)")
    cb.outline.set_visible(False)
    ax.set_title(f"Where the Knicks shot from  ·  {len(xy):,} attempts")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- 2. shot type
def chart_shot_type(shots):
    by_type = (shots.groupby("family")
               .agg(FGA=("made", "size"), FGM=("made", "sum"))
               .assign(FG=lambda d: d.FGM / d.FGA)
               .sort_values("FGA"))

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 5), sharey=True,
                                 gridspec_kw={"width_ratios": [1.3, 1]})
    y = np.arange(len(by_type))
    a1.barh(y, by_type["FGA"], color=BLUE, height=0.6)
    a1.set_yticks(y, by_type.index)
    a1.set_title("Shot type: volume")
    a1.set_xlabel("Field-goal attempts")
    a1.grid(axis="y", visible=False)
    for yi, v in zip(y, by_type["FGA"]):
        a1.text(v, yi, f" {v:,}", va="center", color=INK_2, fontsize=9)

    avg = shots["made"].mean() * 100
    a2.barh(y, by_type["FG"] * 100, color=ORANGE, height=0.6)
    a2.set_title("…and how often it went in")
    a2.set_xlabel(f"FG%   (dashed line = team avg {avg:.0f}%)")
    a2.set_xlim(0, 100)
    a2.axvline(avg, color=INK_2, lw=1, ls="--")
    a2.grid(axis="y", visible=False)
    for yi, v in zip(y, by_type["FG"]):
        a2.text(v * 100, yi, f" {v:.0%}", va="center", color=INK_2, fontsize=9)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- 3. efficiency by minute
def chart_efficiency(shots):
    reg = shots[shots["period"] <= 4].copy()  # skip OT (few games, short periods)
    reg["elapsed"] = (reg["period"] - 1) * 720 + (720 - reg["clock"].map(clock_to_sec))
    reg["minute"] = (reg["elapsed"] // 60).clip(0, 47).astype(int) + 1

    by_min = reg.groupby("minute").apply(lambda g: efg(g["made"], g["is3"]))
    smooth = by_min.rolling(3, center=True, min_periods=1).mean()
    season = efg(reg["made"], reg["is3"])

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(by_min.index, by_min * 100, color=BLUE, alpha=0.3, lw=1,
            marker="o", ms=3, label="Per minute")
    ax.plot(by_min.index, smooth * 100, color=BLUE, lw=2, label="3-min rolling")
    ax.axhline(season * 100, color=INK_2, lw=1, ls="--")
    ax.text(48.5, season * 100, f"season {season:.1%}", va="center", color=INK_2, fontsize=9)
    for q in (12, 24, 36):
        ax.axvline(q + 0.5, color=GRID, lw=1.5)
    for i, label in enumerate(["Q1", "Q2", "Q3", "Q4"]):
        ax.text(6.5 + 12 * i, ax.get_ylim()[1], label, ha="center", va="bottom",
                color=INK_2, fontweight="bold")
    ax.set_xlim(0.5, 48.5)
    ax.set_xticks([1, 6, 12, 18, 24, 30, 36, 42, 48])
    ax.set_xlabel("Game minute")
    ax.set_ylabel("Effective FG%")
    ax.set_title("Efficiency throughout the game", pad=22)
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- 4. leaderboards
def leaderboards(nyk, shots):
    """Season totals per player: points, rebounds, assists, 3PM."""
    made = shots[shots.made]
    pts = pd.concat([
        made.assign(p=np.where(made["is3"], 3, 2))[["player", "p"]],
        nyk.loc[(nyk.type == "Free Throw") & ~nyk.desc.str.startswith("MISS", na=False),
                ["player"]].assign(p=1),
    ])
    points = pts.groupby("player")["p"].sum()
    rebounds = nyk[(nyk.type == "Rebound") & (nyk.playerid != 0)].groupby("player").size()
    threes = made[made.is3].groupby("player").size()

    # Assists live inside the desc text, e.g. "(Towns 1 AST)" -> map last name to player.
    last_to_player = (nyk.dropna(subset=["player"])
                      .assign(last=lambda d: d.player.str.split(". ", n=1).str[-1])
                      .drop_duplicates("last").set_index("last")["player"])
    ast_names = made["desc"].str.extract(r"\(([^()]+?) \d+ AST\)")[0].dropna()
    assists = ast_names.map(last_to_player).dropna().value_counts()

    return {"Points": points, "Rebounds": rebounds,
            "Assists": assists, "3-pointers made": threes}


def chart_leaderboards(nyk, shots, top_n=5):
    n_games = nyk["gameid"].nunique()
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (name, s) in zip(axes.flat, leaderboards(nyk, shots).items()):
        top = (s / n_games).sort_values(ascending=False).head(top_n)[::-1]  # per game
        ax.barh(top.index, top.values, color=BLUE, height=0.6)
        ax.set_title(f"{name} per game")
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
        for yi, (v, tot) in enumerate(zip(top.values, s[top.index])):
            ax.text(v, yi, f" {v:.1f}  ({int(tot):,} total)", va="center",
                    color=INK_2, fontsize=9)
        ax.set_xlim(0, top.max() * 1.45)
    fig.suptitle("Knicks leaderboard, 2025-26", fontweight="bold", fontsize=15,
                 x=0.01, ha="left")
    fig.text(0.01, 0.935, f"Per game = season total ÷ {n_games} team games",
             color=INK_2, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


# ---------------------------------------------------------------- shared entry
def build_all():
    """Load data and return (summary dict, {filename: figure})."""
    nyk = load_team_rows()
    shots = prepare(nyk)
    boards = leaderboards(nyk, shots)
    summary = {
        "games": nyk["gameid"].nunique(),
        "fga": len(shots),
        "fg_pct": shots["made"].mean(),
        "efg": efg(shots["made"], shots["is3"]),
        "fg3m": int((shots.made & shots.is3).sum()),
        "top_scorer": boards["Points"].idxmax(),
    }
    figs = {
        "1_shot_heatmap.png": chart_heatmap(shots),
        "2_shot_type.png": chart_shot_type(shots),
        "3_efficiency_by_minute.png": chart_efficiency(shots),
        "4_leaderboards.png": chart_leaderboards(nyk, shots),
    }
    return summary, figs


if __name__ == "__main__":
    out = HERE / "charts"
    out.mkdir(exist_ok=True)
    summary, figs = build_all()
    print(f"{TEAM}: {summary['games']} games, {summary['fga']:,} FGA")
    for name, fig in figs.items():
        fig.savefig(out / name, dpi=150)
    print(f"Saved charts to {out}")
    plt.show()

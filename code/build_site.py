"""
Build the interactive dashboard for Render.

    python code/build_site.py   ->  site/index.html

Python does the data work: it parses the play-by-play into compact, columnar
records (shots, rebounds, steals, blocks, assists, games, players) and embeds
them as JSON in code/dashboard.html. All filtering and charting happens in the
browser, so the page is a static site that works offline too.
"""

import json
import re

import numpy as np
import pandas as pd

from knicks_2026 import ROOT, TEAM, clock_to_sec, load_games

HERE = ROOT / "code"
SITE = ROOT / "site"
TEMPLATE = HERE / "dashboard.html"

# NBA team ids (used for logo URLs on cdn.nba.com)
TEAM_IDS = {
    "ATL": 1610612737, "BOS": 1610612738, "CLE": 1610612739, "NOP": 1610612740,
    "CHI": 1610612741, "DAL": 1610612742, "DEN": 1610612743, "GSW": 1610612744,
    "HOU": 1610612745, "LAC": 1610612746, "LAL": 1610612747, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "BKN": 1610612751, "NYK": 1610612752,
    "ORL": 1610612753, "IND": 1610612754, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "OKC": 1610612760,
    "TOR": 1610612761, "UTA": 1610612762, "MEM": 1610612763, "WAS": 1610612764,
    "DET": 1610612765, "CHA": 1610612766,
}

# Shot categories, in radar order. Index 0 = free throw.
CATS = ["Free throw", "Layup", "Dunk", "Hook", "Floater", "Midrange", "3-pointer"]
# Event kinds
EVENT_KINDS = ["OREB", "DREB", "STL", "BLK", "TOV", "PF"]


def shot_cat(subtype: str, is3: bool) -> int:
    if is3:
        return 6
    s = str(subtype).lower()
    if "dunk" in s:
        return 2
    if "hook" in s:
        return 3
    if "float" in s:
        return 4
    if "layup" in s or "finger roll" in s or "tip" in s:
        return 1
    return 5  # 2-pt jumpers: pull-ups, fadeaways, step-backs...


def elapsed(period: int, clock: str) -> int:
    s = clock_to_sec(clock)
    if period <= 4:
        return int((period - 1) * 720 + 720 - s)
    return int(2880 + (period - 5) * 300 + 300 - s)


def last_name(name: str) -> str:
    return str(name).split(". ", 1)[-1]


def build_data() -> dict:
    df = load_games().reset_index(drop=True)
    df["row"] = np.arange(len(df))
    nyk = df[(df["team"] == TEAM) & (df["playerid"] != 0)].copy()

    # ---- players
    roster = (nyk.dropna(subset=["player"])
              .groupby("playerid")["player"].agg(lambda s: s.mode().iloc[0]))
    # ---- games (sorted by id = schedule order)
    game_ids = sorted(df["gameid"].unique())
    gidx = {g: i for i, g in enumerate(game_ids)}

    nyk["g"] = nyk["gameid"].map(gidx)
    nyk["q"] = nyk["period"].clip(upper=5).astype(int)
    nyk["t"] = [elapsed(p, c) for p, c in zip(nyk["period"], nyk["clock"])]

    # ---- shots: field goals + free throws
    fga = nyk[nyk["type"].isin(["Made Shot", "Missed Shot"])].copy()
    fga["is3"] = fga["desc"].str.contains("3PT", na=False)
    fga["c"] = [shot_cat(s, t) for s, t in zip(fga["subtype"], fga["is3"])]
    fga["m"] = fga["type"].eq("Made Shot").astype(int)
    fga["v"] = np.where(fga["is3"], 3, 2)

    fta = nyk[nyk["type"] == "Free Throw"].copy()
    fta["c"] = 0
    fta["m"] = (~fta["desc"].str.startswith("MISS", na=False)).astype(int)
    fta["v"] = 1
    fta[["x", "y"]] = 0

    # assister: "(Towns 1 AST)" -> player id, resolved against that game's roster
    game_roster = (nyk.dropna(subset=["player"])
                   .assign(last=lambda d: d["player"].map(last_name))
                   .drop_duplicates(["gameid", "last"])
                   .set_index(["gameid", "last"])["playerid"])
    ast_last = fga["desc"].str.extract(r"\(([^()]+?) \d+ AST\)")[0]
    fga["a"] = [game_roster.get((g, n), -1) if isinstance(n, str) else -1
                for g, n in zip(fga["gameid"], ast_last)]
    fta["a"] = -1

    shots = pd.concat([fga, fta]).sort_values("row")

    # ---- events: rebounds (off/def from running counters), steals, blocks, TOV, fouls
    reb = nyk[nyk["type"] == "Rebound"].copy()
    counts = reb["desc"].str.extract(r"Off:(\d+) Def:(\d+)").astype(float)
    reb["off"] = counts[0]
    reb = reb.dropna(subset=["off"]).sort_values("row")
    prev = reb.groupby(["gameid", "playerid"])["off"].shift(fill_value=0)
    reb["k"] = np.where(reb["off"] > prev, 0, 1)

    stl = nyk[nyk["desc"].str.contains(r" STEAL \(", na=False)].assign(k=2)
    blk = nyk[nyk["desc"].str.contains(r" BLOCK \(", na=False)].assign(k=3)
    tov = nyk[nyk["type"] == "Turnover"].assign(k=4)
    pf = nyk[nyk["type"] == "Foul"].assign(k=5)
    events = pd.concat([reb, stl, blk, tov, pf]).sort_values("row")

    # ---- player index (sorted by points)
    pts = shots.loc[shots["m"] == 1].groupby("playerid")["v"].sum()
    order = sorted(roster.index, key=lambda pid: -pts.get(pid, 0))
    pidx = {pid: i for i, pid in enumerate(order)}
    players = [{"id": int(pid), "name": roster[pid], "last": last_name(roster[pid]),
                "pts": int(pts.get(pid, 0))} for pid in order]

    # ---- game metadata
    games = []
    team_pts = shots.loc[shots["m"] == 1].groupby("gameid")["v"].sum()
    appear = nyk.groupby("gameid")["playerid"].unique()
    for gid in game_ids:
        g = df[df["gameid"] == gid]
        opp = g["team"].dropna()
        opp = opp[opp != TEAM].mode().iloc[0]
        h, a = g["h_pts"].max(), g["a_pts"].max()
        mine = team_pts.get(gid, 0)
        home = abs(mine - h) <= abs(mine - a)
        nyk_pts, opp_pts = (h, a) if home else (a, h)
        games.append({
            "id": gid, "opp": opp, "oppId": TEAM_IDS.get(opp, 0), "home": bool(home),
            "pts": int(nyk_pts), "oppPts": int(opp_pts), "win": bool(nyk_pts > opp_pts),
            "ot": int(max(g["period"].max() - 4, 0)),
            "players": sorted(pidx[p] for p in appear.get(gid, []) if p in pidx),
        })

    def cols(frame, spec):
        return {k: [int(v) for v in f(frame)] for k, f in spec.items()}

    return {
        "team": TEAM, "teamId": TEAM_IDS[TEAM], "season": "2025-26",
        "cats": CATS, "eventKinds": EVENT_KINDS,
        "players": players, "games": games,
        "shots": cols(shots, {
            "g": lambda d: d["g"], "p": lambda d: d["playerid"].map(pidx),
            "q": lambda d: d["q"], "t": lambda d: d["t"], "c": lambda d: d["c"],
            "m": lambda d: d["m"], "v": lambda d: d["v"],
            "x": lambda d: d["x"].fillna(0).round(), "y": lambda d: d["y"].fillna(0).round(),
            "a": lambda d: d["a"].map(lambda pid: pidx.get(pid, -1)),
        }),
        "events": cols(events, {
            "g": lambda d: d["g"], "p": lambda d: d["playerid"].map(pidx),
            "q": lambda d: d["q"], "k": lambda d: d["k"],
        }),
    }


def main():
    data = build_data()
    SITE.mkdir(exist_ok=True)
    payload = json.dumps(data, separators=(",", ":"))
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    (SITE / "index.html").write_text(page, encoding="utf-8")
    w = sum(g["win"] for g in data["games"])
    print(f"{len(data['games'])} games ({w}-{len(data['games']) - w}), "
          f"{len(data['shots']['g']):,} shots, {len(data['events']['g']):,} events, "
          f"{len(data['players'])} players")
    print(f"Built {SITE / 'index.html'} ({len(page) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()

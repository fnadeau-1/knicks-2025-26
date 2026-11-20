"""
Build the static web page for Render.

    python code/build_site.py   ->  site/index.html + site/img/*.png

Render runs this as the static site's build command and publishes the site/ folder.
Open site/index.html locally to preview.
"""

import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display on the build server

from knicks_2026 import ROOT, build_all  # noqa: E402

SITE = ROOT / "site"
IMG = SITE / "img"

CHARTS = [
    ("1_shot_heatmap.png", "Where the shots came from",
     "Every Knicks field-goal attempt on a half court. Darker hexes mean more attempts. "
     "Most shots come at the rim and from beyond the arc, especially the corners."),
    ("2_shot_type.png", "Shot type",
     "How many attempts each shot type got, and how often each one went in."),
    ("3_efficiency_by_minute.png", "Efficiency throughout the game",
     "Effective FG% (3-pointers count 1.5×) for each minute of regulation, "
     "with a 3-minute rolling average."),
    ("4_leaderboards.png", "Leaderboards",
     "Top five Knicks in points, rebounds, assists and 3-pointers made."),
]

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knicks 2025-26</title>
<meta name="description" content="Shot charts, efficiency and leaderboards for the 2025-26 New York Knicks.">
<style>
  :root {{
    --bg: #fcfcfb; --card: #ffffff; --ink: #0b0b0b; --ink-2: #52514e;
    --line: #e4e3df; --accent: #2a78d6;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }}
  main {{ max-width: 1080px; margin: 0 auto; padding: 48px 16px 64px; }}
  header p.kicker {{
    margin: 0 0 6px; color: var(--accent); font-weight: 700;
    letter-spacing: .08em; text-transform: uppercase; font-size: 13px;
  }}
  h1 {{ margin: 0 0 8px; font-size: clamp(28px, 5vw, 44px); line-height: 1.1; }}
  header p.lede {{ margin: 0; color: var(--ink-2); max-width: 60ch; }}
  .stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px; margin: 32px 0 40px;
  }}
  .stat {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }}
  .stat .v {{ font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; }}
  .stat .k {{ color: var(--ink-2); font-size: 13px; }}
  section {{
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 24px; margin-bottom: 24px;
  }}
  section h2 {{ margin: 0 0 4px; font-size: 20px; }}
  section p {{ margin: 0 0 16px; color: var(--ink-2); }}
  section img {{ display: block; width: 100%; height: auto; }}
  .narrow img {{ max-width: 640px; margin: 0 auto; }}
  footer {{ color: var(--ink-2); font-size: 13px; margin-top: 32px; }}
</style>
</head>
<body>
<main>
  <header>
    <p class="kicker">New York Knicks · 2025-26</p>
    <h1>The Knicks Championship Run</h1>
    <p class="lede">Where the shots came from, what kind of shots they were, how efficiency
    moved through a game, and who led the team.</p>
  </header>

  <div class="stats">
{stats}
  </div>

{sections}

  <footer>
    Source: NBA play-by-play, 2025-26 regular season ({games} games).
    Per-game leaderboard values divide season totals by team games played.
  </footer>
</main>
</body>
</html>
"""


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    summary, figs = build_all()

    for name, fig in figs.items():
        fig.savefig(IMG / name, dpi=150)

    stats = [
        (summary["games"], "Games"),
        (f"{summary['fga']:,}", "Shot attempts"),
        (f"{summary['efg']:.1%}", "Effective FG%"),
        (f"{summary['fg3m']:,}", "3-pointers made"),
        (summary["top_scorer"], "Top scorer"),
    ]
    stats_html = "\n".join(
        f'    <div class="stat"><div class="v">{html.escape(str(v))}</div>'
        f'<div class="k">{k}</div></div>'
        for v, k in stats
    )
    sections_html = "\n".join(
        f'  <section{" class=\"narrow\"" if fname.startswith("1_") else ""}>\n'
        f"    <h2>{title}</h2>\n    <p>{desc}</p>\n"
        f'    <img src="img/{fname}" alt="{title} chart" loading="lazy">\n  </section>'
        for fname, title, desc in CHARTS
    )

    (SITE / "index.html").write_text(
        PAGE.format(stats=stats_html, sections=sections_html, games=summary["games"]),
        encoding="utf-8",
    )
    print(f"Built {SITE / 'index.html'}")


if __name__ == "__main__":
    main()

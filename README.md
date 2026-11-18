# Team Success (HoopsMatic)

Every NBA player's team record with him and without him, every season since 1946-47.
Served at https://hoopsmatic.com/team-success/.

## Data pipeline

```
bash scripts/fetch_sources.sh          # public repos + Ramiro's Parquet files into _src/ (git-ignored)
python scripts/build_history.py        # rebuilds everything in data/ (about 1 minute)
python scripts/step0_report.py         # docs/step0-report.md
python scripts/audit.py                # docs/audit-report.md + data/audit.json (no network)
python scripts/build_help.py           # data/help.json: teammate help per team-season + peers
python -m pytest tests/ -q             # sanity checks on the committed data
```

| File | What it is |
|---|---|
| `data/team_standings.csv` | the owner's standings file (records, finish, RNK, playoff finish) |
| `data/franchise_map.json` | (era code, season) -> current franchise + the team's real name that season |
| `data/player_ids.json` | NBA personId -> stable slug (Career Map style) + display name + headshot file |
| `data/team_seasons.json` | one row per franchise-season: record, finish, RNK, playoff series |
| `data/players.json` | one row per player-team-season: games, with/without records, on/off, starts, close games; best duos; accolade score |
| `data/step0.json` | the numbers behind `docs/step0-report.md` (incl. `impossible_rows_dropped`) |
| `data/gamelog/<season>.json` | every counted game and who appeared for each side (audit, opponent tables) |
| `data/audit.json` | the numbers behind `docs/audit-report.md`, re-checked by `tests/test_audit.py` |

## Pages

```
python scripts/build_site.py           # every page (about 5 seconds); writes only files that changed
python -m pytest tests/ -q             # data + page checks (canonical, footer, links, escaping, JS = Python ranks)
node tests/layout.js                   # no horizontal scroll, every template, 320-1920 px (Playwright)
node scripts/render_cards.js           # share PNGs of the suggested comparisons (compare/img/), local only
python scripts/quantize_cards.py       # shrink them to a 64-colour palette (~30 KB each)
```

Output is served from the repo root (GitHub Pages: main, / (root)), and will be served at
https://hoopsmatic.com/team-success/ through the HoopsMatic Worker:
`index.html` (hub), `player/<slug>.html`, `lists/<list>.html` (incl. the eight career boards,
filtered in the browser by `assets/boards.js` from `assets/board.json`), `seasons/<1997-98>.html`
(every team ranked by final finish), `players/<a-z>.html`,
`how-we-count.html`, `sitemap.xml`, `assets/` (CSS, fonts, headshots, share card, search).
Internal links are relative; canonical, og:url, og:image and the sitemap use hoopsmatic.com.

## Nightly

`.github/workflows/nightly.yml` runs at 11:15 UTC: `scripts/update_current.py` downloads only
the 2026-27 season (Ramiro's Parquet files; nba-boxscores' season folder once it exists) into
`data/current.json`; `scripts/daily_story.py` writes the day's "Today in Team Success" story
(`data/stories.json`, `stories/img/<date>.png`; tonight's schedule from cdn.nba.com, no key); if either
changed, `scripts/build_site.py --current` rebuilds the hub, the stories, the
two current-season boards, the active players' pages, A-Z, search and the sitemap. It commits
only when something changed. `data/sitemap_lastmod.json` keeps each page's content hash, so a
`<lastmod>` date moves only when that page's content changes.

## When a season ends

Add the season to `data/team_standings.csv`, bump `LAST_COMPLETE` and `CURRENT_SEASON` in
`scripts/common.py`, run `bash scripts/fetch_sources.sh`, `python scripts/build_history.py`,
`python scripts/build_site.py`, and the tests.

No keys or tokens are needed anywhere.

## Copy rules

Every factual sentence is a template filled from data; the rules are in `docs/story-rules.md`.

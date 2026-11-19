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

## Round 2 (Nov 2026)

- Look: the Head-to-Head design system (nba-head-to-head `src/styles.css`): black links, tinted leader
  cells, H2H faces (initials when there is no file) and H2H's logo rule (`assets/logos/`: the current
  logo only for a current name, 8 historical files for exact old names, otherwise none). Search at the
  top and the bottom of every page.
- Data: career W-L, with/without and every career board count the season to date (`data/current.json`,
  team records in `teams`); season counts and finishes use completed seasons. Boards have "Completed
  seasons only". The nightly job runs the full `build_site.py` (about 40 seconds).
- New board `lists/no-allstar-teammate.html`; `seasons/2026-27.html` (standings to date).
- `assets/card/<slug>.json`, `assets/card/lists/<list>.json`, `assets/card/seasons/<season>.json`: data
  for the hoopsmatic-og-card social cards.

## Round 3 (Nov 2026)

- Share cards: og:image / twitter:image point at hoopsmatic-og-card (`https://hoopsmatic.com/og/team-success/`):
  `player/<slug>.png` (players with a completed season), `list/<list>.png` (the 9 career boards),
  `season/<season>.png` (completed seasons), `compare/<a>--<b>.png`. Everything else keeps
  `assets/og-team-success.png`. The pre-rendered `compare/img/` PNGs and their scripts are gone; the
  in-browser "Download image" button stays.
- No-All-Star board: team-seasons whose All-Stars are not in the awards data (or no `data/help.json` rows)
  are left out, not counted as "no All-Star" (`boards.honors_missing`); they return on the next
  rebuild once nba-player-data has them.
- Honors come from nba-player-data's `awards.json` (same fields as the old Awards.csv, which stops at
  2024-25). After awards.json changes: `python scripts/build_history.py --awards-only`, then
  `build_help.py`, `step0_report.py`, `build_site.py`.
- Average finish: league-size-adjusted by default, shown as a 30-team equivalent (1 + adjusted x 29).
- Tables and cards name teams by city that season (`city_of`); headings, titles and prose keep full names.
- `tests/layout.js` also fails on a lone ":" "," or "·" line in tables/cards and on a team name that wraps
  inside a word (390 and 1366 px).

## Round 4 (Nov 2026)

- Nightly: four slots a day (11:37, 14:37, 18:37, 23:37 UTC). Ramiro's Parquet files land around
  13:00-13:30 UTC, after the old single 11:15 slot, and GitHub delays or skips scheduled runs. The
  first run of a date writes the story and fun facts; a later run rewrites them only when newer
  games arrive; nothing is committed otherwise. `data/current.json` now carries the season's game
  log (`log`), so "last night" passes come from the games, not from the previous run's totals.
- Fun facts strip under the homepage title (`scripts/fun_facts.py` -> `data/facts.json`), rules in
  `docs/story-rules.md`. Daily story: no lead repeats within 30 days, quiet days always have a
  comparison, supporting links are about the story's players.
- Compare any two players: `compare/?a=<slug>&b=<slug>` (`compare/index.html`, `assets/compare.js`),
  noindex, canonical `compare/` or the pre-built pair page. Player pages: "Compare X with..." block
  under the lead; `?peer=` links redirect there (ts.js). Pre-built pair pages unchanged otherwise.
- "Download image" links the og-card PNG (`/og/team-success/compare/<a>--<b>.png`,
  `/og/team-success/player/<slug>.png`); the canvas card is gone.
- Homepage with/without: 10+ played and 8+ missed, career leaders when fewer than 3 qualify.
  Comparison of the day: `scripts/picks.py` (300+ games each, one All-Star, same era, 120-day cycle).
- Result wording: "Missed playoffs", "Lost in play-in".

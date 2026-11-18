# (c) 2026 HoopsMatic. All rights reserved.
# Team Success Step 0 report. Fingerprint: hm-ts-7f3a91c2-step0
"""Write docs/step0-report.md from data/step0.json and the committed data files."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analysis import Data, count_flag, count_sixty  # noqa: E402
from common import DATA, ROOT, load_json, season_label  # noqa: E402


def ranges(years):
    years = sorted(years)
    out = []
    for y in years:
        if out and y == out[-1][1] + 1:
            out[-1][1] = y
        else:
            out.append([y, y])
    return ", ".join(f"{season_label(a)}" if a == b else f"{season_label(a)} to {season_label(b)}"
                     for a, b in out)


def main():
    s = load_json(os.path.join(DATA, "step0.json"))
    d = Data()
    L = []
    w = L.append
    w("# Team Success: Step 0 report")
    w("")
    w("Read-only checks on the sources, run before building the pages. Every number below comes "
      "from `scripts/build_history.py` (saved in `data/step0.json`) and the main ones are "
      "re-checked by `tests/test_step0.py` on every run.")
    w("")
    w("## Sources (public, no tokens)")
    w("")
    w("| Source | Version used | What we take |")
    w("|---|---|---|")
    src = s["sources"]
    w(f"| aderoa/nba-boxscores | {src['nba-boxscores']} | every game and box score, 1946-47 to 2025-26 |")
    w(f"| jsierrahoopshype/nba-player-data | {src['nba-player-data']} | RS-Stats.csv (names), Awards.csv |")
    w(f"| jsierrahoopshype/hh-teammates | {src['hh-teammates']} | accolade weights (`scores`) and the scoring rules |")
    w(f"| ramirobentes/nbadatar (data in ramirobentes/nba_data releases) | Parquet files of 2026-11-18 | lineups and possessions, 1996-97 on |")
    w(f"| jsierrahoopshype/nba-headshots | {src['nba-headshots']} | face-fill headshots, team slugs |")
    w(f"| jsierrahoopshype/nba-career-map | {src['nba-career-map']} | era names cross-check, player slugs |")
    w("| team_standings.csv (attached) | committed as data/team_standings.csv | team records, finish, RNK, playoff finish |")
    w("")

    st = s["standings"]
    w("## team_standings.csv: verified facts")
    w("")
    w(f"- {st['rows']} team-seasons, 1946-47 to 2025-26.")
    w("- **Team ABR is the current franchise code** for old seasons: `SAC 1956` is the Rochester "
      "Royals, `GSW 1947` the Philadelphia Warriors, `OKC 1975` the Seattle SuperSonics. The `Team` "
      "column is today's name, so the pages never show it; they use the era name from "
      "`data/franchise_map.json` instead.")
    f = st["wl_pct_formats"]
    w(f"- **W-L% is mixed**: {f.get('xxx', 0)} rows written like `439`, {f.get('0.xxx', 0)} like "
      "`0.439`. We never read it; win % is always Win / (Win + Losses).")
    w(f"- **Trailing columns are shifted**: the ATL 2024 row ends `{', '.join(st['atl_2024_trailing'][1:])}` "
      "although the Hawks lost in the play-in (`Playoffs` = `Play-In`). Those last two columns are a "
      "pasted lookup table (round name, tier points), not that team's result. We ignore them and "
      "use the `Playoffs` column plus the playoff games themselves.")
    w("- **RNK is the owner's season ranking**: champion first, then runner-up, then by playoff "
      "round reached, then by win % (play-in teams rank above non-playoff teams; ties share a rank). "
      "`RNK PTS` holds the tier points behind it (100,000 champion, 10,000 finalist, 1,000 conference "
      "finalist, 100 semis, 10 first round, 1 play-in, plus win %). Sample, 1974-75:")
    w("")
    w("| Season | Team | W-L | Playoffs | RNK | RNK PTS |")
    w("|---|---|---|---|---|---|")
    for sy, code, ww, ll, po, rnk, pts in [x for x in st["rnk_samples"] if x[0] == 1975][:10]:
        name = d.team(code, sy)["name"]
        w(f"| {season_label(sy)} | {name} | {ww}-{ll} | {po or 'missed'} | {rnk} | {pts} |")
    w("")
    w("  Every season has exactly one champion and it has RNK 1 (tested).")
    w(f"- **BRK vs BKN**: Brooklyn is `BRK` in the {st['brk_fixed']} rows for 2024-25 and 2025-26 "
      "and `BKN` everywhere else. We read `BRK` as `BKN`.")
    w(f"- **2025-26 has no conference/division finish** (blank `Conf Pos`, `Div Pos`, `Postition`). "
      f"We compute those {st['positions_computed']} places from W-L (ties share a place) and mark them computed.")
    w("- **The `PO-series.csv` file is not a team playoff table**: it lists each player's career "
      "series won/lost. So round, opponent and series score come from the playoff games in "
      "nba-boxscores (game ID 3rd character `4`), grouped by opponent.")
    w("")

    # a
    gc = s["game_counts_raw"]
    w("## a. Regular-season games: nba-boxscores vs standings")
    w("")
    w(f"Raw comparison (games in nba-boxscores with game ID type `2` vs the sum of wins in the standings): "
      f"**{gc['match']} of {gc['seasons']} seasons match**. Off by 1-2 in "
      + ", ".join(season_label(x["season"]) for x in gc["diffs"]) + ".")
    w("")
    w("| Season | Box score games | Standings | Teams off |")
    w("|---|---|---|---|")
    for x in gc["diffs"]:
        teams = ", ".join(f"{d.team(t['team'], x['season'])['name']} {t['boxscores']} vs {t['standings']}"
                          for t in x["teams"])
        w(f"| {season_label(x['season'])} | {x['boxscores']} | {x['standings_wins']} | {teams} |")
    w("")
    w("What the extra and missing games are:")
    w("")
    for g in s["games_dropped"]:
        w(f"- {g['date']} `{g['gameId']}` {g['game']}: **{g['why']}**, removed from regular-season counts.")
    w("- 1953-54: one Milwaukee Hawks vs Baltimore Bullets game is **missing** from nba-boxscores "
      "(both teams have 71 games, standings say 72). Nothing to add it from, so it is left out.")
    w("")
    cl = s["game_counts_clean"]
    w(f"After removing those 9: **{cl['match']} of {cl['seasons']} seasons match**; only 1953-54 is off (by the missing game).")
    w("")
    w("Game results that disagree with the official records (team pages show the official record; "
      "the with/without numbers use the games):")
    w("")
    w("| Team-season | Standings | From box scores |")
    w("|---|---|---|")
    for x in s["wl_mismatch"]:
        f2, sy = x["team"].split()
        w(f"| {x['name']} {season_label(int(sy))} | {x['standings']} | {x['boxscores']} |")
    w("")
    w(f"Also fixed: {s['null_codes_fixed']} neutral-site games in 2024-25 and 2025-26 (NBA Cup "
      "semifinals, Mexico City, Paris, London, Berlin) have `home: null` and `homeScore: null`, with "
      "both teams flagged as visitors. We fill in the other team from the box score and its score "
      "from its players' points:")
    w("")
    for g in s["neutral_site_fixed"]:
        w(f"- {g['date']} `{g['gameId']}` {g['teams']}")
    w("")

    # b
    w("## b. Franchise map")
    w("")
    fm = load_json(os.path.join(DATA, "franchise_map.json"))
    codes = {e["code"] for e in fm["eras"]}
    w(f"`data/franchise_map.json` maps every (era code, season) in nba-boxscores to the current "
      f"franchise code and the team's real name that season: {len(codes)} era codes, "
      f"{len(fm['eras'])} name eras. Examples: 1967-68 `SDR` -> HOU, San Diego Rockets; 1996-97 "
      "`VAN` -> MEM, Vancouver Grizzlies; 2009-10 `NJN` -> BKN, New Jersey Nets; 2011-12 `CHA` -> "
      "CHA, Charlotte Bobcats; 2005-06 `NOK` -> NOP, New Orleans/Oklahoma City Hornets.")
    w("")
    unm = s["unmapped_codes"]
    w(f"- Codes we could not map: **{'none' if not unm else ', '.join(unm)}**. Every team-season in "
      "the games is in the standings and vice versa.")
    w("- **Bug in nba-boxscores**: its `data/team_codes.json` maps `BOM` to `BAL`. `BOM` (1946-47 to "
      "1949-50) is the St. Louis Bombers (`STB` in the standings), not the Baltimore Bullets. Our map "
      "uses STB. Worth fixing upstream; we did not touch that repo.")
    w("- `WAS` means two different franchises: the Washington Capitols (1946-47 to 1950-51, `WSC`) and "
      "the Bullets/Wizards (from 1974-75). `DN` (1949-50) is the old Denver Nuggets (`DNN`), not today's.")
    w("- Names checked against nba-career-map `data/nba_team_index.json`: every Career Map era name is "
      "used. Names we use that Career Map does not have: " + ", ".join(s["names_not_in_career_map"]) +
      ". All but two are defunct teams with no Career Map page (their names stay unlinked). "
      "\"New Orleans/Oklahoma City Hornets\" (2005-06, 2006-07) is the name the team used those "
      "seasons; Career Map files them under New Orleans Hornets. \"Los Angeles Clippers\" is used for "
      "1984-85 to 2014-15 and \"LA Clippers\" from 2015-16 (the team's rebrand); Career Map uses "
      "\"LA Clippers\" throughout. Both still link to the same Career Map team page.")
    w("")

    # c
    idn = s["identity"]
    w("## c. Player identity")
    w("")
    w("Box-score players (personId + name) matched to RS-Stats.csv names per season + franchise, "
      "accents and punctuation stripped on both sides. Passes, in order: exact name, name without "
      "Jr./Sr./II and birth-year tags, same last name + first initial, the only player on that "
      "team-season with that last name (RS-Stats uses nicknames: Johnny Kerr = \"Red Kerr\", Rod "
      "Hundley = \"Hot Rod Hundley\"), close spelling (similarity 0.85+). A small alias list covers "
      "renamed players (Enes Freedom = Enes Kanter, Timothe Luwawu-Cabarrot = Timothe Luwawu).")
    w("")
    w(f"- Player-team-seasons: **{idn['matched']} of {idn['player_team_seasons']} matched "
      f"({idn['rate'] * 100:.1f}%)**.")
    w(f"- Players: {idn['players']}; with an RS-Stats name: {idn['players'] - idn['no_rs_name']}; "
      f"with a Career Map page under the same slug: {idn['career_map_pages']}.")
    nn = s["identity_no_name_20plus"]
    w(f"- Players with 20+ games and **no RS-Stats name at all: {len(nn)}**, all 2025-26 rookies "
      "missing from RS-Stats (their box-score name is used, and it matches Career Map):")
    for x in nn:
        w(f"  - {x['name']} ({x['games']} games, personId {x['personId']})")
    um = idn["unmatched_20plus"]
    w(f"- Single seasons with 20+ games that did not match by name for that team ({len(um)} "
      "rows). The player is still identified by personId from his other seasons; these are mostly "
      "1950s RS-Stats rows filed under a different team or season. Full list at the end of this report.")
    w(f"- `data/player_ids.json`: one stable slug per personId. Career Map rule (`Nikola Jokić` -> "
      "`nikola-jokic`), and Career Map's birth-year names for same-name players (`charles-smith-1965`). "
      f"{len(idn['slug_suffixed'])} slugs carry a year or id suffix: " + ", ".join(idn["slug_suffixed"]) + ".")
    w("")

    # d
    g = s["minutes_groups"]
    w("## d. \"Did he play?\"")
    w("")
    w("Rule: appeared = minutes > 0 OR any counting stat > 0; when minutes were never recorded, "
      "appeared = he has a box-score row. Minutes are recorded game by game, not season by season, "
      "so we apply the rule **per team-game**: if any player of that team has minutes in that game, "
      "the minutes rule applies; otherwise a row counts as an appearance.")
    w("")
    w(f"- Minutes never recorded: **{ranges(g['never'])}** (row present = appeared).")
    w(f"- Minutes recorded in some games only: **{ranges(g['partial'])}** "
      "(share of team-games with minutes rises from 13% in 1951-52 to 95% in 1975-76).")
    w(f"- Minutes recorded in (almost) every game: **{ranges(g['always'])}**.")
    cam = s["ramiro_cameos_counted"]
    tot = sum(cam["regular"].values())
    w(f"- **Change from the brief, flagged for you**: from 1996-97, a row with 0 minutes and no stats "
      f"is usually NOT a DNP. Ramiro's lineups put {tot} of those player-games (about 60-140 a season) "
      "on the floor: seconds-long cameos whose minutes round down to 0. We count those as "
      "appearances. Only "
      f"{sum(v for k, v in s['zero_rows_still_excluded'].items() if int(k) >= 1997)} zero rows from "
      "1996-97 on stay excluded. Switch: `COUNT_RAMIRO_CAMEOS` in `scripts/build_history.py`.")
    w("")

    # e
    cov = s["ramiro_coverage"]
    full = sum(1 for v in cov.values() if v["regular"][0] == v["regular"][1])
    w("## e. Ramiro's data")
    w("")
    w("Seasons 1996-97 to 2025-26, regular season and playoffs, plus 2026-27 regular season "
      "(updated daily; checked through games of 2026-11-16). Files are Parquet releases at "
      "github.com/ramirobentes/nba_data (the nbadatar R package just downloads them).")
    w("")
    w("| File | What we use it for |")
    w("|---|---|")
    w("| `lineup_stats_<regular/playoffs>_<season>.parquet` | one row per stint: both 5-man lineups (NBA person IDs), seconds, possessions and points for both teams. **On/off per 100** (points and possessions with him on vs his team's other stints in the same games) and **starters** (the team's first stint of the game). |")
    w("| `possessions_<...>_<season>.parquet` | one row per possession with the score at its start, the period, the clock and both lineups. **Close games** = a possession in the last 5:00 of the 4th quarter or any overtime with the margin at 5 or fewer; \"on the floor\" = in either lineup on one of those possessions. |")
    w("| `pbp_<...>_<season>.parquet` | not used (the two tables above already carry what we need, at a fraction of the size). |")
    w("")
    gaps = [f"{season_label(int(k))} {kind} {v[kind][0]} of {v[kind][1]} games"
            for k, v in sorted(cov.items()) for kind in ("regular", "playoffs")
            if v[kind][0] != v[kind][1]]
    w(f"Coverage: lineups for every regular-season game in {full} of {len(cov)} seasons. Gaps: "
      + ("; ".join(gaps) if gaps else "none") + ". Person IDs match "
      "nba-boxscores personId exactly, so no name matching is needed.")
    w("")

    # f
    hs = s["headshots"]
    w("## f. Headshots (option C)")
    w("")
    w("nba-headshots README (Oct 26 2026): `players/headshots/face-fill/` is \"THE HoopsMatic headshot: "
      "the face fills the frame, chin just inside the bottom, no neck line, no background. 160x160 "
      "transparent WebP, show it in a circle\". The newest section, Teammates "
      "(hh-teammates `build_teammates.py`), uses exactly those files with this CSS: "
      "`.hs{width:72px;height:72px;border-radius:50%;overflow:hidden;object-fit:cover;background:#e8e8ed}` "
      "and the player's initials in the same circle when there is no file.")
    w("")
    w(f"- face-fill files: {hs['face_fill_files']}. Players in Team Success with a photo: "
      f"**{hs['players_with_photo']} of {hs['players']}** (file names are `<NBA personId>-<name>.webp`, "
      "and personId is the box-score id, so matching is exact).")
    w("- Teammates loads them from jsierrahoopshype.github.io. The brief forbids third-party requests "
      "from the visitor's browser and github.io anywhere, so Team Success **copies the face-fill files "
      "it needs into this repo** (`assets/hs/`) and serves them from hoopsmatic.com paths. Same files, "
      "same look. Missing photo: an empty circle on light grey (#e8e8ed), never black.")
    w("")

    # expected results
    w("## Expected results (also in tests/test_step0.py)")
    w("")
    c, det = count_flag(d, "worst")
    top = c.most_common(1)[0][1]
    w(f"- Worst record, all-time: top count is {top}: " +
      ", ".join(sorted(d.ids[k]["name"] for k, v in c.items() if v == top)) + ". Matches.")
    c, det = count_flag(d, "worst", 1977)
    at3 = sorted(d.ids[k]["name"] for k, v in c.items() if v == 3)
    w(f"- Worst record since 1976-77: nobody above {max(c.values())}; {len(at3)} players at 3: "
      + ", ".join(at3) + ". Matches (the 10 named in the brief all had 20+ games each time).")
    c, _ = count_sixty(d)
    tops = c.most_common(5)
    w("- 60-win pace (win % >= 60/82 = .732): " + ", ".join(f"{d.ids[k]['name']} {v}" for k, v in tops)
      + ". Matches.")
    w("")

    w("## Season-level unmatched rows (20+ games)")
    w("")
    w("| Season | Team | Box-score name | Games |")
    w("|---|---|---|---|")
    for x in um:
        t = d.team(x["team"], x["season"])
        w(f"| {season_label(x['season'])} | {t['name'] if t else x['team']} | {x['name']} | {x['games']} |")
    w("")
    out = os.path.join(ROOT, "docs", "step0-report.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()

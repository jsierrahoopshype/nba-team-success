# (c) 2026 HoopsMatic. All rights reserved.
# Team Success data audit. Fingerprint: hm-ts-7f3a91c2-audit
"""Audit of the Team Success data against its own rules (brief section 6).

python scripts/audit.py        # writes data/audit.json and docs/audit-report.md

Runs on the committed data (data/gamelog/, team_seasons.json, players.json, team_standings.csv,
current.json). When the raw sources are present in _src/ (scripts/fetch_sources.sh) it also
checks them for duplicate games and duplicate box-score rows. No network.
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis as A  # noqa: E402
from common import (CURRENT_SEASON, DATA, FIRST_SEASON, LAST_COMPLETE, RAMIRO_FIRST, ROOT, SRC,  # noqa: E402
                    STANDINGS_CODE_FIX, dump_json, load_json, season_label)

TIER = {"Champion": 5, "Finalist": 4, "Conf Finalist": 3, "Conf Semis": 2, "First Round": 1,
        "Play-In": 0.5, "": 0}
out = {}


def gamelogs():
    g = {}
    for sy in range(FIRST_SEASON, LAST_COMPLETE + 1):
        p = os.path.join(DATA, "gamelog", f"{sy}.json")
        if os.path.exists(p):
            g[sy] = load_json(p)
    return g


def won(row, fr):
    gid, date, h, a, hc, ac, hs, as_ = row
    return (hs > as_) if fr == h else (as_ > hs)


def check_rnk(d):
    """Recompute RNK from the published rule and compare with the CSV."""
    by = defaultdict(list)
    for t in d.teams.values():
        by[t["s"]].append(t)
    mism, sizes, ties = [], {}, 0
    for sy, ts in sorted(by.items()):
        sizes[sy] = len(ts)
        keys = {t["f"]: (TIER[t["po"]], round(t["w"] / (t["w"] + t["l"]), 6)) for t in ts}
        for t in ts:
            want = 1 + sum(1 for o in ts if keys[o["f"]] > keys[t["f"]])
            if want != t["rnk"]:
                mism.append({"season": sy, "team": t["f"], "name": t["name"], "po": t["po"],
                             "rec": f'{t["w"]}-{t["l"]}', "csv": t["rnk"], "rule": want})
        c = Counter(t["rnk"] for t in ts)
        ties += sum(v for v in c.values() if v > 1)
    out["rnk"] = {"mismatches": mism, "league_sizes": sizes,
                  "tied_rows": ties, "max_rank_le_size": all(
                      max(t["rnk"] for t in by[sy]) <= sizes[sy] for sy in by)}


def check_playoffs(d, logs):
    """Standings playoff result vs the playoff games."""
    faults = []
    for t in d.teams.values():
        sr = t["series"]
        po = t["po"]
        if po in ("", "Play-In") and sr:
            faults.append({"team": f'{t["f"]} {t["s"]}', "name": t["name"], "po": po or "missed",
                           "series": [f'{s["opp"]} {s["w"]}-{s["l"]}' for s in sr]})
        if po not in ("", "Play-In") and not sr:
            faults.append({"team": f'{t["f"]} {t["s"]}', "name": t["name"], "po": po, "series": []})
        if po == "Champion" and sr and not sr[-1]["won"]:
            faults.append({"team": f'{t["f"]} {t["s"]}', "name": t["name"], "po": po,
                           "series": ["last series lost"]})
    # "series" that are not a best-of series: pairs that met in a round robin, or met twice
    odd = []
    for t in d.teams.values():
        for s in t["series"]:
            if s["w"] == s["l"] or (max(s["w"], s["l"]) == 1 and s["w"] + s["l"] > 1):
                if t["f"] < s["opp"]:
                    odd.append({"season": t["s"], "teams": f'{t["f"]}-{s["opp"]}',
                                "games": f'{s["w"]}-{s["l"]}', "from": s["start"], "to": s["end"]})
    out["playoffs"] = {"standings_vs_games": sorted(faults, key=lambda x: x["team"]),
                       "non_series_pairs": sorted(odd, key=lambda x: (x["season"], x["teams"]))}


def check_games(d, logs):
    per_team = Counter()
    dup_matchups = []
    two_teams = []
    for sy, lg in logs.items():
        seen = Counter()
        for row in lg["games"]:
            gid, date, h, a = row[:4]
            if gid[2] == "2":
                per_team[(h, sy)] += 1
                per_team[(a, sy)] += 1
                seen[(date, h, a)] += 1
            hp, ap = lg["app"].get(gid, [[], []])
            both = set(hp) & set(ap)
            if both:
                two_teams.append({"gameId": gid, "date": date, "players": sorted(both)})
        dup_matchups += [{"season": sy, "date": k[0], "home": k[1], "away": k[2], "n": v}
                         for k, v in seen.items() if v > 1]
    off = []
    for t in d.teams.values():
        n = per_team[(t["f"], t["s"])]
        if n != t["w"] + t["l"]:
            off.append({"team": f'{t["f"]} {t["s"]}', "name": t["name"], "games": n,
                        "standings": t["w"] + t["l"]})
    out["games"] = {"team_game_counts_off": sorted(off, key=lambda x: x["team"]),
                    "same_matchup_same_day": dup_matchups, "player_on_both_sides": two_teams,
                    "regular_season_games": sum(1 for lg in logs.values() for r in lg["games"] if r[0][2] == "2"),
                    "playoff_games": sum(1 for lg in logs.values() for r in lg["games"] if r[0][2] == "4")}


def check_raw_sources():
    """Duplicates inside the raw source files (dedup by dict would hide them)."""
    box = os.path.join(SRC, "nba-boxscores", "data")
    if not os.path.isdir(box):
        out["raw"] = None
        return
    dup_gid, dup_row, types = Counter(), Counter(), Counter()
    for sy in range(FIRST_SEASON, LAST_COMPLETE + 1):
        gp = os.path.join(box, str(sy), "games.ndjson")
        if not os.path.exists(gp):
            continue
        c = Counter()
        for line in open(gp):
            g = json.loads(line)
            c[g["gameId"]] += 1
            types[(sy, g["gameId"][2])] += 1
        dup_gid[sy] = sum(v - 1 for v in c.values() if v > 1)
        r = Counter()
        for line in open(os.path.join(box, str(sy), "boxscores.ndjson")):
            b = json.loads(line)
            r[(b["gameId"], b["personId"], b["team"])] += 1
        dup_row[sy] = sum(v - 1 for v in r.values() if v > 1)
    play_in = {str(sy): n for (sy, t), n in types.items() if t == "5"}
    out["raw"] = {"duplicate_game_ids": {str(k): v for k, v in dup_gid.items() if v},
                  "duplicate_box_rows": {str(k): v for k, v in dup_row.items() if v},
                  "play_in_games_type5": play_in,
                  "game_types": sorted({t for (_, t) in types})}


def windows(d, logs):
    """How the published window proxy counts games he could not have played."""
    team_games = defaultdict(list)
    for sy, lg in logs.items():
        for row in lg["games"]:
            if row[0][2] == "2":
                team_games[(row[2], sy)].append(row)
                team_games[(row[3], sy)].append(row)
    pre = post = gapboth = 0
    pre_rows = post_rows = traded_rows = 0
    examples = {"before_first": [], "after_last": [], "between_teams": []}
    zero_missed_careers = 0
    for pid, p in d.players.items():
        by = defaultdict(list)
        for st in p["seasons"]:
            if st["s"] <= LAST_COMPLETE and st["g"]:
                by[st["s"]].append(st)
        cw = sum(st["ow"] + st["ol"] for sts in by.values() for st in sts)
        if by and cw == 0:
            zero_missed_careers += 1
        for sy, sts in by.items():
            sts.sort(key=lambda x: x["first"])
            for i, st in enumerate(sts):
                tg = team_games[(st["f"], sy)]
                before = [r for r in tg if r[1] < st["first"] and st["win"][0][0] <= r[1]]
                after = [r for r in tg if r[1] > st["last"] and r[1] <= st["win"][-1][1]]
                if len(sts) == 1:
                    if before:
                        pre += len(before)
                        pre_rows += 1
                        examples["before_first"].append((len(before), pid, sy, st["f"]))
                    if after:
                        post += len(after)
                        post_rows += 1
                        examples["after_last"].append((len(after), pid, sy, st["f"]))
                else:
                    # games in the days between two teams, counted "without him" for both
                    n = 0
                    if i < len(sts) - 1:
                        n += len([r for r in after if r[1] < sts[i + 1]["first"]])
                    if i > 0:
                        n += len([r for r in before if r[1] > sts[i - 1]["last"]])
                    if n:
                        gapboth += n
                        traded_rows += 1
                        examples["between_teams"].append((n, pid, sy, st["f"]))
    for k in examples:
        examples[k] = [{"games": n, "player": d.ids[pid]["name"], "slug": d.ids[pid]["slug"],
                        "season": sy, "team": f} for n, pid, sy, f in sorted(examples[k], reverse=True)[:8]]
    out["windows"] = {
        "one_team_games_before_first_appearance": pre, "rows_before": pre_rows,
        "one_team_games_after_last_appearance": post, "rows_after": post_rows,
        "traded_games_between_teams": gapboth, "rows_traded": traded_rows,
        "zero_missed_careers": zero_missed_careers, "examples": examples}


def span_totals(d, pid):
    w = l = ow = ol = sw = sl = 0
    for st in d.stints(pid):
        w, l, ow, ol = w + st["w"], l + st["l"], ow + st["ow"], ol + st["ol"]
        sw, sl = sw + st.get("sw", 0), sl + st.get("sl", 0)
    return w, l, ow, ol, sw, sl


def jordan(d):
    pid = next(k for k, v in d.ids.items() if v["slug"] == "michael-jordan")
    sm = A.summary(d, pid)
    w, l, ow, ol, sw, sl = span_totals(d, pid)
    rows = []
    for sy, (main, end, lst) in sorted(d.season_main(pid).items()):
        t = d.team(main["f"], sy)
        rows.append({"season": sy, "team": t["name"], "g": main["g"], "with": f'{main["w"]}-{main["l"]}',
                     "without": f'{main["ow"]}-{main["ol"]}', "span_without": f'{main.get("sw", 0)}-{main.get("sl", 0)}',
                     "first": main["first"], "last": main["last"], "window": main["win"],
                     "team_rec": f'{t["w"]}-{t["l"]}', "winning": t["w"] > t["l"], "po": t["po"], "rnk": t["rnk"]})
    out["jordan"] = {
        "with": [w, l], "games": w + l, "pct": w / (w + l), "w_minus_l": w - l,
        "without": [ow, ol], "without_games": ow + ol, "without_pct": ow / (ow + ol),
        "gap_pp": 100 * (w / (w + l) - ow / (ow + ol)),
        "span_without": [sw, sl], "span_without_pct": (sw / (sw + sl)) if sw + sl else None,
        "span_gap_pp": 100 * (w / (w + l) - sw / (sw + sl)) if sw + sl else None,
        "winning": sm["winning"], "trips": sm["trips"], "titles": sm["titles"], "avg_rnk": sm["rnk"],
        "seasons": rows}


def opponents(d, logs):
    """Every player's games grouped by opponent franchise must add up to his career record."""
    by = defaultdict(lambda: [0, 0])
    opp = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for sy, lg in logs.items():
        for row in lg["games"]:
            if row[0][2] != "2":
                continue
            hp, ap = lg["app"].get(row[0], [[], []])
            for side, pids in ((0, hp), (1, ap)):
                fr, of = (row[2], row[3]) if side == 0 else (row[3], row[2])
                ok = won(row, fr)
                for pid in pids:
                    opp[str(pid)][of][0 if ok else 1] += 1
    bad = []
    for pid in d.players:
        w = sum(st["w"] for st in d.stints(pid))
        l = sum(st["l"] for st in d.stints(pid))
        ow = sum(v[0] for v in opp[pid].values())
        ol = sum(v[1] for v in opp[pid].values())
        if (w, l) != (ow, ol):
            bad.append({"player": d.ids[pid]["name"], "career": f"{w}-{l}", "by_opponent": f"{ow}-{ol}"})
    out["opponents"] = {"players_checked": len(d.players), "not_adding_up": bad[:50], "n_bad": len(bad)}


def shortened(d):
    rows = []
    for sy in (1999, 2012, 2020, 2021):
        ts = [t for t in d.teams.values() if t["s"] == sy]
        gp = sorted({t["w"] + t["l"] for t in ts})
        rows.append({"season": sy, "teams": len(ts), "games_per_team": gp})
    out["shortened"] = rows


def coverage(d):
    cur = load_json(os.path.join(DATA, "current.json"), {})
    st0 = load_json(os.path.join(DATA, "step0.json"), {})
    out["coverage"] = {
        "career_seasons": [season_label(FIRST_SEASON), season_label(LAST_COMPLETE)],
        "current_season": season_label(CURRENT_SEASON),
        "current_through": cur.get("through"), "current_source": cur.get("source"),
        "current_games": cur.get("games"),
        "ramiro_first": season_label(RAMIRO_FIRST),
        "minutes_never": st0.get("minutes_groups", {}).get("never"),
        "ramiro_gaps": {k: v for k, v in st0.get("ramiro_coverage", {}).items()
                        if v["regular"][0] != v["regular"][1] or v["playoffs"][0] != v["playoffs"][1]},
    }


def standings_csv_faults():
    path = os.path.join(DATA, "team_standings.csv")
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    head = rows[0]
    bad = []
    for r in rows[1:]:
        for i, v in enumerate(r):
            if v and i < len(head) and head[i] and v == head[i]:
                bad.append({"row": r[0], "column": head[i]})
    brk = [r[0] for r in rows[1:] if r[2] in STANDINGS_CODE_FIX]
    out["standings_csv"] = {"header_text_in_data": bad, "brk_rows": brk}


def write_report():
    a = out
    j = a["jordan"]
    w = a["windows"]
    lines = []
    P = lines.append
    P("# Team Success data audit\n")
    P("Run `python scripts/audit.py` (numbers saved in `data/audit.json`, re-checked by `tests/test_audit.py`). "
      "Every fault below lists the rows it touches, the cause and the fix.\n")
    P("## Jordan regression check\n")
    P("| Measure | Expected | Got |\n|---|---|---|")
    P(f"| With him | 706–366, 1,072 games, 65.9%, W − L +340 | {j['with'][0]}–{j['with'][1]}, {j['games']:,} games, "
      f"{100 * j['pct']:.1f}%, W − L {j['w_minus_l']:+d} |")
    P(f"| Without him (published window proxy) | 63–95 in 158 games, 39.9% | {j['without'][0]}–{j['without'][1]} in "
      f"{j['without_games']} games, {100 * j['without_pct']:.1f}% |")
    P(f"| Gap (unrounded rates) | +26.0 pp | {j['gap_pp']:+.1f} pp ({j['gap_pp']:+.4f}) |")
    P(f"| Winning seasons | 10 | {j['winning']} |\n| Playoff trips | 13 | {j['trips']} |\n| Titles | 6 | {j['titles']} |")
    P(f"| Average final finish | 7.4 | {j['avg_rnk']:.1f} (mean of {len(j['seasons'])} seasons' RNK) |")
    sw = j["span_without"]
    P(f"| Without him, between his first and last game (appearance span) | n/a | {sw[0]}–{sw[1]} in {sum(sw)} games, "
      f"{100 * j['span_without_pct']:.1f}%, gap {j['span_gap_pp']:+.1f} pp |\n")
    P("Season by season (the rows behind every number above):\n")
    P("| Season | Team | His games | With | Without (window) | Without (span) | First / last game | Team W–L | Playoffs | RNK |")
    P("|---|---|---|---|---|---|---|---|---|---|")
    for r in j["seasons"]:
        P(f"| {season_label(r['season'])} | {r['team']} | {r['g']} | {r['with'].replace('-', '–')} | "
          f"{r['without'].replace('-', '–')} | {r['span_without'].replace('-', '–')} | {r['first']} / {r['last']} | "
          f"{r['team_rec'].replace('-', '–')} | {r['po'] or 'missed'} | {r['rnk']} |")
    P("")
    P("- **Why Chicago's 34–31 before his March 1995 return counts.** Under the published proxy a player with one team "
      "in a season has a window of the whole season. Jordan played only for Chicago in 1994-95, so every Bulls game "
      "he did not play (the 65 before his first game on 1995-03-19) counts as \"without him\". The appearance-span "
      "definition starts at his first game, so those 65 games drop out.")
    P("- **Why 1993-94 is outside the proxy.** He has no appearance for any team that season (he was retired), so he "
      "has no team-season and no window. The proxy only opens a window for a team-season he appeared in.")
    P("- **Winning seasons 10**: team W–L above .500 in 1987-88 to 1992-93 and 1994-95 to 1997-98 (Chicago 38–44 in "
      "1984-85, 30–52 in 1985-86, 40–42 in 1986-87 and Washington 37–45 twice are not). **Playoff trips 13**: every "
      "Chicago season. **Titles 6**: 1990-91 to 1992-93, 1995-96 to 1997-98. **Average finish 7.4** = (14 + 16 + 15 + 6 "
      "+ 4 + 3 + 1 + 1 + 1 + 8 + 1 + 1 + 1 + 19 + 20) / 15. The leaderboards call the same `analysis.summary()` rules.\n")
    P("## How with/without works now\n")
    P("Two definitions, computed for every player-team-season, both reproducible from `data/gamelog/`:\n")
    P("1. **Team-season window (the published proxy, the headline number).** One team all season: the whole "
      "season. Traded: the first team's window ends the day before his first game for the next team; the next "
      "window starts the day after his last game for the previous team.")
    P("2. **Appearance span (dated by his own games).** The team's games he missed between his first and last game "
      "for that team, per stint. No game before he arrived or after he left can count, and no game counts for two "
      "teams. It can miss real absences at the start or end of a stint (an injury before his first game).\n")
    P("No free, allowed source has historical signing, waiver or trade dates, so neither definition uses them. Pages "
      "show the proxy, with the span figure and its definition next to it.\n")
    P("## Faults and limits found\n")
    n = 1

    def F(title, rows, cause, fix):
        nonlocal n
        P(f"### {n}. {title}\n")
        P(f"- **Rows affected:** {rows}")
        P(f"- **Cause:** {cause}")
        P(f"- **Fix:** {fix}\n")
        n += 1

    st0 = load_json(os.path.join(DATA, "step0.json"), {})
    drops = st0.get("impossible_rows_dropped", [])
    ids = load_json(os.path.join(DATA, "player_ids.json"), {})
    grp = Counter()
    for x in drops:
        sy = int(x["date"][:4]) + (1 if int(x["date"][5:7]) >= 8 else 0)
        grp[(ids.get(str(x["personId"]), {}).get("name", x["personId"]), sy, x["team"])] += 1
    F("Appearances a player could not have made (fixed)",
      f"{len(drops)} box-score rows in {len(grp)} player-team-seasons. Largest: " + "; ".join(
          f"{n_} {season_label(sy)} {f} ({c_} rows)" for (n_, sy, f), c_ in grp.most_common(12)) +
      ". Every row is listed on How we count and in data/step0.json (`impossible_rows_dropped`).",
      "Source box scores file one player's line under another player's ID or on the wrong team. The signs: "
      "games for team B between two games he played for team A with no team-A game missed in between; "
      "appearances for two teams on one day (13 were the same game, both sides); stints made only of 0-minute "
      "rows in games where minutes were kept. Before the fix, 44 players' games by opponent did not add up to "
      "their career record, and windows broke into dozens of one-day pieces (George Mikan 1950-51 had 22).",
      "`drop_impossible()` in build_history.py drops the 0-minute rows among the flagged ones, or, in seasons "
      "without minutes, the rows of the team he played fewer games for. After the fix every player's opponent rows "
      "add up and no player is on two teams in one day. Rows confirmed by the lineup data (1996-97 on) are never "
      "treated as 0-minute.")
    ex = w["examples"]

    def exs(k):
        return "; ".join(f"{x['player']} {season_label(x['season'])} {x['team']} ({x['games']} games)" for x in ex[k][:5])

    F("Games before a one-team player's first appearance count as \"without him\"",
      f"{w['rows_before']:,} player-team-seasons, {w['one_team_games_before_first_appearance']:,} team games. Largest: {exs('before_first')}.",
      "The proxy window is the whole season for a one-team player. A late signing, a rookie called up in "
      "midseason or a return from injury all look the same in box scores.",
      "Kept as the labeled proxy (it is the published method). Every row now also carries the appearance-span "
      "record (`sw`, `sl`), which excludes these games, and the page shows both with their definitions.")
    F("Games after a one-team player's last appearance count as \"without him\" (cuts, season-ending injuries)",
      f"{w['rows_after']:,} player-team-seasons, {w['one_team_games_after_last_appearance']:,} team games. Largest: {exs('after_last')}.",
      "The window runs to season's end; box scores cannot show the day he was waived.",
      "Same as above: proxy kept and labeled, appearance span added.")
    F("Days between two teams count for both teams",
      f"{w['rows_traded']:,} traded player-team-seasons, {w['traded_games_between_teams']:,} team games. Largest: {exs('between_teams')}.",
      "The first window ends the day before his first game for the new team and the new window starts the day "
      "after his last game for the old one, so the days in between are inside both.",
      "Appearance span never overlaps. Proxy kept, labeled.")
    F("Players with no missed games",
      f"{w['zero_missed_careers']:,} careers have 0 games without him under the proxy.",
      "One-team seasons where he played every game.",
      "Empty samples show N/A, never 0.0% or a gap; the gap leaderboards require a minimum on both sides.")
    rk = a["rnk"]
    F("RNK ordering",
      f"{len(rk['mismatches'])} team-seasons where the CSV's RNK differs from champion, runner-up, then playoff round, "
      f"then win % (ties share a rank). {rk['tied_rows']} rows share a rank with another team." +
      ("" if not rk["mismatches"] else " Rows: " + "; ".join(
          f"{season_label(m['season'])} {m['name']} ({m['po'] or 'missed'}, {m['rec']}): CSV {m['csv']}, rule {m['rule']}"
          for m in rk["mismatches"][:20])),
      "RNK comes from the owner's sheet (RNK PTS = round points + win %).",
      "We display the CSV's RNK unchanged (same source on player pages and season boards); the audit re-derives it "
      "every run. League size per season goes next to every rank: " +
      ", ".join(f"{season_label(sy)} {n_}" for sy, n_ in sorted(rk["league_sizes"].items())
                if sy in (1947, 1950, 1951, 1955, 1962, 1967, 1968, 1977, 1989, 1990, 1996, 2005)) + ", 30 since 2004-05.")
    po = a["playoffs"]
    F("Playoff result vs playoff games",
      f"{len(po['standings_vs_games'])} team-seasons disagree" + (": " + "; ".join(
          f"{x['team']} {x['name']} standings '{x['po']}', games {', '.join(x['series']) or 'none'}"
          for x in po["standings_vs_games"][:12]) if po["standings_vs_games"] else "") + ".",
      "Play-in and tiebreaker games sit in the playoff game type in some seasons.",
      "Team result always comes from the standings' Playoffs column; series lists come from the games and are "
      "shown as games, not as a round.")
    F("Playoff \"series\" that are not best-of series",
      f"{len(po['non_series_pairs'])} team pairs" + (": " + "; ".join(
          f"{season_label(x['season'])} {x['teams']} {x['games']}" for x in po["non_series_pairs"][:12]) if po["non_series_pairs"] else "") + ".",
      "Early playoff formats had round-robin groups and tiebreakers; we group playoff games by opponent.",
      "These show as games played against that opponent, not as a series won or lost; series records on the "
      "opponent table count only pairs decided by a series.")
    g = a["games"]
    F("Team game counts vs standings",
      f"{len(g['team_game_counts_off'])} team-seasons: " + "; ".join(
          f"{x['name']} {x['team'].split()[1]} {x['games']} vs {x['standings']}" for x in g["team_game_counts_off"]) + ".",
      "One 1953-54 Milwaukee-Baltimore game is missing from the box scores.",
      "Team records use the standings; with/without uses the games we have (the two can differ by that one game).")
    raw = a.get("raw") or {}
    F("Duplicate games and rows",
      f"Duplicate game IDs in the raw files: {raw.get('duplicate_game_ids') or 'none'}. Duplicate box-score rows: "
      f"{raw.get('duplicate_box_rows') or 'none'}. Same matchup twice on one day after clean-up: "
      f"{len(g['same_matchup_same_day'])}. A player on both sides of one game: {len(g['player_on_both_sides'])}.",
      "n/a", "Nothing to fix." if not (raw.get("duplicate_game_ids") or raw.get("duplicate_box_rows")
                                       or g["same_matchup_same_day"] or g["player_on_both_sides"]) else "See rows.")
    op = a["opponents"]
    F("Opponent rows vs career totals",
      f"{op['n_bad']} of {op['players_checked']:,} players' opponent rows do not add up to the career record.",
      "Checks every regular-season game he appeared in, grouped by opponent franchise.",
      "Nothing to fix." if not op["n_bad"] else "See data/audit.json.")
    sc = a["standings_csv"]
    F("Standings file quirks",
      f"Header text inside a data cell: {', '.join(x['row'] + ' (' + x['column'] + ')' for x in sc['header_text_in_data']) or 'none'}. "
      f"BRK instead of BKN: {', '.join(sc['brk_rows'])}.",
      "Hand-edited spreadsheet.",
      "We never read the shifted cells (only Win, Losses, Conference, Division, positions, Playoffs, RNK). BRK is read as BKN.")
    P("## Shortened seasons and early leagues\n")
    for r in a["shortened"]:
        P(f"- {season_label(r['season'])}: {r['teams']} teams, games per team {', '.join(map(str, r['games_per_team']))}. "
          "Win % and RNK use each team's own games, so unequal schedules (2019-20) compare by win %.")
    P(f"- League size by season ranges from {min(rk['league_sizes'].values())} to {max(rk['league_sizes'].values())}. "
      "Final finish is shown as \"#8 of 30\" with that season's size, and the league-size-adjusted view uses "
      "(rank − 1) / (teams − 1), 0 = champion, 1 = last.\n")
    c = a["coverage"]
    P("## Coverage, and the Nov. 16 question\n")
    P(f"- Career numbers: completed seasons, {c['career_seasons'][0]} to {c['career_seasons'][1]} (box scores + standings).")
    P(f"- Current season: {c['current_season']}, {c['current_games']} games through {c['current_through']}, "
      f"from {c['current_source']}. Shown in its own block and on the daily boards, never added to career totals.")
    P(f"- Why the board said Nov. 16 while Jordan's page said 2025-26: both were right, they describe different scopes. "
      "Jordan's page states the career scope (completed seasons only; 2026-27 is not in any career total until it "
      "ends). The board is the current season, and its date is the last game in Ramiro's 2026-27 files at the "
      "last nightly run (games of a US evening land in those files the following day). The copy now names both "
      "scopes on every page: \"Career: 1946-47 to 2025-26 regular seasons. 2026-27: games through <date>, shown "
      "separately.\"")
    P(f"- On/off, starts and close games: {c['ramiro_first']} on. Minutes not kept in "
      f"{', '.join(season_label(y) for y in (c['minutes_never'] or []))}.")
    if c["ramiro_gaps"]:
        P("- Ramiro gaps: " + "; ".join(f"{season_label(int(k))} regular {v['regular'][0]}/{v['regular'][1]}, playoffs "
                                         f"{v['playoffs'][0]}/{v['playoffs'][1]}" for k, v in c["ramiro_gaps"].items()))
    P("- Play-in games (game type 5) are in neither the regular season nor the playoffs" +
      (f" ({', '.join(f'{season_label(int(k))}: {v}' for k, v in raw.get('play_in_games_type5', {}).items())})." if raw else "."))
    with open(os.path.join(ROOT, "docs", "audit-report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    d = A.Data()
    logs = gamelogs()
    check_rnk(d)
    check_playoffs(d, logs)
    check_games(d, logs)
    check_raw_sources()
    windows(d, logs)
    jordan(d)
    opponents(d, logs)
    shortened(d)
    coverage(d)
    standings_csv_faults()
    dump_json(os.path.join(DATA, "audit.json"), out, compact=False)
    write_report()
    print("audit written")


if __name__ == "__main__":
    main()

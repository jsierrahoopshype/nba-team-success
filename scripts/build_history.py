# (c) 2026 HoopsMatic. All rights reserved.
# Team Success data pipeline. Fingerprint: hm-ts-7f3a91c2-history
"""Full rebuild of the Team Success data from the public sources.

Reads (see scripts/fetch_sources.sh):
  _src/nba-boxscores/data/<season>/games.ndjson + boxscores.ndjson   every game, 1947-2026
  _src/nba-player-data/RS-Stats.csv, Awards.csv                     names, awards
  _src/ramiro/*.parquet                                              lineups/possessions, 1997+
  data/team_standings.csv                                           records, RNK, playoff finish

Writes (all committed):
  data/franchise_map.json   (era code, season) -> franchise + that season's real name
  data/player_ids.json      personId -> stable slug + display name
  data/team_seasons.json    one row per franchise-season (record, finish, RNK, playoff series)
  data/players.json         one row per player-team-season + career extras (duos, awards)
  data/step0.json           numbers behind docs/step0-report.md and tests/

Run: python scripts/build_history.py            (about 3-5 minutes)
"""
import csv
import datetime as dt
import difflib
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (DATA, ERAS, FIRST_SEASON, LAST_COMPLETE, RAMIRO_FIRST, SRC,  # noqa: E402
                    NAME_ALIASES, STANDINGS_CODE_FIX, base_name, dump_json, era_lookup, norm_name,
                    slugify)

BOX = os.path.join(SRC, "nba-boxscores", "data")
PDATA = os.path.join(SRC, "nba-player-data")
CMAP = os.path.join(SRC, "nba-career-map")
HEAD = os.path.join(SRC, "nba-headshots")
TEAMMATES = os.path.join(SRC, "hh-teammates")
RAMIRO = os.path.join(SRC, "ramiro")

STATS = ("fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "reb", "ast",
         "stl", "blk", "tov", "pf", "pts")
# Tiebreaker games stored as regular-season games in nba-boxscores (official W-L excludes them).
TIEBREAKERS = {
    "0024700193", "0024700194",   # 1948 Chicago Stags vs Washington, vs Baltimore
    "0024900564", "0024900563",   # 1950 Fort Wayne vs Chicago, Minneapolis vs Rochester
    "0025500289", "0025500290",   # 1956 New York vs Syracuse, Minneapolis vs St. Louis
    "0025600289", "0025600290",   # 1957 St. Louis vs Fort Wayne, vs Minneapolis
}

# Count Ramiro on-court cameos (0 box-score minutes, no stats) as appearances. See step0 report.
COUNT_RAMIRO_CAMEOS = True
ROUND_ORDER = {"": 0, "Play-In": 0.5, "First Round": 1, "Conf Semis": 2,
               "Conf Finalist": 3, "Finalist": 4, "Champion": 5}

step0 = {}
ZERO_MIN = set()     # (pid, gid, franchise): 0-minute rows in games where minutes were kept
AWARDS_BY_YEAR = {}  # (RS-Stats name, season) -> [awards with a Teammates Score weight]


def log(*a):
    print(*a, flush=True)


def d2(s):
    return dt.date.fromisoformat(s)


# ---------------------------------------------------------------------------
# 1. Standings
# ---------------------------------------------------------------------------
def ordinal(n):
    n = int(n)
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def load_standings():
    path = os.path.join(DATA, "team_standings.csv")
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    head = rows[0]
    ix = {h: i for i, h in enumerate(head) if h}
    out = {}
    fmt = Counter()
    rnk_rows = []
    for r in rows[1:]:
        code = STANDINGS_CODE_FIX.get(r[ix["Team ABR"]], r[ix["Team ABR"]])
        sy = int(r[ix["SEASON"]])
        w, l = int(r[ix["Win"]]), int(r[ix["Losses"]])
        raw = r[ix["W-L%"]]
        fmt["0.xxx" if raw.startswith("0.") or raw.startswith("1.") else "xxx"] += 1
        rec = {
            "f": code, "s": sy, "w": w, "l": l,
            "conf": r[ix["Conference"]].replace(" Div", ""),
            "div": r[ix["Division"]],
            "confPos": r[ix["Conf Pos"]], "divPos": r[ix["Div Pos"]],
            "po": r[ix["Playoffs"]],
            "rnk": int(r[ix["RNK"]]) if r[ix["RNK"]].strip() else None,
            "rnkPts": r[ix["RNK PTS"]],
        }
        out[(code, sy)] = rec
        if sy in (2024, 1975):
            rnk_rows.append((sy, code, w, l, rec["po"], rec["rnk"], rec["rnkPts"]))
    # 2025-26 rows have no conference/division finish: compute from W-L (ties share a place).
    computed = 0
    for key in ("conf", "div"):
        groups = defaultdict(list)
        for rec in out.values():
            groups[(rec["s"], rec[key])].append(rec)
        for (sy, g), recs in groups.items():
            for rec in recs:
                if rec[key + "Pos"]:
                    continue
                p = rec["w"] / (rec["w"] + rec["l"])
                better = sum(1 for o in recs if o["w"] / (o["w"] + o["l"]) > p)
                rec[key + "Pos"] = ordinal(better + 1)
                rec[key + "PosComputed"] = True
                computed += 1
    step0["standings"] = {
        "rows": len(out), "wl_pct_formats": dict(fmt), "positions_computed": computed,
        "rnk_samples": sorted(rnk_rows, key=lambda x: (x[0], x[5] or 99))[:12],
        "brk_fixed": sum(1 for r in rows[1:] if r[ix["Team ABR"]] == "BRK"),
        "atl_2024_trailing": rows[1][-3:] if rows[1][0].startswith("ATL 2024") else None,
    }
    return out


# ---------------------------------------------------------------------------
# 2. Games + box scores
# ---------------------------------------------------------------------------
def load_games_and_box(seasons):
    """games: gid -> dict; app: list of appearance tuples."""
    games = {}
    unmapped = Counter()
    null_fixed = 0
    neutral = []
    rows_out = []        # (pid, gid, franchise, appeared, min, pts)
    names = defaultdict(Counter)
    minutes_mode = {}
    dnp_like_recorded = Counter()
    for sy in seasons:
        gpath = os.path.join(BOX, str(sy), "games.ndjson")
        bpath = os.path.join(BOX, str(sy), "boxscores.ndjson")
        if not os.path.exists(gpath):
            continue
        sg = {}
        with open(gpath) as fh:
            for line in fh:
                g = json.loads(line)
                sg[g["gameId"]] = g
        box = []
        with open(bpath) as fh:
            for line in fh:
                box.append(json.loads(line))
        # Fill a missing home/away code from the box score rows of that game.
        # Neutral-site games (NBA Cup semifinals, Mexico City, Paris, London, Berlin) come with
        # home=null and homeScore=null, both teams flagged homeGame=0. The missing team is the
        # other team in the box score and its score is the sum of its players' points.
        teams_in = defaultdict(set)
        tpts = Counter()
        for b in box:
            teams_in[b["gameId"]].add(b["team"])
            tpts[(b["gameId"], b["team"])] += b.get("pts") or 0
        for gid, g in sg.items():
            for k, sk, other in (("home", "homeScore", "away"), ("away", "awayScore", "home")):
                if not g.get(k) and g.get(other):
                    rest = teams_in[gid] - {g[other]}
                    if len(rest) == 1:
                        g[k] = rest.pop()
                        if g.get(sk) is None:
                            g[sk] = tpts[(gid, g[k])]
                        g["neutralFix"] = True
                        null_fixed += 1
                        neutral.append({"gameId": gid, "date": g["date"], "teams":
                                        f"{g['away']} {g['awayScore']} - {g['home']} {g['homeScore']}"})
        # minutes recorded per team-game?
        rec = defaultdict(bool)
        for b in box:
            if (b.get("min") or 0) > 0:
                rec[(b["gameId"], b["team"])] = True
        n_rec = sum(1 for v in rec.values() if v)
        team_games = len({(b["gameId"], b["team"]) for b in box})
        minutes_mode[sy] = (n_rec, team_games)
        for gid, g in sg.items():
            t = gid[2]
            hm = era_lookup(g["home"], sy) if g.get("home") else None
            aw = era_lookup(g["away"], sy) if g.get("away") else None
            if not hm:
                unmapped[(g.get("home"), sy)] += 1
            if not aw:
                unmapped[(g.get("away"), sy)] += 1
            if not (hm and aw) or g.get("homeScore") is None or g.get("awayScore") is None:
                continue
            games[gid] = {"gid": gid, "sy": sy, "t": t, "date": g["date"],
                          "h": hm[0], "a": aw[0], "hc": g["home"], "ac": g["away"],
                          "hs": g["homeScore"], "as": g["awayScore"]}
        for b in box:
            gid = b["gameId"]
            if gid not in games:
                continue
            fr = era_lookup(b["team"], sy)
            if not fr:
                unmapped[(b["team"], sy)] += 1
                continue
            m = b.get("min") or 0
            anystat = any((b.get(k) or 0) > 0 for k in STATS)
            if rec[(gid, b["team"])]:
                appeared = m > 0 or anystat
                if not appeared:
                    dnp_like_recorded[sy] += 1
            else:
                appeared = True
            pid = b["personId"]
            names[pid][b["name"]] += 1
            if rec[(gid, b["team"])] and m == 0:
                ZERO_MIN.add((pid, gid, fr[0]))
            rows_out.append((pid, gid, fr[0], appeared, m, b.get("pts") or 0))
    step0["null_codes_fixed"] = null_fixed
    step0["neutral_site_fixed"] = neutral
    step0["unmapped_codes"] = sorted([f"{c} {s}" for (c, s) in unmapped])
    groups = {"never": [], "partial": [], "always": []}
    for sy, (n_rec, tg) in sorted(minutes_mode.items()):
        share = n_rec / tg if tg else 0
        k = "never" if share < 0.01 else ("always" if share > 0.98 else "partial")
        groups[k].append(sy)
    step0["minutes_groups"] = groups
    step0["minutes_share"] = {sy: round(a / b, 3) for sy, (a, b) in minutes_mode.items() if b}
    step0["dnp_rows_excluded"] = dict(dnp_like_recorded)
    return games, rows_out, names


def drop_impossible(rows, games, oncourt=frozenset()):
    """Remove appearances a player could not have made (audit 2026-11).

    Some source box scores file a player's ID under a team he was not on that day (another
    player's line under his ID, or a row on the wrong side). The sign: his games for team B sit
    between two games of team A that he played, with no team-A game missed in between, so he
    could not have left and come back. Among the rows involved we drop the 0-minute rows from
    games where minutes were kept; if there are none (seasons without minutes), the rows of
    the team he played fewer games for that season. Repeats until no impossible run is left.
    Rows the lineup data puts on the floor (oncourt, 1996-97 on) are never treated as 0-minute.
    Returns (clean rows, dropped list).
    """
    zero_min = {k for k in ZERO_MIN if (k[0], k[1]) not in oncourt}
    team_games = defaultdict(list)
    for g in games.values():
        if g["t"] == "2":
            team_games[(g["h"], g["sy"])].append(g["date"])
            team_games[(g["a"], g["sy"])].append(g["date"])
    seq = defaultdict(list)
    for i, (pid, gid, fr, appeared, m, p) in enumerate(rows):
        if appeared and gid[2] == "2":
            seq[(pid, games[gid]["sy"])].append((games[gid]["date"], gid, fr, i))
    drop = set()
    for (pid, sy), lst in seq.items():
        if len({x[2] for x in lst}) < 2:
            continue
        alive = sorted(lst)
        for _ in range(20):
            cnt = Counter(x[2] for x in alive)
            runs = []
            for x in alive:
                if runs and runs[-1][0] == x[2]:
                    runs[-1][1].append(x)
                else:
                    runs.append([x[2], [x]])
            bad = []
            for k in range(1, len(runs) - 1):
                a = runs[k - 1][0]
                if runs[k + 1][0] != a:
                    continue
                lo, hi = runs[k - 1][1][-1][0], runs[k + 1][1][0][0]
                if not any(lo < dd < hi for dd in team_games[(a, sy)]):
                    bad += runs[k][1] + [runs[k - 1][1][-1], runs[k + 1][1][0]]
                elif all((pid, x[1], x[2]) in zero_min for x in runs[k][1]):
                    # a stint made only of 0-minute rows, in games where minutes were kept
                    bad += runs[k][1]
            # same game both sides, or two teams on the same day
            by_day = defaultdict(list)
            for x in alive:
                by_day[x[0]].append(x)
            for xs in by_day.values():
                if len({x[2] for x in xs}) > 1:
                    bad += xs
            if not bad:
                break
            zero = [x for x in bad if (pid, x[1], x[2]) in zero_min]
            if zero:
                kill = set(zero)
            else:
                small = min({x[2] for x in bad}, key=lambda f: (cnt[f], f))
                kill = {x for x in bad if x[2] == small}
            drop |= {x[3] for x in kill}
            alive = [x for x in alive if x not in kill]
    dropped = [{"personId": rows[i][0], "gameId": rows[i][1], "team": rows[i][2],
                "date": games[rows[i][1]]["date"]} for i in sorted(drop)]
    return [r for i, r in enumerate(rows) if i not in drop], dropped


def game_counts_check(games, standings):
    rs = Counter()
    per_team = Counter()
    for g in games.values():
        if g["t"] == "2":
            rs[g["sy"]] += 1
            per_team[(g["h"], g["sy"])] += 1
            per_team[(g["a"], g["sy"])] += 1
    wins = Counter()
    for (f, sy), r in standings.items():
        wins[sy] += r["w"]
    seasons = sorted(set(wins))
    diffs = []
    for sy in seasons:
        if rs[sy] != wins[sy]:
            teams = []
            for (f, s), r in standings.items():
                if s == sy and per_team[(f, sy)] != r["w"] + r["l"]:
                    teams.append({"team": f, "boxscores": per_team[(f, sy)],
                                  "standings": r["w"] + r["l"]})
            diffs.append({"season": sy, "boxscores": rs[sy], "standings_wins": wins[sy],
                          "diff": rs[sy] - wins[sy], "teams": sorted(teams, key=lambda x: x["team"])})
    step0["game_counts"] = {"seasons": len(seasons),
                            "match": len(seasons) - len(diffs), "diffs": diffs}
    # Team-season pairs in games but not in standings and vice versa
    in_games = set(per_team)
    in_stand = {k for k in standings if k[1] <= LAST_COMPLETE}
    step0["teamseason_only_in_games"] = sorted(f"{f} {s}" for f, s in in_games - in_stand)
    step0["teamseason_only_in_standings"] = sorted(f"{f} {s}" for f, s in in_stand - in_games)


# ---------------------------------------------------------------------------
# 3. Playoff series from playoff games
# ---------------------------------------------------------------------------
def playoff_series(games):
    """(franchise, season) -> list of series dicts in date order."""
    by = defaultdict(lambda: defaultdict(list))
    for g in games.values():
        if g["t"] != "4":
            continue
        pair = tuple(sorted((g["h"], g["a"])))
        by[g["sy"]][pair].append(g)
    out = defaultdict(list)
    for sy, pairs in by.items():
        for pair, gl in pairs.items():
            gl.sort(key=lambda x: (x["date"], x["gid"]))
            wins = Counter()
            for g in gl:
                wins[g["h"] if g["hs"] > g["as"] else g["a"]] += 1
            a, b = pair
            for me, opp in ((a, b), (b, a)):
                out[(me, sy)].append({
                    "opp": opp, "oppName": None, "w": wins[me], "l": wins[opp],
                    "start": gl[0]["date"], "end": gl[-1]["date"],
                    "won": wins[me] > wins[opp]})
    for k in out:
        out[k].sort(key=lambda x: x["start"])
    return out


# ---------------------------------------------------------------------------
# 4. Identity: box score personId -> RS-Stats name -> slug
# ---------------------------------------------------------------------------
def load_rs_stats():
    rs = defaultdict(list)   # (sy, franchise) -> [(PLAYER, base, norm, GP)]
    with open(os.path.join(PDATA, "RS-Stats.csv"), encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if not r["TEAM"] or not r["YEAR"].strip().isdigit():
                continue
            p = r["PLAYER"].strip()
            gp = int(float(r["GP"] or 0))
            rs[(int(r["YEAR"]), r["TEAM"])].append((p, base_name(p), norm_name(p), gp))
    return rs


def match_identities(rows, names, rs):
    """Return pid -> RS name (or None), plus match stats."""
    # player games per (pid, sy, franchise)
    pts = defaultdict(int)
    for pid, gid, fr, appeared, m, p in rows:
        if appeared and gid[2] == "2":
            pts[(pid, season_of_gid(gid), fr)] += 1
    votes = defaultdict(Counter)
    seasons_unmatched = []
    total = matched = 0
    # RS names that a box-score player on the same team-season matches exactly are taken: the
    # loose passes below may not hand them to someone else (Curtis Jones is not Spencer Jones).
    taken = defaultdict(set)
    for (pid, sy, fr) in pts:
        bx = NAME_ALIASES.get(names[pid].most_common(1)[0][0], names[pid].most_common(1)[0][0])
        for c in rs.get((sy, fr), []):
            if c[1] == base_name(bx):
                taken[(sy, fr)].add(c[0])
    for (pid, sy, fr), g in pts.items():
        bx = names[pid].most_common(1)[0][0]
        bx = NAME_ALIASES.get(bx, bx)
        all_cands = rs.get((sy, fr), [])
        total += 1
        nb, bb = norm_name(bx), base_name(bx)
        hit = [c for c in all_cands if c[2] == nb]
        if len(hit) != 1:
            hit = [c for c in all_cands if c[1] == bb]
        cands = [c for c in all_cands if c[0] not in taken[(sy, fr)]]
        if len(hit) != 1:
            # same last name + first initial
            parts = bb.split()
            if parts:
                hit = [c for c in cands if c[1].split() and c[1].split()[-1] == parts[-1]
                       and c[1][:1] == bb[:1]]
        if len(hit) != 1:
            # nickname in RS-Stats (Johnny Kerr = "Red Kerr"): the only same-last-name player
            parts = bb.split()
            if parts:
                hit = [c for c in cands if c[1].split() and c[1].split()[-1] == parts[-1]]
        if len(hit) != 1:
            scored = sorted(((difflib.SequenceMatcher(None, bb, c[1]).ratio(), c) for c in cands),
                            key=lambda x: -x[0])
            hit = [scored[0][1]] if scored and scored[0][0] >= 0.85 and (
                len(scored) == 1 or scored[1][0] < scored[0][0] - 0.05) else []
        if len(hit) == 1:
            matched += 1
            votes[pid][hit[0][0]] += g
        else:
            seasons_unmatched.append((pid, bx, sy, fr, g))
    # Player-level fallback for players never matched: same base name anywhere within one
    # season of his seasons (team codes in old RS rows sometimes differ from the box scores).
    by_base = defaultdict(set)
    for (sy, fr), lst in rs.items():
        for c in lst:
            by_base[(sy, c[1])].add(c[0])
    taken_any = set()
    for v in taken.values():
        taken_any |= v
    for pid, bx, sy, fr, g in seasons_unmatched:
        if votes[pid]:
            continue
        cand = set()
        for d in (0, -1, 1):
            cand |= by_base.get((sy + d, base_name(bx)), set())
        if len(cand) == 1:
            votes[pid][cand.pop()] += g
    ident = {pid: (votes[pid].most_common(1)[0][0] if votes[pid] else None) for pid in names}
    return ident, total, matched, seasons_unmatched


def season_of_gid(gid):
    yy = int(gid[3:5])
    return (1900 + yy if yy >= 46 else 2000 + yy) + 1


# ---------------------------------------------------------------------------
# 5. Awards (Teammates Score weights)
# ---------------------------------------------------------------------------
def load_awards():
    tm = json.load(open(os.path.join(TEAMMATES, "data", "teammates.json"), encoding="utf-8"))
    scores = tm["scores"]
    allnba = {"All-NBA First Team", "All-NBA Second Team", "All-NBA Third Team"}
    alldef = {"All-Defensive First Team", "All-Defensive Second Team"}
    by = defaultdict(lambda: defaultdict(list))
    allstar = defaultdict(set)
    with open(os.path.join(PDATA, "Awards.csv"), encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            a = (r.get("AWARD") or "").strip()
            p = (r.get("PLAYER / COACH") or "").strip()
            y = (r.get("YEAR") or "").strip()
            if p and a in scores and y.isdigit():
                by[p][int(y)].append(a)
            if p and a == "All-Star" and y.isdigit():
                allstar[p].add(int(y))
    AWARDS_BY_YEAR.clear()
    for p, years in by.items():
        for y, aws in years.items():
            AWARDS_BY_YEAR[(p, y)] = list(aws)
    out = {}
    for p, years in by.items():
        total = 0.0
        per_year = {}
        counts = Counter()
        for y, aws in years.items():
            s = set(aws)
            for a in aws:
                pts = scores[a]
                # Same rule as Teammates Score: an MVP already covers that season's All-NBA
                # nod, a DPOY already covers that season's All-Defensive nod.
                if "Most Valuable Player" in s and a in allnba:
                    pts = 0
                elif "Defensive Player of the Year" in s and a in alldef:
                    pts = 0
                total += pts
                per_year[y] = per_year.get(y, 0) + pts
                counts[a] += 1
        out[p] = {"score": round(total, 3), "counts": dict(counts),
                  "byYear": {str(y): round(v, 3) for y, v in sorted(per_year.items()) if v},
                  "allstar": sorted(allstar.get(p, ()))}
    return scores, out


# ---------------------------------------------------------------------------
# 6. Ramiro: on/off, starters, close games (1997+)
# ---------------------------------------------------------------------------
ID_RE = re.compile(r"(\d+) ")


def lineup_ids(s):
    return [int(x) for x in ID_RE.findall(s or "")]


def clock_secs(s):
    try:
        m, rest = s.split(":")
        return int(m) * 60 + float(rest)
    except Exception:
        return None


def ramiro_season(sy, kind, games):
    """Per (pid, gid) on-court sums + starters + clutch presence for one season file."""
    import pyarrow.parquet as pq
    lp = os.path.join(RAMIRO, f"lineup_stats_{kind}_{sy}.parquet")
    pp = os.path.join(RAMIRO, f"possessions_{kind}_{sy}.parquet")
    res = {"on": defaultdict(lambda: [0, 0, 0, 0]), "team": defaultdict(lambda: [0, 0, 0, 0]),
           "starters": defaultdict(set), "clutch_games": set(), "clutch_on": set(),
           "side": {}, "games": set(), "oncourt": set(), "pteam": {}}
    if not os.path.exists(lp):
        return None
    t = pq.read_table(lp, columns=["game_id", "location_team", "period", "stint", "team",
                                    "lineup_team", "poss_team", "pts_team", "poss_opp",
                                    "pts_opp", "secs_game_start"]).to_pylist()
    first = {}
    for r in t:
        gid = r["game_id"]
        g = games.get(gid)
        if not g:
            continue
        res["games"].add(gid)
        side = "h" if r["location_team"] == "home" else "a"
        fr = g[side]
        res["side"][(gid, r["team"])] = fr
        vals = (r["pts_team"] or 0, r["poss_team"] or 0, r["pts_opp"] or 0, r["poss_opp"] or 0)
        tt = res["team"][(gid, fr)]
        for i in range(4):
            tt[i] += vals[i]
        for pid in lineup_ids(r["lineup_team"]):
            o = res["on"][(pid, gid)]
            for i in range(4):
                o[i] += vals[i]
            res["oncourt"].add((pid, gid))
            res["pteam"][(pid, gid)] = fr
        key = (gid, fr)
        st = r["secs_game_start"] if r["secs_game_start"] is not None else 1e9
        if key not in first or st < first[key][0]:
            first[key] = (st, r["lineup_team"])
    for (gid, fr), (_, lu) in first.items():
        res["starters"][(gid, fr)] = set(lineup_ids(lu))
    if os.path.exists(pp):
        p = pq.read_table(pp, columns=["game_id", "period", "start_time", "score_team_start",
                                        "score_opp_start", "team_poss", "lineup_team",
                                        "lineup_opp"]).to_pylist()
        for r in p:
            if (r["period"] or 0) < 4:
                continue
            cs = clock_secs(r["start_time"] or "")
            if cs is None or cs > 300:
                continue
            a, b = r["score_team_start"], r["score_opp_start"]
            if a is None or b is None or abs(a - b) > 5:
                continue
            gid = r["game_id"]
            if gid not in games:
                continue
            res["clutch_games"].add(gid)
            for pid in lineup_ids(r["lineup_team"]) + lineup_ids(r["lineup_opp"]):
                res["clutch_on"].add((pid, gid))
    return res


# ---------------------------------------------------------------------------
# 7. Main build
# ---------------------------------------------------------------------------
def team_won(g, fr):
    if g["h"] == fr:
        return g["hs"] > g["as"]
    return g["as"] > g["hs"]


def source_versions():
    import subprocess
    out = {}
    for name in ("nba-boxscores", "nba-player-data", "hh-teammates", "nba-headshots",
                 "nba-career-map"):
        try:
            out[name] = subprocess.run(["git", "-C", os.path.join(SRC, name), "log", "-1",
                                        "--format=%h %cs"], capture_output=True, text=True,
                                       check=True).stdout.strip()
        except Exception:
            out[name] = "unknown"
    return out


def write_gamelogs(games, rows):
    """data/gamelog/<season>.json: every game we count, and who appeared for each side.

    games: [gameId, date, home franchise, away franchise, home era code, away era code,
            home score, away score]; app: {gameId: [[home pids], [away pids]]}. Committed, so the
    audit, the opponent tables and the per-player game files rebuild without the sources.
    """
    by = defaultdict(list)
    app = defaultdict(lambda: ([], []))
    for g in games.values():
        by[g["sy"]].append([g["gid"], g["date"], g["h"], g["a"], g["hc"], g["ac"], g["hs"], g["as"]])
    for pid, gid, fr, appeared, m, p in rows:
        if not appeared:
            continue
        g = games[gid]
        side = 0 if fr == g["h"] else 1
        app[gid][side].append(pid)
    for sy, lst in by.items():
        lst.sort(key=lambda x: (x[1], x[0]))
        doc = {"season": sy, "games": lst,
               "app": {x[0]: [sorted(set(app[x[0]][0])), sorted(set(app[x[0]][1]))] for x in lst}}
        dump_json(os.path.join(DATA, "gamelog", f"{sy}.json"), doc)


def build():
    step0["sources"] = source_versions()
    standings = load_standings()
    seasons = list(range(FIRST_SEASON, LAST_COMPLETE + 1))
    log("loading box scores...")
    games, rows, names = load_games_and_box(seasons)
    log(f"  {len(games)} games, {len(rows)} box rows, {len(names)} players")
    game_counts_check(games, standings)
    # Clean-up after the raw check: tiebreaker games (not part of the official regular-season
    # records) and the cancelled 2013 Celtics-Pacers game (stored 0-0) leave the data.
    dropped = []
    for gid, g in list(games.items()):
        why = None
        if gid in TIEBREAKERS:
            why = "tiebreaker"
        elif g["hs"] == 0 and g["as"] == 0:
            why = "cancelled (0-0)"
        if why:
            dropped.append({"gameId": gid, "date": g["date"], "why": why,
                            "game": f"{g['ac']} {g['as']} @ {g['hc']} {g['hs']}"})
            del games[gid]
    rows = [r for r in rows if r[1] in games]
    step0["games_dropped"] = dropped
    step0["game_counts_raw"] = step0.pop("game_counts")
    game_counts_check(games, standings)
    step0["game_counts_clean"] = step0.pop("game_counts")
    step0["game_counts"] = step0["game_counts_raw"]

    # franchise map
    fmap = {"eras": [{"code": c, "from": a, "to": (None if b == 9999 else b),
                      "franchise": f, "name": n} for c, a, b, f, n in ERAS],
            "by_season": {}}
    used = defaultdict(set)
    for g in games.values():
        used[g["sy"]].add(g["hc"])
        used[g["sy"]].add(g["ac"])
    for sy in sorted(used):
        fmap["by_season"][str(sy)] = {}
        for c in sorted(used[sy]):
            r = era_lookup(c, sy)
            if r:
                fmap["by_season"][str(sy)][c] = {"franchise": r[0], "name": r[1]}
    dump_json(os.path.join(DATA, "franchise_map.json"), fmap, compact=False)

    # Career Map name cross-check
    cm_idx = json.load(open(os.path.join(CMAP, "data", "nba_team_index.json"), encoding="utf-8"))
    cm_names = set(cm_idx["eras"])
    our_names = {n for _, _, _, f, n in ERAS}
    step0["names_not_in_career_map"] = sorted(our_names - cm_names)
    step0["career_map_names_not_used"] = sorted(cm_names - our_names)

    # team seasons
    series = playoff_series(games)
    team_games = defaultdict(list)
    for g in games.values():
        team_games[(g["h"], g["sy"], g["t"])].append(g)
        team_games[(g["a"], g["sy"], g["t"])].append(g)
    for k in team_games:
        team_games[k].sort(key=lambda x: (x["date"], x["gid"]))
    season_bounds = {}
    for sy in seasons:
        ds = [g["date"] for g in games.values() if g["sy"] == sy and g["t"] == "2"]
        if ds:
            season_bounds[sy] = (min(ds), max(ds))

    tseasons = {}
    for (f, sy), r in standings.items():
        if sy > LAST_COMPLETE:
            continue
        p = r["w"] / (r["w"] + r["l"])
        rec = dict(r)
        rec["pct"] = round(p, 4)
        rec.pop("rnkPts", None)
        rec["name"] = None
        # real name that season: from the era table (any era code mapping to f in sy)
        for c, a, b, ff, n in ERAS:
            if ff == f and a <= sy <= b:
                rec["name"] = n
                break
        sr = series.get((f, sy), [])
        rec["series"] = sr
        lost = [s for s in sr if not s["won"]]
        rec["elim"] = lost[-1] if lost and r["po"] != "Champion" else None
        rec["gpBox"] = len(team_games.get((f, sy, "2"), []))
        tseasons[(f, sy)] = rec
    # worst / best record each season (ties all count)
    by_s = defaultdict(list)
    for k, r in tseasons.items():
        by_s[k[1]].append(r)
    for sy, recs in by_s.items():
        lo = min(r["w"] / (r["w"] + r["l"]) for r in recs)
        hi = max(r["w"] / (r["w"] + r["l"]) for r in recs)
        for r in recs:
            p = r["w"] / (r["w"] + r["l"])
            r["worst"] = abs(p - lo) < 1e-9
            r["best"] = abs(p - hi) < 1e-9
    # team W-L from the box-score games vs the standings
    wl = []
    for (f, sy), rec in tseasons.items():
        gl = team_games.get((f, sy, "2"), [])
        w = sum(1 for g in gl if team_won(g, f))
        if (w, len(gl) - w) != (rec["w"], rec["l"]):
            wl.append({"team": f"{f} {sy}", "name": rec["name"], "standings": f"{rec['w']}-{rec['l']}",
                       "boxscores": f"{w}-{len(gl) - w}"})
    step0["wl_mismatch"] = wl
    missing_names = sorted({f"{f} {s}" for (f, s), r in tseasons.items() if not r["name"]})
    step0["teamseasons_without_name"] = missing_names

    # ---------------- Ramiro (1997+), loaded first: its lineups also settle "did he play?"
    log("ramiro...")
    ram = {}
    for sy in seasons:
        if sy < RAMIRO_FIRST:
            continue
        for kind in ("regular", "playoffs"):
            r = ramiro_season(sy, kind, games)
            if r:
                ram[(sy, kind)] = r
    step0["ramiro_seasons"] = sorted({f"{k[0]} {k[1]}" for k in ram})
    rs_n = Counter(g["sy"] for g in games.values() if g["t"] == "2")
    po_n = Counter(g["sy"] for g in games.values() if g["t"] == "4")
    step0["ramiro_coverage"] = {
        str(sy): {"regular": [len(ram[(sy, "regular")]["games"]) if (sy, "regular") in ram else 0,
                              rs_n[sy]],
                  "playoffs": [len({x for x in ram[(sy, "playoffs")]["games"] if x[2] == "4"})
                               if (sy, "playoffs") in ram else 0, po_n[sy]]}
        for sy in seasons if sy >= RAMIRO_FIRST}
    oncourt = set()
    for r in ram.values():
        oncourt |= r["oncourt"]
    # A box row with 0 minutes and no stats, for a player Ramiro's lineups put on the floor in
    # that game, is a seconds-long cameo (minutes are rounded down to 0), not a DNP.
    flips = Counter()
    flips_po = Counter()
    if COUNT_RAMIRO_CAMEOS:
        new_rows = []
        for row in rows:
            pid, gid, fr, appeared, m, p = row
            if not appeared and (pid, gid) in oncourt:
                row = (pid, gid, fr, True, m, p)
                (flips if gid[2] == "2" else flips_po)[season_of_gid(gid)] += 1
            new_rows.append(row)
        rows = new_rows
    rows, impossible = drop_impossible(rows, games, oncourt)
    step0["impossible_rows_dropped"] = impossible
    excluded_left = Counter(season_of_gid(r[1]) for r in rows if not r[3])
    step0["ramiro_cameos_counted"] = {"regular": dict(flips), "playoffs": dict(flips_po),
                                      "enabled": COUNT_RAMIRO_CAMEOS}
    step0["zero_rows_still_excluded"] = dict(excluded_left)

    # ---------------- identities
    log("matching identities...")
    rs = load_rs_stats()
    ident, total, matched, unmatched = match_identities(rows, names, rs)
    # per player games for the unmatched report
    unmatched_big = [u for u in unmatched if u[4] >= 20]
    # players with no RS-Stats name at all
    pgames = Counter()
    for pid, gid, fr, appeared, m, p in rows:
        if appeared and gid[2] == "2":
            pgames[pid] += 1
    no_name = sorted([(pgames[pid], pid, names[pid].most_common(1)[0][0]) for pid in names
                      if not ident.get(pid) and pgames[pid] >= 20], reverse=True)
    step0["identity_no_name_20plus"] = [{"personId": pid, "name": n, "games": g}
                                        for g, pid, n in no_name]
    step0["identity"] = {"player_team_seasons": total, "matched": matched,
                         "rate": round(matched / total, 4) if total else None,
                         "unmatched_20plus": [{"personId": u[0], "name": u[1], "season": u[2],
                                               "team": u[3], "games": u[4]} for u in
                                              sorted(unmatched_big, key=lambda x: (x[2], x[1]))],
                         "unmatched_total": len(unmatched)}
    cm_players = set(os.path.splitext(x)[0] for x in os.listdir(os.path.join(CMAP, "player"))
                     if x.endswith(".html"))
    ff_dir = os.path.join(HEAD, "players", "headshots", "face-fill")
    ff = {}
    for x in os.listdir(ff_dir):
        m = re.match(r"(\d+)-(.+)\.webp$", x)
        if m:
            ff.setdefault(int(m.group(1)), []).append(x)
    pids_appeared = {r[0] for r in rows if r[3]}
    pid_ids = {}
    slug_owner = {}
    # deterministic: by personId
    for pid in sorted(pids_appeared):
        nm = ident.get(pid)
        bx = names[pid].most_common(1)[0][0]
        disp = nm or bx
        slug = slugify(disp)
        if slug in slug_owner:
            slug = f"{slug}-{pid}"
        slug_owner[slug] = pid
        clean = re.sub(r"\s*\(\d{4}\)\s*", "", disp).strip()
        hs = None
        files = ff.get(pid)
        if files:
            # prefer the file whose name part matches the player's slug
            want = slugify(clean)
            pick = [f for f in files if f[len(str(pid)) + 1:-5] == want]
            hs = (pick or sorted(files))[0]
        pid_ids[pid] = {"slug": slug, "name": clean, "rsName": nm, "bxName": bx,
                        "cm": slugify(disp) in cm_players, "hs": hs}
    dump_json(os.path.join(DATA, "player_ids.json"),
              {str(k): v for k, v in pid_ids.items()}, compact=False)
    step0["identity"]["players"] = len(pid_ids)
    step0["identity"]["no_rs_name"] = sum(1 for v in pid_ids.values() if not v["rsName"])
    step0["identity"]["career_map_pages"] = sum(1 for v in pid_ids.values() if v["cm"])
    step0["identity"]["slug_suffixed"] = sorted(v["slug"] for v in pid_ids.values()
                                                if re.search(r"-\d{3,}$", v["slug"]))
    step0["headshots"] = {"face_fill_files": sum(len(v) for v in ff.values()),
                          "players_with_photo": sum(1 for v in pid_ids.values() if v["hs"]),
                          "players": len(pid_ids)}

    # ---------------- appearances
    log("windows and with/without...")
    app = defaultdict(list)          # (pid, sy) -> [(date, gid, fr, t)]
    pg_pts = {}
    pg_fr = {}
    for pid, gid, fr, appeared, m, p in rows:
        if not appeared:
            continue
        g = games[gid]
        app[(pid, g["sy"])].append((g["date"], gid, fr, g["t"]))
        pg_pts[(pid, gid)] = (m, p)
        pg_fr[(pid, gid)] = fr
    team_pts = Counter()
    for pid, gid, fr, appeared, m, p in rows:
        team_pts[(gid, fr)] += p


    players = defaultdict(lambda: {"seasons": []})
    duo_g = Counter()
    duo_w = Counter()
    for (pid, sy), lst in app.items():
        rsg = sorted([x for x in lst if x[3] == "2"])
        if not rsg:
            # playoff-only appearance: still record playoff line under that team
            pass
        # stints
        stints = []
        for d, gid, fr, t in rsg:
            if stints and stints[-1]["fr"] == fr:
                stints[-1]["games"].append((d, gid))
            else:
                stints.append({"fr": fr, "games": [(d, gid)]})
        sb = season_bounds.get(sy)
        per_team = {}
        for i, st in enumerate(stints):
            start = sb[0] if i == 0 else (d2(stints[i - 1]["games"][-1][0]) +
                                          dt.timedelta(days=1)).isoformat()
            end = sb[1] if i == len(stints) - 1 else (d2(stints[i + 1]["games"][0][0]) -
                                                     dt.timedelta(days=1)).isoformat()
            mine = {gid for _, gid in st["games"]}
            pt = per_team.setdefault(st["fr"], {
                "f": st["fr"], "s": sy, "g": 0, "w": 0, "l": 0, "ow": 0, "ol": 0,
                "first": st["games"][0][0], "last": st["games"][-1][0], "win": [],
                "pts": 0, "min": 0, "minG": 0, "teamPts": 0})
            pt["win"].append([start, end])
            pt["first"] = min(pt["first"], st["games"][0][0])
            pt["last"] = max(pt["last"], st["games"][-1][0])
            # Appearance span (audit 2026-11): the team's games he missed between his own first
            # and last game of this stint. Dated only by his appearances, so no game before he
            # arrived or after he left can count. Kept next to the published window proxy.
            sp_a, sp_b = st["games"][0][0], st["games"][-1][0]
            pt.setdefault("span", [])
            pt["span"].append([sp_a, sp_b])
            pt.setdefault("sw", 0)
            pt.setdefault("sl", 0)
            for g in team_games.get((st["fr"], sy, "2"), []):
                if not (start <= g["date"] <= end):
                    continue
                won = team_won(g, st["fr"])
                if g["gid"] not in mine and sp_a <= g["date"] <= sp_b:
                    pt["s" + ("w" if won else "l")] += 1
                if g["gid"] in mine:
                    pt["g"] += 1
                    pt["w" if won else "l"] += 1
                    m, p = pg_pts[(pid, g["gid"])]
                    pt["pts"] += p
                    pt["teamPts"] += team_pts[(g["gid"], st["fr"])]
                    if m:
                        pt["min"] += m
                        pt["minG"] += 1
                else:
                    pt["o" + ("w" if won else "l")] += 1
        order = [st["fr"] for st in stints]
        end_team = order[-1] if order else None
        # before / after records for traded seasons
        if len(per_team) > 1:
            for fr, pt in per_team.items():
                lo = min(w[0] for w in pt["win"])
                hi = max(w[1] for w in pt["win"])
                bw = bl = aw = al = 0
                for g in team_games.get((fr, sy, "2"), []):
                    won = team_won(g, fr)
                    if g["date"] < lo:
                        bw, bl = bw + won, bl + (not won)
                    elif g["date"] > hi:
                        aw, al = aw + won, al + (not won)
                pt["before"] = [bw, bl]
                pt["after"] = [aw, al]
        # playoffs: teams he appeared for in the playoffs
        pog = [x for x in lst if x[3] == "4"]
        po_teams = sorted({x[2] for x in pog})
        for fr in po_teams:
            pt = per_team.setdefault(fr, {"f": fr, "s": sy, "g": 0, "w": 0, "l": 0, "ow": 0,
                                          "ol": 0, "first": None, "last": None, "win": [],
                                          "pts": 0, "min": 0, "minG": 0, "teamPts": 0})
            mine = {x[1] for x in pog if x[2] == fr}
            po = {"g": 0, "w": 0, "l": 0, "ow": 0, "ol": 0}
            for g in team_games.get((fr, sy, "4"), []):
                won = team_won(g, fr)
                if g["gid"] in mine:
                    po["g"] += 1
                    po["w" if won else "l"] += 1
                else:
                    po["o" + ("w" if won else "l")] += 1
            pt["po"] = po
        # Ramiro extras
        for fr, pt in per_team.items():
            pt["endTeam"] = fr == end_team
            if sy < RAMIRO_FIRST:
                continue
            for kind, key in (("regular", "2"), ("playoffs", "4")):
                r = ram.get((sy, kind))
                if not r:
                    continue
                on = [0, 0, 0, 0]
                tm = [0, 0, 0, 0]
                st_w = st_l = bn_w = bn_l = cl_w = cl_l = 0
                any_g = False
                for g in team_games.get((fr, sy, key), []):
                    gid = g["gid"]
                    # he must have appeared FOR THIS TEAM (not against it after a trade)
                    if pg_fr.get((pid, gid)) != fr or gid not in r["games"]:
                        continue
                    any_g = True
                    o = r["on"].get((pid, gid))
                    if o:
                        for i in range(4):
                            on[i] += o[i]
                    t4 = r["team"].get((gid, fr))
                    if t4:
                        for i in range(4):
                            tm[i] += t4[i]
                    won = team_won(g, fr)
                    if pid in r["starters"].get((gid, fr), ()):
                        st_w, st_l = st_w + won, st_l + (not won)
                    else:
                        bn_w, bn_l = bn_w + won, bn_l + (not won)
                    if gid in r["clutch_games"] and (pid, gid) in r["clutch_on"]:
                        cl_w, cl_l = cl_w + won, cl_l + (not won)
                if not any_g:
                    continue
                off = [tm[i] - on[i] for i in range(4)]
                block = {"on": on, "off": off, "st": [st_w, st_l], "bn": [bn_w, bn_l],
                         "cl": [cl_w, cl_l]}
                if key == "2":
                    pt["rm"] = block
                elif "po" in pt:
                    pt["po"]["rm"] = block
        for fr, pt in per_team.items():
            players[pid]["seasons"].append(pt)
    # duos: team-games with both appeared (regular season)
    log("duos...")
    tg_players = defaultdict(list)
    for pid, gid, fr, appeared, m, p in rows:
        if appeared and gid[2] == "2":
            tg_players[(gid, fr)].append(pid)
    for (gid, fr), pl in tg_players.items():
        won = team_won(games[gid], fr)
        pl = sorted(set(pl))
        for i in range(len(pl)):
            for j in range(i + 1, len(pl)):
                k = (pl[i], pl[j])
                duo_g[k] += 1
                if won:
                    duo_w[k] += 1
    duos = defaultdict(list)
    for k, g in duo_g.items():
        if g >= 50:
            w = duo_w[k]
            duos[k[0]].append((k[1], g, w))
            duos[k[1]].append((k[0], g, w))

    # awards
    scores, awards = load_awards()
    out_players = {}
    for pid, p in players.items():
        info = pid_ids.get(pid)
        if not info:
            continue
        d = sorted(duos.get(pid, []), key=lambda x: (-(x[2] / x[1]), -x[1], x[0]))[:10]
        aw = awards.get(info["rsName"] or info["name"], {"score": 0, "counts": {}, "byYear": {}, "allstar": []})
        seas = sorted(p["seasons"], key=lambda x: (x["s"], x.get("first") or "9999"))
        out_players[str(pid)] = {"seasons": seas,
                                 "duos": [[a, g, w] for a, g, w in d],
                                 "acc": aw["score"], "accY": aw["byYear"], "awards": aw["counts"],
                                 "as": aw.get("allstar", [])}
    dump_json(os.path.join(DATA, "players.json"), out_players)
    write_gamelogs(games, rows)
    ts_out = {f"{f}-{s}": r for (f, s), r in sorted(tseasons.items())}
    dump_json(os.path.join(DATA, "team_seasons.json"), ts_out)
    meta = {"season_bounds": {str(k): v for k, v in season_bounds.items()},
            "accolade_weights": scores}
    dump_json(os.path.join(DATA, "meta.json"), meta, compact=False)
    dump_json(os.path.join(DATA, "step0.json"), step0, compact=False)
    log("done.")


if __name__ == "__main__":
    build()

# (c) 2026 HoopsMatic. All rights reserved.
# Team Success career leaderboards. Fingerprint: hm-ts-7f3a91c2-boards
"""The eight career-card leaderboards, with filters.

The ranking rules run on the compact data in assets/board.json, the same file the browser uses
(assets/boards.js mirrors compute() line by line), so the pre-rendered default view, the rank on
each career card and any filtered view in the browser come from one set of rules. The Python side
is checked against analysis.summary() by tests/test_boards.py, and the JS side against this file.

Filters (URL parameters): from, to, season (sets both), ts (team-season games min), cg (career
games min), team (franchise), as (ever | season), st (active | retired), sort, ms (min seasons),
mp / mm (min games played / missed), hl (player to highlight).
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CURRENT_SEASON, LAST_COMPLETE, season_label  # noqa: E402

PO = ["", "Play-In", "First Round", "Conf Semis", "Conf Finalist", "Finalist", "Champion"]
DEPTH = [0, 0, 1, 2, 3, 4, 5]
DEPTH_LABEL = {5: "Won the title", 4: "NBA Finals", 3: "Conference finals", 2: "Conference semifinals",
               1: "First round", 0: "Missed playoffs"}

# key -> board definition. "sorts": sort key -> (label, direction, value fn name, default mins)
BOARDS = {
    "career-wins": {
        "title": "Most wins in his games: NBA career leaderboard",
        "h1": "Career wins in his games",
        "desc": "Every NBA player ranked by his teams' regular-season wins in the games he played, since 1946-47, including the season in progress to date. Switch to win % (minimum 400 games) and filter by era, team, All-Stars and games.",
        "card": "Career record",
        "sorts": {"w": ("Wins", "desc", {}), "pct": ("Win %", "desc", {"cg": 400})},
        "cols": ["w", "l", "pct", "gp", "wl"],
    },
    "wins-minus-losses": {
        "title": "Wins minus losses: NBA career leaderboard",
        "h1": "Wins minus losses",
        "desc": "His teams' regular-season wins minus losses in the games he played, every NBA player since 1946-47. It rewards sustained winning and availability, so it favors long careers: switch to win % or filter by era.",
        "card": "Wins minus losses",
        "sorts": {"wl": ("W − L", "desc", {}), "pct": ("Win %", "desc", {"cg": 400})},
        "cols": ["wl", "rec", "pct", "gp"],
    },
    "winning-seasons": {
        "title": "Most winning seasons: NBA career leaderboard",
        "h1": "Winning seasons",
        "desc": "Seasons on a team that finished above .500 (the team he played the most games for that season), and their share of his seasons.",
        "card": "Winning seasons",
        "sorts": {"winning": ("Winning seasons", "desc", {}), "wshare": ("Share", "desc", {"ms": 5})},
        "cols": ["winning", "seasons", "wshare"],
    },
    "playoff-trips": {
        "title": "Most playoff trips: NBA career leaderboard",
        "h1": "Playoff trips",
        "desc": "Seasons in which he played a playoff game or finished the season with a playoff team, and their share of his seasons. Play-in losses are not trips.",
        "card": "Playoff trips",
        "sorts": {"trips": ("Playoff trips", "desc", {}), "tshare": ("Share", "desc", {"ms": 5})},
        "cols": ["trips", "seasons", "tshare"],
    },
    "deepest-run": {
        "title": "Deepest playoff run: NBA career leaderboard",
        "h1": "Deepest playoff run",
        "desc": "Every player's best playoff finish, from a title to missing the playoffs. Equal outcomes share a rank; within a rank, players are listed by how many times they got that far.",
        "card": "Deepest playoff run",
        "sorts": {"deep": ("Deepest run", "desc", {})},
        "cols": ["deep", "deepn", "seasons"],
    },
    "titles": {
        "title": "Most NBA titles: career leaderboard",
        "h1": "Titles",
        "desc": "Championships won by the team he played for, counted when he played a playoff game for the champion or finished the season with it.",
        "card": "Titles",
        "sorts": {"titles": ("Titles", "desc", {})},
        "cols": ["titles", "seasons", "years"],
    },
    "average-finish": {
        "title": "Best average final NBA finish, adjusted for league size: career leaderboard",
        "h1": "Average final NBA finish",
        "desc": "The average final NBA finish (1 = champion) of his teams, one team per season, minimum 5 seasons, adjusted for league size and shown on a 30-team scale: 3rd of 9 teams in 1964-65 counts as 8.25 of 30. The raw average is the second view.",
        "card": "Average final finish",
        "explain": "Adjusted = each season's finish put on a 30-team scale, 1 + (rank − 1) / (teams − 1) × 29, then averaged: 3rd of 9 counts as 8.25 of 30. Raw = the plain average of the ranks.",
        "sorts": {"adj": ("Average finish, adjusted for league size", "asc", {"ms": 5}),
                  "avg": ("Raw average finish", "asc", {"ms": 5})},
        "cols": ["adj", "avg", "seasons"],
    },
    "no-allstar-teammate": {
        "title": "Most wins without an All-Star teammate: NBA career leaderboard",
        "h1": "Most wins without an All-Star teammate",
        "desc": "His teams' record in his games, counting only team-seasons in which no teammate who shared a game with him that season was an All-Star that season.",
        "card": "Without an All-Star teammate",
        "sorts": {"w": ("Wins", "desc", {}), "wl": ("W − L", "desc", {}), "pct": ("Win %", "desc", {"cg": 500})},
        "cols": ["w", "wl", "pct", "rec", "gp", "seasons"],
        "noas": True,
    },
    "gap-career": {
        "title": "Biggest with/without win-rate gaps in an NBA career",
        "h1": "With vs without: career win-rate gap",
        "desc": "His teams' win % in the games he played minus in the games he missed (team-season window), minimum 200 games played and 50 missed, both samples shown.",
        "card": "With vs without",
        "sorts": {"gap": ("Gap", "desc", {"mp": 200, "mm": 50})},
        "cols": ["with", "without", "gap", "gp", "gm"],
    },
}
COL_LABEL = {"w": "Wins", "l": "Losses", "pct": "Win %", "gp": "Games in this view", "wl": "W − L",
             "rec": "W–L", "winning": "Winning seasons", "seasons": "Seasons", "wshare": "Share",
             "trips": "Playoff trips", "tshare": "Share", "deep": "Deepest run", "deepn": "Times",
             "titles": "Titles", "years": "Title seasons", "avg": "Raw average",
             "adj": "Adjusted (of 30)", "gap": "Gap (points)", "with": "With him", "without": "Without him",
             "gm": "Missed"}


def compact(d, cur, help_doc=None, partial_years=()):
    """Build assets/board.json: team table + one row per player, completed seasons plus the live
    season (team entries with live = 1: in W-L totals, never in season counts).
    Stint: [season, franchise, g, w, l, ow, ol, endTeam, played playoffs, last date,
            no All-Star teammate (1/0), he was an All-Star (1/0), honors missing (1/0)].
    "Honors missing" = that season's All-Stars are not in the awards data (awards.json in nba-player-data)
    or it has no teammate-help rows yet (the season in progress on 2026-11-19). The no-All-Star board
    leaves those team-seasons out instead of counting them as "no All-Star"; they come back on their own
    once awards.json names the All-Stars and data/help.json has the season."""
    teams = {}
    size = defaultdict(int)
    for t in d.teams.values():
        size[t["s"]] += 1
    for k, t in d.teams.items():
        teams[k] = [t["w"], t["l"], t["rnk"], size[t["s"]], PO.index(t["po"]), 1 if t.get("live") else 0]
    hs = (help_doc or {}).get("season", {})
    known = honors_known(d, help_doc)
    active = set(cur["players"]) if cur else set()
    rows = []
    for pid, p in d.players.items():
        v = d.ids.get(pid)
        if not v:
            continue
        st = []
        allstar = set(p.get("as", []))
        for s in p["seasons"]:
            if s["s"] > CURRENT_SEASON or not s["g"] or not d.team(s["f"], s["s"]):
                continue
            last = int((s.get("last") or "0").replace("-", ""))
            mates = hs.get(pid, {}).get(f"{s['f']}-{s['s']}", [0, 0, 0, []])[3]
            noas = 0 if any("All-Star" in m[4] for m in mates) else 1
            st.append([s["s"], s["f"], s["g"], s["w"], s["l"], s["ow"], s["ol"],
                       1 if s.get("endTeam") else 0, 1 if (s.get("po") and s["po"]["g"] > 0) else 0, last,
                       noas, 1 if s["s"] in allstar else 0, 0 if s["s"] in known else 1])
        if not st:
            continue
        face = v.get("hs") if v.get("hs") and os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "hs", v["hs"])) else ""
        rows.append([pid, v["slug"], v["name"], 1 if pid in active else 0, p.get("as", []), st, face])
    rows.sort(key=lambda r: int(r[0]))
    return {"t": teams, "p": rows, "first": 1947, "last": CURRENT_SEASON, "complete": LAST_COMPLETE,
            "through": d.through}


def honors_known(d, help_doc):
    """Seasons whose All-Stars are in the awards data (awards.json) and with teammate help built
    (data/help.json). Seasons with no All-Star Game (1946-47 to 1949-50, 1998-99) count once they
    have any other weighted honors."""
    as_years = {int(y) for p in d.players.values() for y in p.get("as", [])}
    aw_years = {int(y) for p in d.players.values() for y in p.get("awY", {})}
    no_game = set(range(1947, 1951)) | {1999}
    help_years = {int(k.rsplit("-", 1)[1]) for v in (help_doc or {}).get("season", {}).values() for k in v}
    return (as_years | (aw_years & no_game)) & help_years


def honors_missing(d, help_doc):
    """Seasons 1947..CURRENT_SEASON the no-All-Star board cannot count yet."""
    known = honors_known(d, help_doc)
    return [sy for sy in range(1947, CURRENT_SEASON + 1) if sy not in known]


def player_metrics(row, teams, flt):
    """Everything any board needs for one player under one filter. None if no stint qualifies."""
    pid, slug, name, active, allstar, stints = row[:6]
    lo, hi = flt.get("from", 1947), flt.get("to", CURRENT_SEASON)
    ts, team = flt.get("ts", 1), flt.get("team", "")
    inc = [s for s in stints if lo <= s[0] <= hi and s[2] >= ts and (not team or s[1] == team)]
    if flt.get("noas"):                               # winning without an All-Star teammate
        inc = [s for s in inc if s[10] and not s[12]]   # leave out seasons with no honors data
        if flt.get("self") == "yes":
            inc = [s for s in inc if s[11]]
        elif flt.get("self") == "no":
            inc = [s for s in inc if not s[11]]
    if not inc:
        return None
    if flt.get("st") == "active" and not active:
        return None
    if flt.get("st") == "retired" and active:
        return None
    if flt.get("as") == "ever" and not allstar:
        return None
    if flt.get("as") == "season" and not (lo == hi and lo in allstar):
        return None
    w = sum(s[3] for s in inc)
    l = sum(s[4] for s in inc)
    ow = sum(s[5] for s in inc)
    ol = sum(s[6] for s in inc)
    by = defaultdict(list)
    for s in inc:
        by[s[0]].append(s)
    winning = trips = titles = 0
    deep, deepn = -1, 0
    rk = []
    adj = []
    title_years = []
    live_n = 0
    for sy in sorted(by):
        lst = by[sy]
        if teams[f"{lst[0][1]}-{sy}"][5]:                     # season in progress: W-L only
            live_n += 1
            continue
        main = max(lst, key=lambda x: (x[2], x[9]))           # most games, ties -> later team
        ends = [x for x in lst if x[7]]
        end = ends[0] if ends else max(lst, key=lambda x: x[9])
        t = teams[f"{main[1]}-{sy}"]
        if t[0] / (t[0] + t[1]) > 0.5:
            winning += 1
        rk.append(t[2])
        adj.append((t[2] - 1) / (t[3] - 1) if t[3] > 1 else 0.0)
        best = None
        for x in lst:                                         # same order as analysis.playoff_result
            if x is end or x[8]:
                tt = teams[f"{x[1]}-{sy}"]
                if best is None or DEPTH[tt[4]] > DEPTH[best[4]]:
                    best = tt
        dpt = DEPTH[best[4]] if best else 0
        if dpt >= 1:
            trips += 1
        if best and best[4] == 6:
            titles += 1
            title_years.append(sy)
        if dpt > deep:
            deep, deepn = dpt, 1
        elif dpt == deep:
            deepn += 1
    n = len(by) - live_n
    return {"pid": pid, "slug": slug, "name": name, "w": w, "l": l, "ow": ow, "ol": ol,
            "gp": w + l, "gm": ow + ol, "wl": w - l, "pct": (w / (w + l)) if w + l else None,
            "seasons": n + live_n if flt.get("noas") else n, "winning": winning,
            "wshare": winning / n if n else None, "trips": trips, "tshare": trips / n if n else None,
            "titles": titles, "years": title_years, "deep": deep if n else 0, "deepn": deepn,
            "avg": sum(rk) / n if n else None, "adj": sum(adj) / n if n else None,
            "gap": ((w / (w + l)) - (ow / (ow + ol))) if (w + l) and (ow + ol) else None}


def mins_for(board, sort, flt):
    """Default minimums of a sort, overridden by explicit filter values."""
    base = dict(BOARDS[board]["sorts"][sort][2])
    for k in ("cg", "ms", "mp", "mm"):
        if k in flt:
            base[k] = flt[k]
    base.setdefault("cg", 1)
    return base


def sort_key(board, sort, m):
    """(primary value for ranking, tiebreak tuple for display)."""
    v = m[sort]
    if sort == "deep":
        return (-v, (-m["deepn"], m["name"]))
    if sort in ("avg", "adj"):
        return (round(v, 9), (m["name"],))
    if sort == "w":
        return (-v, (m["l"], m["name"]))
    if sort == "wl":
        return (-v, (-m["w"], m["name"]))
    if sort in ("pct", "wshare", "tshare", "gap"):
        sec = {"pct": -m["gp"], "wshare": -m["seasons"], "tshare": -m["seasons"], "gap": -m["gp"]}[sort]
        return (-round(v, 9), (sec, m["name"]))
    return (-v, (-m["seasons"], m["name"]))


def compute(data, board, flt=None):
    """Ranked rows for a board: [(rank, tied, metrics)], plus the eligible population size."""
    flt = dict(flt or {})
    if BOARDS[board].get("noas"):
        flt["noas"] = 1
    sort = flt.get("sort") or next(iter(BOARDS[board]["sorts"]))
    if sort not in BOARDS[board]["sorts"]:
        sort = next(iter(BOARDS[board]["sorts"]))
    mins = mins_for(board, sort, flt)
    out = []
    for row in data["p"]:
        m = player_metrics(row, data["t"], flt)
        if not m or m["gp"] < mins["cg"]:
            continue
        if m["seasons"] < mins.get("ms", 0):
            continue
        if m["gp"] < mins.get("mp", 0) or m["gm"] < mins.get("mm", 0):
            continue
        if m[sort] is None:
            continue
        out.append(m)
    out.sort(key=lambda m: sort_key(board, sort, m))
    ranked = []
    prev = object()
    rank = 0
    for i, m in enumerate(out):
        k = sort_key(board, sort, m)[0]
        if k != prev:
            rank = i + 1
            prev = k
        ranked.append([rank, False, m])
    cnt = defaultdict(int)
    for r in ranked:
        cnt[r[0]] += 1
    for r in ranked:
        r[1] = cnt[r[0]] > 1
    return ranked, sort, mins


# ---------------------------------------------------------------------------
# One ranking rule and one scope label everywhere (player cards, boards, the daily list, fun facts,
# share-card data, comparison scoreboards): the board's default view, its qualifying group, and
# standard competition ranking (1, 2, 2, 4) shown as "T-2" for a shared rank.
# ---------------------------------------------------------------------------
# which boards count the season in progress (career W-L totals) and which are completed seasons only
LIVE_BOARDS = {"career-wins", "wins-minus-losses", "gap-career"}
SCOPE_LIVE = f"incl. {season_label(CURRENT_SEASON)} to date"
SCOPE_DONE = f"through {season_label(LAST_COMPLETE)}"


def scope_label(board, flt=None):
    """A few words for the scope of a board's numbers: "incl. 2026-27 to date" / "through 2025-26"."""
    flt = flt or {}
    if board in LIVE_BOARDS and int(flt.get("to", CURRENT_SEASON)) >= CURRENT_SEASON:
        return SCOPE_LIVE
    return SCOPE_DONE


def rank_label(rank, tied):
    return f"T-{rank:,}" if tied else f"#{rank:,}"


def rank_of(data, board, pid, flt=None):
    """(rank, tied, qualifying players, metrics) for one player on a board view, or None."""
    ranked, sort, mins = compute(data, board, flt)
    for r, tied, m in ranked:
        if m["pid"] == pid:
            return r, tied, len(ranked), m
    return None


def ranks_before(data, board, delta, flt=None):
    """Ranks on a board view as they stood before the games in delta (pid -> [w, l] to take off
    his live season). Same qualifying group, sort and tie rule as compute(). Returns
    (before, after): pid -> (rank, tied, value)."""
    ranked, sort, mins = compute(data, board, flt)
    after = {m["pid"]: (r, t, m[sort]) for r, t, m in ranked}
    rows = []
    for row in data["p"]:
        m = player_metrics(row, data["t"], dict(flt or {}, **({"noas": 1} if BOARDS[board].get("noas") else {})))
        if not m:
            continue
        dw, dl = delta.get(m["pid"], (0, 0))
        if dw or dl:
            m = dict(m)
            m["w"] -= dw
            m["l"] -= dl
            m["gp"] -= dw + dl
            m["wl"] = m["w"] - m["l"]
            m["pct"] = m["w"] / m["gp"] if m["gp"] else None
        if m["gp"] < mins["cg"] or m["seasons"] < mins.get("ms", 0) or m[sort] is None:
            continue
        rows.append(m)
    rows.sort(key=lambda m: sort_key(board, sort, m))
    before, prev, rank, cnt = {}, object(), 0, defaultdict(int)
    tmp = []
    for i, m in enumerate(rows):
        k = sort_key(board, sort, m)[0]
        if k != prev:
            rank, prev = i + 1, k
        tmp.append((m["pid"], rank, m[sort]))
        cnt[rank] += 1
    for pid, r, v in tmp:
        before[pid] = (r, cnt[r] > 1, v)
    return before, after


def passes(data, board, delta, flt=None):
    """Players in delta who moved ahead of someone on a board view because of those games:
    [(pid, (rank, tied, value) now, [(passed pid, (rank, tied, value) now), ...])], best rank first.
    'Passed' = level with or ahead of him before, strictly behind him now (same board rule)."""
    before, after = ranks_before(data, board, delta, flt)
    out = []
    for p in delta:
        if p not in after or p not in before:
            continue
        rp0, rp1 = before[p][0], after[p][0]
        if rp1 >= rp0 and not (before[p][1] and not after[p][1]):
            continue
        got = [q for q, v in after.items() if q != p and q in before and before[q][0] <= rp0 and v[0] > rp1]
        if got:
            got.sort(key=lambda q: after[q][0])
            out.append((p, after[p], [(q, after[q]) for q in got]))
    out.sort(key=lambda x: x[1][0])
    return out

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
from common import LAST_COMPLETE  # noqa: E402

PO = ["", "Play-In", "First Round", "Conf Semis", "Conf Finalist", "Finalist", "Champion"]
DEPTH = [0, 0, 1, 2, 3, 4, 5]
DEPTH_LABEL = {5: "Won the title", 4: "NBA Finals", 3: "Conference finals", 2: "Conference semifinals",
               1: "First round", 0: "Missed the playoffs"}

# key -> board definition. "sorts": sort key -> (label, direction, value fn name, default mins)
BOARDS = {
    "career-wins": {
        "title": "Most wins in his games: NBA career leaderboard",
        "h1": "Career wins in his games",
        "desc": "Every NBA player ranked by his teams' regular-season wins in the games he played, 1946-47 to 2025-26. Switch to win % (minimum 400 games) and filter by era, team, All-Stars and games.",
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
        "title": "Best average final NBA finish: career leaderboard",
        "h1": "Average final NBA finish",
        "desc": "The average final NBA finish (1 = champion) of his teams, one team per season, minimum 5 seasons. The league-size-adjusted view puts every season on one scale, 0 = champion, 1 = last.",
        "card": "Average final finish",
        "sorts": {"avg": ("Average finish", "asc", {"ms": 5}), "adj": ("Adjusted", "asc", {"ms": 5})},
        "cols": ["avg", "adj", "seasons"],
    },
    "gap-career": {
        "title": "Biggest with/without win-rate gaps in an NBA career",
        "h1": "With vs without: career win-rate gap",
        "desc": "His teams' win % in the games he played minus in the games he missed (team-season window), minimum 200 games played and 50 missed, both samples shown.",
        "card": "With vs without",
        "sorts": {"gap": ("Gap", "desc", {"mp": 200, "mm": 50})},
        "cols": ["gap", "with", "without", "gp", "gm"],
    },
}
COL_LABEL = {"w": "Wins", "l": "Losses", "pct": "Win %", "gp": "Games", "wl": "W − L",
             "rec": "W–L", "winning": "Winning seasons", "seasons": "Seasons", "wshare": "Share",
             "trips": "Playoff trips", "tshare": "Share", "deep": "Deepest run", "deepn": "Times",
             "titles": "Titles", "years": "Title seasons", "avg": "Average finish",
             "adj": "Adjusted (0 = champion)", "gap": "Gap", "with": "With him", "without": "Without him",
             "gm": "Missed"}


def compact(d, cur):
    """Build assets/board.json: team table + one row per player (completed seasons only)."""
    teams = {}
    size = defaultdict(int)
    for t in d.teams.values():
        size[t["s"]] += 1
    for k, t in d.teams.items():
        teams[k] = [t["w"], t["l"], t["rnk"], size[t["s"]], PO.index(t["po"])]
    active = set(cur["players"]) if cur else set()
    rows = []
    for pid, p in d.players.items():
        v = d.ids.get(pid)
        if not v:
            continue
        st = []
        for s in p["seasons"]:
            if s["s"] > LAST_COMPLETE or not s["g"] or not d.team(s["f"], s["s"]):
                continue
            last = int((s.get("last") or "0").replace("-", ""))
            st.append([s["s"], s["f"], s["g"], s["w"], s["l"], s["ow"], s["ol"],
                       1 if s.get("endTeam") else 0, 1 if (s.get("po") and s["po"]["g"] > 0) else 0, last])
        if not st:
            continue
        rows.append([pid, v["slug"], v["name"], 1 if pid in active else 0, p.get("as", []), st])
    rows.sort(key=lambda r: int(r[0]))
    return {"t": teams, "p": rows, "first": 1947, "last": LAST_COMPLETE}


def player_metrics(row, teams, flt):
    """Everything any board needs for one player under one filter. None if no stint qualifies."""
    pid, slug, name, active, allstar, stints = row
    lo, hi = flt.get("from", 1947), flt.get("to", LAST_COMPLETE)
    ts, team = flt.get("ts", 1), flt.get("team", "")
    inc = [s for s in stints if lo <= s[0] <= hi and s[2] >= ts and (not team or s[1] == team)]
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
    for sy in sorted(by):
        lst = by[sy]
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
    n = len(by)
    return {"pid": pid, "slug": slug, "name": name, "w": w, "l": l, "ow": ow, "ol": ol,
            "gp": w + l, "gm": ow + ol, "wl": w - l, "pct": (w / (w + l)) if w + l else None,
            "seasons": n, "winning": winning, "wshare": winning / n, "trips": trips, "tshare": trips / n,
            "titles": titles, "years": title_years, "deep": deep, "deepn": deepn,
            "avg": sum(rk) / n, "adj": sum(adj) / n,
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
    flt = flt or {}
    sort = flt.get("sort") or next(iter(BOARDS[board]["sorts"]))
    if sort not in BOARDS[board]["sorts"]:
        sort = next(iter(BOARDS[board]["sorts"]))
    mins = mins_for(board, sort, flt)
    out = []
    for row in data["p"]:
        m = player_metrics(row, data["t"], flt)
        if not m or m["gp"] < mins["cg"]:
            continue
        if m["seasons"] < mins.get("ms", 1):
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

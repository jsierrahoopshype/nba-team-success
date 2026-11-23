# (c) 2026 HoopsMatic. All rights reserved.
# Team Success: a player's record with and without each teammate. Fingerprint: hm-ts-7f3a91c2-teammates
"""Pure functions over the committed data (data/gamelog/<season>.json, data/players.json,
data/current.json). No network, no sources. Used by build_site.py, fun_facts.py and tests/.

For player A and teammate B, regular season only, 1946-47 through the season in progress:
  together   games A and B both played for the same team
  A without B  games A played for that team while B was on it that season (inside B's appearance
             span: between B's first and last game of a stint with that team) and B did not play
Records are the team's W-L in those games.

The span is the one the player with/without numbers already use (build_history.py and
update_current.py: per stint, the team's games between his own first and last game). Completed
seasons read it as stored (players.json "span"); the season in progress stores no span, so it is
rebuilt from the same appearance log with the same stint rule (stint_spans). tests/test_teammates.py
checks both against the stored sw / sl counts for every player-team-season.
"""
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CURRENT_SEASON, DATA, FIRST_SEASON, LAST_COMPLETE, load_json  # noqa: E402

TOO_FEW_WITHOUT = 20                # fewer games without him: the record shows, the gap does not
PAGE_ROWS = 12                      # player page: his 12 teammates with the most games together
SWING_MIN_TOGETHER, SWING_MIN_WITHOUT, SWING_Z = 100, 40, 2.58   # "Biggest teammate swings"


def stint_spans(appearances):
    """[(date, gid, franchise)] of one player's regular-season games in one season ->
    {franchise: [[first, last], ...]}: one span per stint (a run of games for the same team, in
    date order), the same rule as build_history.py / update_current.py."""
    stints = []
    for d, gid, fr in sorted(appearances):
        if stints and stints[-1][0] == fr:
            stints[-1][2] = d
        else:
            stints.append([fr, d, d])
    out = defaultdict(list)
    for fr, a, b in stints:
        out[fr].append([a, b])
    return dict(out)


def season_games(sy, cur=None):
    """[(gid, date, home, away, home won, [home pids], [away pids])] for one season, regular season."""
    if sy == CURRENT_SEASON and cur is not None:
        log = cur.get("log") or {}
        app = log.get("app", {})
        out = []
        for gid, date, h, a, hs, as_ in log.get("games", []):
            if gid[2] != "2":
                continue
            sides = app.get(gid, [[], []])
            out.append((gid, date, h, a, hs > as_, [str(p) for p in sides[0]], [str(p) for p in sides[1]]))
        return out
    doc = load_json(os.path.join(DATA, "gamelog", f"{sy}.json"))
    if not doc:
        return []
    out = []
    for gid, date, h, a, hc, ac, hs, as_ in doc["games"]:
        if gid[2] != "2":
            continue
        sides = doc["app"].get(gid, [[], []])
        out.append((gid, date, h, a, hs > as_, [str(p) for p in sides[0]], [str(p) for p in sides[1]]))
    return out


def team_season_masks(games):
    """Per (franchise) in one season: the team's games in date order, a win bitmask, and each
    player's played bitmask and appearance list."""
    by = defaultdict(list)
    for gid, date, h, a, hwon, hp, ap in games:
        by[h].append((date, gid, hwon, hp))
        by[a].append((date, gid, not hwon, ap))
    out = {}
    for fr, lst in by.items():
        lst.sort()
        win = 0
        played = defaultdict(int)
        for i, (date, gid, won, ps) in enumerate(lst):
            if won:
                win |= 1 << i
            for p in ps:
                played[p] |= 1 << i
        out[fr] = {"dates": [x[0] for x in lst], "win": win, "played": dict(played)}
    return out


def season_spans(games):
    """{pid: {franchise: [[first, last], ...]}} for one season: each player's stints across all his
    teams (a trade ends a stint, a trade back starts a new one)."""
    apps = defaultdict(list)
    for gid, date, h, a, hwon, hp, ap in games:
        for p in hp:
            apps[p].append((date, gid, h))
        for p in ap:
            apps[p].append((date, gid, a))
    return {p: stint_spans(lst) for p, lst in apps.items()}


def span_mask(dates, spans):
    m = 0
    for i, d in enumerate(dates):
        if any(a <= d <= b for a, b in spans):
            m |= 1 << i
    return m


def pc(x):
    return bin(x).count("1")


def all_pairs(players=None, cur=None, first=FIRST_SEASON, last=None):
    """{(A, B): {"t": [w, l], "o": [w, l], "seasons": [[franchise, season], ...]}} for every pair
    of teammates with 1+ game together. "o" is A without B. Pids are strings."""
    if players is None:
        players = load_json(os.path.join(DATA, "players.json"), {})
    if cur is None:
        cur = load_json(os.path.join(DATA, "current.json"), None)
    if last is None:
        last = CURRENT_SEASON if cur and cur.get("season") == CURRENT_SEASON else LAST_COMPLETE
    stored = {}                      # (pid, franchise, season) -> stored spans (completed seasons)
    for pid, p in players.items():
        for s in p.get("seasons", []):
            if s.get("span"):
                stored[(pid, s["f"], s["s"])] = s["span"]
    pairs = {}
    for sy in range(first, last + 1):
        live = sy == CURRENT_SEASON and sy > LAST_COMPLETE
        games = season_games(sy, cur if live else None)
        teams = team_season_masks(games)
        rebuilt = season_spans(games)
        for fr, t in teams.items():
            win, dates = t["win"], t["dates"]
            spans = {}
            for b in t["played"]:
                sp = None if live else stored.get((b, fr, sy))
                if sp is None:
                    sp = rebuilt.get(b, {}).get(fr, [])
                spans[b] = span_mask(dates, sp)
            for a, pa in t["played"].items():
                for b, pb in t["played"].items():
                    if a == b:
                        continue
                    tog = pa & pb
                    wo = pa & spans[b] & ~pb
                    if not tog and not wo:
                        continue
                    r = pairs.get((a, b))
                    if r is None:
                        r = pairs[(a, b)] = {"t": [0, 0], "o": [0, 0], "seasons": []}
                    tw = pc(tog & win)
                    ow = pc(wo & win)
                    r["t"][0] += tw
                    r["t"][1] += pc(tog) - tw
                    r["o"][0] += ow
                    r["o"][1] += pc(wo) - ow
                    if tog:
                        r["seasons"].append([fr, sy])
    return {k: v for k, v in pairs.items() if sum(v["t"])}


def pct(wl):
    return wl[0] / (wl[0] + wl[1]) if (wl[0] + wl[1]) else None


def gap(r):
    """Together win % minus without win % (a positive gap: his teams did worse without B)."""
    a, b = pct(r["t"]), pct(r["o"])
    return None if a is None or b is None else a - b


def too_few(r):
    return sum(r["o"]) < TOO_FEW_WITHOUT


def z_score(r):
    """Two-proportion z test: together vs without, pooled."""
    n1, n2 = sum(r["t"]), sum(r["o"])
    if not n1 or not n2:
        return 0.0
    p = (r["t"][0] + r["o"][0]) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (pct(r["t"]) - pct(r["o"])) / se if se else 0.0


def qualifies(r):
    """Biggest teammate swings: 100+ games together, 40+ without, a drop too big to be luck (z >= 2.58)."""
    return (sum(r["t"]) >= SWING_MIN_TOGETHER and sum(r["o"]) >= SWING_MIN_WITHOUT
            and gap(r) is not None and gap(r) > 0 and z_score(r) >= SWING_Z)


def top_teammates(pairs_by_a, n=PAGE_ROWS):
    """A's teammates with the most games together (ties: more wins together, then pid)."""
    return sorted(pairs_by_a.items(), key=lambda kv: (-sum(kv[1]["t"]), -kv[1]["t"][0], kv[0]))[:n]


def by_player(pairs):
    out = defaultdict(dict)
    for (a, b), r in pairs.items():
        out[a][b] = r
    return out


def seasons_compact(seasons):
    """[[franchise, season], ...] -> [[franchise, first season, last season], ...] (consecutive runs)."""
    runs = []
    for fr, sy in sorted(seasons, key=lambda x: (x[1], x[0])):
        for r in runs:
            if r[0] == fr and r[2] == sy - 1:
                r[2] = sy
                break
        else:
            runs.append([fr, sy, sy])
    return sorted(runs, key=lambda r: (r[1], r[0]))


if __name__ == "__main__":
    import time
    t0 = time.time()
    P = all_pairs()
    print(len(P), "pairs in", round(time.time() - t0, 1), "s")
    ids = load_json(os.path.join(DATA, "player_ids.json"))
    slug = {v["slug"]: k for k, v in ids.items()}
    for a, b in (("draymond-green", "stephen-curry"), ("stephen-curry", "draymond-green"),
                 ("john-paxson", "michael-jordan")):
        r = P[(slug[a], slug[b])]
        print(a, "with", b, r["t"], round(100 * pct(r["t"]), 1), "without", r["o"],
              round(100 * pct(r["o"]), 1) if sum(r["o"]) else None, "z", round(z_score(r), 2))
    print(json.dumps(seasons_compact(P[(slug["draymond-green"], slug["stephen-curry"])]["seasons"])))

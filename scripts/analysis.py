# (c) 2026 HoopsMatic. All rights reserved.
# Team Success: list and summary calculations. Fingerprint: hm-ts-7f3a91c2-analysis
"""Pure functions over the committed data files (no network, no sources needed).

Used by the site build and by tests/. Every list takes the same two filters as the pages:
  era_from  1947 (all-time) | 1977 (since 1976-77) | 1997 (since 1996-97)
  min_games 1 (any appearance) | 20 ("20+ games only")
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CURRENT_SEASON, DATA, LAST_COMPLETE, SIXTY_PACE, franchise_name, load_json  # noqa: E402

ERAS = ((1947, "all"), (1977, "1977"), (1997, "1997"))
GAME_FILTERS = ((1, "any"), (20, "20"))
PO_DEPTH = {"": 0, "Play-In": 0, "First Round": 1, "Conf Semis": 2, "Conf Finalist": 3,
            "Finalist": 4, "Champion": 5}
PO_LABEL = {"First Round": "First round", "Conf Semis": "Conference semifinals",
            "Conf Finalist": "Conference finals", "Finalist": "NBA Finals",
            "Champion": "Won the title", "Play-In": "Lost in play-in", "": "Missed playoffs"}


class Data:
    """live=True adds the season in progress (data/current.json) as team-seasons flagged "live":
    they count in career W-L totals, never in season-based counts (winning seasons, trips, finish)."""
    def __init__(self, data_dir=DATA, live=False):
        self.players = load_json(os.path.join(data_dir, "players.json"), {})
        self.teams = load_json(os.path.join(data_dir, "team_seasons.json"), {})
        self.ids = load_json(os.path.join(data_dir, "player_ids.json"), {})
        self.meta = load_json(os.path.join(data_dir, "meta.json"), {})
        self.through = None
        cur = load_json(os.path.join(data_dir, "current.json"), None) if live else None
        if cur and cur.get("teams"):
            self.through = cur["through"]
            sy = cur["season"]
            for f, (w, l) in cur["teams"].items():
                self.teams[f"{f}-{sy}"] = {"f": f, "s": sy, "w": w, "l": l, "pct": round(w / (w + l), 4) if w + l else 0,
                                           "name": franchise_name(f, sy) or f, "rnk": None, "po": "", "series": [],
                                           "elim": None, "best": False, "worst": False, "gpBox": w + l, "live": True,
                                           "conf": "", "div": "", "confPos": "", "divPos": ""}
            for k, v in cur.get("newIds", {}).items():
                self.ids.setdefault(k, v)
            for pid, sts in cur["players"].items():
                p = self.players.setdefault(pid, {"seasons": [], "duos": [], "acc": 0, "accY": {}, "awards": {}, "as": []})
                for st in sts:
                    p["seasons"].append({"f": st["f"], "s": sy, "g": st["g"], "w": st["w"], "l": st["l"],
                                         "ow": st["ow"], "ol": st["ol"], "sw": st.get("sw", 0), "sl": st.get("sl", 0),
                                         "first": st.get("last"), "last": st.get("last"), "endTeam": st.get("endTeam"),
                                         "win": [], "live": True})

    def team(self, f, s):
        return self.teams.get(f"{f}-{s}")

    def stints(self, pid, era_from=1947, min_games=1, upto=LAST_COMPLETE):
        """Player-team-seasons he appeared in (regular season), completed seasons only."""
        for s in self.players[pid]["seasons"]:
            if s["s"] < era_from or s["s"] > upto or s["g"] < min_games:
                continue
            if not self.team(s["f"], s["s"]):
                continue
            yield s

    def season_main(self, pid, era_from=1947, min_games=1):
        """season -> (main stint = most games, ties -> later team; end-of-season stint)."""
        by = defaultdict(list)
        for s in self.stints(pid, era_from, min_games):
            by[s["s"]].append(s)
        out = {}
        for sy, lst in by.items():
            main = max(lst, key=lambda x: (x["g"], x.get("last") or ""))
            end = [x for x in lst if x.get("endTeam")] or [max(lst, key=lambda x: x.get("last") or "")]
            out[sy] = (main, end[0], lst)
        return out


def win_pct(t):
    return t["w"] / (t["w"] + t["l"])


def count_flag(d, flag, era_from=1947, min_games=1):
    """Seasons on a team with flag ('worst'/'best'); a season counts once."""
    c = Counter()
    det = defaultdict(list)
    for pid in d.players:
        seen = set()
        for s in d.stints(pid, era_from, min_games):
            t = d.team(s["f"], s["s"])
            if t[flag] and s["s"] not in seen:
                seen.add(s["s"])
                c[pid] += 1
                det[pid].append(s)
    return c, det


def count_sixty(d, era_from=1947, min_games=1):
    c = Counter()
    det = defaultdict(list)
    for pid in d.players:
        seen = set()
        for s in d.stints(pid, era_from, min_games):
            t = d.team(s["f"], s["s"])
            if win_pct(t) >= SIXTY_PACE - 1e-12 and s["s"] not in seen:
                seen.add(s["s"])
                c[pid] += 1
                det[pid].append(s)
    return c, det


def playoff_result(d, s_end, lst):
    """Best playoff finish in a season: teams he appeared for in the playoffs + his end team."""
    best = None
    for s in lst:
        if s is s_end or (s.get("po") and s["po"]["g"] > 0):
            t = d.team(s["f"], s["s"])
            if t and (best is None or PO_DEPTH[t["po"]] > PO_DEPTH[best[0]["po"]]):
                best = (t, s)
    return best


# ---------------------------------------------------------------------------
# Shared small helpers
# ---------------------------------------------------------------------------
def pct(w, l):
    return w / (w + l) if (w + l) else None


def net100(x):
    """[pts for, poss for, pts against, poss against] -> net points per 100 possessions."""
    if not x or x[1] <= 0 or x[3] <= 0:
        return None
    return 100 * (x[0] / x[1] - x[2] / x[3])


def onoff(rm):
    """On/off per 100: net with him on minus net with him off (same games)."""
    if not rm:
        return None
    a, b = net100(rm["on"]), net100(rm["off"])
    if a is None or b is None:
        return None
    return a - b


def per82(t):
    return 82 * win_pct(t)


# ---------------------------------------------------------------------------
# Player career summary
# ---------------------------------------------------------------------------
def summary(d, pid, min_games=1, era_from=1947):
    """Career summary. W-L, with/without and span include the live season when the Data has one;
    season counts (seasons, winning, trips, titles, finish) use completed seasons only."""
    seasons = d.season_main(pid, era_from, min_games)
    w = l = ow = ol = sw = sl = 0
    for s in d.stints(pid, era_from, min_games, upto=CURRENT_SEASON):
        w += s["w"]
        l += s["l"]
        ow += s["ow"]
        ol += s["ol"]
        sw += s.get("sw", 0)        # appearance span (games missed between his first and last game)
        sl += s.get("sl", 0)
    winning = trips = titles = 0
    deepest = None
    rnks = []
    title_years = []
    for sy, (main, end, lst) in sorted(seasons.items()):
        t = d.team(main["f"], sy)
        if win_pct(t) > 0.5:
            winning += 1
        if t["rnk"]:
            rnks.append(t["rnk"])
        pr = playoff_result(d, end, lst)
        if pr and PO_DEPTH[pr[0]["po"]] >= 1:
            trips += 1
            if deepest is None or PO_DEPTH[pr[0]["po"]] > PO_DEPTH[deepest[0]["po"]]:
                deepest = pr
            if pr[0]["po"] == "Champion":
                titles += 1
                title_years.append(sy)
    return {"w": w, "l": l, "ow": ow, "ol": ol, "sw": sw, "sl": sl, "seasons": len(seasons), "winning": winning,
            "trips": trips, "titles": titles, "titleYears": title_years, "deepest": deepest,
            "rnk": (sum(rnks) / len(rnks)) if rnks else None,
            "gap": (pct(w, l) - pct(ow, ol)) if (w + l) and (ow + ol) else None}


# ---------------------------------------------------------------------------
# Lists. Each returns rows (dicts) already sorted; the page renders the top N.
# ---------------------------------------------------------------------------
def list_flag(d, flag, era_from, mg):
    c, det = count_flag(d, flag, era_from, mg)
    rows = [{"pid": k, "n": v, "seasons": sorted(det[k], key=lambda s: s["s"])} for k, v in c.items()]
    rows.sort(key=lambda r: (-r["n"], d.ids[r["pid"]]["name"]))
    return rows


def list_sixty(d, era_from, mg):
    c, det = count_sixty(d, era_from, mg)
    rows = [{"pid": k, "n": v, "seasons": sorted(det[k], key=lambda s: s["s"])} for k, v in c.items() if v]
    rows.sort(key=lambda r: (-r["n"], d.ids[r["pid"]]["name"]))
    return rows


def list_never500(d, era_from, mg, min_seasons=5):
    rows = []
    for pid in d.players:
        st = list(d.stints(pid, era_from, mg))
        seasons = {s["s"] for s in st}
        if len(seasons) < min_seasons:
            continue
        if all(win_pct(d.team(s["f"], s["s"])) < 0.5 for s in st):
            best = max(st, key=lambda s: win_pct(d.team(s["f"], s["s"])))
            rows.append({"pid": pid, "n": len(seasons), "best": best,
                         "g": sum(s["g"] for s in st)})
    rows.sort(key=lambda r: (-r["n"], -r["g"]))
    return rows


def _streak(seq):
    """Longest run of True in [(season, bool)] (seasons he played, in order)."""
    best = (0, None, None)
    cur = 0
    start = None
    for sy, ok in seq:
        if ok:
            if cur == 0:
                start = sy
            cur += 1
            if cur > best[0]:
                best = (cur, start, sy)
        else:
            cur = 0
    return best


def list_winning_streak(d, era_from, mg):
    rows = []
    for pid in d.players:
        seasons = d.season_main(pid, era_from, mg)
        seq = [(sy, win_pct(d.team(m["f"], sy)) > 0.5) for sy, (m, e, lst) in sorted(seasons.items())]
        n, a, b = _streak(seq)
        if n:
            rows.append({"pid": pid, "n": n, "from": a, "to": b})
    rows.sort(key=lambda r: (-r["n"], r["from"]))
    return rows


def list_drought(d, era_from, mg):
    rows = []
    last = {}
    for pid in d.players:
        seasons = d.season_main(pid, era_from, mg)
        seq = []
        for sy, (m, e, lst) in sorted(seasons.items()):
            pr = playoff_result(d, e, lst)
            seq.append((sy, not (pr and PO_DEPTH[pr[0]["po"]] >= 1)))
        n, a, b = _streak(seq)
        if n:
            rows.append({"pid": pid, "n": n, "from": a, "to": b})
            last[pid] = seq[-1][0] if seq else None
    rows.sort(key=lambda r: (-r["n"], r["from"]))
    return rows


def list_franchise(d, era_from, mg, min_games=200, top=3):
    by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for pid in d.players:
        for s in d.stints(pid, era_from, mg):
            x = by[s["f"]][pid]
            x[0] += s["w"]
            x[1] += s["l"]
    out = {}
    for f, ps in by.items():
        rows = [{"pid": pid, "w": v[0], "l": v[1]} for pid, v in ps.items() if v[0] + v[1] >= min_games]
        rows.sort(key=lambda r: (-r["w"], r["l"]))
        if rows:
            out[f] = rows[:top]
    return out


def list_gap_season(d, era_from, mg, min_each=20):
    rows = []
    for pid in d.players:
        for s in d.stints(pid, era_from, max(mg, min_each)):
            if s["ow"] + s["ol"] < min_each:
                continue
            rows.append({"pid": pid, "s": s, "gap": pct(s["w"], s["l"]) - pct(s["ow"], s["ol"])})
    rows.sort(key=lambda r: -r["gap"])
    return rows


def list_gap_career(d, era_from, mg, min_with=200, min_without=50):
    rows = []
    for pid in d.players:
        w = l = ow = ol = 0
        for s in d.stints(pid, era_from, mg):
            w, l, ow, ol = w + s["w"], l + s["l"], ow + s["ow"], ol + s["ol"]
        if w + l >= min_with and ow + ol >= min_without:
            rows.append({"pid": pid, "w": w, "l": l, "ow": ow, "ol": ol,
                         "gap": pct(w, l) - pct(ow, ol)})
    rows.sort(key=lambda r: -r["gap"])
    return rows


def avg_team_pct(d, pid, era_from, mg):
    """Games-weighted average win % of his teams (each stint weighted by his games)."""
    num = den = 0
    for s in d.stints(pid, era_from, mg):
        num += s["g"] * win_pct(d.team(s["f"], s["s"]))
        den += s["g"]
    return num / den if den else None


def accolades(d, pid, era_from):
    return sum(v for y, v in d.players[pid].get("accY", {}).items() if int(y) >= era_from)


def list_bad_luck(d, era_from, mg, min_seasons=5):
    rows = []
    for pid in d.players:
        seasons = {s["s"] for s in d.stints(pid, era_from, mg)}
        if len(seasons) < min_seasons:
            continue
        acc = accolades(d, pid, era_from)
        avg = avg_team_pct(d, pid, era_from, mg)
        if acc <= 0 or avg is None or avg >= 0.5:
            continue
        rows.append({"pid": pid, "acc": acc, "avg": avg, "idx": acc * (0.5 - avg) * 10,
                     "n": len(seasons)})
    rows.sort(key=lambda r: -r["idx"])
    return rows


def title_seasons(d, pid, era_from, mg):
    """[(season, stint on the champion)] where his season ended with a title."""
    out = []
    for sy, (main, end, lst) in sorted(d.season_main(pid, era_from, mg).items()):
        pr = playoff_result(d, end, lst)
        if pr and pr[0]["po"] == "Champion":
            out.append((sy, pr[1]))
    return out


def team_top_scorers(d):
    best = {}
    for pid, p in d.players.items():
        for s in p["seasons"]:
            k = (s["f"], s["s"])
            if s.get("pts", 0) > best.get(k, (0, None))[0]:
                best[k] = (s["pts"], pid)
    return {k: v[1] for k, v in best.items()}


def list_ring_chasers(d, era_from, mg, min_titles=2, max_ppg=6.0):
    rows = []
    for pid in d.players:
        ts = title_seasons(d, pid, era_from, mg)
        if len(ts) < min_titles:
            continue
        g = sum(s["g"] for _, s in ts)
        pts = sum(s.get("pts", 0) for _, s in ts)
        ppg = pts / g if g else 0
        if ppg > max_ppg:
            continue
        rows.append({"pid": pid, "n": len(ts), "ppg": ppg, "years": [y for y, _ in ts]})
    rows.sort(key=lambda r: (-r["n"], r["ppg"]))
    return rows


def list_carriers(d, era_from, mg, top_scorers=None):
    top_scorers = top_scorers or team_top_scorers(d)
    rows = []
    for pid in d.players:
        ts = title_seasons(d, pid, era_from, mg)
        led = [y for y, s in ts if top_scorers.get((s["f"], y)) == pid]
        if led:
            rows.append({"pid": pid, "n": len(led), "years": led, "titles": len(ts)})
    rows.sort(key=lambda r: (-r["n"], -r["titles"]))
    return rows

# (c) 2026 HoopsMatic. All rights reserved.
# Team Success daily list ("Last night in Team Success"). Fingerprint: hm-ts-7f3a91c2-daily
"""Pick the noteworthy items from the last game date by the rules in docs/story-rules.md and write
the day's list to data/stories.json (one entry per UTC date, newest first).

python scripts/daily_story.py [--date 2026-11-19]   # nightly Action, after update_current.py

Every item is one sentence from a template filled from data, with a face or a logo, its scope and
the link to the board row or games that prove it. Ranks use the board's own rule (boards.py:
default view, qualifying group, standard competition ranking with T- ties). "Last night" = the
games of the last game date in data/current.json (its game log), never the previous run's totals.

No item qualifies: "Quiet night" and three items labeled "From the archive". No new games since
the previous list: the list says which games it covers. A later run the same date rewrites the list
only when newer games arrive. Also draws stories/img/<date>.png (the share card).
Prints CHANGED or UNCHANGED.
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis as A  # noqa: E402
import boards as B  # noqa: E402
from common import (CURRENT_SEASON, DATA, LAST_COMPLETE, ROOT, dump_json, era_lookup,  # noqa: E402
                    franchise_name, load_json, season_label)

# the schedule nba-head-to-head reads for "Tonight's duels" (nba-editorial-bots' public Pages site)
SCHEDULE = "https://jsierrahoopshype.github.io/nba-editorial-bots/data/schedule_{season}.csv"
EN, MINUS = "–", "−"
MAX_ITEMS, MIN_ITEMS, ARCHIVE_N = 10, 4, 3
WINS_STEP, WINS_FROM = 100, 300            # career wins milestones: 300, 400, ... 1,000, ...
WL_STEP = 100                              # career W - L milestones: +100, +200, ... (and -100, ...)
PCT_MIN_GAMES, PCT_TOP = 500, 25           # career win %: players with 500+ games, top 25
NOTABLE_RANK, NOTABLE_AS = 100, 3          # a passed player is notable: top 100 on that board, a Hall of Famer or a 3+ time All-Star
PASS_MAX_RANK, PASS_CAP = 250, 4           # the passer is in that board's top 250; at most 4 pass items a night
TYPE_CAP = {"start": 3, "tonight": 2}      # at most 3 team starts and 2 tonight items, so tonight always has room
WW_PLAYED, WW_MISSED = 10, 8               # with/without this season: a real sample
WW_GAP = 0.40                              # ... and a gap of 40+ points, or one side unbeaten / winless
START_MIN, START_GAP = 8, 10               # team start: 8+ games, franchise best/worst since 10+ seasons ago
STREAK_MIN, STREAK_GAP = 5, 10             # team streak: 5+ games, the franchise's longest since 10+ seasons ago
MATCHUP_MIN, MATCHUP_HI, MATCHUP_LO = 15, 0.700, 0.350


def signed(n):
    return ("+" if n > 0 else (MINUS if n < 0 else "")) + f"{abs(n):,}"


def wl(w, l):
    return f"{w}{EN}{l}"


def pct1(p):
    return f"{100 * p:.1f}%"


def nice_date(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    mon = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."][m - 1]
    return f"{mon} {d}, {y}"


def nice_md(iso):
    return nice_date(iso).rsplit(",", 1)[0]


def season_slug(sy=CURRENT_SEASON):
    return f"{sy - 1}-{str(sy)[2:]}"


def et_today():
    """Today's date in US Eastern time (the schedule's game_date_et), like nba-head-to-head's etDate."""
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def schedule(day=None):
    """[(home franchise, away franchise)] for tonight, or (None, None) if the file cannot be read.

    Same source and same reading as nba-head-to-head's "Tonight's duels" (scripts/update_current.py
    and build/build.mjs there): nba-editorial-bots' public schedule CSV, regular-season and playoff
    games (game_id 002 / 004) that are not final, on today's US Eastern date."""
    day = day or et_today()
    try:
        req = urllib.request.Request(SCHEDULE.format(season=season_slug()), headers={"User-Agent": "hoopsmatic-team-success-build"})
        with urllib.request.urlopen(req, timeout=60) as r:
            rows = list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))
        if not rows or "game_id" not in rows[0]:
            raise ValueError("schedule has no rows")
        out = []
        for g in rows:
            if g["game_date_et"] != day or g["status"] == "final" or g["game_id"][:3] not in ("002", "004"):
                continue
            h = era_lookup(g["home_team_tricode"], CURRENT_SEASON)
            a = era_lookup(g["away_team_tricode"], CURRENT_SEASON)
            if h and a:
                out.append((h[0], a[0]))
        return out, day
    except Exception as e:  # network, format: the "tonight" items are skipped
        print(f"schedule not available ({type(e).__name__}: {e})", file=sys.stderr)
        return None, None


def T(text):
    return [text]


def L(text, href, bold=False):
    return [text, href, 1 if bold else 0]


def text_of(parts):
    return "".join(p[0] for p in parts)


def gamelogs():
    for sy in range(1947, LAST_COMPLETE + 1):
        yield sy, load_json(os.path.join(DATA, "gamelog", f"{sy}.json"))


def on_this_day(d, date):
    """Title-winning and 60-win-pace team-seasons with 5+ games by this calendar date."""
    mmdd = date[5:]
    out = []
    for sy, lg in gamelogs():
        yr = sy - 1 if int(mmdd[:2]) >= 8 else sy
        day = f"{yr}-{mmdd}"
        recs = defaultdict(lambda: [0, 0])
        for gid, dd, h, a, hc, ac, hs, as_ in lg["games"]:
            if gid[2] != "2" or dd > day:
                continue
            recs[h][0 if hs > as_ else 1] += 1
            recs[a][0 if as_ > hs else 1] += 1
        for f, (w, l) in recs.items():
            t = d.team(f, sy)
            if not t or w + l < 5:
                continue
            champ = t["po"] == "Champion"
            if champ or t["w"] / max(1, t["w"] + t["l"]) >= 60 / 82:
                out.append((sy, f, w, l, t, champ))
    return out


def build(date):
    d = A.Data(live=True)
    cur = load_json(os.path.join(DATA, "current.json"))
    help_doc = load_json(os.path.join(DATA, "help.json"), {})
    ids = dict(d.ids)
    ids.update(cur.get("newIds", {}))
    stories = load_json(os.path.join(DATA, "stories.json"), {"stories": []})
    through = cur["through"]
    today = [x for x in stories["stories"] if x["date"] == date]
    if today and today[0]["cutoff"] >= through:
        print("UNCHANGED list for", date, "already written with games through", today[0]["cutoff"])
        return False
    stories["stories"] = [x for x in stories["stories"] if x["date"] != date]
    last_cut = max((x["cutoff"] for x in stories["stories"] if x["date"] < date), default="")
    stale = through <= last_cut                 # no new games since the previous list
    if stale and not today and any(x["date"] < date for x in stories["stories"]):
        # a new UTC date but no new games yet (the night's games arrive around 11:00-13:30 UTC):
        # keep the previous list, which already says which games it covers, instead of repeating it
        print("UNCHANGED no new games since the list of", max(x["date"] for x in stories["stories"] if x["date"] < date),
              f"(games through {through})")
        return False
    data = B.compact(d, cur, help_doc)

    def slug(p):
        return ids[p]["slug"]

    def name(p):
        return ids[p]["name"]

    def plink(p, bold=True):
        return L(name(p), f"player/{slug(p)}.html", bold)

    def tname(f, sy=CURRENT_SEASON):
        t = d.team(f, sy)
        return (t["name"] if t else None) or franchise_name(f, sy) or f

    def notable(q, board, rank):
        p = d.players.get(q, {})
        return rank <= NOTABLE_RANK or bool(p.get("hof")) or len(p.get("as", [])) >= NOTABLE_AS

    def most_notable(cands):
        """The most notable passed player: Hall of Famer first, then All-Star selections, then rank."""
        return min(cands, key=lambda x: (-d.players.get(x[0], {}).get("hof", 0),
                                         -len(d.players.get(x[0], {}).get("as", [])), x[1][0]))

    def who_note(q):
        p = d.players.get(q, {})
        n_as = len(p.get("as", []))
        if p.get("hof"):
            return " (Hall of Famer)"
        return f" ({n_as}-time All-Star)" if n_as >= NOTABLE_AS else ""

    items = []

    def add(pri, order, key, parts, href, pid=None, team=None, scope=None, passed=None):
        it = {"key": key, "type": key.split(":")[0], "parts": parts, "href": href, "pid": pid, "team": team, "scope": scope}
        if passed is not None:
            it["passed"] = passed          # every player he passed (slug), for the "most notable" check
        items.append((pri, order, it))

    # ---- last night's games ------------------------------------------------------------------
    log = cur.get("log", {"games": [], "app": {}})
    night = [g for g in log["games"] if g[1] == through]
    delta = defaultdict(lambda: [0, 0])
    played = set()
    for gid, gd, h, a, hs, as_ in night:
        played |= {h, a}
        hp, ap = log["app"].get(gid, [[], []])
        for p in hp:
            delta[str(p)][0 if hs > as_ else 1] += 1
        for p in ap:
            delta[str(p)][0 if as_ > hs else 1] += 1
    delta = {p: v for p, v in delta.items() if p in ids}

    # ---- 1. career wins: round numbers and notable passes --------------------------------------
    def board_items(board, flt, what, fmt, step_fn, link_q=""):
        before, after = B.ranks_before(data, board, delta, flt)
        href = lambda p: f"lists/{board}.html?{link_q}hl={slug(p)}#p-{slug(p)}"  # noqa: E731
        done = set()
        for p in delta:
            if p not in after or p not in before:
                continue
            r, tied, v = after[p]
            v0 = before[p][2]
            m = step_fn(v0, v)
            if m is not None:
                add(1, r, f"{'wins' if board == 'career-wins' else 'wl'}-mark:{slug(p)}:{m}",
                    [plink(p), T(f" reached {fmt(m)} {B.BOARDS[board]['h1'].lower() if board != 'career-wins' else 'career wins in his games'}: "),
                     L(f"{fmt(v)}, {B.rank_label(r, tied)}", href(p)), T(f" on the board ({B.scope_label(board, flt)}).")],
                    href(p), pid=p, scope=B.scope_label(board, flt))
                done.add(p)
        for p, (r, tied, v), passed in B.passes(data, board, delta, flt):
            if p in done or p not in ids or r > PASS_MAX_RANK:
                continue
            nq = [(q, a) for q, a in passed if q in ids and notable(q, board, a[0])]
            if not nq:
                continue
            q, (rq, tq, vq) = most_notable(nq)
            more = f" and {len(passed) - 1} other{'s' if len(passed) > 2 else ''}" if len(passed) > 1 else ""
            add(2, r, f"{'wins' if board == 'career-wins' else 'wl'}-pass:{slug(p)}:{slug(q)}",
                [plink(p), T(" passed "), plink(q, False), T(f"{who_note(q)}{more} for "),
                 L(f"{B.rank_label(r, tied)} in {what}", href(p)), T(f" ({fmt(v)}, {B.scope_label(board, flt)}).")],
                href(p), pid=p, scope=B.scope_label(board, flt), passed=[slug(x) for x, _ in passed if x in ids])

    def round_up(step, start=None):
        def f(v0, v):
            if v is None or v0 is None:
                return None
            for m in range((int(v0) // step + 1) * step, int(v) + 1, step):
                if m >= (start or step) and v0 < m <= v:
                    return m
            return None
        return f

    def wl_mark(v0, v):
        for m in range(-2000, 2001, WL_STEP):
            if m and ((v0 < m <= v) if m > 0 else (v0 > m >= v)):
                return m
        return None
    board_items("career-wins", {}, "career wins", lambda x: f"{x:,}", round_up(WINS_STEP, WINS_FROM))
    board_items("wins-minus-losses", {}, "career W − L", signed, wl_mark)

    # ---- 2. career win %, 500+ games: into the top 25, or a notable pass ----------------------
    pflt = {"sort": "pct", "cg": PCT_MIN_GAMES}
    before, after = B.ranks_before(data, "career-wins", delta, pflt)
    for p in delta:
        if p in after and after[p][0] <= PCT_TOP and (p not in before or before[p][0] > PCT_TOP):
            r, tied, v = after[p]
            href = f"lists/career-wins.html?sort=pct&cg={PCT_MIN_GAMES}&hl={slug(p)}#p-{slug(p)}"
            add(1, r, f"pct-top:{slug(p)}",
                [plink(p), T(f" moved into the top {PCT_TOP} in career win % in his games: "),
                 L(f"{pct1(v)}, {B.rank_label(r, tied)}", href),
                 T(f" among players with {PCT_MIN_GAMES}+ games ({B.SCOPE_LIVE}).")], href, pid=p, scope=B.SCOPE_LIVE)
    for p, (r, tied, v), passed in B.passes(data, "career-wins", delta, pflt):
        if any(x[2]["key"] == f"pct-top:{slug(p)}" for x in items) or r > NOTABLE_RANK:
            continue
        nq = [(q, a) for q, a in passed if q in ids and notable(q, "pct", a[0])]
        if nq:
            q = most_notable(nq)[0]
            more = f" and {len(passed) - 1} other{'s' if len(passed) > 2 else ''}" if len(passed) > 1 else ""
            href = f"lists/career-wins.html?sort=pct&cg={PCT_MIN_GAMES}&hl={slug(p)}#p-{slug(p)}"
            add(2, r, f"pct-pass:{slug(p)}:{slug(q)}",
                [plink(p), T(" passed "), plink(q, False), T(f"{who_note(q)}{more} in career win % in his games: "),
                 L(f"{pct1(v)}, {B.rank_label(r, tied)}", href),
                 T(f" among players with {PCT_MIN_GAMES}+ games ({B.SCOPE_LIVE}).")], href, pid=p, scope=B.SCOPE_LIVE,
                passed=[slug(x) for x, _ in passed if x in ids])

    # ---- 3. teams that played last night: starts and streaks ---------------------------------
    at_n = defaultdict(list)                   # N -> [(sy, f, wins through N)]
    streaks = defaultdict(list)                # f -> [(sy, longest win streak, longest losing streak)]
    for sy, lg in gamelogs():
        seq = defaultdict(list)
        for gid, dd, h, a, hc, ac, hs, as_ in sorted(lg["games"], key=lambda g: (g[1], g[0])):
            if gid[2] == "2":
                seq[h].append(hs > as_)
                seq[a].append(as_ > hs)
        for f, res in seq.items():
            w = 0
            bw = bl = cw = cl = 0
            for i, x in enumerate(res):
                w += x
                if i < 82:
                    at_n[i + 1].append((sy, f, w))
                cw, cl = (cw + 1, 0) if x else (0, cl + 1)
                bw, bl = max(bw, cw), max(bl, cl)
            streaks[f].append((sy, bw, bl))
    tlog = defaultdict(list)
    for gid, gd, h, a, hs, as_ in log["games"]:
        tlog[h].append(hs > as_)
        tlog[a].append(as_ > hs)
    for f in sorted(played):
        res = tlog.get(f, [])
        w, n = sum(res), len(res)
        tn = tname(f)
        href = f"seasons/{season_label(CURRENT_SEASON)}.html#t-{f}"
        if n >= START_MIN:
            own = [x for x in at_n.get(n, []) if x[1] == f]
            for kind in ("best", "worst"):
                hit = [x for x in own if (x[2] >= w if kind == "best" else x[2] <= w)]
                if len(own) < START_GAP:
                    continue
                if not hit:
                    add(3, -len(own), f"start:{kind}:{f}:{n}",
                        [L(f"The {tn}", href, True), T(f" are {wl(w, n - w)}, the franchise's {kind} start through {n} games "
                                                       f"in {len(own) + 1} seasons ({season_label(CURRENT_SEASON)} to date).")],
                        href, team=[f, CURRENT_SEASON], scope=f"{season_label(CURRENT_SEASON)} to date")
                else:
                    sy = max(x[0] for x in hit)
                    if CURRENT_SEASON - sy >= START_GAP:
                        w2 = [x for x in hit if x[0] == sy][0][2]
                        add(3, -(CURRENT_SEASON - sy), f"start:{kind}:{f}:{n}",
                            [L(f"The {tn}", href, True), T(f" are {wl(w, n - w)}, the franchise's {kind} start through {n} games since "),
                             L(f"{season_label(sy)}", f"seasons/{season_label(sy)}.html#t-{f}"), T(f" ({wl(w2, n - w2)}).")],
                            href, team=[f, CURRENT_SEASON], scope=f"{season_label(CURRENT_SEASON)} to date")
        k = 0
        for x in reversed(res):
            if x == res[-1]:
                k += 1
            else:
                break
        if res and k >= STREAK_MIN:
            won = res[-1]
            hist = [(sy, bw if won else bl) for sy, bw, bl in streaks.get(f, [])]
            longer = [sy for sy, v in hist if v >= k]
            word = "winning" if won else "losing"
            if not longer and len(hist) >= START_GAP:
                tail = f", the longest in franchise history ({len(hist) + 1} seasons)."
            elif longer and CURRENT_SEASON - max(longer) >= STREAK_GAP:
                tail = f", the franchise's longest since {season_label(max(longer))}."
            else:
                tail = None
            if tail:
                add(3, -k, f"streak:{f}:{word}:{k}",
                    [L(f"The {tn}", href, True), T(f" have a {k}-game {word} streak{tail}")],
                    href, team=[f, CURRENT_SEASON], scope=f"{season_label(CURRENT_SEASON)} to date")

    # ---- 4. with / without this season, a real sample, his team played last night -------------
    for p, sts in cur["players"].items():
        if p not in ids:
            continue
        st = ([x for x in sts if x.get("endTeam")] or sts[-1:])[0]
        gm = st["ow"] + st["ol"]
        if st["f"] not in played or st["g"] < WW_PLAYED or gm < WW_MISSED:
            continue
        gap = st["w"] / st["g"] - st["ow"] / gm
        if not (abs(gap) >= WW_GAP or st["ow"] in (0, gm) or st["w"] in (0, st["g"])):
            continue
        tn = tname(st["f"])
        href = f"lists/winning-without-him.html?mp={WW_PLAYED}&mm={WW_MISSED}&hl={slug(p)}#p-{slug(p)}"
        add(4, -abs(gap), f"ww:{slug(p)}",
            [T(f"The {tn} are "), L(f"{wl(st['ow'], st['ol'])} without ", href), plink(p),
             T(f" and {wl(st['w'], st['l'])} with him ({season_label(CURRENT_SEASON)} to date, {st['g']} played, {gm} missed).")],
            href, pid=p, scope=f"{season_label(CURRENT_SEASON)} to date")

    # ---- 5. tonight: a notable record against tonight's opponent (15+ games) -------------------
    games, gdate = schedule()
    if games:
        playing = {}
        for h, a in games:
            playing[h], playing[a] = a, h
        want = {p for p, sts in cur["players"].items() if p in d.players and p in ids and
                ([x for x in sts if x.get("endTeam")] or sts[-1:])[0]["f"] in playing}
        rec = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        for sy, lg in gamelogs():
            for gid, dd, h, a, hc, ac, hs, as_ in lg["games"]:
                if gid[2] != "2":
                    continue
                hp, ap = lg["app"][gid]
                for q in hp:
                    if str(q) in want:
                        rec[str(q)][a][0 if hs > as_ else 1] += 1
                for q in ap:
                    if str(q) in want:
                        rec[str(q)][h][0 if as_ > hs else 1] += 1
        for p in want:
            f = ([x for x in cur["players"][p] if x.get("endTeam")] or cur["players"][p][-1:])[0]["f"]
            opp = playing[f]
            w, l = rec[p].get(opp, [0, 0])
            if w + l < MATCHUP_MIN or MATCHUP_LO < w / (w + l) < MATCHUP_HI:
                continue
            href = f"player/{slug(p)}.html?vs={opp}#vs-{opp}"
            add(5, -abs(w / (w + l) - 0.5), f"tonight:{slug(p)}:{opp}",
                [T(f"Tonight vs the {tname(opp)}: "), plink(p), T("'s teams are "),
                 L(f"{wl(w, l)} ({pct1(w / (w + l))})", href), T(f" in his {w + l} regular-season games against them ({B.SCOPE_DONE}).")],
                href, pid=p, scope=B.SCOPE_DONE)

    # ---- pick ---------------------------------------------------------------------------------
    items.sort(key=lambda x: (x[0], x[1]))
    picked, seen, npass = [], set(), 0
    for _, _, it in items:
        who = it["pid"] or (it["team"][0] if it["team"] else None)
        if who in seen:
            continue
        if it["type"].endswith("-pass"):
            if npass >= PASS_CAP:
                continue
            npass += 1
        if it["type"] in TYPE_CAP:
            if sum(1 for x in picked if x["type"] == it["type"]) >= TYPE_CAP[it["type"]]:
                continue
        picked.append(it)
        seen.add(who)
        if len(picked) >= MAX_ITEMS:
            break
    quiet = not picked
    if len(picked) < MIN_ITEMS:
        # a quiet night (or a short one): items from the archive, clearly labeled, never repeated
        # within 30 days
        used = {it["key"] for x in stories["stories"]
                if 0 < (dt.date.fromisoformat(date) - dt.date.fromisoformat(x["date"])).days <= 30
                for it in x.get("items", [])}
        hc = on_this_day(d, date)
        k = dt.date.fromisoformat(date).toordinal()
        need = ARCHIVE_N if quiet else MIN_ITEMS - len(picked)
        for i in range(len(hc)):
            if need <= 0:
                break
            sy, f, w, l, t, champ = hc[(k * 7 + i * 13) % len(hc)]
            key = f"archive:{sy}:{f}"
            if key in used:
                continue
            end = (f"finished {wl(t['w'], t['l'])} and won the title" if champ else
                   f"finished {wl(t['w'], t['l'])}, a {round(82 * t['w'] / (t['w'] + t['l']))}-win pace over 82 games")
            href = f"seasons/{season_label(sy)}.html#t-{f}"
            picked.append({"key": key, "type": "archive", "archive": 1, "pid": None, "team": [f, sy],
                           "parts": [T(f"On this date in {season_label(sy)}, the "), L(t["name"], href, True),
                                     T(f" were {wl(w, l)}. They {end}.")], "href": href, "scope": season_label(sy)})
            used.add(key)
            need -= 1
    head = f"Last night in Team Success · {nice_md(through)} games"
    entry = {"date": date, "kind": "night", "cutoff": through, "games_date": through, "stale": 1 if stale else 0,
             "quiet": 1 if quiet else 0, "games": len(night), "items": picked, "headline": head,
             "body": [text_of(it["parts"]) for it in picked],
             "players": [slug(it["pid"]) for it in picked if it.get("pid")],
             "rule": "night", "img": f"stories/img/{date}.png"}
    stories["stories"].insert(0, entry)
    stories["stories"].sort(key=lambda x: x["date"], reverse=True)
    dump_json(os.path.join(DATA, "stories.json"), stories, compact=False)
    draw(entry)
    print("CHANGED list for", date, f"({nice_md(through)} games):", ", ".join(it["type"] for it in picked) or "quiet")
    return True


def draw(story):
    """The day's share card: the list's headline and its first three items."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    fd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

    def font(size, weight=400):
        f = ImageFont.truetype(os.path.join(fd, "DMSans.ttf"), size)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        return f

    def wrap(g, text, f, width):
        words, lines, cur = text.split(), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if g.textlength(t, font=f) > width:
                lines.append(cur)
                cur = wd
            else:
                cur = t
        lines.append(cur)
        return lines
    im = Image.new("RGB", (W, H), "#f5f5f7")
    g = ImageDraw.Draw(im)
    g.rounded_rectangle((36, 36, W - 36, H - 36), 24, fill="#ffffff", outline="#d1d1d6", width=2)
    g.text((76, 66), story["headline"], font=font(34, 700), fill="#1d1d1f")
    y = 132
    bf = font(26, 500)
    for txt in story["body"][:3]:
        lines = wrap(g, txt, bf, W - 190)[:3]
        g.ellipse((78, y + 10, 90, y + 22), fill="#1d1d1f")
        for ln in lines:
            g.text((108, y), ln, font=bf, fill="#1d1d1f")
            y += 36
        y += 18
        if y > H - 150:
            break
    g.text((76, H - 92), f"Games through {nice_date(story['cutoff'])}. Records are his teams' in his games.",
           font=font(22, 500), fill="#6e6e73")
    g.text((W - 76, H - 92), "hoopsmatic.com/team-success", font=font(22, 600), fill="#3b82f6", anchor="ra")
    out = os.path.join(ROOT, story["img"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.quantize(colors=64, method=Image.Quantize.FASTOCTREE).save(out, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    build(ap.parse_args().date)


if __name__ == "__main__":
    main()

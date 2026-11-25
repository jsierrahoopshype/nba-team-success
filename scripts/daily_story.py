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
import phrasing as PH  # noqa: E402
from common import (CURRENT_SEASON, DATA, LAST_COMPLETE, ROOT, dump_json, era_lookup,  # noqa: E402
                    franchise_name, load_json, season_label)

# the schedule nba-head-to-head reads for "Tonight's duels" (nba-editorial-bots' public Pages site)
SCHEDULE = "https://jsierrahoopshype.github.io/nba-editorial-bots/data/schedule_{season}.csv"
EN, MINUS = "–", "−"
MAX_ITEMS, MIN_ITEMS, ARCHIVE_N = 10, 4, 3
WINS_STEP, WINS_FROM = 100, 300            # career wins milestones: 300, 400, ... 1,000, ...
WL_STEP = 100                              # career W - L milestones: +100, +200, ... (and -100, ...)
PCT_MIN_GAMES, PCT_TOP = 500, 25           # career win %: players with 500+ games, top 25
# players passed: 1 to 5 are all named; 6+: the 2 most notable, then "and N others" (N is then 4+)
NAMES_MAX, NAMES_SHOWN = 6, 2
RANK_SHOWN_MAX = 1000                      # a milestone's rank is left out when worse than No. 1,000
NOTABLE_RANK, NOTABLE_AS = 100, 3          # a passed player is notable: top 100 on that board, a Hall of Famer or a 3+ time All-Star
PASS_MAX_RANK, PASS_CAP = 250, 4           # the passer is in that board's top 250; at most 4 pass items a night
TYPE_CAP = {"start": 3, "tonight": 2}      # at most 3 team starts and 2 tonight items, so tonight always has room
WW_PLAYED, WW_MISSED = 10, 8               # with/without this season: a real sample
WW_GAP = 0.40                              # ... and a gap of 40+ points, or one side unbeaten / winless
START_MIN, START_GAP = 8, 10               # team start: 8+ games, franchise best/worst since 10+ seasons ago
STREAK_MIN, STREAK_GAP = 5, 10             # team streak: 5+ games, the franchise's longest since 10+ seasons ago
MATCHUP_MIN, MATCHUP_HI, MATCHUP_LO = 15, 0.700, 0.350


def hof_role(p):
    """A players.json row's Hall of Fame role: "player", "coach", "contributor" or None.
    awards.json's own "Hall of Fame" rows are all "player"; data/hof_extra.json adds the rest."""
    return (p.get("hofRole") or "player") if p.get("hof") else None


def is_notable(p, rank):
    """A passed player is notable: top 100 on that board, a Hall of Famer (any role) or a 3+ time All-Star."""
    return rank <= NOTABLE_RANK or bool(hof_role(p)) or len(p.get("as", [])) >= NOTABLE_AS


def notable_key(p, rank):
    """Sort key, lowest = most notable: Hall of Famer as a player first, then All-Star selections, then
    Hall of Famer as a coach or contributor, then rank (so Pat Riley never outranks a 5-time All-Star)."""
    role = hof_role(p)
    return (-(role == "player"), -len(p.get("as", [])), -(role in ("coach", "contributor")), rank)


def note_of(p):
    """The label after a passed player's name."""
    role = hof_role(p)
    if role == "player":
        return " (Hall of Famer)"
    if role in ("coach", "contributor"):
        return f" (Hall of Famer as a {role})"
    n_as = len(p.get("as", []))
    return f" ({n_as}-time All-Star)" if n_as >= NOTABLE_AS else ""


def join_names(entries, more_href):
    """[(name link part, label)] in order -> parts: "A (Hall of Famer)", "A and B", "A, B and C";
    6 or more: the first 2, then "and N others" (N >= 4) linking to more_href."""
    shown = entries if len(entries) < NAMES_MAX else entries[:NAMES_SHOWN]
    parts = []
    for i, (link, note) in enumerate(shown):
        if i:
            parts.append(T(" and " if i == len(shown) - 1 and len(shown) == len(entries) else ", "))
        parts.append(link)
        if note:
            parts.append(T(note))
    if len(shown) < len(entries):
        parts += [T(" and "), L(f"{len(entries) - len(shown)} others", more_href)]
    return parts


def archive_slots(season, team_link, rec, t, champ):
    """(set, slots) for a team-season on this date (archive items, on-this-day fun facts)."""
    pace = round(82 * t["w"] / (t["w"] + t["l"]))
    ap = PH.article(f"{pace}")
    return ("archive-title" if champ else "archive-pace",
            {"season": season, "team": team_link, "rec": rec, "final": wl(t["w"], t["l"]), "pace": f"{pace}",
             "ap": ap, "AP": ap.capitalize()})


def tonight_slots(player, opp_name, rec_link, rate):
    """(set, slots) for "tonight": his teams' record against tonight's opponent (incl. the season to date,
    like his opponent row). Good records read upbeat, bad ones dry."""
    pct = pct1(rate)
    return ("tonight-good" if rate >= 0.5 else "tonight-bad",
            {"P": player, "opp": f"the {opp_name}", "Opp": f"The {opp_name}", "rec": rec_link,
             "pct": pct, "a": PH.article(pct)})


def tonight_parts(player, opp_name, rec_link, rate, date="", subject="", used=None):
    """The rendered "tonight" sentence (one template of the set, picked like every other item)."""
    kind, slots = tonight_slots(player, opp_name, rec_link, rate)
    return PH.render(PH.pick(kind, date, subject, used if used is not None else set())[1], slots)


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
        return is_notable(d.players.get(q, {}), rank)

    def most_notable(cands):
        """The most notable passed player (see notable_key)."""
        return min(cands, key=lambda x: notable_key(d.players.get(x[0], {}), x[1][0]))

    def who_note(q):
        return note_of(d.players.get(q, {}))

    def passed_names(passed, rank_of, more_href):
        """Every player passed, linked, labels kept, most notable first: "A (Hall of Famer), B and C".
        8 or more: the 7 most notable, then "and N more players" linking to the board at that spot."""
        qs = sorted([q for q, a in passed if q in ids],
                    key=lambda q: notable_key(d.players.get(q, {}), rank_of(q)))
        return join_names([(plink(q, False), who_note(q)) for q in qs], more_href)

    items = []

    def add(pri, order, key, kind, slots, href, pid=None, team=None, scope=None, passed=None):
        """kind / slots: the sentence's template set and its values (phrasing.py); the sentence itself is
        written once the list is picked, so no template repeats within the list."""
        it = {"key": key, "type": key.split(":")[0], "_k": kind, "_s": slots, "href": href, "pid": pid, "team": team,
              "scope": scope}
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
                kind = "wins-mark" if board == "career-wins" else ("wl-mark-up" if m > 0 else "wl-mark-down")
                add(1, r, f"{'wins' if board == 'career-wins' else 'wl'}-mark:{slug(p)}:{m}", kind,
                    {"P": plink(p), "M": L(f"{abs(m):,}", href(p)),
                     # a rank worse than No. 1,000 says nothing: the milestone stands alone
                     "rank": L(B.rank_label(r, tied), href(p)) if r <= RANK_SHOWN_MAX and m > 0 else None},
                    href(p), pid=p, scope=B.scope_label(board, flt))
                done.add(p)
        for p, (r, tied, v), passed in B.passes(data, board, delta, flt):
            if p in done or p not in ids or r > PASS_MAX_RANK:
                continue
            nq = [(q, a) for q, a in passed if q in ids and notable(q, board, a[0])]
            if not nq:
                continue
            q, (rq, tq, vq) = most_notable(nq)
            ranks = {x: a[0] for x, a in passed}
            add(2, r, f"{'wins' if board == 'career-wins' else 'wl'}-pass:{slug(p)}:{slug(q)}",
                "wins-pass" if board == "career-wins" else "wl-pass",
                {"P": plink(p), "names": passed_names(passed, ranks.get, href(p)),
                 "rank": L(B.rank_label(r, tied), href(p)), "val": fmt(v)},
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
            add(1, r, f"pct-top:{slug(p)}", "pct-top",
                {"P": plink(p), "pct": pct1(v), "rank": L(B.rank_label(r, tied), href), "mins": f"{PCT_MIN_GAMES}"},
                href, pid=p, scope=B.SCOPE_LIVE)
    for p, (r, tied, v), passed in B.passes(data, "career-wins", delta, pflt):
        if any(x[2]["key"] == f"pct-top:{slug(p)}" for x in items) or r > NOTABLE_RANK:
            continue
        nq = [(q, a) for q, a in passed if q in ids and notable(q, "pct", a[0])]
        if nq:
            q = most_notable(nq)[0]
            href = f"lists/career-wins.html?sort=pct&cg={PCT_MIN_GAMES}&hl={slug(p)}#p-{slug(p)}"
            ranks = {x: a[0] for x, a in passed}
            add(2, r, f"pct-pass:{slug(p)}:{slug(q)}", "pct-pass",
                {"P": plink(p), "names": passed_names(passed, ranks.get, href), "pct": pct1(v),
                 "rank": L(B.rank_label(r, tied), href), "mins": f"{PCT_MIN_GAMES}"}, href, pid=p, scope=B.SCOPE_LIVE,
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
                    add(3, -len(own), f"start:{kind}:{f}:{n}", f"start-fr-ever-{kind}",
                        {"Team": L(f"The {tn}", href, True), "team": L(f"the {tn}", href, True), "rec": wl(w, n - w),
                         "n": f"{n}", "k": f"{len(own) + 1}"},
                        href, team=[f, CURRENT_SEASON], scope=f"{season_label(CURRENT_SEASON)} to date")
                else:
                    sy = max(x[0] for x in hit)
                    if CURRENT_SEASON - sy >= START_GAP:
                        w2 = [x for x in hit if x[0] == sy][0][2]
                        add(3, -(CURRENT_SEASON - sy), f"start:{kind}:{f}:{n}", f"start-fr-since-{kind}",
                            {"Team": L(f"The {tn}", href, True), "team": L(f"the {tn}", href, True), "rec": wl(w, n - w),
                             "n": f"{n}", "then": L(f"{season_label(sy)}", f"seasons/{season_label(sy)}.html#t-{f}"),
                             "then_rec": wl(w2, n - w2)},
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
            slots = {"Team": L(f"The {tn}", href, True), "team": L(f"the {tn}", href, True), "k": f"{k}"}
            side = "win" if won else "lose"
            if not longer and len(hist) >= START_GAP:
                kind = f"streak-{side}-ever"
                slots["S"] = f"{len(hist) + 1}"
            elif longer and CURRENT_SEASON - max(longer) >= STREAK_GAP:
                kind = f"streak-{side}-since"
                slots["then"] = season_label(max(longer))
            else:
                kind = None
            if kind:
                add(3, -k, f"streak:{f}:{word}:{k}", kind, slots,
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
        add(4, -abs(gap), f"ww:{slug(p)}", "ww-with" if gap > 0 else "ww-without",
            {"Tm": f"The {tn}", "tm": f"the {tn}", "P": plink(p), "wo": L(wl(st['ow'], st['ol']), href),
             "w": wl(st['w'], st['l']), "g": f"{st['g']}", "m": f"{gm}"},
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
        # the season to date too (current.json's game log), like the opponent row the item links to
        lg = cur.get("log") or {}
        for gid, dd, h, a, hs, as_ in lg.get("games", []):
            if gid[2] != "2":
                continue
            hp, ap = lg["app"].get(gid, [[], []])
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
                *tonight_slots(plink(p), tname(opp), L(wl(w, l), href), w / (w + l)),
                href, pid=p, scope=B.SCOPE_LIVE)

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
            href = f"seasons/{season_label(sy)}.html#t-{f}"
            kind, slots = archive_slots(season_label(sy), L(t["name"], href, True), wl(w, l), t, champ)
            picked.append({"key": key, "type": "archive", "archive": 1, "pid": None, "team": [f, sy],
                           "_k": kind, "_s": slots, "href": href, "scope": season_label(sy)})
            used.add(key)
            need -= 1
    # one sentence per item, no template twice in the list (phrasing.pick: hash of date, set, subject)
    used_tpl = set()
    for it in picked:
        kind, slots = it.pop("_k"), it.pop("_s")
        i, tpl = PH.pick(kind, date, it["pid"] or (it["team"][0] if it.get("team") else it["key"]), used_tpl)
        it["parts"], it["tpl"] = PH.render(tpl, slots), f"{kind}#{i}"
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


def draw_single(story):
    """The share card of the single-story format (lists before Nov. 19, 2026): label, headline, the
    first body sentence. Same layout as when those stories were published."""
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
    g.text((76, 70), f"Today in Team Success · {nice_date(story['date'])}", font=font(26, 600), fill="#6e6e73")
    hf = font(52, 700)
    y = 130
    for ln in wrap(g, story["headline"], hf, W - 152)[:3]:
        g.text((76, y), ln, font=hf, fill="#1d1d1f")
        y += 64
    bf = font(28, 500)
    y += 20
    for ln in wrap(g, story["body"][0], bf, W - 152)[:4]:
        g.text((76, y), ln, font=bf, fill="#1d1d1f")
        y += 40
    g.text((76, H - 92), f"Data through {nice_date(story['cutoff'])}. Records are his teams' in his games.",
           font=font(22, 500), fill="#6e6e73")
    g.text((W - 76, H - 92), "hoopsmatic.com/team-success", font=font(22, 600), fill="#3b82f6", anchor="ra")
    out = os.path.join(ROOT, story["img"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.quantize(colors=64, method=Image.Quantize.FASTOCTREE).save(out, optimize=True)


IMG_HASH = os.path.join(DATA, "story_img_hash.json")


def drawn_text(story):
    """Exactly the text a story's share card shows, so its hash moves only when the image would."""
    night = story.get("kind") == "night"
    return {"kind": "night" if night else "single", "date": story["date"], "headline": story["headline"],
            "body": story.get("body", [])[:3 if night else 1], "cutoff": story["cutoff"]}


def img_hash(story):
    import hashlib
    txt = json.dumps(drawn_text(story), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def sync_images(stories=None):
    """Redraw stories/img/<date>.png only for entries whose drawn text changed since the image was
    drawn (data/story_img_hash.json), or whose image is missing. Everything else is left byte for
    byte as it is, so a run with no text change commits nothing. Returns the redrawn dates."""
    if stories is None:
        stories = load_json(os.path.join(DATA, "stories.json"), {"stories": []})["stories"]
    old = load_json(IMG_HASH, {})
    new, redrawn = {}, []
    for st in stories:
        if not st.get("img"):
            continue
        h = img_hash(st)
        new[st["date"]] = h
        if old.get(st["date"]) != h or not os.path.exists(os.path.join(ROOT, st["img"])):
            (draw if st.get("kind") == "night" else draw_single)(st)
            redrawn.append(st["date"])
    dump_json(IMG_HASH, new, compact=False)
    return redrawn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    build(ap.parse_args().date)
    # share images whose text changed (today's list, or an older entry rewritten in place)
    redrawn = sync_images()
    if redrawn:
        print("CHANGED share images redrawn:", ", ".join(sorted(redrawn)))


if __name__ == "__main__":
    main()

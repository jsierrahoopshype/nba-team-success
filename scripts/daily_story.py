# (c) 2026 HoopsMatic. All rights reserved.
# Team Success daily lead ("Today in Team Success"). Fingerprint: hm-ts-7f3a91c2-daily
"""Pick today's story by the rules in docs/story-rules.md and write it to data/stories.json.

python scripts/daily_story.py [--date 2026-11-18]   # nightly Action, after update_current.py

Every sentence is a template filled from data. Sources: committed data (career boards, game logs,
current.json, help.json) and tonight's schedule from cdn.nba.com (public JSON, no key; if it cannot
be fetched, the matchup candidates are skipped). Keeps data/stories_state.json (yesterday's career
W - L and absence records) to detect passes and thresholds. One story per date; a date that already
has a story is left alone. Also draws stories/img/<date>.png with Pillow and the site's fonts.
Prints CHANGED or UNCHANGED.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis as A  # noqa: E402
import boards as B  # noqa: E402
import picks  # noqa: E402
from common import (CURRENT_SEASON, DATA, LAST_COMPLETE, ROOT, dump_json, era_lookup,  # noqa: E402
                    franchise_name, load_json, season_label)

SCHEDULE = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
EN, MINUS = "–", "−"
MIN_ABSENCE = 8          # homepage cutoff: 8+ games played AND 8+ missed (boards use 5)
MATCHUP_MIN = 15         # regular-season games against that franchise
MATCHUP_MAX_PCT = 0.40
REPEAT_DAYS = 30         # a lead (rule + players) never repeats within 30 days


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


def schedule():
    """[(home franchise, away franchise)] for tonight, or None if the feed cannot be read."""
    try:
        req = urllib.request.Request(SCHEDULE, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            doc = json.loads(r.read())
        out = []
        for g in doc["scoreboard"]["games"]:
            h = era_lookup(g["homeTeam"]["teamTricode"], CURRENT_SEASON)
            a = era_lookup(g["awayTeam"]["teamTricode"], CURRENT_SEASON)
            if h and a and g.get("gameStatus", 1) == 1:
                out.append((h[0], a[0]))
        return out, doc["scoreboard"].get("gameDate")
    except Exception as e:  # network, format: the story falls back to other candidates
        print(f"schedule not available ({type(e).__name__})", file=sys.stderr)
        return None, None


def opp_record(pid, logs_by_pid, opp):
    w = l = 0
    for won, o in logs_by_pid.get(pid, ()):
        if o == opp:
            w, l = w + won, l + (not won)
    return w, l


def build(date):
    d = A.Data()
    cur = load_json(os.path.join(DATA, "current.json"))
    ids = dict(d.ids)
    ids.update(cur.get("newIds", {}))
    stories = load_json(os.path.join(DATA, "stories.json"), {"stories": []})
    state = load_json(os.path.join(DATA, "stories_state.json"), {})
    through = cur["through"]
    today = [x for x in stories["stories"] if x["date"] == date]
    if today and today[0]["cutoff"] >= through:
        print("UNCHANGED story for", date, "already written with data through", today[0]["cutoff"])
        return False
    if today:
        # an earlier run today wrote the story from older data: rewrite it, comparing with the
        # state from before that run (the previous date's), not with the earlier run's
        stories["stories"] = [x for x in stories["stories"] if x["date"] != date]
        state = state.get("base", {}) if state.get("date") == date else state
    base_state = {k: v for k, v in state.items() if k != "base"}
    # leads of the last 30 days: the same story (rule + players) never leads twice in 30 days
    recent = {(x["rule"], tuple(x.get("players", []))) for x in stories["stories"]
              if 0 < (dt.date.fromisoformat(date) - dt.date.fromisoformat(x["date"])).days <= REPEAT_DAYS}
    data = B.compact(d, cur)
    comp = {}
    for row in data["p"]:
        m = B.player_metrics(row, data["t"], {})
        comp[row[0]] = m["w"] - m["l"]
    cur_wl = {pid: sum(x["w"] - x["l"] for x in sts) for pid, sts in cur["players"].items()}
    total = dict(comp)
    for pid, v in cur_wl.items():
        total[pid] = total.get(pid, 0) + v
    order = sorted(total, key=lambda p: (-total[p], ids.get(p, {}).get("name", "")))
    rank = {p: i + 1 for i, p in enumerate(order)}

    def name(p):
        return ids[p]["name"]

    def plink(p):
        return f"player/{ids[p]['slug']}.html"

    cands = []
    # (a) passed someone on the career W - L board in the games of the last game date, worked out
    # from the season's game log (not from the previous run's totals, which code changes can move);
    # only when those games are newer than the previous story's cutoff
    last_cut = max((x["cutoff"] for x in stories["stories"] if x["date"] < date), default="")
    prev = None
    if through > last_cut and cur.get("log"):
        delta = defaultdict(int)
        lg_ = cur["log"]
        for gid, gd, h, a, hs, as_ in lg_["games"]:
            if gd != through:
                continue
            hp_, ap_ = lg_["app"].get(gid, [[], []])
            for q in hp_:
                delta[str(q)] += 1 if hs > as_ else -1
            for q in ap_:
                delta[str(q)] += 1 if as_ > hs else -1
        prev = {q: v - delta.get(q, 0) for q, v in total.items()}
    if prev:
        for p in cur["players"]:
            if p not in prev or p not in total:
                continue
            passed = [q for q in prev if q != p and prev[p] <= prev[q] and total[p] > total.get(q, prev[q])]
            if passed and rank[p] <= 200:
                q = min(passed, key=lambda q: rank.get(q, 10 ** 6))
                cands.append((1, rank[p], {
                    "rule": "pass",
                    "players": [ids[p]["slug"], ids[q]["slug"]],
                    "headline": f"{name(p)} passes {name(q)} on the career wins-minus-losses list",
                    "body": [f"{name(p)}'s teams are {signed(total[p])} in his regular-season games: {signed(comp.get(p, 0))} "
                             f"through {season_label(LAST_COMPLETE)} and {signed(cur_wl[p])} in {season_label(CURRENT_SEASON)}.",
                             f"That is #{rank[p]} all time counting this season, ahead of {name(q)} "
                             f"({signed(total.get(q, prev[q]))})."],
                    "link": {"text": f"{name(p)}'s page", "href": plink(p)},
                    "more": {"text": "Career W − L board (completed seasons)", "href": f"lists/wins-minus-losses.html?hl={ids[p]['slug']}#p-{ids[p]['slug']}"},
                    "line": f"{name(p)} passed {name(q)} on the career W − L list."}))
    # (b) tonight's matchup against his toughest franchise
    games, gdate = schedule()
    if games:
        logs = defaultdict(list)
        for sy in range(1947, LAST_COMPLETE + 1):
            lg = load_json(os.path.join(DATA, "gamelog", f"{sy}.json"))
            for gid, dd, h, a, hc, ac, hs, as_ in lg["games"]:
                if gid[2] != "2":
                    continue
                hp, ap = lg["app"][gid]
                for q in hp:
                    logs[str(q)].append((hs > as_, a))
                for q in ap:
                    logs[str(q)].append((as_ > hs, h))
        playing = {}
        for h, a in games:
            playing[h] = a
            playing[a] = h
        for p, sts in cur["players"].items():
            if p not in comp:
                continue
            team = [x for x in sts if x.get("endTeam")] or sts[-1:]
            f = team[0]["f"]
            if f not in playing or sum(1 for _ in logs.get(p, ())) < 300:
                continue
            opp = playing[f]
            by = defaultdict(lambda: [0, 0])
            for won, o in logs[p]:
                by[o][0 if won else 1] += 1
            w, l = by.get(opp, [0, 0])
            if w + l < MATCHUP_MIN or w / (w + l) > MATCHUP_MAX_PCT:
                continue
            lowest = min((v[0] / (v[0] + v[1]), o) for o, v in by.items() if v[0] + v[1] >= MATCHUP_MIN)[1] == opp
            on = franchise_name(opp, CURRENT_SEASON)
            tn = franchise_name(f, CURRENT_SEASON)
            cands.append((2, w / (w + l), {
                "rule": "matchup",
                "players": [ids[p]["slug"]],
                "headline": f"Tonight: {name(p)} and the {tn} face the {on}",
                "body": [f"In his {w + l} regular-season games against the {on} franchise, his teams are {wl(w, l)} "
                         f"({pct1(w / (w + l))})" + (", his lowest win rate against any franchise he has faced "
                                                     f"{MATCHUP_MIN}+ times." if lowest else ".")],
                "link": {"text": f"{name(p)} against the {on}, game by game", "href": f"{plink(p)}?vs={opp}#vs-{opp}"},
                "line": f"Tonight: {name(p)} is {wl(w, l)} against the {on} in his games."}))
    # (a') climbed the most places on the career W - L list this season
    base = sorted(comp, key=lambda p: (-comp[p], ids.get(p, {}).get("name", "")))
    base_rank = {p: i + 1 for i, p in enumerate(base)}
    climbs = []
    for p in cur["players"]:
        if p in base_rank and rank[p] <= 300:
            gain = base_rank[p] - rank[p]
            if gain > 0:
                passed = [q for q in comp if comp[q] >= comp[p] and total.get(q, comp[q]) < total[p] and q != p]
                if passed:
                    # the passed player named in the story: highest Accolade score (Teammates Score weights)
                    top = max(passed, key=lambda q: (d.players.get(q, {}).get("acc", 0), -base_rank[q]))
                    # a top-100 player's climb comes first (best rank), then the biggest climb
                    key = (0, rank[p]) if rank[p] <= 100 else (1, -gain)
                    climbs.append((key, rank[p], p, len(passed), top))
    if climbs:
        g, r, p, n, q = min(climbs)
        cands.append((3, r, {
            "rule": "climb",
            "players": [ids[p]["slug"], ids[q]["slug"]],
            "headline": f"{name(p)} moves past {name(q)} on the career wins-minus-losses list",
            "body": [f"His teams are {signed(cur_wl[p])} in his {season_label(CURRENT_SEASON)} games, which takes his career "
                     f"total to {signed(total[p])}: #{rank[p]} all time counting this season, up from #{base_rank[p]} at the "
                     f"end of {season_label(LAST_COMPLETE)}.",
                     f"He has passed {n} player{'s' if n != 1 else ''} this season; the most decorated of them is "
                     f"{name(q)} ({signed(total.get(q, comp[q]))})."],
            "link": {"text": f"{name(p)}'s page", "href": plink(p)},
            "more": {"text": "Career W − L board (completed seasons)", "href": f"lists/wins-minus-losses.html?hl={ids[p]['slug']}#p-{ids[p]['slug']}"},
            "line": f"{name(p)} has passed {n} players on the career W − L list this season."}))
    # (c) a team crossed 10 wins in the games a player missed (stricter cutoff: 8+ each side)
    prev_ow = state.get("ow", {})
    for p, sts in cur["players"].items():
        st = ([x for x in sts if x.get("endTeam")] or sts[-1:])[0]
        if st["g"] < MIN_ABSENCE or st["ow"] + st["ol"] < MIN_ABSENCE:
            continue
        if st["ow"] >= 10 > prev_ow.get(p, 10 ** 6):
            tn = franchise_name(st["f"], CURRENT_SEASON)
            cands.append((4, -st["ow"], {
                "rule": "absence",
                "players": [ids[p]["slug"]],
                "headline": f"The {tn} reach 10 wins in the games {name(p)} has missed",
                "body": [f"They are {wl(st['ow'], st['ol'])} without him and {wl(st['w'], st['l'])} in his {st['g']} games "
                         f"this season (minimum {MIN_ABSENCE} games each side for this page)."],
                "link": {"text": f"{season_label(CURRENT_SEASON)} with and without board", "href": "lists/winning-without-him.html"},
                "line": f"The {tn} are {wl(st['ow'], st['ol'])} in games {name(p)} missed."}))
    # (e) supporting only: biggest win-rate gap on the current board, stricter cutoff (8+ each side)
    gaps = []
    for p, sts in cur["players"].items():
        st = ([x for x in sts if x.get("endTeam")] or sts[-1:])[0]
        if st["g"] >= MIN_ABSENCE and st["ow"] + st["ol"] >= MIN_ABSENCE and p in ids:
            gaps.append((st["w"] / st["g"] - st["ow"] / (st["ow"] + st["ol"]), p, st))
    if gaps:
        gp, p, st = max(gaps, key=lambda x: (abs(x[0]), x[1]))
        tn = franchise_name(st["f"], CURRENT_SEASON)
        word = "played" if gp > 0 else "missed"
        cands.append((6, 0, {
            "rule": "board", "players": [ids[p]["slug"]],
            "headline": f"The {tn}: {wl(st['w'], st['l'])} with {name(p)}, {wl(st['ow'], st['ol'])} without",
            "body": [f"The biggest win-rate gap on the {season_label(CURRENT_SEASON)} board among players with "
                     f"{MIN_ABSENCE}+ games each side, higher in the games he {word}."],
            "link": {"text": f"{season_label(CURRENT_SEASON)} with and without board", "href": "lists/winning-without-him.html"},
            "line": f"Biggest gap this season ({MIN_ABSENCE}+ games each side): the {tn} are {wl(st['w'], st['l'])} with "
                    f"{name(p)} and {wl(st['ow'], st['ol'])} without."}))
    # (d) quiet day: comparison from the comparison-of-the-day pool (picks.py), half a cycle away
    # from the homepage's pair; then the next pairs in the cycle if a pair led in the last 30 days
    hp = load_json(os.path.join(DATA, "help.json"), {"peers": {}, "avg": {}})
    pool = picks.pair_pool(d, hp)
    for step in range(len(pool)):
        day = (dt.date.fromisoformat(date) + dt.timedelta(days=step)).isoformat()
        a, b = picks.pair_of_day(pool, day, half_cycle=True)
        if ("compare", (ids[a]["slug"], ids[b]["slug"])) in recent:
            continue
        sa, sb = A.summary(d, a), A.summary(d, b)
        x, y = sorted((ids[a]["slug"], ids[b]["slug"]))
        cands.append((5, 0, {
            "rule": "compare",
            "players": [ids[a]["slug"], ids[b]["slug"]],
            "headline": f"{name(a)} and {name(b)}: same era, similar teammate help",
            "body": [f"{name(a)}'s teams went {wl(sa['w'], sa['l'])} in his games with an average final finish of "
                     f"{sa['rnk']:.1f}; {name(b)}'s went {wl(sb['w'], sb['l'])}, average finish {sb['rnk']:.1f}.",
                     f"Teammate help: {hp['avg'][a]['help']:.1f} and {hp['avg'][b]['help']:.1f} points per season."],
            "link": {"text": "The two careers, season by season", "href": f"compare/{x}--{y}.html"},
            "line": f"{name(a)} vs {name(b)}: {wl(sa['w'], sa['l'])} vs {wl(sb['w'], sb['l'])}."}))
        break
    cands.sort(key=lambda c: (c[0], c[1]))
    cands = [c for c in cands if c[2]["rule"] != "board" and (c[2]["rule"], tuple(c[2]["players"])) not in recent] + \
        [c for c in cands if c[2]["rule"] == "board"]
    leads = [c for c in cands if c[2]["rule"] != "board"]
    if not leads:
        print("UNCHANGED no candidate")
        return False
    lead = dict(leads[0][2])
    more = related_links(lead, ids, d)
    lead.update({"date": date, "cutoff": through, "supporting": more, "schedule": gdate if games else None,
                 "img": f"stories/img/{date}.png"})
    stories["stories"].insert(0, lead)
    dump_json(os.path.join(DATA, "stories.json"), stories, compact=False)
    dump_json(os.path.join(DATA, "stories_state.json"),
              {"date": date, "total": total, "ow": {p: ([x for x in s if x.get("endTeam")] or s[-1:])[0]["ow"]
                                                    for p, s in cur["players"].items()},
               "base": base_state})
    draw(lead, ids)
    print("CHANGED story for", date, lead["rule"])
    return True


def related_links(lead, ids, d):
    """The two supporting links: about the lead's own players and board, never a random pair."""
    by_slug = {v["slug"]: k for k, v in ids.items()}
    sl = lead.get("players", [])
    pid = [by_slug.get(x) for x in sl]

    def page(i, text=None):
        return {"text": text or f"{ids[pid[i]]['name']}: every season and every opponent",
                "href": f"player/{sl[i]}.html"}

    def cmp(text=None):
        return {"text": text or f"{ids[pid[0]]['name']} vs {ids[pid[1]]['name']}, season by season",
                "href": f"compare/?a={sl[0]}&b={sl[1]}"}
    r = lead["rule"]
    if r in ("pass", "climb") and len(sl) == 2:
        return [cmp(), page(1)]
    if r == "matchup":
        return [page(0, f"{ids[pid[0]]['name']}'s record against every franchise"),
                {"text": f"{season_label(CURRENT_SEASON)} with and without board", "href": "lists/winning-without-him.html"}]
    if r == "absence":
        return [page(0), {"text": f"{season_label(CURRENT_SEASON)} standings so far",
                          "href": f"seasons/{season_label(CURRENT_SEASON)}.html"}]
    if r == "compare" and len(sl) == 2:
        return [page(0), page(1)]
    return [page(i) for i in range(min(2, len(sl)))]


def draw(story, ids):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    fd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

    def font(size, weight=400, mono=False):
        f = ImageFont.truetype(os.path.join(fd, "JetBrainsMono.ttf" if mono else "DMSans.ttf"), size)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        return f
    im = Image.new("RGB", (W, H), "#f5f5f7")
    g = ImageDraw.Draw(im)
    g.rounded_rectangle((36, 36, W - 36, H - 36), 24, fill="#ffffff", outline="#d1d1d6", width=2)
    g.text((76, 70), f"Today in Team Success · {nice_date(story['date'])}", font=font(26, 600), fill="#6e6e73")
    # headline, wrapped
    hf = font(52, 700)
    words, lines, cur = story["headline"].split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if g.textlength(t, font=hf) > W - 152:
            lines.append(cur)
            cur = wd
        else:
            cur = t
    lines.append(cur)
    y = 130
    for ln in lines[:3]:
        g.text((76, y), ln, font=hf, fill="#1d1d1f")
        y += 64
    bf = font(28, 500)
    words, blines, cur = story["body"][0].split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if g.textlength(t, font=bf) > W - 152:
            blines.append(cur)
            cur = wd
        else:
            cur = t
    blines.append(cur)
    y += 20
    for ln in blines[:4]:
        g.text((76, y), ln, font=bf, fill="#1d1d1f")
        y += 40
    g.text((76, H - 92), f"Data through {nice_date(story['cutoff'])}. Records are his teams' in his games.",
           font=font(22, 500), fill="#6e6e73")
    g.text((W - 76, H - 92), "hoopsmatic.com/team-success", font=font(22, 600), fill="#3b82f6", anchor="ra")
    out = os.path.join(ROOT, story["img"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.quantize(colors=64, method=Image.Quantize.FASTOCTREE).save(out, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    a = ap.parse_args()
    build(a.date)


if __name__ == "__main__":
    main()

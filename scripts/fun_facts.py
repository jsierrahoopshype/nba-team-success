# (c) 2026 HoopsMatic. All rights reserved.
# Team Success "Fun facts" strip. Fingerprint: hm-ts-7f3a91c2-facts
"""Pick 6-8 short facts for the homepage by the rules in docs/story-rules.md ("Fun facts") and
write them to data/facts.json.

python scripts/fun_facts.py [--date 2026-11-19]   # nightly Action, after daily_story.py

Every fact is a template filled from data; each carries the link that proves it, and a face
(person ID) or a team logo (franchise + season). Sources: committed data (game logs, boards,
help.json), data/current.json (with its game log, for "last night") and tonight's schedule from
cdn.nba.com (if it cannot be read, the matchup facts are skipped).

One set per UTC date. A later run the same date rewrites the set only when the data cutoff moved
(newer games). Keys of past sets are kept 60 days: a fact never repeats the next day, and
historical and streak facts never repeat within 30 days. Prints CHANGED or UNCHANGED.
"""
import argparse
import datetime as dt
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis as A  # noqa: E402
import boards as B  # noqa: E402
from common import (CURRENT_SEASON, DATA, LAST_COMPLETE, dump_json, franchise_name,  # noqa: E402
                    load_json, season_label)

EN, MINUS = "–", "−"
MAX_FACTS, MIN_FACTS = 8, 6
PASS_MAX_RANK = 250           # a pass counts when he is now in the top 250 of that board
START_MIN_GAMES = 8           # team starts: 8+ games played
START_SINCE_GAP = 5           # "best start since X" only when X is 5+ seasons ago
PERFECT_MIN_PLAYED = 10       # perfect / winless in his games: 10+ games played
PERFECT_MIN_MISSED = 8        # perfect / winless in games he missed: 8+ games missed
MATCHUP_MIN = 20              # tonight: 20+ regular-season games against that franchise
MATCHUP_HI, MATCHUP_LO = 0.700, 0.350
REPEAT_DAYS = 30              # historical and streak facts
KEEP_DAYS = 60


def signed(n):
    return ("+" if n > 0 else (MINUS if n < 0 else "")) + f"{abs(n):,}"


def wl(w, l):
    return f"{w}{EN}{l}"


def pct1(p):
    return f"{100 * p:.1f}%"


def nice_md(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    mon = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."][m - 1]
    return f"{mon} {d}"


def T(text):
    return [text]


def L(text, href, bold=False):
    return [text, href, 1 if bold else 0]


def build(date):
    d = A.Data()
    cur = load_json(os.path.join(DATA, "current.json"))
    ids = dict(d.ids)
    ids.update(cur.get("newIds", {}))
    doc = load_json(os.path.join(DATA, "facts.json"), {"history": {}})
    through = cur["through"]
    if doc.get("date") == date and doc.get("cutoff") == through:
        print("UNCHANGED facts for", date, "already written with data through", through)
        return False
    hist = {k: v for k, v in doc.get("history", {}).items() if k != date and
            (dt.date.fromisoformat(date) - dt.date.fromisoformat(k)).days <= KEEP_DAYS}
    yday = (dt.date.fromisoformat(date) - dt.timedelta(days=1)).isoformat()
    used_yday = set(hist.get(yday, []))
    used_30 = {k.rsplit("|", 1)[0] for day, keys in hist.items()
               if (dt.date.fromisoformat(date) - dt.date.fromisoformat(day)).days <= REPEAT_DAYS for k in keys}

    def slug(p):
        return ids[p]["slug"]

    def name(p):
        return ids[p]["name"]

    def plink(p, bold=True, href=None):
        return L(name(p), href or f"player/{slug(p)}.html", bold)

    def team_name(f, sy=CURRENT_SEASON):
        t = d.team(f, sy)
        return (t["name"] if t else None) or franchise_name(f, sy) or f

    cands = []      # (priority, order, fact)

    def add(pri, order, key, parts, href, pid=None, team=None, repeat30=False):
        base = key
        full = f"{key}|{'/'.join(str(x[0]) for x in parts)}"
        if full in used_yday or (repeat30 and base in used_30):
            return
        cands.append((pri, order, {"key": full, "type": key.split(":")[0], "parts": parts, "href": href,
                                   "pid": pid, "team": team}))

    # ---- last night: games on the cutoff date ------------------------------------------------
    log = cur.get("log", {"games": [], "app": {}})
    last = [g for g in log["games"] if g[1] == through]
    delta = defaultdict(lambda: [0, 0])                # pid -> [w, l] last night
    for gid, date_, h, a, hs, as_ in last:
        hp, ap = log["app"].get(gid, [[], []])
        for p in hp:
            delta[str(p)][0 if hs > as_ else 1] += 1
        for p in ap:
            delta[str(p)][0 if as_ > hs else 1] += 1

    when = ("last night" if (dt.date.fromisoformat(date) - dt.date.fromisoformat(through)).days <= 1
            else f"on {nice_md(through)}")

    # ---- 1. passed someone on a career board last night (wins, W - L) -------------------------
    # the board's own ranks (default view, incl. the season to date; ties shown as T-)
    data = B.compact(A.Data(live=True), cur, load_json(os.path.join(DATA, "help.json"), {}))
    for board, title in (("career-wins", "career wins"), ("wins-minus-losses", "career wins minus losses")):
        got = [x for x in B.passes(data, board, delta) if x[0] in ids and x[1][0] <= PASS_MAX_RANK]
        if not got:
            continue
        p, (r, tied, v), passed = got[0]
        q = passed[0][0]
        n = len(passed)
        val = f"{v:,}" if board == "career-wins" else signed(v)
        more = f" and {n - 1} other{'s' if n > 2 else ''}" if n > 1 else ""
        href = f"lists/{board}.html?hl={slug(p)}#p-{slug(p)}"
        add(1, r, f"pass:{board}:{slug(p)}:{slug(q)}",
            [plink(p), T(" passed "), plink(q, False), T(f"{more} {when} for "),
             L(f"{B.rank_label(r, tied)} in {title}", href),
             T(f" ({val} in his games, {B.SCOPE_LIVE}).")], href, pid=p)

    # ---- 2. a team's best / worst start through N games since a season ------------------------
    at_n = defaultdict(list)          # N -> [(sy, f, wins)]
    for sy in range(1947, LAST_COMPLETE + 1):
        lg = load_json(os.path.join(DATA, "gamelog", f"{sy}.json"))
        seq = defaultdict(list)
        for gid, dd, h, a, hc, ac, hs, as_ in sorted(lg["games"], key=lambda g: (g[1], g[0])):
            if gid[2] != "2":
                continue
            seq[h].append(hs > as_)
            seq[a].append(as_ > hs)
        for f, res in seq.items():
            w = 0
            for i, x in enumerate(res[:82]):
                w += x
                at_n[i + 1].append((sy, f, w))
    for f, (w, l) in cur["teams"].items():
        n = w + l
        if n < START_MIN_GAMES or not at_n.get(n):
            continue
        tn = team_name(f)
        for kind in ("best", "worst"):
            if kind == "best":
                hits = [x for x in at_n[n] if x[2] >= w]
            else:
                hits = [x for x in at_n[n] if x[2] <= w]
            href = f"seasons/{season_label(CURRENT_SEASON)}.html#t-{f}"
            if not hits:
                add(2, -w if kind == "best" else w, f"start:{kind}:{f}:{n}",
                    [L(f"The {tn}", href, True), T(f" are {wl(w, l)}, the {kind} record through {n} games of any NBA team since 1946-47.")],
                    href, team=[f, CURRENT_SEASON])
                continue
            sy, f2, w2 = max(hits, key=lambda x: (x[0], x[2] if kind == "best" else -x[2]))
            if CURRENT_SEASON - sy < START_SINCE_GAP:
                # league-wide is too recent: the franchise's own history (10+ earlier seasons)
                own = [x for x in at_n[n] if x[1] == f]
                if len(own) < 10:
                    continue
                oh = [x for x in own if (x[2] >= w if kind == "best" else x[2] <= w)]
                if not oh:
                    add(2, -len(own), f"start:{kind}:{f}:{n}",
                        [L(f"The {tn}", href, True), T(f" are {wl(w, l)}, the franchise's {kind} record through {n} games "
                                                       f"in {len(own) + 1} seasons.")], href, team=[f, CURRENT_SEASON])
                    continue
                sy, f2, w2 = max(oh, key=lambda x: x[0])
                if CURRENT_SEASON - sy < 2 * START_SINCE_GAP:
                    continue
            same = "also " if w2 == w else ""
            whose = "franchise's " if f2 == f and CURRENT_SEASON - sy >= 2 * START_SINCE_GAP and \
                any(x[0] > sy and (x[2] >= w if kind == "best" else x[2] <= w) for x in at_n[n]) else ""
            add(2, -(CURRENT_SEASON - sy), f"start:{kind}:{f}:{n}",
                [L(f"The {tn}", href, True), T(f" are {wl(w, l)}, the {whose}{kind} start through {n} games since the "),
                 L(f"{season_label(sy)} {team_name(f2, sy)}", f"seasons/{season_label(sy)}.html#t-{f2}"),
                 T(f" ({same}{wl(w2, n - w2)}).")],
                href, team=[f, CURRENT_SEASON])

    # ---- 3. perfect / winless in games he played or missed (real samples only) ----------------
    for p, sts in cur["players"].items():
        if p not in ids:
            continue
        st = ([x for x in sts if x.get("endTeam")] or sts[-1:])[0]
        tn = team_name(st["f"])
        gm = st["ow"] + st["ol"]
        href = f"lists/winning-without-him.html?hl={slug(p)}#p-{slug(p)}"
        lines = []
        if st["g"] < PERFECT_MIN_PLAYED or gm < PERFECT_MIN_MISSED:      # a real sample on both sides
            continue
        if st["g"] >= PERFECT_MIN_PLAYED and st["l"] == 0:
            lines.append(("perfect-with", st["g"], f" are {wl(st['w'], 0)} in the games ", " played this season."))
        if st["g"] >= PERFECT_MIN_PLAYED and st["w"] == 0:
            lines.append(("winless-with", st["g"], f" are {wl(0, st['l'])} in the games ", " played this season."))
        if gm >= PERFECT_MIN_MISSED and st["ol"] == 0:
            lines.append(("perfect-without", gm, f" are {wl(st['ow'], 0)} in the games ", " missed this season."))
        if gm >= PERFECT_MIN_MISSED and st["ow"] == 0:
            lines.append(("winless-without", gm, f" are {wl(0, st['ol'])} in the games ", " missed this season."))
        for kind, n, a, b in lines:
            add(3, -n, f"split:{kind}:{slug(p)}", [T(f"The {tn}" + a), plink(p), T(b)], href, pid=p)

    # ---- 4. tonight: an active player's record against tonight's opponent ---------------------
    try:
        from daily_story import schedule
        games, gdate = schedule()
    except Exception:
        games = None
    if games:
        playing = {}
        for h, a in games:
            playing[h], playing[a] = a, h
        rec = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        want = set()
        for p, sts in cur["players"].items():
            f = ([x for x in sts if x.get("endTeam")] or sts[-1:])[0]["f"]
            if f in playing and p in d.players:
                want.add(p)
        for sy in range(1947, LAST_COMPLETE + 1):
            lg = load_json(os.path.join(DATA, "gamelog", f"{sy}.json"))
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
            if w + l < MATCHUP_MIN or p not in ids:
                continue
            r = w / (w + l)
            if MATCHUP_LO < r < MATCHUP_HI:
                continue
            on = team_name(opp)
            add(4, -abs(r - 0.5), f"matchup:{slug(p)}:{opp}",
                [T(f"Tonight vs the {on}: "), plink(p), T("'s teams are "),
                 L(f"{wl(w, l)} ({pct1(r)})", f"player/{slug(p)}.html?vs={opp}#vs-{opp}"),
                 T(f" in his {w + l} regular-season games against them.")],
                f"player/{slug(p)}.html?vs={opp}#vs-{opp}", pid=p)

    # ---- 5. streaks still alive (completed seasons, active players) ---------------------------
    active = [p for p in cur["players"] if p in d.players and p in ids]
    win_streak, drought = [], []
    for p in active:
        seasons = sorted(d.season_main(p).items())
        if not seasons or seasons[-1][0] != LAST_COMPLETE:
            continue
        n = 0
        for sy, (m, e, lst) in reversed(seasons):
            if A.win_pct(d.team(m["f"], sy)) > 0.5:
                n += 1
            else:
                break
        if n >= 5:
            win_streak.append((n, p, seasons[-n][0]))
        n = 0
        for sy, (m, e, lst) in reversed(seasons):
            pr = A.playoff_result(d, e, lst)
            if pr and A.PO_DEPTH[pr[0]["po"]] >= 1:
                break
            n += 1
        if n >= 4:
            drought.append((n, p, seasons[-n][0]))
    win_streak.sort(key=lambda x: (-x[0], ids[x[1]]["name"]))
    drought.sort(key=lambda x: (-x[0], ids[x[1]]["name"]))
    for kind, rows in (("winning", win_streak), ("drought", drought)):
        k = dt.date.fromisoformat(date).toordinal()
        for i in range(min(len(rows), 10)):
            n, p, a = rows[(k + i) % min(len(rows), 10)]
            rk = 1 + sum(1 for x in rows if x[0] > n)
            tie = sum(1 for x in rows if x[0] == n) > 1
            tag = ("the longest active streak" if rk == 1 and not tie else
                   f"{B.rank_label(rk, tie)} among active players")
            href = f"player/{slug(p)}.html#cap-seasons"
            if kind == "winning":
                parts = [plink(p), T("'s teams have had a winning record in each of his last "),
                         L(f"{n} seasons", href), T(f" ({season_label(a)} to {season_label(LAST_COMPLETE)}), {tag}.")]
            else:
                parts = [plink(p), T(" has not been on a playoff team in his last "), L(f"{n} seasons", href),
                         T(f" ({season_label(a)} to {season_label(LAST_COMPLETE)}), {tag.replace('streak', 'drought')}.")]
            before = len(cands)
            add(5, i, f"streak:{kind}:{slug(p)}", parts, href, pid=p, repeat30=True)
            if len(cands) > before:
                break

    # ---- 6. on this day: title-winning and 60-win-pace team-seasons ---------------------------
    mmdd = date[5:]
    hist_c = []
    for sy in range(1947, LAST_COMPLETE + 1):
        yr = sy - 1 if int(mmdd[:2]) >= 8 else sy
        day = f"{yr}-{mmdd}"
        lg = load_json(os.path.join(DATA, "gamelog", f"{sy}.json"))
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
            sixty = t["w"] / max(1, t["w"] + t["l"]) >= 60 / 82
            if champ or sixty:
                hist_c.append((sy, f, w, l, t, champ, sixty))
    if hist_c:
        k = dt.date.fromisoformat(date).toordinal()
        shown = 0
        for i in range(len(hist_c)):
            sy, f, w, l, t, champ, sixty = hist_c[(k * 7 + i * 13) % len(hist_c)]
            end = (f"finished {wl(t['w'], t['l'])} and won the title" if champ else
                   f"finished {wl(t['w'], t['l'])}, a {round(82 * t['w'] / (t['w'] + t['l']))}-win pace over 82 games")
            href = f"seasons/{season_label(sy)}.html#t-{f}"
            before = len(cands)
            add(6, shown, f"onthisday:{sy}:{f}",
                [T(f"On this date in {season_label(sy)}, the "), L(t["name"], href, True),
                 T(f" were {wl(w, l)}. They {end}.")], href, team=[f, sy], repeat30=True)
            if len(cands) > before:
                shown += 1
            if shown >= 3:
                break

    # ---- pick: caps per type, then fill to 8 --------------------------------------------------
    cands.sort(key=lambda c: (c[0], c[1]))
    caps = {"pass": 2, "start": 2, "split": 2, "matchup": 2, "streak": 2, "onthisday": 1}
    # the day's story already covers its players: they get no fun fact
    story = [x for x in load_json(os.path.join(DATA, "stories.json"), {"stories": []})["stories"] if x["date"] == date]
    by_slug = {v["slug"]: k for k, v in ids.items()}
    picked, count, seen = [], defaultdict(int), {by_slug[x] for x in (story[0]["players"] if story else []) if x in by_slug}
    for _, _, f in cands:
        if len(picked) >= MAX_FACTS:
            break
        who = f["pid"] or (f["team"][0] if f["team"] and f["team"][1] == CURRENT_SEASON else None)
        if who and who in seen:                 # one fact per player (or current team) a day
            continue
        if count[f["type"]] < caps[f["type"]]:
            picked.append(f)
            count[f["type"]] += 1
            if who:
                seen.add(who)
    for _, _, f in cands:                   # fewer than 6: more on-this-day items
        if len(picked) >= MIN_FACTS:
            break
        who = f["pid"] or (f["team"][0] if f["team"] and f["team"][1] == CURRENT_SEASON else None)
        if f not in picked and not (who and who in seen):
            picked.append(f)
    hist[date] = [f["key"] for f in picked]
    out = {"date": date, "cutoff": through, "facts": picked, "history": dict(sorted(hist.items()))}
    changed = dump_json(os.path.join(DATA, "facts.json"), out, compact=False)
    print(("CHANGED" if changed else "UNCHANGED"), "facts for", date, ":", ", ".join(f["type"] for f in picked))
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    build(ap.parse_args().date)


if __name__ == "__main__":
    main()

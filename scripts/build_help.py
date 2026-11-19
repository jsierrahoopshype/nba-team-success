# (c) 2026 HoopsMatic. All rights reserved.
# Team Success teammate help and peer matching. Fingerprint: hm-ts-7f3a91c2-help
"""Teammate help per player-team-season, from committed data only (no sources, no network).

python scripts/build_help.py      # writes data/help.json (run after build_history.py)

Help = the HoopsMatic Teammates Score weights applied to the honors won IN THAT SEASON by the
teammates who shared at least one regular-season game with him for that team (checked game by
game in data/gamelog/, so a traded player only gets the teammates he actually played with).
Entering = the same teammates' honors from the season before. A season's help is 0 when no such
teammate was honored, and "partial" when a teammate with 10+ shared games has no award record
(name not matched), so a missing value is never shown as a zero. Player averages are per season
(one team per season: the stint with most games), never a career total.

Peers (players with 300+ games): same era (game-weighted career midpoints within 4 seasons),
similar help (average per season), similar own honors per season, similar career length; the
three closest by a published distance (comparison-rules.html).
"""
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis as A  # noqa: E402
from common import DATA, FIRST_SEASON, LAST_COMPLETE, dump_json, load_json  # noqa: E402

PEER_MIN_GAMES = 300


def build():
    d = A.Data()
    players = d.players
    # games each player played for each team-season
    games = defaultdict(lambda: defaultdict(set))       # (f, sy) -> pid -> {gid}
    for sy in range(FIRST_SEASON, LAST_COMPLETE + 1):
        lg = load_json(os.path.join(DATA, "gamelog", f"{sy}.json"))
        for gid, date, h, a, hc, ac, hs, as_ in lg["games"]:
            if gid[2] != "2":
                continue
            hp, ap = lg["app"][gid]
            for pid in hp:
                games[(h, sy)][str(pid)].add(gid)
            for pid in ap:
                games[(a, sy)][str(pid)].add(gid)
    pts = {pid: {int(y): v for y, v in p.get("accY", {}).items()} for pid, p in players.items()}
    aw = {pid: p.get("awY", {}) for pid, p in players.items()}
    matched = {pid for pid, v in d.ids.items() if v.get("rsName")}
    # seasons whose honors are not in awards.json yet (none through 2025-26 on 2026-11-19): every help
    # score there is partial, never a real zero
    have = set()
    for v in aw.values():
        have |= {int(y) for y in v}
    missing_years = {sy for sy in range(FIRST_SEASON, LAST_COMPLETE + 1) if sy not in have}
    out = {}
    for (f, sy), roster in games.items():
        for pid, mine in roster.items():
            mates = []
            same = enter = 0.0
            partial = False
            for q, theirs in roster.items():
                if q == pid:
                    continue
                shared = len(mine & theirs)
                if not shared:
                    continue
                ps, pe = pts.get(q, {}).get(sy, 0), pts.get(q, {}).get(sy - 1, 0)
                same += ps
                enter += pe
                if q not in matched and shared >= 10:
                    partial = True
                if ps or pe:
                    mates.append([q, shared, round(ps, 3), round(pe, 3), aw.get(q, {}).get(str(sy), [])])
            mates.sort(key=lambda m: (-m[2], -m[3], -m[1]))
            if sy in missing_years:
                partial = True
            out.setdefault(pid, {})[f"{f}-{sy}"] = [round(same, 3), round(enter, 3), 1 if partial else 0, mates]
    # per-player averages: one team per season (the stint with most games)
    avg = {}
    for pid in players:
        if pid not in out:
            continue
        rows = []
        for sy, (main, end, lst) in d.season_main(pid).items():
            h = out[pid].get(f"{main['f']}-{sy}")
            if h:
                rows.append((sy, h[0], h[1], h[2]))
        if not rows:
            continue
        g = sum(st["g"] for st in d.stints(pid))
        mid = sum(st["s"] * st["g"] for st in d.stints(pid)) / g if g else None
        own = sum(v for y, v in pts.get(pid, {}).items() if y <= LAST_COMPLETE) / len(rows)
        avg[pid] = {"help": sum(r[1] for r in rows) / len(rows), "enter": sum(r[2] for r in rows) / len(rows),
                    "partial": sum(r[3] for r in rows), "n": len(rows), "g": g, "mid": mid, "own": own}
    # peers
    pool = [pid for pid, a in avg.items() if a["g"] >= PEER_MIN_GAMES]
    peers = {}
    for pid in pool:
        a = avg[pid]
        cand = []
        for q in pool:
            if q == pid:
                continue
            b = avg[q]
            if abs(a["mid"] - b["mid"]) > 4:
                continue
            dh = abs(math.log1p(a["help"]) - math.log1p(b["help"]))
            dg = abs(math.log(a["g"] / b["g"]))
            do = abs(math.log1p(a["own"]) - math.log1p(b["own"]))
            if dh > 0.35 or dg > 0.7 or do > 0.5:
                continue
            dist = abs(a["mid"] - b["mid"]) / 4 + dh / 0.35 + dg / 0.7 + do / 0.5
            cand.append((round(dist, 6), d.ids[q]["name"], q))
        cand.sort()
        if len(cand) < 3:
            # fallback: the nearest players within 6 seasons of era, same distance, no cutoffs
            have = {q for _, _, q in cand}
            more = []
            for q in pool:
                b = avg[q]
                if q == pid or q in have or abs(a["mid"] - b["mid"]) > 6:
                    continue
                dist = (abs(a["mid"] - b["mid"]) / 4 + abs(math.log1p(a["help"]) - math.log1p(b["help"])) / 0.35
                        + abs(math.log(a["g"] / b["g"])) / 0.7 + abs(math.log1p(a["own"]) - math.log1p(b["own"])) / 0.5)
                more.append((round(dist, 6) + 100, d.ids[q]["name"], q))     # +100: listed after real matches
            cand += sorted(more)[:3 - len(cand)]
        peers[pid] = [[q, dist] for dist, _, q in cand[:3]]
    doc = {"missing_years": sorted(missing_years), "season": out, "avg": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                                  for k, v in avg.items()}, "peers": peers}
    changed = dump_json(os.path.join(DATA, "help.json"), doc)
    n_pairs = len({tuple(sorted((p, q))) for p, lst in peers.items() for q, _ in lst})
    print(f"help: {len(out)} players, peers for {sum(1 for v in peers.values() if v)}, {n_pairs} unique pairs, "
          f"{'changed' if changed else 'unchanged'}")


if __name__ == "__main__":
    build()

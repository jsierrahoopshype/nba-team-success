# (c) 2026 HoopsMatic. All rights reserved.
# Team Success daily picks shared by the homepage and the daily story. Fingerprint: hm-ts-7f3a91c2-picks
"""Comparison of the day: which pair, and the rotation that keeps it from repeating.

Pool (docs/story-rules.md, "Comparison of the day"): suggested peer pairs (same era by the peer
rules: career middles within 4 seasons) where both players have 300+ games and at least one was an
All-Star, ranked by combined Accolade score (Teammates Score weights); the top POOL_SIZE pairs.
The pool is put in a fixed shuffled order and day k shows entry k mod POOL_SIZE, so a pair cannot
come back for POOL_SIZE days (120 > the 60-day rule). The daily story uses the pair half a cycle
away, so the two never show the same pair on the same day.
"""
import datetime as dt
import random

POOL_SIZE = 120
MIN_GAMES = 300
NO_REPEAT_DAYS = 60
SEED = 20261119


def pair_pool(d, help_doc):
    av = help_doc.get("avg", {})
    pairs = set()
    for a, lst in help_doc.get("peers", {}).items():
        for b, dist in lst:
            if av.get(a, {}).get("g", 0) < MIN_GAMES or av.get(b, {}).get("g", 0) < MIN_GAMES:
                continue
            if a not in d.players or b not in d.players or a not in d.ids or b not in d.ids:
                continue
            if not (d.players[a].get("as") or d.players[b].get("as")):
                continue
            pairs.add(tuple(sorted((a, b), key=int)))
    ranked = sorted(pairs, key=lambda p: (-(d.players[p[0]].get("acc", 0) + d.players[p[1]].get("acc", 0)), p))
    pool = ranked[:POOL_SIZE]
    pool.sort()
    random.Random(SEED).shuffle(pool)
    return pool


def pair_of_day(pool, date, half_cycle=False):
    """The pair for an ISO date; half_cycle=True is the daily story's pair (never the homepage's)."""
    if not pool:
        return None
    k = dt.date.fromisoformat(date).toordinal() + (len(pool) // 2 if half_cycle else 0)
    return pool[k % len(pool)]

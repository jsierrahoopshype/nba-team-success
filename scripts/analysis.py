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
from common import DATA, LAST_COMPLETE, SIXTY_PACE, load_json  # noqa: E402

ERAS = ((1947, "all"), (1977, "1977"), (1997, "1997"))
GAME_FILTERS = ((1, "any"), (20, "20"))
PO_DEPTH = {"": 0, "Play-In": 0, "First Round": 1, "Conf Semis": 2, "Conf Finalist": 3,
            "Finalist": 4, "Champion": 5}
PO_LABEL = {"First Round": "First round", "Conf Semis": "Conference semifinals",
            "Conf Finalist": "Conference finals", "Finalist": "NBA Finals",
            "Champion": "Won the title", "Play-In": "Lost in the play-in", "": "Missed the playoffs"}


class Data:
    def __init__(self, data_dir=DATA):
        self.players = load_json(os.path.join(data_dir, "players.json"), {})
        self.teams = load_json(os.path.join(data_dir, "team_seasons.json"), {})
        self.ids = load_json(os.path.join(data_dir, "player_ids.json"), {})
        self.meta = load_json(os.path.join(data_dir, "meta.json"), {})

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

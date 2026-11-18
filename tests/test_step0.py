# (c) 2026 HoopsMatic. All rights reserved.
"""Step 0 sanity checks, run against the committed data files (no network needed).

python -m pytest tests/ -q
"""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from analysis import Data, count_flag, count_sixty  # noqa: E402
from common import LAST_COMPLETE, SIXTY_PACE, season_label  # noqa: E402


@pytest.fixture(scope="module")
def d():
    return Data()


@pytest.fixture(scope="module")
def step0():
    with open(os.path.join(ROOT, "data", "step0.json"), encoding="utf-8") as fh:
        return json.load(fh)


def names(d, counter, value):
    return {d.ids[k]["name"] for k, v in counter.items() if v == value}


# --- a. game counts --------------------------------------------------------
def test_game_counts_match_74_of_80(step0):
    gc = step0["game_counts"]
    assert gc["seasons"] == 80
    assert gc["match"] == 74
    assert {x["season"] for x in gc["diffs"]} == {1948, 1950, 1954, 1956, 1957, 2013}
    assert all(1 <= abs(x["diff"]) <= 2 for x in gc["diffs"])


def test_every_team_season_in_both_sources(step0):
    assert step0["teamseason_only_in_games"] == []
    assert step0["teamseason_only_in_standings"] == []
    assert step0["unmapped_codes"] == []


# --- b. franchise map ------------------------------------------------------
@pytest.mark.parametrize("season,code,fr,name", [
    (1968, "SDR", "HOU", "San Diego Rockets"),
    (1997, "VAN", "MEM", "Vancouver Grizzlies"),
    (2010, "NJN", "BKN", "New Jersey Nets"),
    (2012, "CHA", "CHA", "Charlotte Bobcats"),
    (1956, "ROC", "SAC", "Rochester Royals"),
    (1950, "BOM", "STB", "St. Louis Bombers"),
    (1950, "WAS", "WSC", "Washington Capitols"),
    (2007, "NOK", "NOP", "New Orleans/Oklahoma City Hornets"),
    (1999, "CHH", "CHA", "Charlotte Hornets"),
])
def test_franchise_map(season, code, fr, name):
    with open(os.path.join(ROOT, "data", "franchise_map.json"), encoding="utf-8") as fh:
        fmap = json.load(fh)
    got = fmap["by_season"][str(season)][code]
    assert got == {"franchise": fr, "name": name}


def test_every_team_season_has_a_real_name(d):
    assert all(t["name"] for t in d.teams.values())
    assert d.team("SAC", 1956)["name"] == "Rochester Royals"


# --- standings quirks ------------------------------------------------------
def test_win_pct_is_computed_not_read(d):
    for t in d.teams.values():
        assert abs(t["pct"] - t["w"] / (t["w"] + t["l"])) < 1e-4


def test_atl_2024_is_play_in_not_champion(d):
    assert d.team("ATL", 2024)["po"] == "Play-In"
    assert d.team("BOS", 2024)["po"] == "Champion"


def test_rnk_is_the_season_ranking(d):
    for sy in range(1947, LAST_COMPLETE + 1):
        ts = [t for t in d.teams.values() if t["s"] == sy]
        champs = [t for t in ts if t["po"] == "Champion"]
        assert len(champs) == 1, sy
        assert champs[0]["rnk"] == 1, sy
        assert min(t["rnk"] for t in ts) == 1


def test_one_champion_series_path(d):
    t = d.team("DAL", 2024)
    assert t["elim"]["opp"] == "BOS" and (t["elim"]["w"], t["elim"]["l"]) == (1, 4)


# --- c. identity -----------------------------------------------------------
def test_identity_match_rate(step0):
    assert step0["identity"]["rate"] >= 0.98


def test_slugs_unique_and_safe(d):
    slugs = [v["slug"] for v in d.ids.values()]
    assert len(slugs) == len(set(slugs))
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s) for s in slugs)


def test_career_map_style_slugs(d):
    by = {v["slug"]: v for v in d.ids.values()}
    assert "charles-smith-1965" in by and "nikola-jokic" in by and "lebron-james" in by


# --- d. did he play --------------------------------------------------------
def test_minutes_groups(step0):
    g = step0["minutes_groups"]
    assert g["never"] == [1947, 1948, 1949, 1950, 1951]
    assert 2026 in g["always"]


# --- expected list results ---------------------------------------------------
def test_worst_team_all_time(d):
    c, _ = count_flag(d, "worst")
    top = max(c.values())
    assert top == 5
    assert names(d, c, 5) == {"Johnny Green", "John Block"}


def test_worst_team_since_1977(d):
    c, det = count_flag(d, "worst", era_from=1977)
    assert max(c.values()) == 3
    at3 = names(d, c, 3)
    assert len(at3) == 17
    must = {"Bryant Reeves", "Joe Wolf", "Greg Anthony", "Brad Miller", "Kevin Knox",
            "Alec Burks", "Bojan Bogdanovic", "Sean Rooks", "Pete Chilcutt", "DJ Augustin"}
    assert must <= at3
    by_name = {d.ids[k]["name"]: k for k in c}
    for n in must:
        assert all(s["g"] >= 20 for s in det[by_name[n]]), n


def test_sixty_win_pace(d):
    assert abs(SIXTY_PACE - 0.7317) < 1e-4
    c, _ = count_sixty(d)
    by = {d.ids[k]["name"]: v for k, v in c.items()}
    assert by["Kareem Abdul-Jabbar"] == 8
    for n in ("Tim Duncan", "Tony Parker", "Manu Ginobili", "Danny Green"):
        assert by[n] == 7, n
    assert max(c.values()) == 8


# --- with / without ----------------------------------------------------------
def test_with_without_adds_up(d):
    """Inside one team-season, games with him + without him never exceed the team's games."""
    for pid, p in d.players.items():
        for s in p["seasons"]:
            t = d.team(s["f"], s["s"])
            if not t or not s["win"]:
                continue
            assert s["w"] + s["l"] == s["g"]
            assert s["g"] + s["ow"] + s["ol"] <= t["gpBox"]


def test_traded_player_windows(d):
    harden = next(k for k, v in d.ids.items() if v["name"] == "James Harden")
    rows = {s["f"]: s for s in d.players[harden]["seasons"] if s["s"] == 2021}
    assert set(rows) == {"HOU", "BKN"}
    assert rows["HOU"]["g"] == 8 and rows["BKN"]["g"] == 36
    # Houston's window ends the day before his first Brooklyn game; Brooklyn's starts the day
    # after his last Houston game (the days in between count for both teams, as defined).
    assert rows["HOU"]["win"][-1][1] == "2021-01-15" and rows["BKN"]["first"] == "2021-01-16"
    assert rows["BKN"]["win"][0][0] == "2021-01-13" and rows["HOU"]["last"] == "2021-01-12"
    # started every game he played for Houston
    assert sum(rows["HOU"]["rm"]["st"]) == 8 and sum(rows["HOU"]["rm"]["bn"]) == 0


def test_season_label():
    assert season_label(1997) == "1996-97"
    assert season_label(2000) == "1999-00"

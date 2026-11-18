# (c) 2026 HoopsMatic. All rights reserved.
"""Audit regression checks (scripts/audit.py -> data/audit.json). No network."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from analysis import Data, summary  # noqa: E402
from common import FIRST_SEASON, LAST_COMPLETE  # noqa: E402


@pytest.fixture(scope="module")
def audit():
    with open(os.path.join(ROOT, "data", "audit.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def d():
    return Data()


def test_jordan_regression(audit, d):
    j = audit["jordan"]
    assert j["with"] == [706, 366] and j["games"] == 1072 and j["w_minus_l"] == 340
    assert round(100 * j["pct"], 1) == 65.9
    assert j["without"] == [63, 95] and j["without_games"] == 158
    assert round(100 * j["without_pct"], 1) == 39.9
    assert round(j["gap_pp"], 1) == 26.0
    assert (j["winning"], j["trips"], j["titles"]) == (10, 13, 6)
    assert round(j["avg_rnk"], 1) == 7.4
    # the 1994-95 window: 34-31 before his return counts under the proxy, not under the span
    s95 = next(r for r in j["seasons"] if r["season"] == 1995)
    assert s95["without"] == "34-31" and s95["span_without"] == "0-0"
    assert 1994 not in {r["season"] for r in j["seasons"]}
    pid = next(k for k, v in d.ids.items() if v["slug"] == "michael-jordan")
    sm = summary(d, pid)
    assert (sm["w"], sm["l"], sm["ow"], sm["ol"]) == (706, 366, 63, 95)


def test_rnk_follows_published_rule(audit):
    assert audit["rnk"]["mismatches"] == []
    assert audit["rnk"]["max_rank_le_size"]


def test_no_impossible_appearances_left(audit):
    assert audit["games"]["player_on_both_sides"] == []
    assert audit["games"]["same_matchup_same_day"] == []


def test_opponent_rows_add_up(audit):
    assert audit["opponents"]["n_bad"] == 0


def test_mikan_1951_is_one_team(d):
    pid = next(k for k, v in d.ids.items() if v["slug"] == "george-mikan")
    teams = {s["f"] for s in d.players[pid]["seasons"] if s["s"] == 1951 and s["g"]}
    assert teams == {"LAL"}


def test_span_never_exceeds_window(d):
    for p in d.players.values():
        for s in p["seasons"]:
            if s["g"]:
                assert s.get("sw", 0) + s.get("sl", 0) <= s["ow"] + s["ol"]


def test_gamelogs_cover_every_season():
    for sy in range(FIRST_SEASON, LAST_COMPLETE + 1):
        assert os.path.exists(os.path.join(ROOT, "data", "gamelog", f"{sy}.json")), sy


def test_coverage_scopes(audit):
    c = audit["coverage"]
    assert c["career_seasons"] == ["1946-47", "2025-26"]
    assert c["current_season"] == "2026-27"

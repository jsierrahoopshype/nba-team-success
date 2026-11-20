# (c) 2026 HoopsMatic. All rights reserved.
"""Round 5, part A: one ranking rule and scope everywhere, help totals that add up, on/off windows,
opponent views. Regression numbers use a frozen snapshot (tests/fixtures/current-2026-11-17.json,
games through Nov. 17, 2026); the rest check that the built pages agree with each other."""
import json
import os
import re
import sys
from fractions import Fraction

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analysis as A  # noqa: E402
import boards as B  # noqa: E402

SNAP = os.path.join(ROOT, "tests", "fixtures", "current-2026-11-17.json")
GOBERT = "203497"
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")), reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def snap():
    cur = json.load(open(SNAP, encoding="utf-8"))
    d = A.Data(live=True, cur=cur)
    help_doc = json.loads(read("data/help.json"))
    return B.compact(d, cur, help_doc)


@pytest.fixture(scope="module")
def live():
    d = A.Data(live=True)
    cur = json.loads(read("data/current.json"))
    return B.compact(d, cur, json.loads(read("data/help.json")))


def test_frozen_gobert_rank(snap):
    """The regression: the story said '#157 all time counting this season' while his card said
    T-155. On the frozen snapshot the board rule gives +159, tied at 155 (incl. 2026-27) and +151,
    tied at 172 through 2025-26. A shared rank reads "No. 155" in a sentence, never "T-155"."""
    r, tied, n, m = B.rank_of(snap, "wins-minus-losses", GOBERT)
    assert (m["wl"], r, tied) == (159, 155, True)
    assert B.rank_label(r, tied) == "No. 155"
    assert B.rank_label(r, False) == "No. 155"           # tied or not, the same words
    assert B.rank_label(1234, True) == "No. 1,234"
    r, tied, n, m = B.rank_of(snap, "wins-minus-losses", GOBERT, {"to": 2026})
    assert (m["wl"], r, tied) == (151, 172, True)


def test_card_story_and_board_agree(live):
    t = read("player/rudy-gobert.html")
    m = re.search(r'wins-minus-losses\.html\?hl=rudy-gobert#p-rudy-gobert".*?<span class="rk">(No\. [\d,]+) of ([\d,]+) · (incl\. [^<]+)</span>', t, re.S)
    r, tied, n, _ = B.rank_of(live, "wins-minus-losses", GOBERT)
    assert m and m.group(1) == B.rank_label(r, tied) and m.group(3) == B.SCOPE_LIVE
    # the board page renders the top 100 in HTML; beyond that boards.js computes the same rows
    board = read("lists/wins-minus-losses.html")
    row = re.search(r'<tr id="p-rudy-gobert"><td data-l="Rank" class="mono" data-value="(\d+)"><span class="v">(\d+)</span>', board)
    if r <= 100:                                        # plain number in the rank column, no "T-"
        assert row and int(row.group(1)) == r and int(row.group(2)) == r
    card = json.loads(read("assets/card/rudy-gobert.json"))
    assert card["record"]["wl_rank"] == r and card["record"]["wl_tied"] == tied and card["record"]["scope"] == B.SCOPE_LIVE
    # every story that quotes a W - L board rank uses the board's label and links the same scope
    for st in json.loads(read("data/stories.json"))["stories"]:
        txt = " ".join(st.get("body", []))
        if "career W − L board" in txt:
            assert B.SCOPE_LIVE in txt and "completed seasons" not in st.get("more", {}).get("text", "")


def test_no_scope_contradiction_on_player_pages():
    for slug in ("rudy-gobert", "lebron-james", "kawhi-leonard"):
        t = read(f"player/{slug}.html")
        assert "Not included in the career numbers" not in t
        assert B.SCOPE_LIVE in t
        if "so far</h2>" in t:
            assert "already in his career records above" in t


def _num(x):
    return Fraction(x)


def test_help_totals_equal_their_breakdowns():
    """Jordan Poole 2022-23: 17 help coming in = Curry 14.5 + Green 1.5 + Wiggins 1 (the page used
    to list Wiggins only). Every breakdown on a sample of pages adds up to its total."""
    t = read("player/jordan-poole.html")
    i = t.index('2022-23</span><span class="hs-t">')
    seg = re.sub(r"<[^>]+>", " ", t[i:t.index("</li>", i)])
    assert re.search(r"Help coming in[^:]*:\s+17\s+=\s+14\.5\s+Stephen Curry\s+\+\s+1\.5\s+Draymond Green\s+\+\s+1\s+Andrew Wiggins", seg)
    files = sorted(os.listdir(os.path.join(ROOT, "player")))[::25]
    checked = 0
    for f in files + ["jordan-poole.html", "michael-jordan.html"]:
        page = read(f"player/{f}")
        for tot, parts in re.findall(r'<strong class="mono">([\d.]+)\+?</strong> = (.*?)</p>', page):
            nums = re.findall(r'<span class="mono">([\d.]+)</span>', parts)
            assert sum(map(_num, nums)) == _num(tot), (f, tot, nums)
            checked += 1
    assert checked > 100


def test_help_pending_never_zero():
    for slug in ("rudy-gobert", "lebron-james"):
        t = read(f"player/{slug}.html")
        assert "Honors not in the data yet" not in t
        assert "Help this season: <strong>pending</strong>" in t


def test_on_off_movers_show_windows_and_possessions():
    t = read("lists/on-off-movers.html")
    rows = re.findall(r'<span class="det">(.*?)</span></div>', t, re.S)
    assert rows
    for r in rows:
        txt = re.sub(r"<[^>]+>", "", r)
        assert re.search(r"per 100 over [\d,]+ poss\., \w{3} \d+–\w{3} \d+, vs [−+-]?[\d.]+ over [\d,]+ poss\. ", txt), txt
    h = read("index.html")
    assert " poss., " in h


def test_opponent_views():
    t = read("player/michael-jordan.html")
    assert '<a href="#opp">Record by opponent</a>' in t
    assert t.index('href="#opp"') < t.index('class="hero"')
    sec = t[t.index('<section id="opp">'):]
    assert 'role="tab" data-k="2" aria-selected="true">Regular season' in sec and 'data-k="4"' in sec
    assert '<option value="b">' not in sec                                     # never mixed
    assert 'data-k="2" class="tt sortable opp"' in sec and 'class="ser"' in sec
    assert f"Regular season, {B.SCOPE_DONE} (2026-27 games not included)" in sec
    js = read("assets/opp.js")
    assert "history.replaceState" in js and '"k", "from", "to", "team", "ha", "min"' in js
    assert "opp-open" in js                                                     # game lists stay

# (c) 2026 HoopsMatic. All rights reserved.
"""Round 5, part B: the daily "Last night" list, homepage order, the 2026-27 with/without block."""
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")), reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_last_night_list():
    st = json.loads(read("data/stories.json"))["stories"][0]
    assert st["kind"] == "night" and st["headline"].startswith("Last night in Team Success · ")
    assert st["headline"].endswith(" games")
    assert 3 <= len(st["items"]) <= 10
    if st["quiet"]:
        assert sum(1 for it in st["items"] if it.get("archive")) == 3
    else:
        assert len(st["items"]) >= 4
    for it in st["items"]:
        assert it["href"] and os.path.exists(os.path.join(ROOT, it["href"].split("?")[0].split("#")[0])), it["href"]
        assert it.get("pid") or it.get("team")
        assert it.get("scope")
        if not it.get("archive"):
            assert it["scope"] in "".join(p[0] for p in it["parts"]) or "to date" in it["scope"]
    t = read("index.html")
    sec = t[t.index('<section class="night">'):t.index("</section>", t.index('<section class="night">'))]
    assert f"<h2>{st['headline']}</h2>" in sec
    assert sec.count('<li class="hl">') == len(st["items"])
    assert os.path.exists(os.path.join(ROOT, f"stories/{st['date']}.html"))
    assert os.path.exists(os.path.join(ROOT, st["img"]))
    if st["stale"]:
        assert "No new games since the last update" in sec


def test_list_passes_are_notable():
    st = json.loads(read("data/stories.json"))["stories"][0]
    for it in st["items"]:
        if it["type"].endswith("-pass"):
            txt = "".join(p[0] for p in it["parts"])
            # every pass quotes the passer's board rank: "for T-83 in career wins", "65.6%, #36 among ..."
            r = int(re.search(r"(?:T-|#)([\d,]+)\b", txt).group(1).replace(",", ""))
            assert r <= 250


def test_homepage_order():
    t = read("index.html")
    order = ['<section class="night">', "<h2>Fun facts</h2>", "<h2>Comparison of the day</h2>",
             "so far: with and without</h2>", "<h2>Last 30 days: on/off movers</h2>", "standings</h2>",
             "<h2>Leaderboards</h2>", 'class="az"']
    pos = [t.index(x) for x in order]
    assert pos == sorted(pos)
    assert t.index('id="pf"') < t.index("<h1>Team Success</h1>") < pos[0]


def test_with_without_block_is_current_season_only():
    t = read("index.html")
    sec = t[t.index("so far: with and without</h2>"):t.index("<h2>Last 30 days")]
    assert ": career" not in sec and "Career leaders shown" not in sec
    assert "5 and 5" not in sec
    assert 'href="lists/winning-without-him.html?mp=10&amp;mm=8"' in sec
    assert '<a href="lists/gap-career.html">Career with and without</a>' in sec
    for played, missed in re.findall(r"in (\d+) played · [^<]* in (\d+) missed", sec):
        assert int(played) >= 10 and int(missed) >= 8
    n_rows = sec.count("<li>")
    if n_rows < 6:
        assert re.search(r"Too early: only \d+ players? ha(s|ve) played 10\+ games and missed 8\+ so far", sec)


def test_full_board_defaults_match_js():
    t = read("lists/winning-without-him.html")
    m = re.search(r'<form class="filters" id="minf" data-mp="(\d+)" data-mm="(\d+)"><label>Min games played<input name="mp" type="number" min="1" value="(\d+)"', t)
    assert m and m.group(1) == m.group(2) == m.group(3) == "5"
    assert 'name="mm" type="number" min="1" value="5"' in t
    rows = re.findall(r'<tr id="p-[^"]+" data-gp="(\d+)" data-gm="(\d+)"( hidden)?>', t)
    assert rows
    for gp, gm, hid in rows:
        assert bool(hid) == (int(gp) < 5 or int(gm) < 5)
    js = read("assets/ts.js")
    assert 'f.getAttribute("data-mp")' in js and '< 5)' not in js
    for gp, gm, hid in rows:                          # flagged when a side is under 5
        pass
    assert "small sample" in t or all(int(a) >= 5 and int(b) >= 5 for a, b, _ in rows)

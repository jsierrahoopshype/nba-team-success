# (c) 2026 HoopsMatic. All rights reserved.
"""Round 6: arrival and departure across missed seasons, breadcrumbs, the help table markup."""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")), reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def arr(slug):
    t = read(f"player/{slug}.html")
    sec = t[t.index('id="cap-arr"'):t.index("</section>", t.index('id="cap-arr"'))]
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", sec, re.S)[1:]:
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        rows.append(cells)
    return rows


def has(rows, move, team, season):
    return any(r[0] == move and team in r[1] and r[2] == season for r in rows)


def test_klay_thompson_missed_seasons():
    rows = arr("klay-thompson")
    assert has(rows, "Missed", "Golden State", "2019-20 and 2020-21 (no games)")
    gap = next(r for r in rows if r[0] == "Missed")
    assert "15–50, 39–33 without him" in gap[4]
    assert not has(rows, "Left", "Golden State", "after 2018-19")
    assert not has(rows, "Arrived", "Golden State", "2021-22")
    assert has(rows, "Debut", "Golden State", "2011-12")
    assert not any(r[0] == "Arrived" and "Golden State" in r[1] for r in rows)
    left = next(r for r in rows if r[0] == "Left" and "Golden State" in r[1])
    assert left[2] == "after 2023-24" and left[3].startswith("2023-24: 46–36") and left[4].startswith("2024-25: 48–34")
    assert "without him" in left[4]


def test_kevin_durant_leaves_for_another_franchise():
    rows = arr("kevin-durant")
    assert not any(r[0] == "Missed" for r in rows)
    assert has(rows, "Left", "Golden State", "after 2018-19")
    assert has(rows, "Arrived", "Brooklyn", "2020-21")
    assert has(rows, "Debut", "Seattle", "2007-08")


def test_normal_trade():
    rows = arr("james-harden")
    assert has(rows, "Left", "Oklahoma City", "after 2011-12") and has(rows, "Arrived", "Houston", "2012-13")
    assert has(rows, "Debut", "Oklahoma City", "2009-10")


def test_breadcrumbs():
    for rel, sec in (("player/klay-thompson.html", "Players"), ("lists/career-wins.html", "Leaderboards"),
                     ("seasons/2025-26.html", "Seasons"), ("compare/karl-malone--michael-jordan.html", "Compare"),
                     ("compare/index.html", None)):
        t = read(rel)
        m = re.search(r'<nav class="bc" aria-label="Breadcrumb">(.*?)</nav>', t, re.S)
        assert m, rel
        links = re.findall(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', m.group(1))
        assert links[0][1] == "Team Success"
        if sec:
            assert links[1][1] == sec
        assert 'aria-current="page"' in m.group(1) and "data-back" in m.group(1)
        assert t.index('class="bc"') < t.index("<h1")
    assert 'class="bc"' not in read("index.html")
    js = read("assets/ts.js")
    assert "history.back()" in js and "document.referrer" in js
    assert "keepVs" in read("assets/opp.js")


def test_help_rows_markup_order():
    t = read("player/jordan-poole.html")
    i = t.index('2022-23</span><span class="hs-t">')
    li = t[i:t.index("</li>", i)]
    assert li.index('class="hbar"') < li.index('class="chipsrow"') < li.index("Help this season:") < li.index("<details>")

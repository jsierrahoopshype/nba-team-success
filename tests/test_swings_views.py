# (c) 2026 HoopsMatic. All rights reserved.
"""Biggest teammate swings: the share-card data, the three views, the compact rows and the homepage
Leaderboards block (9 boxes)."""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import teammates as TM  # noqa: E402
from common import DATA, load_json  # noqa: E402

pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "lists", "teammate-swings.html")), reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def views():
    ids = load_json(os.path.join(DATA, "player_ids.json"))
    players = load_json(os.path.join(DATA, "players.json"))
    rows = [(a, b, r) for (a, b), r in TM.all_pairs().items() if a in ids and b in ids and TM.qualifies(r)]
    star = lambda p: bool(players.get(p, {}).get("as"))  # noqa: E731
    return {"as": [x for x in rows if star(x[1])], "both": [x for x in rows if star(x[0]) and star(x[1])],
            "all": rows, "ids": ids}


def test_three_views_and_counts(views):
    t = read("lists/teammate-swings.html")
    labels = re.findall(r'<label for="tsw-(\w+)" class="pill l-\w+">([^<]+)</label>', t)
    assert labels == [("as", "Teammate made an All-Star team"), ("both", "Both made an All-Star team"), ("all", "All teammates")]
    assert re.search(r'id="tsw-as" value="as" checked', t)
    for k in ("as", "both", "all"):
        panel = t[t.index(f'<div class="panel p-{k}">'):]
        panel = panel[:panel.index("</ol>")]
        assert f'<p class="pop">{len(views[k]):,} pairs qualify.</p>' in panel
        assert panel.count("<li ") == len(views[k])
    assert len(views["both"]) < len(views["as"]) < len(views["all"])
    assert 'id="both-draymond-green--stephen-curry"' in t
    assert '<script src="../assets/swings.js" defer></script>' in t
    js = read("assets/swings.js")
    assert '"as", "both", "all"' in js and "history.replaceState" in js and "innerHTML" not in js
    assert "Both made an All-Star team" in read("how-we-count.html")


def test_compact_rows():
    t = read("lists/teammate-swings.html")
    panel = t[t.index('<div class="panel p-as">'):]
    li = re.search(r"<li id=.*?</li>", panel, re.S).group(0)
    assert 'class="more-btn"' not in t                        # the big Compare buttons are gone
    for cls in ("rk", "pr", "tm", "rc", "gp", "cmp"):
        assert f'class="{cls}"' in li, cls
    assert re.search(r'<span class="gp">\d+\.\d lower</span>', li)
    assert re.search(r"Together <span class=\"mono\">\d+–\d+</span> \d+\.\d% · Without <span class=\"mono\">\d+–\d+</span> \d+\.\d%", li)
    assert li.count('href="../player/') == 2 and "nba-career-map/team/" in li


def test_card_data(views):
    doc = json.loads(read("assets/card/lists/teammate-swings.json"))
    assert doc["list"] == "teammate-swings" and doc["title"] == "Biggest teammate swings"
    assert doc["url"] == "https://hoopsmatic.com/team-success/lists/teammate-swings.html"
    # pairs, not "rows": the Worker's one-player list layout never draws this file by mistake
    assert "rows" not in doc and len(doc["pairs"]) == 5
    top = sorted(views["as"], key=lambda x: -TM.gap(x[2]))[:5]
    for p, (a, b, r) in zip(doc["pairs"], top):
        assert p["player"]["slug"] == views["ids"][a]["slug"] and p["teammate"]["slug"] == views["ids"][b]["slug"]
        assert p["gap_points"] == round(100 * TM.gap(r), 1) and p["rank_label"] == str(p["rank"])
        assert p["together_pct"] == round(TM.pct(r["t"]), 4) and p["without_pct"] == round(TM.pct(r["o"]), 4)
    assert doc["pairs"][0]["rank"] == 1


def test_homepage_leaderboards_nine_boxes():
    t = read("index.html")
    sec = t[t.index('<h2 id="leaderboards">'):]
    sec = sec[:sec.index("</section>")]
    heads = re.findall(r'<div class="boxhead">([^<]+?) <a href="([^"]+)">', sec)
    assert [h for h, _ in heads] == ["Career wins in his games", "Wins minus losses", "Titles",
                                     "Most wins without an All-Star teammate", "Bad Luck Index",
                                     "Played for the worst team the most", "Biggest teammate swings",
                                     "Career with and without", "Playoff trips"]
    note = sec[sec.index('<p class="note">'):]
    for href, _ in (("lists/teammate-swings.html", 0), ("lists/gap-career.html", 0), ("lists/playoff-trips.html", 0)):
        assert sec.count(f'href="{href}"') == 1 and href not in note      # listed once, as a box
    for keep in ("lists/winning-seasons.html", "lists/average-finish.html", "lists/low-help-all-stars.html"):
        assert keep in note
    assert sec.count("<li>") == 45

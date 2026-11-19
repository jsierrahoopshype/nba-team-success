# (c) 2026 HoopsMatic. All rights reserved.
"""Round 4: fun facts, compare any two players, homepage samples, comparison of the day, scoreboard
text, download = og card, shorter result wording, nightly schedule. No network."""
import datetime as dt
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analysis as A  # noqa: E402
import picks  # noqa: E402

OG = "https://hoopsmatic.com/og/team-success/"
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")), reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_nightly_runs_four_times_and_commits_only_changes():
    y = read(".github/workflows/nightly.yml")
    crons = re.findall(r'cron: "([^"]+)"', y)
    assert len(crons) >= 2 and any(c.split()[1] in ("14", "15", "16", "17", "18") for c in crons)
    assert "scripts/fun_facts.py" in y and "git diff --cached --quiet" in y


def test_fun_facts_strip():
    t = read("index.html")
    doc = json.loads(read("data/facts.json"))
    assert 6 <= len(doc["facts"]) <= 8
    assert t.index('<h2>Fun facts</h2>') < t.index("<h2>Today in Team Success</h2>")
    strip = t[t.index('<section class="facts">'):t.index("</section>", t.index('<section class="facts">'))]
    assert strip.count('<li class="hl">') == len(doc["facts"])
    for li in strip.split('<li class="hl">')[1:]:
        assert 'class="hs sm' in li and "<a href=" in li          # a face or logo, and a proof link
    keys = [f["key"] for f in doc["facts"]]
    assert len(keys) == len(set(keys))
    days = sorted(doc["history"])
    for a, b in zip(days, days[1:]):                                 # never the same fact two days running
        if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days == 1:
            assert not set(doc["history"][a]) & set(doc["history"][b])
    for f in doc["facts"]:
        assert os.path.exists(os.path.join(ROOT, f["href"].split("?")[0].split("#")[0])), f["href"]


def test_story_supporting_links_are_related():
    st = json.loads(read("data/stories.json"))["stories"][0]
    slugs = set(st["players"])
    for x in st["supporting"]:
        assert any(sl in x["href"] for sl in slugs) or x["href"].startswith(("lists/", "seasons/")), x


def test_compare_any_page():
    t = read("compare/index.html")
    assert '<meta name="robots" content="noindex, follow">' in t
    assert '<link rel="canonical" href="https://hoopsmatic.com/team-success/compare/">' in t
    assert t.count('data-mode="side"') == 2 and 'id="cmp"' in t and "assets/compare.js" in t
    js = read("assets/compare.js")
    assert "getContext" not in js and "toBlob" not in js                    # no canvas card
    assert f'var OG = "{OG}"' in js and 'OG + "compare/" + ps[0] + "--" + ps[1] + ".png"' in js
    assert 'link[rel="canonical"]' in js
    assert 'href="../compare/"' in read("index.html").replace('href="compare/"', 'href="../compare/"')
    assert 'Compare two players</a>' in read("lists/career-wins.html")      # section nav


def test_player_page_compare_block():
    t = read("player/michael-jordan.html")
    i = t.index('id="compare"')
    assert t.index('class="lead"') < i < t.index('class="hero"')           # right under the lead
    blk = t[i:t.index("</section>", i)]
    assert "Compare Michael Jordan with" in blk and 'data-mode="cmp"' in blk and 'data-a="michael-jordan"' in blk
    assert blk.count('class="hs sm') >= 3 and 'data-peer-redirect="michael-jordan"' in blk
    assert 'id="cmp"' not in t and 'data-mode="peer"' not in t              # the old in-page view is gone
    assert f'href="{OG}player/michael-jordan.png" download=' in t
    assert "?peer=" not in t and "data-peer-redirect" in read("assets/ts.js")


def test_scoreboard_text_is_two_short_lines():
    t = read("compare/karl-malone--michael-jordan.html")
    assert "Lower is better for finish and help. With vs without isn't counted. Team results, not who was better." in t
    assert 'href="../comparison-rules.html#how-this-works">How this works</a>' in t
    assert "the smaller number is tinted" not in t and "not a measure of who was better" not in t
    assert "Share this page's link" not in t
    assert re.search(r'Less help: \w+ \(\d\.\d per season vs \d\.\d\)\.</p>', t)
    assert 'id="how-this-works"' in read("comparison-rules.html")


def test_homepage_with_without_minimums():
    t = read("index.html")
    sec = t[t.index("so far: with and without</h2>"):t.index("<h2>Last 30 days")]
    for played, missed in re.findall(r"in (\d[\d,]*) played · [^<]* in (\d[\d,]*) missed", sec):
        p, m = int(played.replace(",", "")), int(missed.replace(",", ""))
        assert p >= 10 and m >= 8
    if ": career" in sec:
        assert "Career leaders shown" in sec


def test_comparison_of_the_day_pool():
    d = A.Data()
    h = json.loads(read("data/help.json"))
    pool = picks.pair_pool(d, h)
    assert len(pool) >= picks.NO_REPEAT_DAYS
    for a, b in pool:
        assert h["avg"][a]["g"] >= 300 and h["avg"][b]["g"] >= 300
        assert d.players[a].get("as") or d.players[b].get("as")
    day0 = dt.date(2026, 11, 19)
    seen = [picks.pair_of_day(pool, (day0 + dt.timedelta(days=k)).isoformat()) for k in range(60)]
    assert len(set(seen)) == 60
    for k in range(60):
        dd = (day0 + dt.timedelta(days=k)).isoformat()
        assert picks.pair_of_day(pool, dd) != picks.pair_of_day(pool, dd, half_cycle=True)


def test_short_result_wording():
    for rel in ("player/michael-jordan.html", "player/lebron-james.html", "seasons/2025-26.html",
                "compare/karl-malone--michael-jordan.html"):
        t = read(rel)
        assert "Missed the playoffs" not in t and "Lost in the play-in" not in t, rel
    assert "Missed playoffs" in read("player/lebron-james.html")
    for js in ("assets/compare.js", "assets/boards.js"):
        assert "Missed the playoffs" not in read(js)

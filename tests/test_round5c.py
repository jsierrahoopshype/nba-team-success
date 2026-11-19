# (c) 2026 HoopsMatic. All rights reserved.
"""Round 5, part C: board filters and labels, the clickable head-to-head scoreboard."""
import json
import os
import re
import subprocess
import sys
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import boards as B  # noqa: E402

pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")), reason="site not built")
LONG = "Help is the Teammates Score of the teammates he shared games with; the smaller number is tinted."


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def data():
    return json.loads(read("assets/board.json"))


def test_no_allstar_board_labels():
    t = read("lists/no-allstar-teammate.html")
    assert "<h1>Most wins without an All-Star teammate</h1>" in t
    taps = t[t.index('class="sorttaps"'):t.index("</p>", t.index('class="sorttaps"'))]
    assert ">Wins</a>" in taps and "?sort=wl" in taps and "?sort=pct" in taps
    assert 'data-l="Games in this view"' in t                                   # sample in every row
    for key in B.BOARDS:                                                        # same labels everywhere
        b = read(f"lists/{key}.html")
        assert "<legend>Games in this filtered sample</legend>" in b and "Career All-Star (any season)" in b
        assert "All-Star that season (pick one season)" in b and 'name="from"' in b
        assert "<legend>Career games</legend>" not in b


def test_long_sentence_nowhere():
    out = subprocess.run(["grep", "-rlF", LONG, "--include=*.html", "--include=*.js", ROOT + "/compare",
                          ROOT + "/player", ROOT + "/lists", ROOT + "/assets", ROOT + "/index.html"],
                         capture_output=True, text=True).stdout.strip()
    assert out == ""
    for rel in ("compare/karl-malone--michael-jordan.html", "assets/compare.js"):
        t = read(rel)
        assert "Lower is better for finish and help. With vs without isn't counted. Team results, not who was better." in t


def _rows(data, board, q):
    flt = {}
    if q.get("sort"):
        flt["sort"] = q["sort"][0]
    ranked, sort, mins = B.compute(data, board, flt)
    return {m["slug"]: r for r, t, m in ranked}


def test_scoreboard_links_resolve(data):
    """Every scoreboard link opens an existing board (or the rules / player page) and every
    highlighted player has a row in that board view."""
    for rel in ("compare/michael-jordan--tim-duncan.html", "compare/karl-malone--michael-jordan.html",
                "compare/charles-barkley--michael-jordan.html"):
        if not os.path.exists(os.path.join(ROOT, rel)) or "Moved" in read(rel)[:400]:
            continue
        t = read(rel)
        sb = t[t.index('<table class="sbt"'):t.index("</table>", t.index('<table class="sbt"'))]
        links = [unescape(h) for h in re.findall(r'<a class="cl" href="([^"]+)"', sb)]
        assert len(links) == 8 * 3, rel
        for h in links:
            u = urlsplit(h)
            path = os.path.normpath(os.path.join(ROOT, "compare", u.path))
            assert os.path.exists(path), h
            if "/lists/" in h:
                board = os.path.basename(u.path)[:-5]
                assert board in B.BOARDS
                q = parse_qs(u.query)
                have = _rows(data, board, q)
                for sl in (q.get("hl", [""])[0].split(",") if q.get("hl") else []):
                    assert sl in have, (h, sl)
                if u.fragment:
                    assert u.fragment[2:] in have
    js = read("assets/compare.js")
    assert "sbHrefs" in js and '"Career record": ["career-wins", "sort=pct"' in js


def test_two_player_highlight():
    js = read("assets/boards.js")
    assert '(f.hl || "").split(",")' in js and "higher-ranked" in js

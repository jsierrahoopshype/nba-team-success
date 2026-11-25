# (c) 2026 HoopsMatic. All rights reserved.
"""Nov. 24 changes: every passed player named, the Tonight sentence, the homepage with/without boxes,
the playoff and regular season + playoffs boards, no "help coming in", the "2026-27 so far" card line."""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import boards as B  # noqa: E402
import daily_story as D  # noqa: E402

built = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")), reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def text(parts):
    return "".join(p[0] for p in parts)


def names(n, notes=None):
    notes = notes or {}
    return [(D.L(f"P{i}", f"player/p{i}.html"), notes.get(i, "")) for i in range(1, n + 1)]


# ---- "Last night": name every player passed -------------------------------------------------
def test_name_listing_rule():
    """Up to 7 players passed: every name, linked, labels kept. 8 or more: the 3 most notable, then
    "and N others" (N >= 5) linking to the board. Never "and 1 other" ... "and 4 others"."""
    assert text(D.join_names(names(1, {1: " (Hall of Famer)"}), "x")) == "P1 (Hall of Famer)"
    assert text(D.join_names(names(2, {1: " (Hall of Famer)"}), "x")) == "P1 (Hall of Famer) and P2"
    assert text(D.join_names(names(3), "x")) == "P1, P2 and P3"
    assert text(D.join_names(names(4), "x")) == "P1, P2, P3 and P4"
    assert text(D.join_names(names(7), "x")) == "P1, P2, P3, P4, P5, P6 and P7"
    eight = D.join_names(names(8), "lists/career-wins.html?hl=a#p-a")
    assert text(eight) == "P1, P2, P3 and 5 others"
    assert eight[-1] == ["5 others", "lists/career-wins.html?hl=a#p-a", 0]              # links to the board
    assert text(D.join_names(names(12), "x")).endswith("P3 and 9 others")
    for n in range(1, 30):
        t = text(D.join_names(names(n), "x"))
        assert not re.search(r"and [1-4] others?\b", t) and "more players" not in t, (n, t)
        linked = sum(1 for p in D.join_names(names(n), "x") if len(p) == 3 and p[1].startswith("player/"))
        assert linked == (n if n < 8 else 3)


def test_name_listing_2_to_4_all_named():
    for n in (2, 3, 4):
        t = text(D.join_names(names(n), "x"))
        assert all(f"P{i}" in t for i in range(1, n + 1)) and "other" not in t


def test_tonight_wording():
    parts = D.tonight_parts(D.L("Isaiah Hartenstein", "player/isaiah-hartenstein.html", True), "Indiana Pacers",
                            D.L("13–3", "player/isaiah-hartenstein.html?vs=IND#vs-IND"), 13 / 16)
    assert text(parts) == ("Isaiah Hartenstein faces the Indiana Pacers tonight. His teams are 13–3 against them "
                           "in the regular season, an 81.2% win rate.")
    assert parts[0][1] == "player/isaiah-hartenstein.html" and parts[2][1].endswith("?vs=IND#vs-IND")
    assert text(D.tonight_parts(D.L("A", "a"), "Utah Jazz", D.L("7–3", "b"), 0.7)).endswith("a 70.0% win rate.")
    assert text(D.tonight_parts(D.L("A", "a"), "Utah Jazz", D.L("2–9", "b"), 2 / 11)).endswith("an 18.2% win rate.")


def test_last_night_sources_have_no_scope_suffix_or_others():
    src = read("scripts/daily_story.py")
    assert "other{'s'" not in src and " and {len(passed) - 1} other" not in src
    assert '({B.SCOPE_LIVE}).")' not in src and "on the board ({B.scope_label" not in src
    # no season-scope parenthetical in any sentence of the list or the fun facts
    for f in ("scripts/daily_story.py", "scripts/fun_facts.py"):
        # sentence parts only; an item's scope= field is metadata, never shown
        body = "\n".join(re.sub(r'scope=(f?"[^"]*"|[\w.]+(\([^)]*\))?)', "", line)
                         for line in read(f).splitlines() if "T(" in line or "L(" in line)
        assert "to date" not in body and "SCOPE_LIVE" not in body, f
    assert "Tonight vs the" not in src and "Tonight vs the" not in read("scripts/fun_facts.py")
    assert "Tonight vs the" not in read("docs/story-rules.md")


# ---- homepage with/without: no empty box ------------------------------------------------------
@built
def test_homepage_with_without_no_empty_box():
    t = read("index.html")
    assert "Nobody yet" not in t and 'class="ww-wait"' not in t
    if "so far: with and without</h2>" in t:
        sec = t[t.index("so far: with and without</h2>"):t.index("<h2>Last 30 days")]
        boxes = sec.count('<div class="box">')
        assert boxes in (1, 2) and ('<div class="dgrid one">' in sec) == (boxes == 1)
        assert sec.count("<li>") >= 1 and "10+ games played and 5+ missed" in sec
    css = read("assets/ts.css")
    assert ".dgrid.one{grid-template-columns:minmax(0,1fr)}" in css


# ---- new boards ---------------------------------------------------------------------------------
@built
def test_playoff_and_combined_boards():
    data = json.loads(read("assets/board.json"))
    r, sort, mins = B.compute(data, "playoff-wins", {})
    assert sort == "pw" and r[0][2]["slug"] == "lebron-james" and all(x[2]["pgp"] > 0 for x in r)
    top = r[0][2]
    assert top["pw"] + top["pl"] == top["pgp"] and top["pwl"] == top["pw"] - top["pl"]
    r2, _, _ = B.compute(data, "playoff-wins", {"sort": "ppct"})
    assert all(x[2]["pgp"] >= 50 for x in r2)
    r3, sort3, _ = B.compute(data, "combined-wins", {})
    assert sort3 == "cpct" and all(x[2]["cgp"] >= 500 for x in r3)
    m = r3[0][2]
    assert m["cw"] == m["w"] + m["pw"] and m["cgp"] == m["gp"] + m["pgp"]
    assert "combined-wins" in B.LIVE_BOARDS and "playoff-wins" not in B.LIVE_BOARDS
    for key in ("playoff-wins", "combined-wins"):
        t = read(f"lists/{key}.html")
        assert f'<link rel="canonical" href="https://hoopsmatic.com/team-success/lists/{key}.html">' in t
        assert f'<meta property="og:image" content="https://hoopsmatic.com/og/team-success/list/{key}.png">' in t
        assert f"lists/{key}.html</loc>" in read("sitemap.xml")
    h = read("index.html")
    sec = h[h.index('<h2 id="leaderboards">'):]
    sec = sec[:sec.index("</section>")]
    heads = re.findall(r'<div class="boxhead">([^<]+?) <a href="([^"]+)">', sec)
    assert len(heads) == 12
    assert [x[0] for x in heads[-3:]] == ["Most playoff wins", "Playoff W − L", "Regular season + playoffs win %"]
    assert heads[-2][1] == "lists/playoff-wins.html?sort=pwl"


# ---- teammate help: same season only ---------------------------------------------------------
@built
def test_no_help_coming_in_anywhere():
    for rel in ("player/aaron-wiggins.html", "player/draymond-green.html", "player/michael-jordan.html",
                "comparison-rules.html", "how-we-count.html", "lists/low-help-all-stars.html", "index.html"):
        t = read(rel).lower()
        assert "coming in" not in t and "help entering" not in t and ">entering<" not in t, rel
    t = read("player/draymond-green.html")
    sec = t[t.index('id="cap-help"'):]
    sec = sec[:sec.index("</section>")]
    assert "<details>" not in sec and "Help this season: <strong>pending</strong>" in sec
    assert "Other teammates (no honors that season)" in sec
    pg = json.loads(read("assets/pg/draymond-green.json"))
    assert all(v[1] is None for v in pg["h"].values())


# ---- finished-season cards: "2026-27 so far" -------------------------------------------------
@built
def test_so_far_line_on_finished_season_cards():
    cur = json.loads(read("data/current.json"))
    ids = json.loads(read("data/player_ids.json"))
    pid = next(k for k, v in ids.items() if v["slug"] == "draymond-green")
    w = sum(x["w"] for x in cur["players"][pid])
    l = sum(x["l"] for x in cur["players"][pid])
    t = read("player/draymond-green.html")
    for board in ("winning-seasons", "playoff-trips", "average-finish", "titles", "deepest-run"):
        card = re.search(rf'<a class="card[^"]*" href="../lists/{board}\.html[^"]*">.*?</a>', t, re.S).group(0)
        assert f'<span class="sub sofar">2026-27 so far: {w}–{l}</span>' in card, board
        assert "through 2025-26" in card
    for board in ("career-wins", "wins-minus-losses"):
        card = re.search(rf'<a class="card[^"]*" href="../lists/{board}\.html[^"]*">.*?</a>', t, re.S).group(0)
        assert "so far:" not in card
    assert "so far:" not in read("player/michael-jordan.html").split('id="cap-seasons"')[0]

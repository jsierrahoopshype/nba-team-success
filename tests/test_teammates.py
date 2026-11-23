# (c) 2026 HoopsMatic. All rights reserved.
"""With and without a teammate (scripts/teammates.py): the span rule, the 20-game cutoff, the
"Biggest teammate swings" qualification rule, the Draymond Green / Stephen Curry pair, and the blocks
on the player, compare and list pages."""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import teammates as TM  # noqa: E402
from common import CURRENT_SEASON, DATA, LAST_COMPLETE, load_json  # noqa: E402

built = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "lists", "teammate-swings.html")), reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def pairs():
    return TM.all_pairs()


@pytest.fixture(scope="module")
def ids():
    return load_json(os.path.join(DATA, "player_ids.json"))


def pid_of(ids, slug):
    return next(k for k, v in ids.items() if v["slug"] == slug)


# ---- the span rule ---------------------------------------------------------------------------
def test_stint_spans_split_on_a_trade_and_back():
    apps = [("2001-11-01", "g1", "AAA"), ("2001-11-03", "g2", "AAA"), ("2001-12-01", "g3", "BBB"),
            ("2002-01-10", "g4", "AAA"), ("2002-02-01", "g5", "AAA")]
    assert TM.stint_spans(apps) == {"AAA": [["2001-11-01", "2001-11-03"], ["2002-01-10", "2002-02-01"]],
                                    "BBB": [["2001-12-01", "2001-12-01"]]}


def test_span_rule_is_the_one_the_player_numbers_use():
    """Games each player missed inside his spans equal the stored span counts (sw / sl) of the
    existing with/without numbers, for every player-team-season, history and the season to date."""
    players = load_json(os.path.join(DATA, "players.json"))
    cur = load_json(os.path.join(DATA, "current.json"))
    stored = {(pid, s["f"], s["s"]): s for pid, p in players.items() for s in p["seasons"]}
    checked = bad = 0
    for sy in range(1947, CURRENT_SEASON + 1):
        live = sy == CURRENT_SEASON and sy > LAST_COMPLETE
        games = TM.season_games(sy, cur if live else None)
        spans = TM.season_spans(games)
        for fr, t in TM.team_season_masks(games).items():
            for b, played in t["played"].items():
                sp = spans[b].get(fr, [])
                if live:
                    ref = next(((x.get("sw", 0), x.get("sl", 0)) for x in cur["players"].get(b, []) if x["f"] == fr), None)
                else:
                    st = stored.get((b, fr, sy))
                    ref = (st.get("sw", 0), st.get("sl", 0)) if st else None
                    if st:
                        assert st.get("span") == sp, (b, fr, sy)
                if ref is None:
                    continue
                m = TM.span_mask(t["dates"], sp) & ~played
                w = TM.pc(m & t["win"])
                checked += 1
                bad += (w, TM.pc(m) - w) != ref
    assert checked > 29000 and bad == 0


def test_without_counts_only_inside_the_teammates_span():
    """A tiny season: B plays games 2-4 of 6; A plays all 6. A without B = game 3 only (B missed it
    inside his span); games 1, 5 and 6 are outside B's span and count nowhere."""
    a, b = "1", "2"
    games = []
    for i, (bp, won) in enumerate([(0, 1), (1, 1), (0, 0), (1, 0), (0, 1), (0, 1)]):
        games.append((f"g{i}", f"2001-11-0{i + 1}", "AAA", "ZZZ", bool(won), [a] + ([b] if bp else []), []))
    games[3] = ("g3", "2001-11-04", "AAA", "ZZZ", False, [a, b], [])
    t = TM.team_season_masks(games)["AAA"]
    sp = TM.season_spans(games)
    mb = TM.span_mask(t["dates"], sp[b]["AAA"])
    pa, pb = t["played"][a], t["played"][b]
    assert TM.pc(pa & pb) == 2                     # games 2 and 4
    wo = pa & mb & ~pb
    assert TM.pc(wo) == 1 and not (wo & t["win"])  # game 3, a loss


# ---- the 20-game cutoff ------------------------------------------------------------------------
def test_too_few_cutoff():
    assert TM.TOO_FEW_WITHOUT == 20
    assert TM.too_few({"t": [50, 50], "o": [10, 9]})          # 19 games without him
    assert not TM.too_few({"t": [50, 50], "o": [10, 10]})     # 20


@built
def test_player_page_too_few_rows():
    t = read("player/draymond-green.html")
    sec = t[t.index('<section id="mates">'):t.index("</section>", t.index('<section id="mates">'))]
    rows = re.findall(r'<li class="mate" data-g="(\d+)" data-gap="([^"]*)">(.*?)</li>', sec, re.S)
    assert len(rows) == 12
    games = [int(g) for g, _, _ in rows]
    assert games == sorted(games, reverse=True)             # most games together first
    for g, gap, body in rows:
        w, l = map(int, re.findall(r'Without him</dt><dd><span class="mono">(\d+)–(\d+)', body)[0])
        if w + l < 20:
            assert gap == "" and "Too few games without him" in body
        else:
            assert gap and re.search(r"\d+\.\d points (lower|higher)|even", body) and "Too few" not in body
        assert 'href="../player/' in body                    # the teammate links to his page
        assert "nba-career-map/team/" in body                # each team links to its page
        assert "pp" not in re.sub(r"<[^>]+>", "", body).split()


# ---- the list's qualification rule ---------------------------------------------------------------
def test_qualification_rule():
    ok = {"t": [70, 30], "o": [10, 30]}                      # 100 together, 40 without, 45 points
    assert TM.qualifies(ok)
    assert not TM.qualifies({"t": [69, 30], "o": [10, 30]})  # 99 together
    assert not TM.qualifies({"t": [70, 30], "o": [10, 29]})  # 39 without
    assert not TM.qualifies({"t": [10, 30], "o": [70, 30]})  # better without him: never listed
    weak = {"t": [55, 45], "o": [20, 20]}                    # 5 points: luck can do that
    assert abs(TM.z_score(weak)) < 2.58 and not TM.qualifies(weak)
    assert TM.SWING_Z == 2.58


@built
def test_swings_page_rows_qualify(pairs, ids):
    t = read("lists/teammate-swings.html")
    players = load_json(os.path.join(DATA, "players.json"))
    slug = {v["slug"]: k for k, v in ids.items()}
    want_all = sum(1 for (a, b), r in pairs.items() if a in ids and b in ids and TM.qualifies(r))
    want_as = sum(1 for (a, b), r in pairs.items() if a in ids and b in ids and TM.qualifies(r) and players.get(b, {}).get("as"))
    assert f"{want_as:,} pairs qualify." in t and f"{want_all:,} pairs qualify." in t
    for tag, n in (("as", want_as), ("all", want_all)):
        got = re.findall(rf'<li id="{tag}-([a-z0-9-]+?)--([a-z0-9-]+)"><span class="rk mono">(\d+)</span>', t)
        assert len(got) == n
        prev_gap, prev_rank = None, 0
        for i, (sa, sb, rk) in enumerate(got):
            r = pairs[(slug[sa], slug[sb])]
            assert TM.qualifies(r)
            g = round(100 * TM.gap(r), 1)
            assert prev_gap is None or g <= prev_gap          # biggest drop first
            assert int(rk) == (prev_rank if g == prev_gap else i + 1)   # ties share a number
            prev_gap, prev_rank = g, int(rk)
    top = re.findall(r'<li id="as-([a-z0-9-]+?)--([a-z0-9-]+)">', t)[:3]
    assert top[1] == ("john-paxson", "michael-jordan")
    assert ("alvin-williams", "vince-carter") in top and ("damion-lee", "stephen-curry") in top
    assert '<meta name="robots"' not in t                    # indexed
    assert "lists/teammate-swings.html</loc>" in read("sitemap.xml")
    assert 'href="lists/teammate-swings.html"' in read("index.html")


# ---- Draymond Green and Stephen Curry ------------------------------------------------------------
def test_draymond_curry(pairs, ids):
    dg, sc = pid_of(ids, "draymond-green"), pid_of(ids, "stephen-curry")
    r, q = pairs[(dg, sc)], pairs[(sc, dg)]
    assert r["t"] == q["t"]                                   # together is the same both ways
    # completed seasons (prototype): 557-237 together; 50-86 and 49-34 without
    w, l = r["t"]
    assert w >= 557 and l >= 237 and w + l <= 557 + 237 + 82
    assert r["o"][0] >= 50 and r["o"][1] >= 86 and q["o"][0] >= 49 and q["o"][1] >= 34
    assert abs(100 * TM.pct(r["o"]) - 36.8) < 2 and abs(100 * TM.gap(r) - 33.4) < 2
    assert TM.qualifies(r) and not TM.qualifies(q)           # Curry's drop is not past z 2.58
    jp, mj = pid_of(ids, "john-paxson"), pid_of(ids, "michael-jordan")
    assert pairs[(jp, mj)]["t"] == [362, 190] and pairs[(jp, mj)]["o"] == [20, 46]


@built
def test_draymond_curry_on_the_pages(pairs, ids):
    dg, sc = pid_of(ids, "draymond-green"), pid_of(ids, "stephen-curry")
    r = pairs[(dg, sc)]
    t = read("player/draymond-green.html")
    i = t.index('<section id="mates">')
    assert t.index("<h2>Career</h2>") < i < t.index("<h2>Latest completed seasons</h2>")
    sec = t[i:t.index("</section>", i)]
    first = re.search(r'<li class="mate".*?</li>', sec, re.S).group(0)
    assert "stephen-curry.html" in first and f"{r['t'][0]}–{r['t'][1]}" in first and f"{r['o'][0]}–{r['o'][1]}" in first
    assert "points lower" in first
    pg = json.loads(read("assets/pg/draymond-green.json"))
    assert len(pg["tm"]) == 12 and pg["tm"][0][:5] == ["stephen-curry", *r["t"], *r["o"]]
    tm = json.loads(read("assets/tm/stephen-curry.json"))["m"]["draymond-green"]
    assert tm[:4] == [*pairs[(sc, dg)]["t"], *pairs[(sc, dg)]["o"]]


@built
def test_compare_block_only_for_teammates():
    js = read("assets/compare.js")
    assert "assets/tm/" in js and "As teammates" in js
    never = read("compare/charles-barkley--michael-jordan.html")
    assert "As teammates" not in never
    pages = [f for f in os.listdir(os.path.join(ROOT, "compare")) if f.endswith(".html") and "--" in f]
    with_block = [f for f in pages if "As teammates" in read(f"compare/{f}")]
    assert with_block
    t = read(f"compare/{with_block[0]}")
    assert t.count("without") >= 2 and 'content="noindex, follow"' in t

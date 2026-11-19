# (c) 2026 HoopsMatic. All rights reserved.
"""Career leaderboards, season boards and the player-page finish (no network).

The browser half of the boards (assets/boards.js) is run under Node when it is installed and
must rank exactly like scripts/boards.py.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import analysis as A  # noqa: E402
import boards as B  # noqa: E402
from common import CURRENT_SEASON, LAST_COMPLETE, season_label  # noqa: E402


@pytest.fixture(scope="module")
def data():
    with open(os.path.join(ROOT, "assets", "board.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def d():
    return A.Data(live=True)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_board_metrics_match_career_summary(data, d):
    for row in data["p"]:
        m = B.player_metrics(row, data["t"], {})
        sm = A.summary(d, row[0])
        assert (m["w"], m["l"], m["ow"], m["ol"]) == (sm["w"], sm["l"], sm["ow"], sm["ol"])
        assert (m["winning"], m["trips"], m["titles"], m["seasons"]) == (
            sm["winning"], sm["trips"], sm["titles"], sm["seasons"])
        assert (m["avg"] is None and sm["rnk"] is None) or abs(m["avg"] - sm["rnk"]) < 1e-9


def test_jordan_card_ranks_match_board_pages():
    t = read("player/michael-jordan.html")
    for key in B.BOARDS:
        if not B.BOARDS[key].get("noas"):               # the eight career cards
            assert f'lists/{key}.html?hl=michael-jordan#p-michael-jordan' in t, key
    m = re.search(r'wins-minus-losses\.html\?hl=michael-jordan.*?<span class="rk">(T-)?#?(\d+) of ([\d,]+) · incl\. ', t, re.S)
    assert m
    board = read("lists/wins-minus-losses.html")
    row = re.search(r'<tr id="p-michael-jordan"><td data-l="Rank" class="mono" data-value="(\d+)"><span class="v">(T-)?\d+', board)
    assert row and row.group(1) == m.group(2) and bool(row.group(2)) == bool(m.group(1))


FILTERS = [{}, {"from": 1977}, {"ts": 20}, {"team": "CHI"}, {"as": "ever"}, {"season": 1998, "as": "season"},
           {"st": "active"}, {"cg": 500}, {"from": 1990, "to": 2005, "ts": 41}, {"to": 2026}, {"self": "no"},
           {"self": "yes"}]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_ranks_like_python(data, tmp_path):
    cases = []
    for key, dfn in B.BOARDS.items():
        for srt in dfn["sorts"]:
            for f in FILTERS:
                cases.append({"b": key, "f": dict(f, sort=srt),
                              "def": {"sorts": {k: list(v) for k, v in dfn["sorts"].items()}, "cols": dfn["cols"],
                                      "noas": 1 if dfn.get("noas") else 0}})
    cp = tmp_path / "cases.json"
    cp.write_text(json.dumps(cases))
    js = ("const fs=require('fs');const B=require(process.argv[1]);const d=JSON.parse(fs.readFileSync(process.argv[2]));"
          "const c=JSON.parse(fs.readFileSync(process.argv[3]));process.stdout.write(JSON.stringify(c.map(x=>{"
          "const r=B.run(d,x.def,Object.assign({},x.f));return {sort:r.sort,n:r.rows.length,"
          "top:r.rows.slice(0,150).map(m=>[m._rank,m._tied,m.slug])};})));")
    out = subprocess.run(["node", "-e", js, os.path.join(ROOT, "assets", "boards.js"),
                          os.path.join(ROOT, "assets", "board.json"), str(cp)],
                         capture_output=True, text=True, check=True).stdout
    for c, j in zip(cases, json.loads(out)):
        f = dict(c["f"])
        if "season" in f:
            f["from"] = f["to"] = f["season"]
        r, srt, _ = B.compute(data, c["b"], f)
        assert j == {"sort": srt, "n": len(r), "top": [[x[0], x[1], x[2]["slug"]] for x in r[:150]]}, c


def test_one_season_board_per_season():
    for sy in range(1947, LAST_COMPLETE + 1):
        assert os.path.exists(os.path.join(ROOT, "seasons", f"{season_label(sy)}.html")), sy


def test_player_finish_matches_season_board(d):
    t = read("player/michael-jordan.html")
    assert 'href="../seasons/1997-98.html#t-CHI">#1 of 29</a>' in t
    assert 'href="../seasons/1994-95.html#t-CHI">#8 of 27</a>' in t
    board = read("seasons/1994-95.html")
    row = re.search(r'<tr id="t-CHI">(.*?)</tr>', board, re.S).group(1)
    assert "#8 of 27" in row and "Chicago Bulls" in row


def test_season_board_ranks_are_the_csv_rnk(d):
    for sy in (1947, 1975, 1998, 2026):
        board = read(f"seasons/{season_label(sy)}.html")
        for t in d.teams.values():
            if t["s"] == sy:
                row = re.search(rf'<tr id="t-{t["f"]}">(.*?)</tr>', board, re.S).group(1)
                assert f'#{t["rnk"]} of ' in row, (sy, t["f"])


def test_leads_are_templates():
    t = read("player/michael-jordan.html")
    lead = re.search(r'<p class="lead">(.*?)</p>', t).group(1)
    assert lead.startswith("His teams won 6 titles: 1990-91 to 1992-93 and 1995-96 to 1997-98.")
    for bad in ("carried", "lifted", "dragged", "made the", "led his", "thanks to"):
        assert bad not in lead


def test_no_allstar_board_sanity(data):
    r, srt, _ = B.compute(data, "no-allstar-teammate", {"to": 2026})
    top = {m["name"]: (m["w"], m["l"], m["seasons"]) for _, _, m in r[:3]}
    assert top["Dirk Nowitzki"] == (544, 422, 14)
    assert top["Andre Miller"][:2] == (529, 548)
    r4 = {m["name"]: (m["w"], m["l"]) for _, _, m in r[:4]}
    assert r4["Nikola Jokic"] == (452, 293)          # 2025-26 (43-22) is out: Jamal Murray was an All-Star
    r, srt, _ = B.compute(data, "no-allstar-teammate", {"to": 2026, "sort": "pct"})
    assert [m["name"] for _, _, m in r[:3]] == ["Tim Duncan", "James Harden", "Rasheed Wallace"]
    assert (r[0][2]["w"], r[0][2]["l"]) == (360, 155)


def test_no_allstar_board_leaves_out_seasons_without_honors(data, d):
    """The season in progress (no All-Stars named yet) is left out, not counted as "no All-Star
    teammate", and the board says so; 2025-26 is counted now that awards.json has it. Seasons with no All-Star Game (1946-47 to
    1949-50, 1998-99) still have honors, so they count."""
    with open(os.path.join(ROOT, "data", "help.json"), encoding="utf-8") as fh:
        h = json.load(fh)
    miss = B.honors_missing(d, h)
    assert 2026 not in miss and 1947 not in miss and 1999 not in miss
    for row in data["p"]:
        for st in row[5]:
            assert st[12] == (1 if st[0] in miss else 0)
    a, _, _ = B.compute(data, "no-allstar-teammate", {})
    b, _, _ = B.compute(data, "no-allstar-teammate", {"to": min(miss) - 1})
    assert [(x[2]["slug"], x[2]["w"], x[2]["l"]) for x in a[:200]] == [(x[2]["slug"], x[2]["w"], x[2]["l"]) for x in b[:200]]
    t = read("lists/no-allstar-teammate.html")
    if miss == [CURRENT_SEASON]:
        assert f"{season_label(CURRENT_SEASON)} is left out until its All-Stars are named." in t
    else:
        assert f"{season_label(min(miss))} onward not counted yet: honors missing from the awards data" in t


def test_average_finish_defaults_to_league_size_adjusted(d):
    t = read("lists/average-finish.html")
    assert 'data-sort="adj" aria-sort="ascending"' in t
    assert "1 + (rank − 1) / (teams − 1) × 29" in t
    p = read("player/michael-jordan.html")
    m = re.search(r'average-finish\.html\?hl=michael-jordan.*?<span class="big mono">([\d.]+) of 30</span>', p, re.S)
    assert m
    jordan = next(k for k, v in d.ids.items() if v["slug"] == "michael-jordan")
    vals = []
    for sy, (main, end, lst) in d.season_main(jordan).items():
        tm = d.team(main["f"], sy)
        n = sum(1 for x in d.teams.values() if x["s"] == sy)
        vals.append((tm["rnk"] - 1) / (n - 1))
    assert m.group(1) == f"{1 + 29 * sum(vals) / len(vals):.1f}"
    assert "adjusted for league size" in p
    assert "1 + adjusted × 29" in read("how-we-count.html")


def test_gap_board_matches_card():
    t = read("player/michael-jordan.html")
    board = read("lists/gap-career.html")
    row = re.search(r'<tr id="p-michael-jordan">(.*?)</tr>', board, re.S).group(1)
    assert "706\u2013366, 65.9%" in row and "63\u201395, 39.9%" in row and "+26.0" in row
    assert "65.9% · 39.9%" in t and "26.0 points higher" in t


def test_live_season_in_totals(data, d):
    """Career W-L counts the season in progress; season counts do not."""
    kawhi = next(k for k, v in d.ids.items() if v["slug"] == "kawhi-leonard")
    sm = A.summary(d, kawhi)
    sm0 = A.summary(A.Data(), kawhi)
    assert sm["w"] + sm["l"] > sm0["w"] + sm0["l"] and sm["seasons"] == sm0["seasons"]

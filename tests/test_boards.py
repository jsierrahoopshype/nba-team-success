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
from common import LAST_COMPLETE, season_label  # noqa: E402


@pytest.fixture(scope="module")
def data():
    with open(os.path.join(ROOT, "assets", "board.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def d():
    return A.Data()


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
        assert abs(m["avg"] - sm["rnk"]) < 1e-9


def test_jordan_card_ranks_match_board_pages():
    t = read("player/michael-jordan.html")
    for key in B.BOARDS:
        assert f'lists/{key}.html?hl=michael-jordan#p-michael-jordan' in t, key
    m = re.search(r'wins-minus-losses\.html\?hl=michael-jordan.*?<span class="rk">#(\d+)( \(tied\))? of ([\d,]+)', t, re.S)
    assert m
    board = read("lists/wins-minus-losses.html")
    row = re.search(r'<tr id="p-michael-jordan"><td data-l="Rank" class="mono" data-value="(\d+)"><span class="v">(T-)?\d+', board)
    assert row and row.group(1) == m.group(1) and bool(row.group(2)) == bool(m.group(2))


FILTERS = [{}, {"from": 1977}, {"ts": 20}, {"team": "CHI"}, {"as": "ever"}, {"season": 1998, "as": "season"},
           {"st": "active"}, {"cg": 500}, {"from": 1990, "to": 2005, "ts": 41}]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_ranks_like_python(data, tmp_path):
    cases = []
    for key, dfn in B.BOARDS.items():
        for srt in dfn["sorts"]:
            for f in FILTERS:
                cases.append({"b": key, "f": dict(f, sort=srt),
                              "def": {"sorts": {k: list(v) for k, v in dfn["sorts"].items()}, "cols": dfn["cols"]}})
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

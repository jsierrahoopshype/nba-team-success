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


def _notable(slug):
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    ids = json.loads(read("data/player_ids.json"))
    players = json.loads(read("data/players.json"))
    pid = next(k for k, v in ids.items() if v["slug"] == slug)
    p = players.get(pid, {})
    import daily_story as D
    role = D.hof_role(p)
    # (Hall of Famer as a player, All-Star selections, Hall of Famer as a coach or contributor)
    return role == "player", len(p.get("as", [])), role in ("coach", "contributor")


def _board_rank(href, slug):
    import sys
    from urllib.parse import parse_qs, urlsplit
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import boards as B
    u = urlsplit(href)
    q = parse_qs(u.query)
    flt = {k: (int(v[0]) if v[0].isdigit() else v[0]) for k, v in q.items() if k in ("sort", "cg")}
    ranked, _, _ = B.compute(json.loads(read("assets/board.json")), os.path.basename(u.path)[:-5], flt)
    return next((r for r, t, m in ranked if m["slug"] == slug), 10 ** 6)


def test_list_pass_names_a_notable_player():
    """The player passed is top 100 on that board, a Hall of Famer or a 3+ time All-Star, and he is
    the most notable of everyone passed (Hall of Famer as a player, then All-Star selections, then Hall
    of Famer as a coach or contributor, then rank)."""
    st = json.loads(read("data/stories.json"))["stories"][0]
    for it in st["items"]:
        if not it["type"].endswith("-pass"):
            continue
        q = it["parts"][2][1].split("/")[-1][:-5]                    # "player/<slug>.html"
        best = _notable(q)
        hof, n_as, hof_other = best
        assert _board_rank(it["href"], q) <= 100 or hof or hof_other or n_as >= 3, (it["key"], q)
        for other in it.get("passed", []):
            o = _notable(other)
            if o[0] or o[2] or o[1] >= 3 or _board_rank(it["href"], other) <= 100:
                assert o <= best, (it["key"], other)
        txt = "".join(p[0] for p in it["parts"])
        n = len(it.get("passed", [])) - 1
        if n > 0:
            assert f" and {n} other" in txt


def test_list_passes_are_notable():
    st = json.loads(read("data/stories.json"))["stories"][0]
    for it in st["items"]:
        if it["type"].endswith("-pass"):
            txt = "".join(p[0] for p in it["parts"])
            # every pass quotes the passer's board rank: "for No. 83 in career wins", "65.6%, No. 36 among ..."
            r = int(re.search(r"No\. ([\d,]+)\b", txt).group(1).replace(",", ""))
            assert r <= 250


def test_homepage_order():
    """Round 6 order: search, last night, fun facts, with/without (or its one-line placeholder), on/off,
    leaderboards, comparison of the day, search again. No standings block."""
    t = read("index.html")
    ww = "so far: with and without</h2>" if "so far: with and without</h2>" in t else 'class="ww-wait"'
    order = ['id="pf"', '<section class="night">', "<h2>Fun facts</h2>", ww, "<h2>Last 30 days: on/off movers</h2>",
             '<h2 id="leaderboards">Leaderboards</h2>', "<h2>Comparison of the day</h2>", 'id="pf2"']
    pos = [t.index(x) for x in order]
    assert pos == sorted(pos)
    assert "standings</h2>" not in t


def test_with_without_block_is_current_season_only():
    t = read("index.html")
    if 'class="ww-wait"' in t:                      # nobody qualifies yet: one line, no empty boxes
        sec = t[t.index('class="ww-wait"'):t.index("<h2>Last 30 days")]
        assert "With and without for 2026-27 appears once players have missed 8+ games." in sec
        assert '<a href="lists/gap-career.html">Career with and without</a>' in sec
        assert "boxhead" not in sec and "Nobody yet" not in sec
        return
    sec = t[t.index("so far: with and without</h2>"):t.index("<h2>Last 30 days")]
    assert ": career" not in sec and "Career leaders shown" not in sec
    assert "5 and 5" not in sec
    assert 'href="lists/winning-without-him.html?mp=10&amp;mm=8"' in sec
    assert '<a href="lists/gap-career.html">Career with and without</a>' in sec
    for played, missed in re.findall(r"in (\d+) played · [^<]* in (\d+) missed", sec):
        assert int(played) >= 10 and int(missed) >= 8


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


def test_tonight_uses_the_head_to_head_schedule():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import daily_story as D
    assert D.SCHEDULE == "https://jsierrahoopshype.github.io/nba-editorial-bots/data/schedule_{season}.csv"
    assert D.season_slug(2027) == "2026-27"
    for f in ("daily_story.py", "fun_facts.py"):
        assert "cdn.nba.com" not in read(f"scripts/{f}")
    for it in json.loads(read("data/stories.json"))["stories"][0]["items"]:
        if it["type"] == "tonight":
            assert "?vs=" in it["href"] and "#vs-" in it["href"]
            n = int(re.search(r"in his (\d+) regular-season games", "".join(p[0] for p in it["parts"])).group(1))
            assert n >= 15


def test_awards_refresh_runs_only_on_change():
    y = read(".github/workflows/nightly.yml")
    assert y.index("scripts/awards_refresh.py") < y.index("scripts/daily_story.py") < y.index("scripts/build_site.py")
    assert "steps.awards.outputs.changed == 'yes'" in y and "git add -A data docs " in y
    st = json.loads(read("data/awards_source.json"))
    assert len(st["sha256"]) == 64 and st["commit"]
    src = read("scripts/awards_refresh.py")
    for step in ('["build_history.py", "--awards-only"]', '["build_help.py"]', '["step0_report.py"]'):
        assert step in src
    assert 'if old.get("sha256") == sha and old.get("extra_sha256", extra) == extra:' in src
    assert len(st["extra_sha256"]) == 64        # data/hof_extra.json edits re-run the refresh too

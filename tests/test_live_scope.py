# (c) 2026 HoopsMatic. All rights reserved.
"""Numbers counted from games include the season to date (Best duos, the "(to date)" rows of the season
and on/off tables, records against each opponent, the franchise list, the tonight items); numbers that
need a finished season stay through the last completed season."""
import html
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analysis as A  # noqa: E402
import boards as B  # noqa: E402
import teammates as TM  # noqa: E402
from common import CURRENT_SEASON, DATA, LAST_COMPLETE, load_json, season_label  # noqa: E402

pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")), reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def text(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def section(t, marker):
    i = t.index(marker)
    return t[i:t.index("</section>", i)]


@pytest.fixture(scope="module")
def ctx():
    return {"players": load_json(os.path.join(DATA, "players.json")),
            "ids": load_json(os.path.join(DATA, "player_ids.json")),
            "cur": load_json(os.path.join(DATA, "current.json")),
            "pairs": TM.by_player(TM.all_pairs())}


def duo_rule(mine):
    out = [(b, sum(r["t"]), r["t"][0]) for b, r in mine.items() if sum(r["t"]) >= 50]
    return sorted(out, key=lambda x: (-(x[2] / x[1]), -x[1], int(x[0])))[:10]


def page_duos(t):
    if "<h2>Best duos</h2>" not in t:
        return []
    return [tuple(map(int, m)) for m in re.findall(r'<span class="mono">(\d+)–(\d+)</span>', section(t, "<h2>Best duos</h2>"))]


def test_best_duos_completed_seasons_match_the_stored_rule(ctx):
    """Over completed seasons alone, the pair engine gives exactly players.json "duos"."""
    done = TM.by_player(TM.all_pairs(last=LAST_COMPLETE))
    bad = [p for p, x in ctx["players"].items() if x.get("duos")
           and [list(map(int, d)) for d in duo_rule(done.get(p, {}))] != x["duos"]]
    assert not bad


def test_best_duos_include_current_season_games(ctx):
    """Players with games this season: Best duos are the same rule over completed seasons plus the
    season to date, the note says so, and at least one shown duo differs from the stored
    (completed-seasons) record because of games played together this season."""
    live = [p for p in ctx["cur"]["players"] if p in ctx["players"] and ctx["players"][p].get("seasons")]
    changed = 0
    for p in live:
        t = read(f"player/{ctx['ids'][p]['slug']}.html")
        want = [(w, g - w) for _, g, w in duo_rule(ctx["pairs"].get(p, {})) if _ in ctx["ids"]]
        assert page_duos(t) == want, p
        if want:
            assert f"incl. {season_label(CURRENT_SEASON)} through " in section(t, "<h2>Best duos</h2>")
            stored = {(w, g - w) for _, g, w in ctx["players"][p].get("duos", [])}
            changed += any(x not in stored for x in want)
    assert changed >= 10
    # Aaron Gordon and Jamal Murray: the 2026-27 games together are in
    ag = next(k for k, v in ctx["ids"].items() if v["slug"] == "aaron-gordon")
    jm = next(k for k, v in ctx["ids"].items() if v["slug"] == "jamal-murray")
    r = ctx["pairs"][ag][jm]
    stored = next((g, w) for m, g, w in ctx["players"][ag]["duos"] if str(m) == jm)
    assert sum(r["t"]) > stored[0] and [CURRENT_SEASON] == [sy for f, sy in r["seasons"] if sy == CURRENT_SEASON]


def test_retired_player_pages_keep_their_wording():
    t = read("player/michael-jordan.html")
    assert "(to date)" not in t and 'class="live"' not in t
    assert "at least 50 games together.</p>" in section(t, "<h2>Best duos</h2>")
    assert f"Regular season, {B.SCOPE_DONE} ({season_label(CURRENT_SEASON)} games not included)" in t


def test_season_and_lineup_rows_to_date(ctx):
    slug = "draymond-green"
    pid = next(k for k, v in ctx["ids"].items() if v["slug"] == slug)
    t = read(f"player/{slug}.html")
    st = ctx["cur"]["players"][pid][-1]
    row = re.search(r'<tr class="live">.*?</tr>', section(t, 'id="cap-seasons"'), re.S).group(0)
    assert f"{season_label(CURRENT_SEASON)} (to date)" in text(row)
    assert text(row).count("In progress") == 2                     # final finish and playoffs
    assert f"{st['w']}–{st['l']}" in row and f"{st['ow']}–{st['ol']}" in row and f">{st['g']} of " in row
    assert "(to date) row counts games through" in section(t, 'id="cap-seasons"')
    lrow = re.search(r'<tr class="live">.*?</tr>', section(t, 'id="cap-lineup"'), re.S).group(0)
    assert f"{st['st'][0]}–{st['st'][1]}" in lrow and f"{st['cl'][0]}–{st['cl'][1]}" in lrow
    # completed seasons are unchanged below it: the next row is the last completed season
    rows = re.findall(r'<td data-l="Season" class="mono" data-value="(\d+)">', section(t, 'id="cap-seasons"'))
    assert rows[0] == str(CURRENT_SEASON) and rows[1] == str(LAST_COMPLETE)


def test_opponents_include_the_season_to_date(ctx):
    d = A.Data(live=True)
    for slug in ("draymond-green", "lebron-james"):
        pid = next(k for k, v in ctx["ids"].items() if v["slug"] == slug)
        sec = section(read(f"player/{slug}.html"), '<section id="opp">')
        sm = A.summary(d, pid)
        assert f"{sm['w'] + sm['l']:,} games, {sm['w']}–{sm['l']}" in sec        # rows add up to the career card
        assert f"incl. {season_label(CURRENT_SEASON)} through " in sec


def test_finished_season_blocks_stay_completed():
    t = read("player/draymond-green.html")
    for lab in ("Winning seasons", "Playoff trips", "Average final NBA finish"):
        card = re.search(rf'<span class="lbl">{lab}</span>.*?</a>', t, re.S).group(0)
        assert B.SCOPE_DONE in card or "seasons" in card
    assert "<h2>Latest completed seasons</h2>" in t
    assert f"{season_label(CURRENT_SEASON)}" not in section(t, "<h2>Latest completed seasons</h2>")


def test_franchise_list_counts_the_season_to_date():
    d = A.Data(live=True)
    live = A.list_franchise(d, 1947, 1, upto=CURRENT_SEASON)
    done = A.list_franchise(d, 1947, 1)
    t = read("lists/franchise-winningest.html")
    assert f"plus {season_label(CURRENT_SEASON)} through " in t
    assert any(live[f][0]["w"] > done[f][0]["w"] for f in live if f in done)
    gsw = live["GSW"][0]
    assert f'<span class="mono">{gsw["w"]}-{gsw["l"]}</span>' in t


def test_tonight_items_use_the_live_scope():
    for f in ("scripts/daily_story.py", "scripts/fun_facts.py"):
        src = read(f)
        assert "against them ({B.SCOPE_LIVE})" in src and 'cur.get("log")' in src

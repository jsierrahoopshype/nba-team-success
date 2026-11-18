# (c) 2026 HoopsMatic. All rights reserved.
"""Record against each opponent: rows add up, files exist, takeaways point at real rows."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from analysis import Data, summary  # noqa: E402


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_jordan_opponents_add_up():
    t = read("player/michael-jordan.html")
    sec = t[t.index('<section id="opp">'):]
    sec = sec[:sec.index("</section>")]
    rows = re.findall(r'<td data-l="W–L" class="mono" data-value="\d+"><span class="v">(\d+)–(\d+)</span>', sec)
    assert sum(int(w) for w, _ in rows) == 706 and sum(int(l) for _, l in rows) == 366
    assert "1,072 games, 706–366, against 30 franchises" in sec


def test_game_file_matches_career():
    d = Data()
    for slug in ("michael-jordan", "george-mikan", "james-harden"):
        pid = next(k for k, v in d.ids.items() if v["slug"] == slug)
        doc = json.loads(read(f"assets/pg/{slug}.json"))
        w = l = 0
        for sy, teams in doc["s"].items():
            for team, games in teams:
                for md, opp, home, ts, os_, typ in games:
                    if typ == 2:
                        w += ts > os_
                        l += ts < os_
        sm = summary(d, pid)
        assert (w, l) == (sm["w"], sm["l"]), slug


def test_takeaways_point_at_rows():
    t = read("player/michael-jordan.html")
    takes = re.search(r'<ul class="takes">(.*?)</ul>', t, re.S).group(1)
    for f in re.findall(r'href="\?vs=([A-Z]{3})', takes):
        assert f'<tr id="vs-{f}"' in t, f
    assert "Most playoff series against one franchise: " in takes

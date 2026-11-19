# (c) 2026 HoopsMatic. All rights reserved.
"""Teammate help, peer comparisons, share images and their indexing rules (no network)."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def help_doc():
    return json.loads(read("data/help.json"))


def ids():
    return json.loads(read("data/player_ids.json"))


def pid_of(slug):
    return next(k for k, v in ids().items() if v["slug"] == slug)


def test_help_counts_only_teammates_he_played_with():
    h = help_doc()
    mj = pid_of("michael-jordan")
    row = h["season"][mj]["CHI-1996"]
    mates = {ids()[m[0]]["name"]: m for m in row[3]}
    assert "Scottie Pippen" in mates and mates["Scottie Pippen"][1] > 0
    assert all(m[1] >= 1 for m in row[3])          # shared games, checked game by game
    # traded player: only the team he played for gets him, and only shared-game mates count
    harden = pid_of("james-harden")
    assert "HOU-2021" in h["season"][harden] and "BKN-2021" in h["season"][harden]


def test_zero_is_not_missing():
    h = help_doc()
    zero = [(p, k) for p, d in h["season"].items() for k, v in d.items() if v[0] == 0 and not v[2]]
    partial = [(p, k) for p, d in h["season"].items() for k, v in d.items() if v[2]]
    assert zero and partial
    t = read("player/michael-jordan.html")
    assert "No honored teammate" in t or "Help per season" in t


def test_average_is_per_season_not_career_total():
    a = help_doc()["avg"][pid_of("michael-jordan")]
    assert a["n"] == 15 and 0 < a["help"] < 20


def test_every_300_game_player_has_three_peers():
    h = help_doc()
    pool = [p for p, a in h["avg"].items() if a["g"] >= 300]
    assert pool and all(len(h["peers"][p]) == 3 for p in pool)


def test_compare_pages_are_noindex_and_out_of_sitemap():
    sm = read("sitemap.xml")
    assert "/compare/" not in sm
    files = [f for f in os.listdir(os.path.join(ROOT, "compare")) if f.endswith(".html")]
    assert len(files) > 1000
    for f in files[:50] + ["charles-barkley--michael-jordan.html"]:
        t = read(f"compare/{f}")
        assert '<meta name="robots" content="noindex, follow">' in t, f


def test_compare_pages_use_og_cards_not_local_pngs():
    assert not os.path.exists(os.path.join(ROOT, "compare", "img"))       # no pre-rendered PNGs in the repo
    t = read("compare/charles-barkley--michael-jordan.html")
    assert 'og:image" content="https://hoopsmatic.com/og/team-success/compare/charles-barkley--michael-jordan.png"' in t
    # "Download image" is the same og card (same site), no in-browser canvas
    assert ('href="https://hoopsmatic.com/og/team-success/compare/charles-barkley--michael-jordan.png" '
            'download="charles-barkley-vs-michael-jordan.png"') in t
    assert 'id="card-dl"' not in t and "toBlob" not in read("assets/compare.js")


def test_player_page_links_its_three_comparisons():
    t = read("player/michael-jordan.html")
    for other in re.findall(r'href="\.\./compare/([a-z0-9-]+--[a-z0-9-]+)\.html"', t):
        assert os.path.exists(os.path.join(ROOT, "compare", other + ".html"))
    assert t.count("../compare/") >= 3

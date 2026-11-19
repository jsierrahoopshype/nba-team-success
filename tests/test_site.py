# (c) 2026 HoopsMatic. All rights reserved.
"""Checks on the built pages (run after scripts/build_site.py). No network."""
import json
import os
import re
from collections import deque
from urllib.parse import unquote

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://hoopsmatic.com/team-success/"
FOOTER = ('<footer class="hm-site-footer">\n'
          '<p>Anything wrong? Email us at <a href="mailto:hoopsmatic@hoopsmatic.com">hoopsmatic@hoopsmatic.com</a></p>\n'
          '<p>For any other inquiry, contact us at <a href="mailto:ads@hoopsmatic.com">ads@hoopsmatic.com</a></p>\n'
          '</footer>')
OG = "https://hoopsmatic.com/og/team-success/"
OG_LISTS = {"average-finish", "career-wins", "deepest-run", "gap-career", "no-allstar-teammate", "playoff-trips",
            "titles", "winning-seasons", "wins-minus-losses"}
WORKER_MARKERS = ("<body", "</head", "</style", "</script", "<!--")


def pages():
    out = []
    for d in ("", "player", "lists", "players", "seasons", "stories"):
        base = os.path.join(ROOT, d)
        if os.path.isdir(base):
            out += [os.path.join(d, f) if d else f for f in sorted(os.listdir(base)) if f.endswith(".html")]
    return out


PAGES = pages()
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")),
                                reason="site not built")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def html():
    return {p: read(p) for p in PAGES}


def test_enough_pages():
    assert len([p for p in PAGES if p.startswith("player/")]) > 5000
    assert "index.html" in PAGES and "how-we-count.html" in PAGES


def test_canonical_and_og_url(html):
    for rel, t in html.items():
        want = BASE + ("" if rel == "index.html" else rel)
        assert f'<link rel="canonical" href="{want}">' in t, rel
        assert f'<meta property="og:url" content="{want}">' in t, rel
        og = re.search(r'<meta property="og:image" content="([^"]+)">', t).group(1)
        assert f'<meta name="twitter:image" content="{og}">' in t, rel
        assert '<meta property="og:image:width" content="1200">' in t, rel
        assert '<meta property="og:image:height" content="630">' in t, rel
        name = rel.rsplit("/", 1)[-1][:-5]
        if rel.startswith("stories/") and rel != "stories/index.html":
            assert og.startswith(f"{BASE}stories/img/"), rel                          # its own share image
        elif rel.startswith("player/") and os.path.exists(os.path.join(ROOT, "assets", "card", name + ".json")):
            assert og == f"{OG}player/{name}.png", rel                               # hoopsmatic-og-card
        elif rel.startswith("lists/") and name in OG_LISTS:
            assert og == f"{OG}list/{name}.png", rel
        elif rel.startswith("seasons/") and re.match(r"\d{4}-\d{2}$", name) and name != "2026-27":
            assert og == f"{OG}season/{name}.png", rel
        else:
            assert og == f"{BASE}assets/og-team-success.png", rel


def test_no_github_io_or_third_party(html):
    for rel, t in html.items():
        assert "github.io" not in t, rel
        assert "fonts.googleapis" not in t and "gstatic" not in t, rel
        # every resource the browser fetches is local (relative)
        for m in re.finditer(r'<(?:img|script|link)\b[^>]*\b(?:src|href)="([^"]+)"', t):
            url = m.group(1)
            if 'rel="canonical"' in m.group(0):
                continue
            assert not url.startswith(("http:", "https:", "//")), (rel, url)
    for f in ("sitemap.xml", "robots.txt", "assets/ts.css", "assets/search.js"):
        assert "github.io" not in read(f)


def test_titles_and_descriptions_unique(html):
    titles, descs = {}, {}
    for rel, t in html.items():
        ti = re.search(r"<title>(.*?)</title>", t).group(1)
        de = re.search(r'<meta name="description" content="(.*?)">', t).group(1)
        assert ti.endswith("| HoopsMatic"), rel
        assert ti not in titles, (rel, titles.get(ti))
        assert de not in descs, (rel, descs.get(de))
        titles[ti] = rel
        descs[de] = rel


def test_footer_exact_and_branding(html):
    for rel, t in html.items():
        assert t.count(FOOTER) == 1, rel
        assert t.count("<footer") == 1, rel
        assert "HoopsHype" not in t and "hoopshype" not in t, rel
        assert "(c) 2026 HoopsMatic. All rights reserved." in t, rel
        assert "hm-ts-7f3a91c2" in t, rel
        assert '<a href="https://hoopsmatic.com/terms">Terms</a>' in t, rel


def test_worker_markers_not_inside_css_js(html):
    for rel, t in html.items():
        assert "<!--" not in t, rel
        for block in re.findall(r"<style>(.*?)</style>", t, re.S) + re.findall(r"<script[^>]*>(.*?)</script>", t, re.S):
            for m in WORKER_MARKERS:
                assert m not in block, (rel, m)
        assert t.count("<body") == 1 and t.count("</head>") == 1, rel
        # the first "</head" in the file must be the real </head> (</header> comes later)
        assert t.index("</head") == t.index("</head>"), rel
    for f in ("assets/ts.css", "assets/search.js", "assets/ts.js", "assets/boards.js"):
        body = read(f)
        assert body.startswith(("/* (c) 2026 HoopsMatic", "// (c) 2026 HoopsMatic")), f
        for m in WORKER_MARKERS:
            assert m not in body, (f, m)


def test_no_unsafe_js():
    for f in ("assets/search.js", "assets/ts.js", "assets/boards.js"):
        js = read(f)
        assert "innerHTML" not in js and "eval(" not in js and "insertAdjacentHTML" not in js, f
        assert "http:" not in js and "https:" not in js, f      # nothing loaded from another site


def test_names_are_escaped():
    t = read("player/shaquille-o-neal.html")
    assert "Shaquille O&#x27;Neal" in t
    assert "Shaquille O'Neal" not in t.split("<body", 1)[1]


def test_internal_links_resolve_and_every_player_reachable(html):
    graph = {}
    for rel, t in html.items():
        here = os.path.dirname(rel)
        outs = []
        for href in re.findall(r'<a [^>]*?href="([^"#]+)', t):
            if href.startswith(("http:", "https:", "mailto:")):
                continue
            href = href.split("?", 1)[0]
            target = os.path.normpath(os.path.join(here, unquote(href)))
            assert os.path.exists(os.path.join(ROOT, target)), (rel, href)
            outs.append(target)
        graph[rel] = outs
    seen = {"index.html"}
    q = deque(["index.html"])
    while q:
        for nxt in graph.get(q.popleft(), []):
            if nxt not in seen and nxt in graph:
                seen.add(nxt)
                q.append(nxt)
    missing = [p for p in PAGES if p not in seen]
    assert not missing, missing[:10]


def test_team_links_go_to_career_map(html):
    t = html["player/michael-jordan.html"]
    # tables show the city that season; the full name is the link title
    assert ('<a href="https://hoopsmatic.com/nba-career-map/team/chicago-bulls.html" title="Chicago Bulls">'
            'Chicago</a>') in t
    t = html["player/bill-russell.html"]
    assert "Boston Celtics" in t


def test_era_names_on_old_seasons(html):
    t = html["player/oscar-robertson.html"]
    seasons = t[t.index('id="cap-seasons"'):t.index('<section id="opp">')]
    assert 'title="Cincinnati Royals">Cincinnati<' in seasons and ">Sacramento<" not in seasons
    # the opponent table groups by franchise (named as today) and keeps the era cities
    opp = t[t.index('<section id="opp">'):]
    assert "as Cincinnati" in opp


def test_city_names_rule(html):
    t = html["seasons/1976-77.html"]
    assert ">New York Knicks<" in t and ">New York Nets<" in t        # two teams in one city that season
    assert ">Kansas City-Omaha<" in html["seasons/1974-75.html"]
    t = html["player/lebron-james.html"]
    assert ">LA Lakers<" in t and ">Cleveland<" in t and ">Miami<" in t
    assert "<h1>LeBron James</h1>" in t
    assert "Boston Celtics</a></span></h2>" in html["lists/franchise-winningest.html"]   # headings: full name


def test_no_bare_missed(html):
    for rel in ("player/michael-jordan.html", "player/lebron-james.html", "seasons/2025-26.html"):
        body = re.sub(r"<[^>]+>", " ", html[rel].split("<body", 1)[1])
        assert not re.search(r"\bMissed\b(?! playoffs)", body), rel


def test_compare_scoreboard():
    t = read("compare/karl-malone--michael-jordan.html")
    assert '<table class="sbt"' in t and "Malone leads " in t and "Jordan leads " in t
    # with vs without is shown but never a lead: 7 counted categories, no tint on that row
    assert re.search(r"Malone leads \d of 7 · Jordan leads \d of 7", t)
    row = re.search(r'<tr><th scope="row">With vs without.*?</tr>', t).group(0)
    assert 'class="la"' not in row and 'class="lb"' not in row
    assert "Less help: Jordan (2.2 per season vs 3.4)" in t
    assert '<ul class="takes">' not in t                                   # the old text boxes are gone
    assert "Better finish" in t and 'class="cmpcards"' in t
    for bad in ("carried", "because of", "thanks to", "better player"):
        assert bad not in t


def test_playoff_na_columns_hidden():
    t = read("player/lebron-james.html")
    po = t[t.index('id="cap-po"'):]
    po = po[:po.index("</section>")]
    assert ">Without him<" not in po and ">Gap<" not in po
    assert "He played every playoff game for these teams" in po


def test_sitemap_lists_every_page_with_stable_lastmod():
    xml = read("sitemap.xml")
    locs = re.findall(r"<loc>(.*?)</loc><lastmod>(\d{4}-\d{2}-\d{2})</lastmod>", xml)
    got = {u for u, _ in locs}
    # noindex pages (daily story permalinks) are never in the sitemap
    indexed = [p for p in PAGES if 'name="robots" content="noindex' not in read(p)]
    want = {BASE + ("" if p == "index.html" else p) for p in indexed}
    assert got == want
    lm = json.load(open(os.path.join(ROOT, "data", "sitemap_lastmod.json")))
    assert set(lm) == set(indexed)


def test_pre_rendered_content(html):
    t = html["player/michael-jordan.html"]
    assert "706\u2013366" in t     # career record is in the HTML, not built by JavaScript
    assert "65.9% · 39.9%" in t and "26.0 points higher" in t
    t = html["lists/worst-team.html"]
    assert "John Block" in t and "Johnny Green" in t


def test_no_popups_or_overlays():
    css = read("assets/ts.css")
    assert "position:fixed" not in css and "<dialog" not in read("index.html")


def test_finder_on_every_page(html):
    for rel, t in html.items():
        assert 'class="finder top"' in t, rel


def test_noindex_pages():
    for f in os.listdir(os.path.join(ROOT, "stories")):
        if f.endswith(".html") and f != "index.html":
            assert '<meta name="robots" content="noindex, follow">' in read("stories/" + f), f
    assert "noindex" not in read("stories/index.html")
    assert "noindex" not in read("index.html") and "noindex" not in read("player/michael-jordan.html")


def test_today_on_hub():
    t = read("index.html")
    assert "<h2>Last night in Team Success · " in t and '<section class="night">' in t
    assert "data through" in t


def test_no_pp_unit_in_pages(html):
    for rel, t in html.items():
        body = re.sub(r"<[^>]+>", " ", t.split("<body", 1)[1])
        assert not re.search(r"\d pp\b", body), rel


def test_search_top_and_bottom(html):
    for rel, t in html.items():
        assert 'class="finder top"' in t and 'class="finder bottom"' in t, rel


def test_logos_follow_h2h_rule():
    t = read("player/kevin-durant.html")
    assert "assets/logos/h-seattle-supersonics.svg" in t        # Seattle SuperSonics: its own historical file
    assert "assets/logos/c-oklahoma-city-thunder.svg" in t
    t = read("player/george-mikan.html")
    assert "c-los-angeles-lakers.svg" not in t.split('id="opp"')[0]  # Minneapolis Lakers: never today's logo
    for f in os.listdir(os.path.join(ROOT, "assets", "logos")):
        assert f.endswith(".svg")


def test_card_json_files():
    doc = json.loads(read("assets/card/michael-jordan.json"))
    assert doc["record"]["w"] == 706 and doc["with_without"]["gap_points"] == 26.0 and doc["titles"] == 6
    assert doc["top_peer"] and doc["headshot"].startswith("assets/hs/")
    lst = json.loads(read("assets/card/lists/no-allstar-teammate.json"))
    assert len(lst["rows"]) == 5
    sea = json.loads(read("assets/card/seasons/1997-98.json"))
    assert sea["rows"][0]["team"] == "Chicago Bulls" and sea["rows"][0]["rank"] == 1


def test_low_help_all_stars_rank_by_adjusted_finish():
    t = read("lists/low-help-all-stars.html")
    tbl = t[t.index('id="cap-low"'):t.index('id="cap-low2"')]
    assert 'aria-sort="ascending" data-first="ascending"><button type="button">Average finish (of 30)</button>' in tbl
    assert "<button type=\"button\">Raw average</button>" in tbl
    adj = [float(x) for x in re.findall(r'data-l="Average finish \(of 30\)" class="mono" data-value="([\d.]+)"', tbl)]
    assert len(adj) > 10 and adj == sorted(adj)

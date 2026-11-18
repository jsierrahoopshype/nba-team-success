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
        if rel.startswith("stories/") and rel != "stories/index.html":
            assert f'<meta property="og:image" content="{BASE}stories/img/' in t, rel     # its own share image
        else:
            assert f'<meta property="og:image" content="{BASE}assets/og-team-success.png">' in t, rel


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
    assert '<a href="https://hoopsmatic.com/nba-career-map/team/chicago-bulls.html">Chicago Bulls</a>' in t
    t = html["player/bill-russell.html"]
    assert "Boston Celtics" in t


def test_era_names_on_old_seasons(html):
    t = html["player/oscar-robertson.html"]
    seasons = t[t.index('id="cap-seasons"'):t.index('<section id="opp">')]
    assert "Cincinnati Royals" in seasons and ">Sacramento Kings<" not in seasons
    # the opponent table groups by franchise (named as today) and keeps the era names
    opp = t[t.index('<section id="opp">'):]
    assert "as Cincinnati Royals" in opp or "Cincinnati Royals" in opp


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
    assert "65.9%" in t and "+26.0 pp" in t
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
    assert "<h2>Today in Team Success</h2>" in t and '<p class="story-head">' in t
    assert "Data through" in t

# (c) 2026 HoopsMatic. All rights reserved.
# Team Success site build. Fingerprint: hm-ts-7f3a91c2-site
"""Pre-render every Team Success page from the committed data files.

python scripts/build_site.py              # every page
python scripts/build_site.py --current    # nightly: hub, current boards, active players, A-Z,
                                          # search index, sitemap (lists use completed seasons only)
Files are written only when their bytes change. sitemap.xml <lastmod> comes from
data/sitemap_lastmod.json: a page's date changes only when its content hash changes.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis as A  # noqa: E402
from common import (CURRENT_SEASON, DATA, DEFUNCT, LAST_COMPLETE, RAMIRO_FIRST, ROOT, SRC,  # noqa: E402
                    dump_json, load_json, season_label)

BASE = "https://hoopsmatic.com/team-success/"
CM_TEAM = "https://hoopsmatic.com/nba-career-map/team/{}.html"
CM_PLAYER = "https://hoopsmatic.com/nba-career-map/player/{}.html"
TERMS = "https://hoopsmatic.com/terms"
FINGERPRINT = "hm-ts-7f3a91c2"
TEAM_SLUG = {
    "ATL": "atlanta-hawks", "BOS": "boston-celtics", "BKN": "brooklyn-nets", "CHA": "charlotte-hornets",
    "CHI": "chicago-bulls", "CLE": "cleveland-cavaliers", "DAL": "dallas-mavericks",
    "DEN": "denver-nuggets", "DET": "detroit-pistons", "GSW": "golden-state-warriors",
    "HOU": "houston-rockets", "IND": "indiana-pacers", "LAC": "la-clippers", "LAL": "los-angeles-lakers",
    "MEM": "memphis-grizzlies", "MIA": "miami-heat", "MIL": "milwaukee-bucks",
    "MIN": "minnesota-timberwolves", "NOP": "new-orleans-pelicans", "NYK": "new-york-knicks",
    "OKC": "oklahoma-city-thunder", "ORL": "orlando-magic", "PHI": "philadelphia-76ers",
    "PHX": "phoenix-suns", "POR": "portland-trail-blazers", "SAC": "sacramento-kings",
    "SAS": "san-antonio-spurs", "TOR": "toronto-raptors", "UTA": "utah-jazz", "WAS": "washington-wizards"}
FEATURED = ["LeBron James", "Michael Jordan", "Bill Russell", "Nikola Jokic", "Stephen Curry",
            "Kareem Abdul-Jabbar", "Tim Duncan", "Kevin Garnett"]
TOP_N = 50
ERA_LABEL = {1947: "All-time", 1977: "Since 1976-77", 1997: "Since 1996-97"}

written = []
skipped = 0


def e(x):
    """Escape every value written into HTML."""
    return html.escape("" if x is None else str(x), quote=True)


def write(rel, text):
    global skipped
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = text.encode("utf-8")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            if fh.read() == data:
                skipped += 1
                return False
    with open(path, "wb") as fh:
        fh.write(data)
    written.append(rel)
    return True


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def fpct(p):
    if p is None:
        return "n/a"
    s = f"{p:.3f}"
    return s[1:] if s.startswith("0") else s


def fgap(g):
    if g is None:
        return "n/a"
    s = f"{abs(g):.3f}"
    s = s[1:] if s.startswith("0") else s
    return ("+" if g > 0 else ("-" if g < 0 else "")) + s


def fnum(x, digits=1, sign=True):
    if x is None:
        return "n/a"
    s = f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"
    return s.replace("-", "-")


def rec(w, l):
    return f"{w}-{l}"


# House formats (brief, Nov 2026): rates 65.9%, gaps +26.0 pp (from unrounded rates), records
# with an en dash in display (706–366), empty samples N/A, minus signs as U+2212.
EN = "\u2013"
MINUS = "\u2212"


def pct1(p):
    return "N/A" if p is None else f"{100 * p:.1f}%"


def pp(g):
    if g is None:
        return "N/A"
    v = round(100 * g, 1)
    if v == 0:
        return "0.0 pp"
    return ("+" if v > 0 else MINUS) + f"{abs(v):.1f} pp"


def wl(w, l):
    return f"{w}{EN}{l}" if (w + l) else "N/A"


def signed(n):
    return ("+" if n > 0 else (MINUS if n < 0 else "")) + f"{abs(n):,}"


def nice_date(iso):
    """'2026-11-16' -> 'Nov. 16, 2026' (AP months)."""
    if not iso:
        return "N/A"
    y, m, d = (int(x) for x in iso.split("-"))
    mon = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.",
           "Nov.", "Dec."][m - 1]
    return f"{mon} {d}, {y}"


def cls_gap(g):
    if g is None:
        return "flat"
    return "up" if g > 0.0005 else ("down" if g < -0.0005 else "flat")


# ---------------------------------------------------------------------------
# Site context
# ---------------------------------------------------------------------------
class Site:
    def __init__(self):
        self.d = A.Data()
        self.cur = load_json(os.path.join(DATA, "current.json"), None)
        self.ids = dict(self.d.ids)
        if self.cur:
            for k, v in self.cur.get("newIds", {}).items():
                self.ids.setdefault(k, v)
        self.d.ids = self.ids
        self.badges = defaultdict(list)
        cnt = defaultdict(int)
        for pid, v in self.ids.items():
            if self.has_page(pid):
                cnt[v["name"]] += 1
        self.dup_names = {n for n, c in cnt.items() if c > 1}

    def has_hist(self, pid):
        p = self.d.players.get(pid)
        return bool(p) and any(st["s"] <= LAST_COMPLETE and st["g"] for st in p["seasons"])

    def has_page(self, pid):
        return self.has_hist(pid) or bool(self.cur and pid in self.cur["players"])

    def name(self, pid):
        return self.ids[pid]["name"]

    def plink(self, pid, up):
        v = self.ids[pid]
        if not self.has_page(pid):
            return e(v["name"])
        return f'<a href="{up}player/{e(v["slug"])}.html">{e(v["name"])}</a>'

    def tlink(self, f, sy, name=None):
        t = self.d.team(f, sy)
        nm = name or (t["name"] if t else None)
        if not nm:
            from common import franchise_name
            nm = franchise_name(f, sy) or f
        if f in TEAM_SLUG:
            return f'<a href="{CM_TEAM.format(TEAM_SLUG[f])}">{e(nm)}</a>'
        return e(nm)

    def pic(self, pid, up, size=""):
        v = self.ids.get(pid, {})
        hs = v.get("hs")
        cls = f"hs {size}".strip()
        if hs and os.path.exists(os.path.join(ROOT, "assets", "hs", hs)):
            return (f'<img class="{cls}" src="{up}assets/hs/{e(hs)}" alt="" width="160" height="160" '
                    f'loading="lazy" decoding="async">')
        return f'<span class="{cls} nohs" aria-hidden="true"></span>'


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------
TD_RE = re.compile(r'(<td data-l="[^"]*"[^>]*>)(.*?)(</td>)', re.S)


def page(rel, title, desc, body, up):
    # one wrapper per card cell so phones show "label .... value" cleanly
    body = TD_RE.sub(lambda m: f'{m.group(1)}<span class="v">{m.group(2)}</span>{m.group(3)}', body)
    url = BASE + ("" if rel == "index.html" else rel)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="copyright" content="(c) 2026 HoopsMatic. All rights reserved.">
<style>/* (c) 2026 HoopsMatic. All rights reserved. Team Success {FINGERPRINT} */</style>
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="HoopsMatic">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{BASE}assets/og-team-success.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{BASE}assets/og-team-success.png">
<link rel="preload" href="{up}assets/fonts/dm-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{up}assets/ts.css">
</head>
<body>
<div class="wrap">
{body}
<nav class="crumbs" aria-label="Team Success"><a href="{up}index.html">Team Success home</a> <a href="{up}how-we-count.html">How we count</a> <a href="{up}players/a.html">Players A-Z</a></nav>
<p class="terms"><a href="{TERMS}">Terms</a></p>
</div>
<footer class="hm-site-footer">
<p>Anything wrong? Email us at <a href="mailto:hoopsmatic@hoopsmatic.com">hoopsmatic@hoopsmatic.com</a></p>
<p>For any other inquiry, contact us at <a href="mailto:ads@hoopsmatic.com">ads@hoopsmatic.com</a></p>
</footer>
</body>
</html>
"""


def toggles(era=False, key="p"):
    """Radio/checkbox filters (CSS only, no JS, no pop-ups)."""
    out = []
    if era:
        out.append(f'<input class="vh" type="radio" name="era-{key}" id="e1947-{key}" checked>')
        out.append(f'<input class="vh" type="radio" name="era-{key}" id="e1977-{key}">')
        out.append(f'<input class="vh" type="radio" name="era-{key}" id="e1997-{key}">')
    out.append(f'<input class="vh" type="checkbox" id="g20-{key}">')
    ctl = ['<div class="seg" role="group" aria-label="Filters">']
    if era:
        for y in (1947, 1977, 1997):
            ctl.append(f'<label for="e{y}-{key}" class="pill l{y}">{ERA_LABEL[y]}</label>')
    ctl.append(f'<label for="g20-{key}" class="pill lg20">20+ games only</label>')
    ctl.append("</div>")
    return "\n".join(out) + "\n" + "".join(ctl)


# ---------------------------------------------------------------------------
# Player pages
# ---------------------------------------------------------------------------
def playoff_text(s, t, up):
    po = t["po"]
    if po == "Champion":
        fin = t["series"][-1] if t["series"] else None
        if fin:
            return (f'Won the title, beat {s.tlink(fin["opp"], t["s"])} '
                    f'<span class="mono">{fin["w"]}-{fin["l"]}</span> in the Finals')
        return "Won the title"
    if po in ("", "Play-In"):
        return A.PO_LABEL[po]
    el = t.get("elim")
    rnd = {"First Round": "first round", "Conf Semis": "conference semifinals",
           "Conf Finalist": "conference finals", "Finalist": "NBA Finals"}.get(po, po)
    if el:
        return (f'Lost {rnd} to {s.tlink(el["opp"], t["s"])} '
                f'<span class="mono">{el["w"]}-{el["l"]}</span>')
    return f"Lost {rnd}"


def finish_text(t):
    parts = []
    if t.get("divPos") and t.get("div") and t["div"] != t["conf"]:
        parts.append(f'{t["divPos"]} in {t["div"]}')
    if t.get("confPos") and t.get("conf"):
        parts.append(f'{t["confPos"]} in {t["conf"]}')
    return ", ".join(parts) or "n/a"


def rec_cell(w, l):
    if w + l == 0:
        return '<span class="flat">none</span>'
    return f'<span class="mono">{w}-{l}</span> <span class="sub">{fpct(A.pct(w, l))}</span>'


def wl2(x):
    return f"{x[0]}-{x[1]}" if sum(x) else "none"


def season_rows(s, pid, up):
    rows = []
    for st in sorted(s.d.players[pid]["seasons"], key=lambda x: (-x["s"], x.get("last") or "")):
        if st["s"] > LAST_COMPLETE or st["g"] == 0:
            continue
        t = s.d.team(st["f"], st["s"])
        if not t:
            continue
        gap = (A.pct(st["w"], st["l"]) - A.pct(st["ow"], st["ol"])) if st["ow"] + st["ol"] else None
        modern = st["s"] >= RAMIRO_FIRST
        rm = st.get("rm")
        oo = A.onoff(rm) if rm else None
        cl = ' class="lt20"' if st["g"] < 20 else ""
        tg = t["w"] + t["l"]
        rows.append(f"""<tr{cl}><td data-l="Season" class="mono">{season_label(st['s'])}</td>
<td data-l="Team">{s.tlink(st['f'], st['s'])}<span class="sub blk">{e(finish_text(t))}</span></td>
<td data-l="Team W-L"><span class="mono">{t['w']}-{t['l']}</span> <span class="sub">{fpct(t['pct'])}</span><span class="sub blk">Rank {e(t['rnk'] if t['rnk'] else 'n/a')}</span></td>
<td data-l="Playoffs">{playoff_text(s, t, up)}</td>
<td data-l="His games" class="mono">{st['g']} of {tg}</td>
<td data-l="With him">{rec_cell(st['w'], st['l'])}</td>
<td data-l="Without him">{rec_cell(st['ow'], st['ol'])}</td>
<td data-l="Gap" class="mono {cls_gap(gap)}">{fgap(gap)}</td>
<td data-l="On/off per 100" class="mono {cls_gap(oo)}">{fnum(oo) if modern and oo is not None else 'n/a'}</td>
<td data-l="Started / bench" class="mono">{(wl2(rm['st']) + ' / ' + wl2(rm['bn'])) if modern and rm else 'n/a'}</td>
<td data-l="Close games" class="mono">{wl2(rm['cl']) if modern and rm else 'n/a'}</td></tr>""")
    return rows


SEASON_HEAD = ("<thead><tr><th>Season</th><th>Team and finish</th><th>Team W-L</th>"
               "<th>Playoffs</th><th>His games</th><th>With him</th><th>Without him</th><th>Gap</th>"
               "<th>On/off per 100</th><th>Started / bench</th><th>Close games</th></tr></thead>")


def summary_cards(s, pid, mg, up):
    sm = A.summary(s.d, pid, mg)
    if not sm["seasons"]:
        return '<p class="empty">No seasons with 20+ games.</p>'
    w, l = sm["w"], sm["l"]
    deep = sm["deepest"]
    if deep:
        t = deep[0]
        deep_txt = f'{A.PO_LABEL[t["po"]]} <span class="sub">{season_label(t["s"])}, {s.tlink(t["f"], t["s"])}</span>'
    else:
        deep_txt = "Never made the playoffs"
    gap = sm["gap"]
    cards = [
        ("Career record in his games", f'<span class="mono">{w}-{l}</span>', fpct(A.pct(w, l))),
        ("Games over .500", f'<span class="mono {cls_gap(w - l)}">{w - l:+d}</span>', f"{w + l} games"),
        ("Winning seasons", f'<span class="mono">{sm["winning"]}</span>', f'of {sm["seasons"]} seasons'),
        ("Playoff trips", f'<span class="mono">{sm["trips"]}</span>', f'of {sm["seasons"]} seasons'),
        ("Deepest playoff run", deep_txt, ""),
        ("Titles", f'<span class="mono">{sm["titles"]}</span>',
         ", ".join(season_label(y) for y in sm["titleYears"]) or ""),
        ("Average team rank", f'<span class="mono">{sm["rnk"]:.1f}</span>' if sm["rnk"] else "n/a",
         "RNK, 1 = champion"),
        ("With him vs without him",
         f'<span class="mono {cls_gap(gap)}">{fgap(gap)}</span>',
         f'{rec(w, l)} with, {rec(sm["ow"], sm["ol"])} without (team-season window). '
         f'Between his first and last game for each team: {rec(sm["sw"], sm["sl"])} without, gap '
         f'{fgap((A.pct(w, l) - A.pct(sm["sw"], sm["sl"])) if (w + l) and (sm["sw"] + sm["sl"]) else None)}'),
    ]
    return '<div class="cards">' + "".join(
        f'<div class="card"><h3>{e(a)}</h3><p class="big">{b}</p><p class="sub">{c}</p></div>'
        for a, b, c in cards) + "</div>"


def arrival_departure(s, pid, up):
    d = s.d
    seasons = defaultdict(set)
    for st in d.stints(pid):
        seasons[st["f"]].add(st["s"])
    rows = []
    for f, ys in seasons.items():
        ys = sorted(ys)
        runs = []
        for y in ys:
            if runs and y == runs[-1][1] + 1:
                runs[-1][1] = y
            else:
                runs.append([y, y])
        for a, b in runs:
            prev, first = d.team(f, a - 1), d.team(f, a)
            last, nxt = d.team(f, b), d.team(f, b + 1)
            if prev and first:
                ch = A.per82(first) - A.per82(prev)
                rows.append((a, f"""<tr><td data-l="Move">Arrived</td><td data-l="Team">{s.tlink(f, a)}</td>
<td data-l="Season before" class="mono">{season_label(a - 1)}: {prev['w']}-{prev['l']} <span class="sub">{A.per82(prev):.1f} per 82</span></td>
<td data-l="His season" class="mono">{season_label(a)}: {first['w']}-{first['l']} <span class="sub">{A.per82(first):.1f} per 82</span></td>
<td data-l="Change" class="mono {cls_gap(ch)}">{ch:+.1f} wins</td></tr>"""))
            if last and nxt and b + 1 <= LAST_COMPLETE:
                ch = A.per82(nxt) - A.per82(last)
                rows.append((b + 0.5, f"""<tr><td data-l="Move">Left</td><td data-l="Team">{s.tlink(f, b)}</td>
<td data-l="His last season" class="mono">{season_label(b)}: {last['w']}-{last['l']} <span class="sub">{A.per82(last):.1f} per 82</span></td>
<td data-l="Season after" class="mono">{season_label(b + 1)}: {nxt['w']}-{nxt['l']} <span class="sub">{A.per82(nxt):.1f} per 82</span></td>
<td data-l="Change" class="mono {cls_gap(ch)}">{ch:+.1f} wins</td></tr>"""))
    if not rows:
        return ""
    rows.sort(key=lambda x: -x[0])
    return ("""<section><h2>Arrival and departure effect</h2>
<p class="note">Team wins per 82 games the season before he arrived vs his first season there, and his last season vs the season after he left. Per 82 so short seasons compare fairly.</p>
<table class="tt"><thead><tr><th>Move</th><th>Team</th><th>Before</th><th>After</th><th>Change</th></tr></thead><tbody>"""
            + "".join(r for _, r in rows) + "</tbody></table></section>")


def trades(s, pid, up):
    by = defaultdict(list)
    for st in s.d.stints(pid):
        by[st["s"]].append(st)
    rows = []
    for sy in sorted(by, reverse=True):
        lst = by[sy]
        if len(lst) < 2:
            continue
        lst.sort(key=lambda x: x.get("first") or "")
        for st in lst:
            b, a = st.get("before", [0, 0]), st.get("after", [0, 0])
            during = [st["w"] + st["ow"], st["l"] + st["ol"]]
            rows.append(f"""<tr><td data-l="Season" class="mono">{season_label(sy)}</td>
<td data-l="Team">{s.tlink(st['f'], sy)}</td>
<td data-l="Before he arrived">{rec_cell(*b)}</td>
<td data-l="While he was there">{rec_cell(*during)}</td>
<td data-l="After he left">{rec_cell(*a)}</td>
<td data-l="His games" class="mono">{st['g']}</td></tr>""")
    if not rows:
        return ""
    return ("""<section><h2>Mid-season trades</h2>
<p class="note">Each team's record before he arrived, while he was there (his window, games with and without him), and after he left, in the seasons he played for two or more teams.</p>
<table class="tt"><thead><tr><th>Season</th><th>Team</th><th>Before he arrived</th><th>While he was there</th><th>After he left</th><th>His games</th></tr></thead><tbody>"""
            + "".join(rows) + "</tbody></table></section>")


def duos(s, pid, up):
    ds = s.d.players[pid].get("duos", [])
    if not ds:
        return ""
    items = []
    for mate, g, w in ds:
        mate = str(mate)
        if mate not in s.ids:
            continue
        items.append(f"""<li>{s.pic(mate, up, 'sm')}<span class="who">{s.plink(mate, up)}</span>
<span class="mono">{w}-{g - w}</span> <span class="sub">{fpct(w / g)}</span></li>""")
    return ("""<section><h2>Best duos</h2>
<p class="note">Team record in regular-season games both played, top 10 by win %, at least 50 games together.</p>
<ol class="duos">""" + "".join(items) + "</ol></section>")


def playoff_table(s, pid, up):
    rows = []
    for st in sorted(s.d.players[pid]["seasons"], key=lambda x: -x["s"]):
        po = st.get("po")
        if not po or st["s"] > LAST_COMPLETE:
            continue
        t = s.d.team(st["f"], st["s"])
        gap = (A.pct(po["w"], po["l"]) - A.pct(po["ow"], po["ol"])) if po["ow"] + po["ol"] and po["g"] else None
        rows.append(f"""<tr><td data-l="Season" class="mono">{season_label(st['s'])}</td>
<td data-l="Team">{s.tlink(st['f'], st['s'])}</td>
<td data-l="Result">{playoff_text(s, t, up) if t else 'n/a'}</td>
<td data-l="His games" class="mono">{po['g']} of {po['g'] + po['ow'] + po['ol']}</td>
<td data-l="With him">{rec_cell(po['w'], po['l'])}</td>
<td data-l="Without him">{rec_cell(po['ow'], po['ol'])}</td>
<td data-l="Gap" class="mono {cls_gap(gap)}">{fgap(gap)}</td></tr>""")
    if not rows:
        return ""
    return ("""<section><h2>Playoffs, with and without him</h2>
<table class="tt"><thead><tr><th>Season</th><th>Team</th><th>Result</th><th>His games</th><th>With him</th><th>Without him</th><th>Gap</th></tr></thead><tbody>"""
            + "".join(rows) + "</tbody></table></section>")


def current_block(s, pid, up):
    if not s.cur or pid not in s.cur["players"]:
        return ""
    rows = []
    for st in s.cur["players"][pid]:
        oo = A.onoff({"on": st["on"], "off": st["off"]})
        gap = (A.pct(st["w"], st["l"]) - A.pct(st["ow"], st["ol"])) if st["ow"] + st["ol"] else None
        rows.append(f"""<tr><td data-l="Team">{s.tlink(st['f'], CURRENT_SEASON)}</td>
<td data-l="His games" class="mono">{st['g']}</td>
<td data-l="With him">{rec_cell(st['w'], st['l'])}</td>
<td data-l="Without him">{rec_cell(st['ow'], st['ol'])}</td>
<td data-l="Gap" class="mono {cls_gap(gap)}">{fgap(gap)}</td>
<td data-l="On/off per 100" class="mono {cls_gap(oo)}">{fnum(oo)}</td>
<td data-l="Started / bench" class="mono">{wl2(st['st'])} / {wl2(st['bn'])}</td>
<td data-l="Close games" class="mono">{wl2(st['cl'])}</td></tr>""")
    return (f"""<section><h2>{season_label(CURRENT_SEASON)} so far</h2>
<p class="note">Games through {e(nice_date(s.cur['through']))}, the last game in the nightly data. Not included in the career numbers (completed seasons through {season_label(LAST_COMPLETE)}) until the season ends.</p>
<table class="tt"><thead><tr><th>Team</th><th>His games</th><th>With him</th><th>Without him</th><th>Gap</th><th>On/off per 100</th><th>Started / bench</th><th>Close games</th></tr></thead><tbody>"""
            + "".join(rows) + "</tbody></table></section>")


def player_page(s, pid):
    up = "../"
    v = s.ids[pid]
    name = v["name"]
    has_hist = s.has_hist(pid)
    rel = f"player/{v['slug']}.html"
    if has_hist:
        sm = A.summary(s.d, pid)
        yrs = sorted({st["s"] for st in s.d.stints(pid)})
        span = f"{season_label(yrs[0])} to {season_label(yrs[-1])}" if yrs else ""
        desc = (f"{name}'s teams went {sm['w']}-{sm['l']} ({fpct(A.pct(sm['w'], sm['l']))}) in his games "
                f"and {sm['ow']}-{sm['ol']} without him, {span}: {sm['winning']} winning seasons, "
                f"{sm['trips']} playoff trips, {sm['titles']} titles. Every season, playoffs, best duos.")
    else:
        sm = None
        span = season_label(CURRENT_SEASON)
        c = s.cur["players"][pid]
        w, l = sum(x["w"] for x in c), sum(x["l"] for x in c)
        ow, ol = sum(x["ow"] for x in c), sum(x["ol"] for x in c)
        desc = (f"{name}'s teams are {w}-{l} with him and {ow}-{ol} without him in {span}, "
                "his first NBA season. Updated every morning.")
    tag = None
    if name in s.dup_names:
        m = re.search(r"\((\d{4})\)", v.get("rsName") or "")
        tag = f"born {m.group(1)}" if m else span
    tname = f"{name} ({tag})" if tag else name
    title = f"{tname}: team record with and without him, every season | HoopsMatic"
    teams = []
    seen = set()
    for st in sorted(s.d.players.get(pid, {"seasons": []})["seasons"], key=lambda x: x["s"]):
        if st["g"] and st["f"] not in seen and st["s"] <= LAST_COMPLETE:
            seen.add(st["f"])
            teams.append(s.tlink(st["f"], st["s"]))
    sub = [e(span)] + ([e(tag)] if tag and tag != span else [])
    if v.get("cm"):
        sub.append(f'<a href="{CM_PLAYER.format(e(v["slug"]))}">Career Map</a>')
    head = f"""<header class="ent">{s.pic(pid, up, 'lg')}<div><h1>{e(name)}</h1>
<p class="subtitle">{' · '.join(sub)}</p>{('<p class="subtitle">' + ', '.join(teams) + '</p>') if teams else ''}</div></header>"""
    parts = [head]
    if has_hist:
        parts.append(toggles(False, "p"))
        parts.append(f"""<section class="sum"><h2>Career summary</h2>
<div class="vall">{summary_cards(s, pid, 1, up)}</div><div class="v20">{summary_cards(s, pid, 20, up)}</div>
<p class="note">Career: regular seasons {season_label(1947)} through {season_label(LAST_COMPLETE)}.{(' ' + season_label(CURRENT_SEASON) + ' (games through ' + e(nice_date(s.cur['through'])) + ') is shown separately and is not in these totals.') if s.cur else ''} "With him" counts games he played; "without him" counts the team's games he missed inside his team-season window (see <a href="../how-we-count.html">How we count</a>).</p></section>""")
    parts.append(current_block(s, pid, up))
    if has_hist:
        rows = season_rows(s, pid, up)
        parts.append(f"""<section><h2>Season by season</h2>
<p class="note">Newest first. On/off, starts and close games start in 1996-97 (n/a before). Rows with fewer than 20 games hide under "20+ games only".</p>
<table class="tt season">{SEASON_HEAD}<tbody>{''.join(rows)}</tbody></table></section>""")
        parts.append(playoff_table(s, pid, up))
        parts.append(arrival_departure(s, pid, up))
        parts.append(trades(s, pid, up))
        parts.append(duos(s, pid, up))
        b = s.badges.get(pid)
        if b:
            parts.append('<section><h2>Clubs he is in</h2><ul class="badges">' + "".join(
                f'<li><a class="badge" href="../lists/{e(k)}.html">{e(t)}</a></li>' for k, t in b) + "</ul></section>")
    body = "\n".join(p for p in parts if p)
    return rel, page(rel, title, desc, body, up)


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------
def season_chips(s, seasons, up):
    return ", ".join(f'{season_label(x["s"])} {s.tlink(x["f"], x["s"])} <span class="sub">{x["g"]} g</span>'
                     for x in seasons)


LISTS = [
    ("worst-team", "Played for the worst team the most times",
     "Players who were on the team with the NBA's worst record most often (lowest win %, ties all count).",
     "Seasons on the league's worst team"),
    ("best-team", "Played for the best record the most times",
     "Players who were on the team with the NBA's best record most often (highest win %, ties all count).",
     "Seasons on the league's best team"),
    ("sixty-win-pace", "Most 60-win-pace seasons",
     "Seasons on a team that won at least 60 of every 82 games (win % .732 or better), so short seasons count.",
     "60-win-pace seasons"),
    ("never-500", "Never played on a .500 team",
     "Players with 5+ seasons whose teams never reached a .500 record.", "Seasons, all under .500"),
    ("winning-streaks", "Longest streak of winning seasons",
     "Seasons in a row on a team that finished above .500 (the team he played the most games for).",
     "Winning seasons in a row"),
    ("playoff-droughts", "Longest playoff drought",
     "Seasons in a row without a playoff trip (play-in losses don't count as a trip).",
     "Seasons in a row without the playoffs"),
    ("franchise-winningest", "Winningest player in each franchise's history",
     "Most wins in the games he played for that franchise, regular season, minimum 200 games.",
     "Wins in his games"),
    ("gap-season", "Biggest with/without gaps in a season",
     "Team win % in the games he played minus win % in the games he missed, one team-season, at least 20 games each side.",
     "Gap"),
    ("gap-career", "Biggest with/without gaps in a career",
     "Career team win % with him minus without him, at least 200 games with him and 50 without.", "Gap"),
    ("bad-luck", "Bad Luck Index: great players on bad teams",
     "Accolades against team success, plus the ring chasers and the carriers.", "Index"),
]
LIST_TITLE = {k: t for k, t, _, _ in LISTS}


def list_panel_rows(s, key, era, mg, up, cache):
    d = s.d
    if key in ("worst-team", "best-team"):
        rows = A.list_flag(d, "worst" if key == "worst-team" else "best", era, mg)
        return [(r["pid"], f'<span class="big mono">{r["n"]}</span>',
                 season_chips(s, r["seasons"], up)) for r in rows[:TOP_N]], rows
    if key == "sixty-win-pace":
        rows = A.list_sixty(d, era, mg)
        return [(r["pid"], f'<span class="big mono">{r["n"]}</span>',
                 season_chips(s, r["seasons"], up)) for r in rows[:TOP_N]], rows
    if key == "never-500":
        rows = A.list_never500(d, era, mg)
        out = []
        for r in rows[:TOP_N]:
            b = r["best"]
            t = d.team(b["f"], b["s"])
            out.append((r["pid"], f'<span class="big mono">{r["n"]}</span>',
                        f'{r["g"]} games. Best team: {season_label(b["s"])} {s.tlink(b["f"], b["s"])} '
                        f'<span class="mono">{t["w"]}-{t["l"]}</span>'))
        return out, rows
    if key in ("winning-streaks", "playoff-droughts"):
        rows = A.list_winning_streak(d, era, mg) if key == "winning-streaks" else A.list_drought(d, era, mg)
        return [(r["pid"], f'<span class="big mono">{r["n"]}</span>',
                 f'{season_label(r["from"])} to {season_label(r["to"])}') for r in rows[:TOP_N]], rows
    if key == "gap-season":
        rows = A.list_gap_season(d, era, mg)
        out = []
        for r in rows[:TOP_N]:
            st = r["s"]
            out.append((r["pid"], f'<span class="big mono up">{fgap(r["gap"])}</span>',
                        f'{season_label(st["s"])} {s.tlink(st["f"], st["s"])}: '
                        f'<span class="mono">{st["w"]}-{st["l"]}</span> with him, '
                        f'<span class="mono">{st["ow"]}-{st["ol"]}</span> without'))
        return out, rows
    if key == "gap-career":
        rows = A.list_gap_career(d, era, mg)
        return [(r["pid"], f'<span class="big mono up">{fgap(r["gap"])}</span>',
                 f'<span class="mono">{r["w"]}-{r["l"]}</span> with him, '
                 f'<span class="mono">{r["ow"]}-{r["ol"]}</span> without') for r in rows[:TOP_N]], rows
    if key == "bad-luck":
        rows = A.list_bad_luck(d, era, mg)
        return [(r["pid"], f'<span class="big mono">{r["idx"]:.1f}</span>',
                 f'Accolade score {r["acc"]:g}, teams averaged {fpct(r["avg"])} '
                 f'over {r["n"]} seasons') for r in rows[:TOP_N]], rows
    raise KeyError(key)


def rows_html(s, items, up):
    if not items:
        return '<p class="empty">Nobody qualifies with these filters.</p>'
    out = []
    rank = 0
    prev = None
    for i, (pid, val, det) in enumerate(items):
        if val != prev:
            rank = i + 1
            prev = val
        out.append(f"""<li><span class="rk mono">{rank}</span>{s.pic(pid, up, 'sm')}<div class="who"><strong>{s.plink(pid, up)}</strong>
<span class="det">{det}</span></div><div class="val">{val}</div></li>""")
    return '<ol class="lst">' + "".join(out) + "</ol>"


def panels(s, key, up, fn):
    out = []
    for era in (1947, 1977, 1997):
        for mg, tag in ((1, "any"), (20, "20")):
            out.append(f'<div class="panel p{era}-{tag}">{fn(era, mg)}</div>')
    return '<div class="panels">' + "".join(out) + "</div>"


def list_page(s, key, title, desc, value_label, cache):
    up = "../"
    rel = f"lists/{key}.html"
    first_rows = None

    def standard(era, mg):
        nonlocal first_rows
        items, rows = list_panel_rows(s, key, era, mg, up, cache)
        if era == 1947 and mg == 1:
            first_rows = rows
        return rows_html(s, items, up)

    extra = ""
    if key == "franchise-winningest":
        def fr(era, mg):
            res = A.list_franchise(s.d, era, mg)
            if not res:
                return '<p class="empty">Nobody qualifies with these filters.</p>'
            blocks = []
            order = sorted(res, key=lambda f: (f in DEFUNCT, f))
            for f in order:
                last_season = max(st for (ff, st) in ((t["f"], t["s"]) for t in s.d.teams.values()) if ff == f)
                items = [(r["pid"], f'<span class="big mono">{r["w"]}</span>',
                          f'<span class="mono">{r["w"]}-{r["l"]}</span> in his games, {fpct(A.pct(r["w"], r["l"]))}')
                         for r in res[f]]
                blocks.append(f'<h3 class="fr">{s.tlink(f, last_season)}</h3>' + rows_html(s, items, up))
            return "".join(blocks)
        body_panels = panels(s, key, up, fr)
        first_rows = [{"pid": r[0]["pid"]} for r in A.list_franchise(s.d, 1947, 1, top=1).values()]
    elif key == "bad-luck":
        def bl(era, mg):
            items, rows = list_panel_rows(s, key, era, mg, up, cache)
            rc = A.list_ring_chasers(s.d, era, mg)
            ca = A.list_carriers(s.d, era, mg, cache.setdefault("top", A.team_top_scorers(s.d)))
            rc_items = [(r["pid"], f'<span class="big mono">{r["n"]}</span>',
                         f'{r["ppg"]:.1f} points per game in those seasons: '
                         + ", ".join(season_label(y) for y in r["years"])) for r in rc[:25]]
            ca_items = [(r["pid"], f'<span class="big mono">{r["n"]}</span>',
                         f'of his {r["titles"]} titles: ' + ", ".join(season_label(y) for y in r["years"]))
                        for r in ca[:25]]
            return (f'<h3>Bad luck: great players on bad teams</h3>{rows_html(s, items, up)}'
                    f'<h3>Ring chasers: most titles with the smallest role</h3>'
                    f'<p class="note">2+ titles, 6 or fewer points per game in his title seasons.</p>{rows_html(s, rc_items, up)}'
                    f'<h3>Carriers: titles as his team\'s top scorer</h3>'
                    f'<p class="note">Titles won in a season he scored the most regular-season points on the champion.</p>{rows_html(s, ca_items, up)}')
        body_panels = panels(s, key, up, bl)
        first_rows = A.list_bad_luck(s.d, 1947, 1)[:TOP_N]
        w = s.d.meta["accolade_weights"]
        extra = ("""<section class="formula"><h2>The formula</h2>
<p><strong>Accolade score</strong> = the same weights Teammates Score uses, added up over his awards: """
                 + ", ".join(f"{e(k)} {v:g}" for k, v in sorted(w.items(), key=lambda x: -x[1]))
                 + """. An MVP already covers that season's All-NBA nod, and a DPOY that season's All-Defensive nod.</p>
<p><strong>Bad Luck Index</strong> = Accolade score × (.500 − his teams' average win %) × 10. His teams' average is weighted by the games he played for each. Only players whose teams averaged under .500, minimum 5 seasons. With an era filter on, both numbers count only seasons in that era.</p></section>""")
    else:
        body_panels = panels(s, key, up, standard)
    # badges: top-50 all-time membership
    if first_rows:
        for i, r in enumerate(first_rows[:TOP_N]):
            pid = r["pid"]
            if (key, title) not in s.badges[pid]:
                s.badges[pid].append((key, title))
    body = f"""<header><h1>{e(title)}</h1><p class="subtitle">{e(desc)}</p></header>
{toggles(True, 'l')}
{extra}
{body_panels}
<p class="note">Regular season, 1946-47 through 2025-26. A player was on a team-season if he played at least one game for it; "20+ games only" keeps only team-seasons where he played 20 or more. The number next to each season is his games for that team. <a href="../how-we-count.html">How we count</a>.</p>
<p class="more">More lists: {' · '.join(f'<a href="{k}.html">{e(t)}</a>' for k, t, _, _ in LISTS if k != key)}</p>"""
    pdesc = f"{title}: {desc} All-time, since 1976-77 and since 1996-97, with every player's team and games."
    return rel, page(rel, f"{title} | HoopsMatic", pdesc, body, up)


# ---------------------------------------------------------------------------
# Current-season boards
# ---------------------------------------------------------------------------
def current_rows(s):
    if not s.cur:
        return [], [], None
    gaps = []
    movers = []
    pre_ok = 0
    for pid, sts in s.cur["players"].items():
        st = [x for x in sts if x.get("endTeam")] or sts[-1:]
        st = st[0]
        if st["g"] >= 5 and st["ow"] + st["ol"] >= 5:
            gaps.append((A.pct(st["w"], st["l"]) - A.pct(st["ow"], st["ol"]), pid, st))
        pre_on = [st["on"][i] - st["on30"][i] for i in range(4)]
        if pre_on[1] >= 300:
            pre_ok += 1
    baseline = "earlier" if pre_ok >= 20 else "last"
    for pid, sts in s.cur["players"].items():
        st = ([x for x in sts if x.get("endTeam")] or sts[-1:])[0]
        if st["on30"][1] < 250 or st["off30"][1] < 100:
            continue
        now = A.onoff({"on": st["on30"], "off": st["off30"]})
        if now is None:
            continue
        if baseline == "earlier":
            pre = {"on": [st["on"][i] - st["on30"][i] for i in range(4)],
                   "off": [st["off"][i] - st["off30"][i] for i in range(4)]}
            if pre["on"][1] < 300 or pre["off"][1] < 100:
                continue
            base = A.onoff(pre)
        else:
            if pid not in s.d.players:
                continue
            on = [0, 0, 0, 0]
            off = [0, 0, 0, 0]
            for x in s.d.players[pid]["seasons"]:
                if x["s"] == LAST_COMPLETE and x.get("rm"):
                    for i in range(4):
                        on[i] += x["rm"]["on"][i]
                        off[i] += x["rm"]["off"][i]
            if on[1] < 500 or off[1] < 200:
                continue
            base = A.onoff({"on": on, "off": off})
        if base is None:
            continue
        movers.append((now - base, pid, st, now, base))
    gaps.sort(key=lambda x: -x[0])
    movers.sort(key=lambda x: -x[0])
    return gaps, movers, baseline


def gap_items(s, rows, up):
    return [(pid, f'<span class="big mono {cls_gap(g)}">{fgap(g)}</span>',
             f'{s.tlink(st["f"], CURRENT_SEASON)}: <span class="mono">{st["w"]}-{st["l"]}</span> with him, '
             f'<span class="mono">{st["ow"]}-{st["ol"]}</span> without') for g, pid, st in rows]


def mover_items(s, rows, up, baseline):
    lab = "earlier this season" if baseline == "earlier" else "2025-26"
    return [(pid, f'<span class="big mono {cls_gap(ch)}">{ch:+.1f}</span>',
             f'{s.tlink(st["f"], CURRENT_SEASON)}: on/off {now:+.1f} per 100 in the last 30 days, '
             f'{base:+.1f} {lab}') for ch, pid, st, now, base in rows]


def board_page(s, key):
    up = "../"
    gaps, movers, baseline = current_rows(s)
    through = s.cur["through"] if s.cur else "n/a"
    if key == "without-him":
        rel = "lists/winning-without-him.html"
        title = f"{season_label(CURRENT_SEASON)} with and without: team win rate in games he played vs missed"
        desc = (f"Every active player's {season_label(CURRENT_SEASON)} team record with him and without him "
                f"(at least 5 games each side), sorted by the gap. Updated every morning; games through {nice_date(through) if s.cur else through}.")
        body = f"""<header><h1>{e(title)}</h1><p class="subtitle">{e(desc)}</p></header>
<section><h2>Higher win rate in games he played</h2>{rows_html(s, gap_items(s, gaps[:TOP_N], up), up)}</section>
<section><h2>Higher win rate in games he missed</h2>{rows_html(s, gap_items(s, gaps[::-1][:TOP_N], up), up)}</section>"""
    else:
        rel = "lists/on-off-movers.html"
        lab = "the rest of the season" if baseline == "earlier" else "2025-26"
        title = f"Last 30 days movers: on/off per 100, {season_label(CURRENT_SEASON)}"
        desc = (f"Biggest change in on/off per 100 possessions over the last 30 days compared with {lab}. "
                f"From Ramiro's lineup data, updated every morning; games through {nice_date(through) if s.cur else through}.")
        note = ("" if baseline == "earlier" else
                "<p class=\"note\">Early in the season the last 30 days are the whole season, so the comparison is "
                "with his 2025-26 on/off (any team). It switches to the earlier part of this season once enough "
                "games are played.</p>")
        body = f"""<header><h1>{e(title)}</h1><p class="subtitle">{e(desc)}</p></header>{note}
<p class="note">On/off = team net points per 100 possessions with him on the floor minus with him off, in the games he played. Minimum 250 on-court possessions in the last 30 days.</p>
<section><h2>Biggest risers</h2>{rows_html(s, mover_items(s, movers[:TOP_N], up, baseline), up)}</section>
<section><h2>Biggest fallers</h2>{rows_html(s, mover_items(s, movers[::-1][:TOP_N], up, baseline), up)}</section>"""
    return rel, page(rel, f"{title} | HoopsMatic", desc, body, up)


# ---------------------------------------------------------------------------
# Hub, A-Z, How we count
# ---------------------------------------------------------------------------
def hub(s):
    up = ""
    gaps, movers, baseline = current_rows(s)
    by_name = {v["name"]: k for k, v in s.ids.items()}
    feat = []
    for n in FEATURED:
        pid = by_name.get(n)
        if not pid or pid not in s.d.players:
            continue
        sm = A.summary(s.d, pid)
        feat.append(f"""<li>{s.pic(pid, up, 'md')}<div><strong>{s.plink(pid, up)}</strong>
<span class="det"><span class="mono">{sm['w']}-{sm['l']}</span> with him, <span class="mono">{sm['ow']}-{sm['ol']}</span> without, {sm['titles']} titles</span></div></li>""")
    lists = "".join(f'<li><a href="lists/{k}.html"><strong>{e(t)}</strong></a><span class="det">{e(d)}</span></li>'
                    for k, t, d, _ in LISTS)
    through = s.cur["through"] if s.cur else "n/a"
    az = " ".join(f'<a href="players/{c}.html">{c.upper()}</a>' for c in "abcdefghijklmnopqrstuvwxyz")
    body = f"""<header><h1>Team Success</h1>
<p class="subtitle">How every NBA player's teams did with him and without him, every season since 1946-47: records, playoff runs, on/off from 1996-97, best duos and the all-time lists.</p></header>
<section class="search"><h2>Find a player</h2>
<form id="ts-search" role="search" action="players/a.html"><label for="q" class="vh">Player name</label>
<input id="q" name="q" type="search" autocomplete="off" placeholder="Type a name, e.g. Bill Russell" data-index="assets/players.json"></form>
<ul id="results" class="results" aria-live="polite"></ul>
<p class="az">Browse A-Z: {az}</p></section>
<section><h2>{season_label(CURRENT_SEASON)}: with and without</h2>
<p class="note">Team record with him and without him this season, at least 5 games each side. {season_label(CURRENT_SEASON)} games through {e(nice_date(through) if s.cur else through)}; career pages cover completed seasons through {season_label(LAST_COMPLETE)}. <a href="lists/winning-without-him.html">Full board</a></p>
<div class="two"><div><h3>Higher win rate in games he played</h3>{rows_html(s, gap_items(s, gaps[:8], up), up)}</div>
<div><h3>Higher win rate in games he missed</h3>{rows_html(s, gap_items(s, gaps[::-1][:8], up), up)}</div></div></section>
<section><h2>Last 30 days movers</h2>
<p class="note">Change in on/off per 100 possessions, last 30 days vs {'earlier this season' if baseline == 'earlier' else '2025-26'}. <a href="lists/on-off-movers.html">Full board</a></p>
<div class="two"><div><h3>Risers</h3>{rows_html(s, mover_items(s, movers[:8], up, baseline), up)}</div>
<div><h3>Fallers</h3>{rows_html(s, mover_items(s, movers[::-1][:8], up, baseline), up)}</div></div></section>
<section><h2>The lists</h2><ul class="lists">{lists}
<li><a href="lists/winning-without-him.html"><strong>{season_label(CURRENT_SEASON)} with and without</strong></a><span class="det">Updated every morning.</span></li>
<li><a href="lists/on-off-movers.html"><strong>Last 30 days movers</strong></a><span class="det">On/off per 100, updated every morning.</span></li></ul></section>
<section><h2>Featured players</h2><ul class="feat">{''.join(feat)}</ul></section>
<script src="assets/search.js" defer></script>"""
    desc = ("Every NBA player's team record with him and without him since 1946-47: worst and best teams, "
            "60-win seasons, playoff droughts, on/off, best duos and a daily current-season board.")
    return "index.html", page("index.html", "Team Success: NBA team records with and without every player | HoopsMatic",
                              desc, body, up)


def last_name_key(name):
    parts = [p for p in name.replace(".", " ").split() if p.lower() not in ("jr", "sr", "ii", "iii", "iv")]
    ln = parts[-1] if parts else name
    c = ln[:1].lower()
    import unicodedata
    c = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode() or "z"
    return (c if c.isalpha() else "z"), ln.lower(), name.lower()


def az_pages(s):
    groups = defaultdict(list)
    for pid, v in s.ids.items():
        if s.has_page(pid):
            groups[last_name_key(v["name"])[0]].append(pid)
    out = []
    nav = " ".join(f'<a href="{c}.html">{c.upper()}</a>' for c in "abcdefghijklmnopqrstuvwxyz")
    for c in "abcdefghijklmnopqrstuvwxyz":
        pids = sorted(groups.get(c, []), key=lambda p: last_name_key(s.ids[p]["name"])[1:])
        items = []
        for pid in pids:
            st = s.d.players.get(pid, {"seasons": []})["seasons"]
            ys = sorted({x["s"] for x in st if x["g"]})
            if s.cur and pid in s.cur["players"]:
                ys.append(CURRENT_SEASON)
            span = f"{season_label(ys[0])} to {season_label(ys[-1])}" if ys else ""
            items.append(f'<li>{s.plink(pid, "../")} <span class="sub">{e(span)}</span></li>')
        rel = f"players/{c}.html"
        body = f"""<header><h1>Players: {c.upper()}</h1><p class="subtitle">{len(pids)} players whose last name starts with {c.upper()}.</p></header>
<p class="az">{nav}</p><ul class="azl">{''.join(items)}</ul>"""
        out.append((rel, page(rel, f"NBA players {c.upper()}: team records with and without them | HoopsMatic",
                              f"Team Success pages for the {len(pids)} NBA players whose last name starts with {c.upper()}: "
                              "team record with and without each of them, every season.", body, "../")))
    return out


def how_page(s):
    """How we count: every rule, traced to the code, with the audit's worked examples."""
    st0 = load_json(os.path.join(DATA, "step0.json"), {})
    au = load_json(os.path.join(DATA, "audit.json"), {})
    groups = st0.get("minutes_groups", {})
    j = au.get("jordan", {})
    w = au.get("windows", {})
    rk = au.get("rnk", {})
    through = s.cur["through"] if s.cur else None
    sizes = rk.get("league_sizes", {})
    jrows = "".join(
        f"""<tr><td data-l="Season" class="mono">{season_label(r['season'])}</td><td data-l="Team">{e(r['team'])}</td>
<td data-l="His games" class="mono">{r['g']}</td><td data-l="First and last game" class="mono">{e(r['first'])} to {e(r['last'])}</td>
<td data-l="With him" class="mono">{e(r['with'].replace('-', EN))}</td><td data-l="Without, window" class="mono">{e(wl(*map(int, r['without'].split('-'))))}</td>
<td data-l="Without, span" class="mono">{e(wl(*map(int, r['span_without'].split('-'))))}</td><td data-l="Final finish" class="mono">#{r['rnk']} of {sizes.get(str(r['season']), '?')}</td></tr>"""
        for r in j.get("seasons", []))
    jw, jl = j.get("with", [0, 0])
    ow, ol = j.get("without", [0, 0])
    sw, sl = j.get("span_without", [0, 0])
    dropped = len(st0.get("impossible_rows_dropped", []))
    # the season that moves the most between the two definitions, filled from the audit rows
    j95_html = ""
    rows95 = [r for r in j.get("seasons", []) if r["season"] == 1995]
    if rows95:
        r = rows95[0]
        a, b = map(int, r["without"].split("-"))
        missing = sorted(set(range(1985, 2004)) - {x["season"] for x in j["seasons"]})
        j95_html = (f"<p>The difference is mostly {season_label(1995)}. He played only for the {e(r['team'])} that season, "
                    f"so the window is the whole season and the team's <span class=\"mono\">{a}{EN}{b}</span> before his first game "
                    f"on {e(nice_date(r['first']))} counts as \"without him\". The span starts at his first game, so those "
                    f"{a + b} games drop out. Seasons with no games for any team "
                    f"({e(', '.join(season_label(y) for y in missing))}) are outside both definitions: no team-season, no window.</p>")
    # removed appearances, grouped by player-season-team
    grp = defaultdict(list)
    for x in st0.get("impossible_rows_dropped", []):
        grp[(str(x["personId"]), x["team"], x["date"][:4])].append(x["date"])
    items = []
    for (pid, f, _), dates in sorted(grp.items(), key=lambda kv: (min(kv[1]), kv[0])):
        sy = int(min(dates)[:4]) + (1 if int(min(dates)[5:7]) >= 8 else 0)
        nm = s.plink(pid, "") if pid in s.ids else e(pid)
        items.append(f"<li>{nm}, {season_label(sy)}, {s.tlink(f, sy)}: {len(dates)} "
                     f"{'game' if len(dates) == 1 else 'games'} ({', '.join(e(nice_date(d)) for d in sorted(dates))})</li>")
    # the two player-seasons with the most removed rows, named from the data
    bys = defaultdict(lambda: defaultdict(int))
    for (pid, f, _), dates in grp.items():
        sy = int(min(dates)[:4]) + (1 if int(min(dates)[5:7]) >= 8 else 0)
        bys[(pid, sy)][f] += len(dates)
    top = sorted(bys.items(), key=lambda kv: -sum(kv[1].values()))[:2]
    ex = []
    for (pid, sy), fs in top:
        if pid not in s.ids:
            continue
        teams = " and ".join(s.tlink(f, sy) for f in sorted(fs, key=lambda f: -fs[f]))
        ex.append(f"{season_label(sy)} rows that put {s.plink(pid, '')} on the {teams}")
    examples_html = (" (for example, " + "; ".join(ex) + ")") if ex else ""
    removed_html = (f'<details><summary>{dropped} removed appearances, by player</summary><ul>{"".join(items)}</ul></details>'
                    if items else "")
    size_txt = ", ".join(f"{season_label(int(y))}: {n}" for y, n in sorted(sizes.items(), key=lambda x: int(x[0]))
                         if int(y) in (1947, 1950, 1951, 1954, 1962, 1967, 1968, 1977, 1981, 1989, 1996, 2005))
    body = f"""<header><h1>How we count</h1><p class="subtitle">The rules behind every number in Team Success, traced to the data and code that produce them.</p></header>
<section class="prose">
<h2>What each page covers</h2>
<p><strong>Career numbers</strong> cover completed regular seasons, {season_label(1947)} through {season_label(LAST_COMPLETE)}, plus the playoffs of those seasons. <strong>The current season</strong> ({season_label(CURRENT_SEASON)}) is shown separately: games through {e(nice_date(through))}, the last game in the nightly data. It is not added to any career total until the season ends.</p>
<p>That is why a player page can say "through {season_label(LAST_COMPLETE)}" while the daily boards show games from {e(nice_date(through))}: one is the career, the other the season in progress.</p>
<h2>Formats</h2>
<p>Records use an en dash (706{EN}366). Win rates read 65.9%. Differences between two win rates read +26.0 pp (percentage points), worked out from the unrounded rates. Possession-based on/off is in points per 100 possessions, a different unit, and is always labeled that way. An empty sample (no games) shows N/A, never 0.0%.</p>
<h2>Final NBA finish</h2>
<p>Each team-season's final finish is the RNK column of our standings table. The champion is #1 and the runner-up #2; the other teams follow by playoff round reached, then by regular-season win %. Teams with the same round and win % share a rank. We re-derived every RNK from that rule: {len(rk.get('mismatches', [])) if rk else 'N/A'} of {sum(sizes.values()):,} team-seasons differ, and {rk.get('tied_rows', 0):,} share a rank.</p>
<p>A finish always comes with that season's league size: "#8 of 30". League sizes changed a lot ({e(size_txt)}; 30 since 2004-05), so the league-size-adjusted finish puts every season on one scale: (rank {MINUS} 1) / (teams {MINUS} 1), where 0 is the champion and 1 is last. Live standings and conference seeds are labeled as such and never mixed with the final finish.</p>
<h2>Was he on that team?</h2>
<p>A player was on a team-season if he played at least one regular-season game for it. "Played" means he logged minutes or any stat. Minutes were not kept from {season_label(1947)} to {season_label(1951)} and only in some games until {season_label(1976)}; in a game without minutes, being in the box score counts as playing. From {season_label(RAMIRO_FIRST)}, a 0-minute row with no stats counts when the lineup data puts him on the floor (a seconds-long appearance, not a DNP).</p>
<p>We removed {dropped} appearances a player could not have made: source box scores that file one player's line under another player's ID, or on the wrong team{examples_html}. The rule flags games for one team that sit between two games he played for another team with no game of that team missed in between, appearances for two teams on the same day, and stints made only of 0-minute rows in games where minutes were kept. Among the flagged rows, the 0-minute ones go; when there are none (seasons without minutes), the rows of the team he played fewer games for that season go. Every removed row is listed below.</p>
{removed_html}
<h2>With him and without him</h2>
<p>"With him" is the team's record in the regular-season games he played for it. "Without him" is the team's record in games he missed, and it needs a window: which missed games count. No free source we are allowed to use has historical signing, waiver or trade dates, so we publish two definitions, both rebuilt from the game logs.</p>
<ul>
<li><strong>Team-season window</strong> (the headline number): with one team all season, the whole season. If he changed teams, the first window ends the day before his first game for the next team, and the next window starts the day after his last game for the previous one.</li>
<li><strong>Appearance span</strong>: only the team's games between his first and last game for that team (per stint). No game before he arrived or after he left counts, and no game counts for two teams. It can miss a real absence at the start or end of a stint.</li>
</ul>
<p>What the window proxy counts that the span does not, across every player: {w.get('one_team_games_before_first_appearance', 0):,} team games before a one-team player's first appearance (late signings, call-ups, injuries) in {w.get('rows_before', 0):,} team-seasons; {w.get('one_team_games_after_last_appearance', 0):,} games after his last appearance (cuts, season-ending injuries) in {w.get('rows_after', 0):,} team-seasons; and {w.get('traded_games_between_teams', 0):,} games in the days between two teams, which count for both, in {w.get('rows_traded', 0):,} traded team-seasons.</p>
<p>The gap is win % with him minus win % without him, in percentage points. Leaderboards that rank gaps set separate minimums for games played and games missed and show both samples.</p>
<h2>Worked example: Michael Jordan</h2>
<p>With him: <span class="mono">{jw}{EN}{jl}</span> in {jw + jl:,} games ({pct1(jw / (jw + jl)) if jw + jl else 'N/A'}), wins minus losses <span class="mono">{signed(jw - jl)}</span>. Without him, team-season window: <span class="mono">{wl(ow, ol)}</span> in {ow + ol} games ({pct1(ow / (ow + ol)) if ow + ol else 'N/A'}), a gap of <span class="mono">{pp((jw / (jw + jl)) - (ow / (ow + ol))) if ow + ol else 'N/A'}</span>. Without him, appearance span: <span class="mono">{wl(sw, sl)}</span> in {sw + sl} games ({pct1(sw / (sw + sl)) if sw + sl else 'N/A'}), a gap of <span class="mono">{pp((jw / (jw + jl)) - (sw / (sw + sl))) if sw + sl else 'N/A'}</span>.</p>
{j95_html}
<table class="tt"><thead><tr><th>Season</th><th>Team</th><th>His games</th><th>First and last game</th><th>With him</th><th>Without, window</th><th>Without, span</th><th>Final finish</th></tr></thead><tbody>{jrows}</tbody></table>
<p>His career cards trace to the same rows: {j.get('winning', 'N/A')} winning seasons (team above .500), {j.get('trips', 'N/A')} playoff trips, {j.get('titles', 'N/A')} titles and an average final finish of {j.get('avg_rnk', 0):.1f} (the mean of his {len(j.get('seasons', []))} seasons' ranks). The leaderboards use the same functions.</p>
<h2>Seasons split between teams</h2>
<p>Each stint is its own row with its own window. Where a summary needs one row per season (winning seasons, average finish, streaks), it uses the stint with the most games; ties go to the later team. A playoff trip means he played a playoff game, or the team he finished the season with made the playoffs; a title follows the same rule. Play-in losses are not playoff trips.</p>
<h2>Playoffs</h2>
<p>Playoff with/without works the same way, shown separately, for each team he played at least one playoff game for. A team's playoff result always comes from the standings; series scores come from the playoff games. Play-in games are in neither the regular season nor the playoffs. In 1953-54 the first round was a round robin: the Fort Wayne Pistons and New York Knicks played playoff games but are listed as missing the playoffs, as in the standings.</p>
<h2>On/off, starts and close games ({season_label(RAMIRO_FIRST)} on)</h2>
<ul><li><strong>On/off per 100</strong>: the team's net points per 100 possessions with him on the floor minus with him off, in the games he played for that team. A different unit from the win-rate gaps.</li>
<li><strong>Started / bench</strong>: the team's record in games he was in the first five vs games he came off the bench.</li>
<li><strong>Close games</strong>: games where the margin was 5 points or fewer at some point in the last 5 minutes of the 4th quarter or overtime, and he was on the floor for at least one of those possessions.</li></ul>
<p>These come from Ramiro Bentes' public lineup and possession data, which starts in {season_label(RAMIRO_FIRST)}. Before that they show N/A.</p>
<h2>Lists</h2>
<p>Every list covers regular seasons {season_label(1947)} through {season_label(LAST_COMPLETE)} and has three eras: all-time, since 1976-77 and since 1996-97. "Winning seasons" and "playoff droughts" count the seasons he played, in a row; a season he missed entirely neither breaks nor extends a streak. The Accolade score uses the Teammates Score weights; the formula is on the <a href="lists/bad-luck.html">Bad Luck Index</a> page.</p>
<h2>What is missing or corrected</h2>
<ul>
<li>One 1953-54 Milwaukee Hawks vs Baltimore Bullets game is missing from the box scores, and eight games from 1946-47 to 1953-54 have results that disagree with the official standings. Team records use the standings; with/without uses the games we have.</li>
<li>Eight tiebreaker games from 1948 to 1957 and the cancelled April 2013 Celtics-Pacers game are left out of the regular season.</li>
<li>Ten neutral-site games (2024-25 and 2025-26) have the missing team and score filled in from the box score.</li>
<li>2025-26 conference and division finishes are worked out from the records.</li>
<li>Seasons with no minutes at all: {e(', '.join(season_label(y) for y in groups.get('never', [])))}.</li>
<li>The current season uses Ramiro's daily lineup data until the box-score archive adds it.</li>
</ul>
<h2>Sources</h2>
<p>Box scores for every game since 1946-47 (Alberto de Roa's nba-boxscores), lineups and possessions since 1996-97 (Ramiro Bentes' nba_data), player names and awards (HoopsMatic's player database), team standings (HoopsMatic). All public.</p>
</section>"""
    rel = "how-we-count.html"
    return rel, page(rel, "How we count: team records with and without a player | HoopsMatic",
                     "The rules behind Team Success: final NBA finish, the two with/without definitions, "
                     "traded players, playoffs, on/off per 100 and the data corrections, with a worked example.",
                     body, "")


# ---------------------------------------------------------------------------
# Assets, search index, sitemap
# ---------------------------------------------------------------------------
def copy_assets(s):
    """Fonts (OFL, from hh-teammates) and the face-fill headshots, self-hosted."""
    fdir = os.path.join(ROOT, "assets", "fonts")
    os.makedirs(fdir, exist_ok=True)
    src_fonts = os.path.join(SRC, "hh-teammates", "assets", "fonts")
    if os.path.isdir(src_fonts):
        for f in os.listdir(src_fonts):
            if not os.path.exists(os.path.join(fdir, f)):
                shutil.copy(os.path.join(src_fonts, f), os.path.join(fdir, f))
    hdir = os.path.join(ROOT, "assets", "hs")
    os.makedirs(hdir, exist_ok=True)
    src_hs = os.path.join(SRC, "nba-headshots", "players", "headshots", "face-fill")
    if os.path.isdir(src_hs):
        for v in s.ids.values():
            f = v.get("hs")
            if f and not os.path.exists(os.path.join(hdir, f)) and os.path.exists(os.path.join(src_hs, f)):
                shutil.copy(os.path.join(src_hs, f), os.path.join(hdir, f))


def search_index(s):
    rows = []
    for pid, v in s.ids.items():
        if not s.has_page(pid):
            continue
        st = s.d.players.get(pid, {"seasons": []})["seasons"]
        ys = sorted({x["s"] for x in st if x["g"]})
        if s.cur and pid in s.cur["players"]:
            ys.append(CURRENT_SEASON)
        rows.append([v["name"], v["slug"], season_label(ys[0]) if ys else "", season_label(ys[-1]) if ys else ""])
    rows.sort(key=lambda r: r[0])
    return "assets/players.json", json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def sitemap(pages_rel):
    path = os.path.join(DATA, "sitemap_lastmod.json")
    lm = load_json(path, {})
    today = dt.date.today().isoformat()
    urls = []
    for rel in sorted(pages_rel):
        full = os.path.join(ROOT, rel)
        with open(full, "rb") as fh:
            h = hashlib.sha256(fh.read()).hexdigest()[:16]
        cur = lm.get(rel)
        if not cur or cur["h"] != h:
            lm[rel] = {"h": h, "d": today}
        loc = BASE + ("" if rel == "index.html" else rel)
        urls.append(f"<url><loc>{e(loc)}</loc><lastmod>{lm[rel]['d']}</lastmod></url>")
    for k in list(lm):
        if k not in pages_rel:
            del lm[k]
    dump_json(path, lm, compact=False)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    write("sitemap.xml", xml)


def all_page_paths():
    out = []
    for d in ("", "player", "lists", "players"):
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for f in os.listdir(base):
            if f.endswith(".html"):
                out.append(os.path.join(d, f) if d else f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", action="store_true", help="nightly: only pages the current season touches")
    args = ap.parse_args()
    s = Site()
    copy_assets(s)
    cache = {}
    # lists first: they fill the player badges
    list_pages = [list_page(s, k, t, d, v, cache) for k, t, d, v in LISTS]
    if not args.current:
        for rel, txt in list_pages:
            write(rel, txt)
        write(*how_page(s))
    for key in ("without-him", "movers"):
        write(*board_page(s, key))
    write(*hub(s))
    for rel, txt in az_pages(s):
        write(rel, txt)
    write(*search_index(s))
    if args.current:
        targets = list(s.cur["players"]) if s.cur else []
    else:
        targets = [p for p in s.ids if s.has_page(p)]
    for pid in targets:
        write(*player_page(s, pid))
    # robots + sitemap
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n")
    write(".nojekyll", "")
    sitemap(all_page_paths())
    print(f"wrote {len(written)} files, {skipped} unchanged")


if __name__ == "__main__":
    main()

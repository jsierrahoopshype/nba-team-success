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
import boards as B  # noqa: E402
import charts as CH  # noqa: E402
import leads as LEADS  # noqa: E402
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
    """Win rate, house format: 65.9% (N/A for an empty sample)."""
    return pct1(p)


def fgap(g):
    """Gap between two win rates, house format: +26.0 pp."""
    return pp(g)


def fnum(x, digits=1, sign=True):
    if x is None:
        return "N/A"
    s = f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"
    return s.replace("-", "\u2212")


def rec(w, l):
    return f"{w}\u2013{l}"


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
        # league size per season, for "#8 of 30"
        self.sizes = defaultdict(int)
        for t in self.d.teams.values():
            self.sizes[t["s"]] += 1
        # career leaderboards: one compact data set, default ranks for the career cards
        self.board_data = B.compact(self.d, self.cur)
        self.ranks, self.rank_n, self.board_default = {}, {}, {}
        for key in B.BOARDS:
            ranked, sort, mins = B.compute(self.board_data, key)
            self.board_default[key] = (ranked, sort, mins)
            self.ranks[key] = {m["pid"]: (r, tied) for r, tied, m in ranked}
            self.rank_n[key] = len(ranked)
        self.lead_rules = {}
        # who played for each team-season, most games first (season boards)
        self.roster = defaultdict(list)
        for pid, p in self.d.players.items():
            for st in p["seasons"]:
                if st["g"] and st["s"] <= LAST_COMPLETE:
                    self.roster[(st["f"], st["s"])].append((st["g"], pid))
        for k in self.roster:
            self.roster[k].sort(key=lambda x: (-x[0], self.ids.get(x[1], {}).get("name", "")))

    def adj_avg(self, pid):
        """Mean league-size-adjusted finish, (rank - 1) / (teams - 1), one team per season."""
        vals = []
        for sy, (main, end, lst) in self.d.season_main(pid).items():
            t = self.d.team(main["f"], sy)
            n = self.sizes[sy]
            vals.append((t["rnk"] - 1) / (n - 1) if n > 1 else 0.0)
        return sum(vals) / len(vals) if vals else 0.0

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
<script src="{up}assets/ts.js" defer></script>
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
    ctl.append(f'<label for="g20-{key}" class="pill lg20">Only team-seasons where he played 20+ games</label>')
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
                    f'<span class="mono">{fin["w"]}{EN}{fin["l"]}</span> in the Finals')
        return "Won the title"
    if po in ("", "Play-In"):
        return A.PO_LABEL[po]
    el = t.get("elim")
    rnd = {"First Round": "first round", "Conf Semis": "conference semifinals",
           "Conf Finalist": "conference finals", "Finalist": "NBA Finals"}.get(po, po)
    if el:
        return (f'Lost {rnd} to {s.tlink(el["opp"], t["s"])} '
                f'<span class="mono">{el["w"]}{EN}{el["l"]}</span>')
    return f"Lost {rnd}"


def finish_text(t):
    """Regular-season standing (conference / division), labeled apart from the final finish."""
    parts = []
    if t.get("divPos") and t.get("div") and t["div"] != t["conf"]:
        parts.append(f'{t["divPos"]} in {t["div"]}')
    if t.get("confPos") and t.get("conf"):
        parts.append(f'{t["confPos"]} in {t["conf"]}')
    return ", ".join(parts) or "N/A"


def rec_cell(w, l):
    if w + l == 0:
        return '<span class="flat">N/A</span>'
    return f'<span class="mono">{w}{EN}{l}</span> <span class="sub">{pct1(A.pct(w, l))}</span>'


def wl2(x):
    return f"{x[0]}{EN}{x[1]}" if sum(x) else "N/A"


# --- sortable tables (Modern Web Guidance "sortable-table") --------------------------------------
def th(label, typ="number", sort=None, first=None):
    """A sortable header: a <button> inside <th scope=col>; aria-sort only on the sorted one."""
    a = f' aria-sort="{sort}"' if sort else ""
    f = f' data-first="{first}"' if first else ""
    return f'<th scope="col" data-type="{typ}"{a}{f}><button type="button">{label}</button></th>'


def td(label, inner, value=None, cls=""):
    v = "" if value is None else f' data-value="{e(value)}"'
    c = f' class="{cls}"' if cls else ""
    return f'<td data-l="{e(label)}"{c}{v}>{inner}</td>'


def sortable(cap_id, caption, heads, rows, extra_cls=""):
    return (f'<div class="tblwrap"><table class="tt sortable {extra_cls}" aria-labelledby="{cap_id}">'
            f'<thead><tr>{"".join(heads)}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
            f'<p class="vh sort-status" role="status"></p></div>')


def fval(x, nd=6):
    return None if x is None else round(x, nd)


def board_link(up, sy, f):
    return f"{up}seasons/{season_label(sy)}.html#t-{f}"


def finish_cell(s, t, up):
    size = s.sizes[t["s"]]
    return (f'<a class="mono" href="{board_link(up, t["s"], t["f"])}">#{t["rnk"]} of {size}</a>')


def season_rows(s, pid, up):
    rows = []
    lineup = []
    by = defaultdict(list)
    for st in s.d.players[pid]["seasons"]:
        if st["s"] <= LAST_COMPLETE and st["g"] and s.d.team(st["f"], st["s"]):
            by[st["s"]].append(st)
    mains = {sy: v[0] for sy, v in s.d.season_main(pid).items()}
    for sy in sorted(by, reverse=True):
        lst = sorted(by[sy], key=lambda x: x.get("first") or "")
        for i, st in enumerate(lst):
            t = s.d.team(st["f"], sy)
            gap = (A.pct(st["w"], st["l"]) - A.pct(st["ow"], st["ol"])) if st["ow"] + st["ol"] else None
            sgap = (A.pct(st["w"], st["l"]) - A.pct(st.get("sw", 0), st.get("sl", 0))) if st.get("sw", 0) + st.get("sl", 0) else None
            modern = sy >= RAMIRO_FIRST
            rm = st.get("rm")
            oo = A.onoff(rm) if rm else None
            tg = t["w"] + t["l"]
            note = ""
            if len(lst) > 1:
                drives = " Season summary uses this stint." if mains.get(sy) is st else ""
                note = (f'<span class="sub blk">Stint {i + 1} of {len(lst)}: {e(nice_date(st["first"]))} to '
                        f'{e(nice_date(st["last"]))}.{drives}</span>')
            depth = A.PO_DEPTH[t["po"]] + (0.5 if t["po"] == "Play-In" else 0)
            rows.append("<tr>" + "".join([
                td("Season", season_label(sy), sy, "mono"),
                td("Team", f'{s.tlink(st["f"], sy)}{note}<span class="sub blk">Regular season: {e(finish_text(t))}</span>', t["name"]),
                td("Final NBA finish", finish_cell(s, t, up), t["rnk"]),
                td("Team W–L", rec_cell(t["w"], t["l"]), fval(A.pct(t["w"], t["l"]))),
                td("Playoffs", playoff_text(s, t, up), depth),
                td("His games", f'{st["g"]} of {tg}', st["g"], "mono"),
                td("With him", rec_cell(st["w"], st["l"]), fval(A.pct(st["w"], st["l"]))),
                td("Without him", rec_cell(st["ow"], st["ol"])
                   + (f'<span class="sub blk">span: {wl(st.get("sw", 0), st.get("sl", 0))}, gap {pp(sgap)}</span>'
                      if st["ow"] + st["ol"] else ""),
                   fval(A.pct(st["ow"], st["ol"]))),
                td("Gap", pp(gap), fval(gap), f"mono {cls_gap(gap)}"),
            ]) + "</tr>")
            if modern and rm:
                lineup.append("<tr>" + "".join([
                    td("Season", season_label(sy), sy, "mono"), td("Team", s.tlink(st["f"], sy), t["name"]),
                    td("On/off per 100", fnum(oo) if oo is not None else "N/A", fval(oo), f"mono {cls_gap(oo)}"),
                    td("Started", rec_cell(*rm["st"]), sum(rm["st"])),
                    td("Off the bench", rec_cell(*rm["bn"]), sum(rm["bn"])),
                    td("Close games", rec_cell(*rm["cl"]), fval(A.pct(*rm["cl"])))]) + "</tr>")
    return rows, lineup


SEASON_HEADS = [th("Season", sort="descending"), th("Team", "text"), th("Final NBA finish", first="ascending"),
                th("Team W\u2013L"), th("Playoffs"), th("His games"), th("With him"), th("Without him"), th("Gap")]
LINEUP_HEADS = [th("Season", sort="descending"), th("Team", "text"), th("On/off per 100"), th("Started"),
                th("Off the bench"), th("Close games")]


# --- career cards -------------------------------------------------------------------------------
def rank_txt(s, board, pid):
    r = s.ranks[board].get(pid)
    n = s.rank_n[board]
    if not r:
        need = {"average-finish": "5+ seasons", "gap-career": "200+ games played and 50+ missed"}.get(board, "")
        return f'<span class="rk">Not ranked{(": needs " + need) if need else ""}</span>'
    return (f'<span class="rk">#{r[0]:,}{" (tied)" if r[1] else ""} of {n:,}</span>')


def summary_cards(s, pid, up):
    sm = A.summary(s.d, pid)
    if not sm["seasons"]:
        return '<p class="empty">No completed seasons.</p>'
    w, l = sm["w"], sm["l"]
    slug = s.ids[pid]["slug"]
    adj = s.adj_avg(pid)

    def href(board):
        return f"{up}lists/{board}.html?hl={e(slug)}#p-{e(slug)}"

    deep = sm["deepest"]
    if deep:
        t = deep[0]
        deep_txt = A.PO_LABEL[t["po"]]
        deep_sub = f'Best: {season_label(t["s"])}, {e(t["name"])}'
    else:
        deep_txt, deep_sub = "Missed the playoffs", "in every season"
    gap = sm["gap"]
    sgap = (A.pct(w, l) - A.pct(sm["sw"], sm["sl"])) if (w + l) and (sm["sw"] + sm["sl"]) else None
    hero = [
        ("career-wins", "Career record in his games", f'{w}{EN}{l}', f"{pct1(A.pct(w, l))} of {w + l:,} games"),
        ("wins-minus-losses", "Wins minus losses", signed(w - l), f"{w:,} wins, {l:,} losses"),
        ("average-finish", "Average final NBA finish", f'{sm["rnk"]:.1f}',
         f"over {sm['seasons']} seasons; league-size-adjusted {adj:.3f} (0 = champion)"),
    ]
    small = [
        ("winning-seasons", "Winning seasons", str(sm["winning"]), f'of {sm["seasons"]} ({pct1(sm["winning"] / sm["seasons"])})'),
        ("playoff-trips", "Playoff trips", str(sm["trips"]), f'of {sm["seasons"]} ({pct1(sm["trips"] / sm["seasons"])})'),
        ("deepest-run", "Deepest playoff run", deep_txt, deep_sub),
        ("titles", "Titles", str(sm["titles"]), ", ".join(season_label(y) for y in sm["titleYears"]) or "None"),
        ("gap-career", "With vs without", pp(gap),
         f'{wl(w, l)} with, {wl(sm["ow"], sm["ol"])} without (team-season window); '
         f'span: {wl(sm["sw"], sm["sl"])} without, {pp(sgap)}'),
    ]

    def card(c, cls):
        board, lab, big, sub = c
        return (f'<a class="card {cls}" href="{href(board)}"><span class="lbl">{e(lab)}</span>'
                f'<span class="big{" mono" if any(ch.isdigit() for ch in big) else ""}">{e(big)}</span>'
                f'<span class="sub">{sub}</span>{rank_txt(s, board, pid)}</a>')
    return ('<div class="cards hero3">' + "".join(card(c, "hero") for c in hero) + "</div>"
            + '<div class="cards small5">' + "".join(card(c, "") for c in small) + "</div>")


# --- lead, chart, latest seasons ------------------------------------------------------------------
def player_facts(s, pid):
    sm = A.summary(s.d, pid)
    mains = s.d.season_main(pid)
    teams = {st["f"] for st in s.d.stints(pid)}
    best = None
    finals = []
    title_team = None
    pts = []
    prev = None
    jump = None
    for sy, (main, end, lst) in sorted(mains.items()):
        t = s.d.team(main["f"], sy)
        size = s.sizes[sy]
        if best is None or t["rnk"] < best["rnk"] or (t["rnk"] == best["rnk"]):
            best = {"rnk": t["rnk"], "size": size, "sy": sy, "team": t["name"]}
        pr = A.playoff_result(s.d, end, lst)
        po = pr[0]["po"] if pr else ""
        if po == "Finalist":
            finals.append(sy)
        if po == "Champion" and title_team is None:
            title_team = pr[0]["name"]
        if prev and prev[0] == sy - 1 and prev[1] == main["f"]:
            gain = prev[2] - t["rnk"]
            if jump is None or gain > jump["gain"]:
                jump = {"gain": gain, "team": t["name"], "a": prev[2], "b": t["rnk"], "sy": sy}
        prev = (sy, main["f"], t["rnk"])
        kind = {"Champion": "title", "Finalist": "finals", "Conf Finalist": "playoffs", "Conf Semis": "playoffs",
                "First Round": "playoffs"}.get(po, "missed")
        pts.append({"sy": sy, "rnk": t["rnk"], "size": size, "kind": kind, "f": main["f"],
                    "label": f"{season_label(sy)}: {t['name']}, #{t['rnk']} of {size}, {A.PO_LABEL[po] if po else 'missed the playoffs'}"})
    return {"seasons": sm["seasons"], "teams": len(teams), "w": sm["w"], "l": sm["l"], "titles": sm["titles"],
            "title_years": sm["titleYears"], "title_team": title_team, "finals": finals, "trips": sm["trips"],
            "best": best, "avg": sm["rnk"] or 0, "jump": jump}, pts


def latest_seasons(s, pid, up, pts):
    if not pts:
        return ""
    items = []
    for p in sorted(pts, key=lambda p: -p["sy"])[:3]:
        t = s.d.team(p["f"], p["sy"])
        items.append(f'<li><a class="mono" href="{board_link(up, p["sy"], p["f"])}">{season_label(p["sy"])}</a> '
                     f'{s.tlink(p["f"], p["sy"])}: <strong class="mono">#{p["rnk"]} of {p["size"]}</strong>, '
                     f'<span class="mono">{t["w"]}{EN}{t["l"]}</span>, {playoff_text(s, t, up)}</li>')
    return '<ul class="latest">' + "".join(items) + "</ul>"


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
                rows.append((a, "<tr>" + "".join([
                    td("Move", "Arrived", 0), td("Team", s.tlink(f, a), first["name"]),
                    td("Season", season_label(a), a, "mono"),
                    td("Before", f'{season_label(a - 1)}: {wl(prev["w"], prev["l"])} <span class="sub">{A.per82(prev):.1f} per 82</span>', fval(A.per82(prev)), "mono"),
                    td("After", f'{season_label(a)}: {wl(first["w"], first["l"])} <span class="sub">{A.per82(first):.1f} per 82</span>', fval(A.per82(first)), "mono"),
                    td("Change", f"{fnum(ch)} wins", fval(ch), f"mono {cls_gap(ch)}")]) + "</tr>"))
            if last and nxt and b + 1 <= LAST_COMPLETE:
                ch = A.per82(nxt) - A.per82(last)
                rows.append((b + 0.5, "<tr>" + "".join([
                    td("Move", "Left", 1), td("Team", s.tlink(f, b), last["name"]),
                    td("Season", season_label(b + 1), b + 1, "mono"),
                    td("Before", f'{season_label(b)}: {wl(last["w"], last["l"])} <span class="sub">{A.per82(last):.1f} per 82</span>', fval(A.per82(last)), "mono"),
                    td("After", f'{season_label(b + 1)}: {wl(nxt["w"], nxt["l"])} <span class="sub">{A.per82(nxt):.1f} per 82</span>', fval(A.per82(nxt)), "mono"),
                    td("Change", f"{fnum(ch)} wins", fval(ch), f"mono {cls_gap(ch)}")]) + "</tr>"))
    if not rows:
        return ""
    rows.sort(key=lambda x: -x[0])
    heads = [th("Move", "number"), th("Team", "text"), th("Season", sort="descending"), th("Before"), th("After"), th("Change")]
    return ('<section><h2 id="cap-arr">Arrival and departure</h2>'
            '<p class="note">Team wins per 82 games the season before he arrived vs his first season there, and his last '
            'season vs the season after he left. Per 82 so short seasons compare fairly. These are team records, not a '
            'measure of what he did.</p>' + sortable("cap-arr", "", heads, [r for _, r in rows]) + "</section>")


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
            rows.append("<tr>" + "".join([
                td("Season", season_label(sy), sy, "mono"), td("Team", s.tlink(st["f"], sy), st["f"]),
                td("First and last game", f'{e(nice_date(st["first"]))} to {e(nice_date(st["last"]))}',
                   int(st["first"].replace("-", ""))),
                td("Before he arrived", rec_cell(*b), fval(A.pct(*b))),
                td("While he was there", rec_cell(*during), fval(A.pct(*during))),
                td("After he left", rec_cell(*a), fval(A.pct(*a))),
                td("His games", str(st["g"]), st["g"], "mono")]) + "</tr>")
    if not rows:
        return ""
    heads = [th("Season", sort="descending"), th("Team", "text"), th("First and last game"), th("Before he arrived"),
             th("While he was there"), th("After he left"), th("His games")]
    return ('<section><h2 id="cap-trades">Seasons split between teams</h2>'
            "<p class=\"note\">Each team's record before his first game for it, inside his window (games with and without "
            "him) and after his last game, in the seasons he played for two or more teams.</p>"
            + sortable("cap-trades", "", heads, rows) + "</section>")


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
<span class="mono">{w}{EN}{g - w}</span> <span class="sub">{pct1(w / g)}</span></li>""")
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
        if not t:
            continue
        gap = (A.pct(po["w"], po["l"]) - A.pct(po["ow"], po["ol"])) if po["ow"] + po["ol"] and po["g"] else None
        rows.append("<tr>" + "".join([
            td("Season", season_label(st["s"]), st["s"], "mono"), td("Team", s.tlink(st["f"], st["s"]), t["name"]),
            td("Result", playoff_text(s, t, up), A.PO_DEPTH[t["po"]]),
            td("Final NBA finish", finish_cell(s, t, up), t["rnk"]),
            td("His games", f'{po["g"]} of {po["g"] + po["ow"] + po["ol"]}', po["g"], "mono"),
            td("With him", rec_cell(po["w"], po["l"]), fval(A.pct(po["w"], po["l"]))),
            td("Without him", rec_cell(po["ow"], po["ol"]), fval(A.pct(po["ow"], po["ol"]))),
            td("Gap", pp(gap), fval(gap), f"mono {cls_gap(gap)}")]) + "</tr>")
    if not rows:
        return ""
    heads = [th("Season", sort="descending"), th("Team", "text"), th("Result"), th("Final NBA finish", first="ascending"),
             th("His games"), th("With him"), th("Without him"), th("Gap")]
    return ('<section><h2 id="cap-po">Playoffs, with and without him</h2>' + sortable("cap-po", "", heads, rows) + "</section>")


def current_block(s, pid, up):
    if not s.cur or pid not in s.cur["players"]:
        return ""
    rows = []
    for st in s.cur["players"][pid]:
        oo = A.onoff({"on": st["on"], "off": st["off"]})
        gap = (A.pct(st["w"], st["l"]) - A.pct(st["ow"], st["ol"])) if st["ow"] + st["ol"] else None
        rows.append("<tr>" + "".join([
            td("Team", s.tlink(st["f"], CURRENT_SEASON)), td("His games", str(st["g"]), None, "mono"),
            td("With him", rec_cell(st["w"], st["l"])), td("Without him", rec_cell(st["ow"], st["ol"])),
            td("Gap", pp(gap), None, f"mono {cls_gap(gap)}"), td("On/off per 100", fnum(oo), None, f"mono {cls_gap(oo)}"),
            td("Started / bench", f"{wl2(st['st'])} / {wl2(st['bn'])}", None, "mono"),
            td("Close games", wl2(st["cl"]), None, "mono")]) + "</tr>")
    return (f"""<section><h2>{season_label(CURRENT_SEASON)} so far</h2>
<p class="note">Games through {e(nice_date(s.cur['through']))}, the last game in the nightly data. Not included in the career numbers (completed seasons through {season_label(LAST_COMPLETE)}) until the season ends. No final finish until the season ends.</p>
<table class="tt"><thead><tr><th scope="col">Team</th><th scope="col">His games</th><th scope="col">With him</th><th scope="col">Without him</th><th scope="col">Gap</th><th scope="col">On/off per 100</th><th scope="col">Started / bench</th><th scope="col">Close games</th></tr></thead><tbody>"""
            + "".join(rows) + "</tbody></table></section>")


def player_page(s, pid):
    up = "../"
    v = s.ids[pid]
    name = v["name"]
    has_hist = s.has_hist(pid)
    rel = f"player/{v['slug']}.html"
    facts = pts = None
    if has_hist:
        sm = A.summary(s.d, pid)
        yrs = sorted({st["s"] for st in s.d.stints(pid)})
        span = f"{season_label(yrs[0])} to {season_label(yrs[-1])}" if yrs else ""
        facts, pts = player_facts(s, pid)
        desc = (f"{name}'s teams went {sm['w']}{EN}{sm['l']} ({pct1(A.pct(sm['w'], sm['l']))}) in his games, {span}: "
                f"{sm['winning']} winning seasons, {sm['trips']} playoff trips, {sm['titles']} titles, average final "
                f"finish {sm['rnk']:.1f}. Every season ranked, playoffs, with and without him.")
    else:
        sm = None
        span = season_label(CURRENT_SEASON)
        c = s.cur["players"][pid]
        w, l = sum(x["w"] for x in c), sum(x["l"] for x in c)
        ow, ol = sum(x["ow"] for x in c), sum(x["ol"] for x in c)
        desc = (f"{name}'s teams are {w}{EN}{l} with him and {wl(ow, ol)} without him in {span}, "
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
        rule, sents = LEADS.lead(facts)
        s.lead_rules[rule] = s.lead_rules.get(rule, 0) + 1
        for p in pts:
            p["href"] = board_link(up, p["sy"], p["f"])
        best = facts["best"]
        nxt = (f'<a class="next" href="{board_link(up, best["sy"], next(p["f"] for p in pts if p["sy"] == best["sy"]))}">'
               f'All {best["size"]} teams ranked in {season_label(best["sy"])}, his best finish (#{best["rnk"]})</a>')
        chart = CH.finish_chart(pts, "chart-t")
        parts.append(f"""<p class="lead">{' '.join(e(x) for x in sents)}</p>
<div class="hero">
<section class="tl"><h2 id="chart-t">Final NBA finish, season by season</h2>
{chart}
<p class="note legend"><span class="key title"></span>Title <span class="key finals"></span>Finals <span class="key playoffs"></span>Other playoffs <span class="key missed"></span>Missed. #1 = champion; the dashed line is last place that season. Each point opens that season's final standings.</p>
{nxt}</section>
<section class="sum"><h2>Career</h2>{summary_cards(s, pid, up)}
<p class="note">Career: regular seasons {season_label(1947)} through {season_label(LAST_COMPLETE)}.{(' ' + season_label(CURRENT_SEASON) + ' (games through ' + e(nice_date(s.cur['through'])) + ') is shown separately and is not in these totals.') if s.cur else ''} Each card opens its leaderboard with him highlighted. <a href="../how-we-count.html">How we count</a>.</p></section>
</div>""")
        parts.append(f'<section><h2>Latest completed seasons</h2>{latest_seasons(s, pid, up, pts)}</section>')
    parts.append(current_block(s, pid, up))
    if has_hist:
        rows, lineup = season_rows(s, pid, up)
        parts.append(f"""<section><h2 id="cap-seasons">Season by season</h2>
<p class="note">Newest first; every header sorts. Final NBA finish is the team's rank among all teams that season (#1 = champion) and opens that season's standings. "Without him" uses the team-season window; the span line counts only the games between his first and last game for the team.</p>
{sortable("cap-seasons", "", SEASON_HEADS, rows, "season")}</section>""")
        if lineup:
            parts.append(f"""<section><h2 id="cap-lineup">On/off, starts and close games</h2>
<p class="note">From the lineup data, {season_label(RAMIRO_FIRST)} on. On/off is net points per 100 possessions with him on the floor minus off, a different unit from the win-rate gaps. Started and off the bench are team records in those games; close games are those within 5 points in the last 5 minutes with him on the floor.</p>
{sortable("cap-lineup", "", LINEUP_HEADS, lineup)}</section>""")
        parts.append(playoff_table(s, pid, up))
        parts.append(arrival_departure(s, pid, up))
        parts.append(trades(s, pid, up))
        parts.append(duos(s, pid, up))
        b = s.badges.get(pid)
        if b:
            parts.append('<section><h2>Lists he is on</h2><ul class="badges">' + "".join(
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
        return (f'<p class="pop">{len(rows):,} players qualify; top {min(TOP_N, len(rows))} shown.</p>'
                + rows_html(s, items, up))

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
<p class="note">Regular season, 1946-47 through 2025-26. A player was on a team-season if he played at least one game for it; "Only team-seasons where he played 20+ games" drops the others before counting. The number next to each season is his games for that team. <a href="../how-we-count.html">How we count</a>.</p>
<p class="more">More lists: {' · '.join(f'<a href="{k}.html">{e(t)}</a>' for k, t, _, _ in LISTS if k != key)}</p>
<p class="more">Career boards: {' · '.join(f'<a href="{k}.html">{e(B.BOARDS[k]["h1"])}</a>' for k in B.BOARDS)}</p>"""
    pdesc = f"{title}: {desc} All-time, since 1976-77 and since 1996-97, with every player's team and games."
    return rel, page(rel, f"{title} | HoopsMatic", pdesc, body, up)


# ---------------------------------------------------------------------------
# Season boards: every team ranked by final NBA finish, one page per season
# ---------------------------------------------------------------------------
def season_page(s, sy):
    up = "../"
    lab = season_label(sy)
    rel = f"seasons/{lab}.html"
    ts = sorted((t for t in s.d.teams.values() if t["s"] == sy), key=lambda t: (t["rnk"], t["name"]))
    n = len(ts)
    cnt = defaultdict(int)
    for t in ts:
        cnt[t["rnk"]] += 1
    rows = []
    for t in ts:
        mates = s.roster.get((t["f"], sy), [])[:3]
        who = ", ".join(f'{s.plink(pid, up)} <span class="sub">{g} g</span>' for g, pid in mates if pid in s.ids)
        depth = A.PO_DEPTH[t["po"]] + (0.5 if t["po"] == "Play-In" else 0)
        rows.append(f'<tr id="t-{e(t["f"])}">' + "".join([
            td("Final NBA finish", f'<span class="mono">{"T-" if cnt[t["rnk"]] > 1 else ""}#{t["rnk"]} of {n}</span>', t["rnk"]),
            td("Team", s.tlink(t["f"], sy), t["name"]),
            td("W–L", f'<span class="mono">{t["w"]}{EN}{t["l"]}</span>', t["w"] - t["l"]),
            td("Win %", pct1(A.pct(t["w"], t["l"])), fval(A.pct(t["w"], t["l"])), "mono"),
            td("Playoffs", playoff_text(s, t, up), depth),
            td("Regular-season standing", e(finish_text(t)) + (' <span class="sub wrap">(worked out from records)</span>' if t.get("confPosComputed") else ""), None),
            td("Most games for this team", who or "N/A", None),
        ]) + "</tr>")
    heads = [th("Final NBA finish", sort="ascending", first="ascending"), th("Team", "text"), th("W–L"), th("Win %"),
             th("Playoffs"), '<th scope="col">Regular-season standing</th>', '<th scope="col">Most games for this team</th>']
    champ = ts[0]
    runner = next((t for t in ts if t["po"] == "Finalist"), None)
    nav = []
    if s.d.team(champ["f"], sy - 1) or any(t["s"] == sy - 1 for t in s.d.teams.values()):
        if sy - 1 >= 1947:
            nav.append(f'<a href="{season_label(sy - 1)}.html">{season_label(sy - 1)}</a>')
    nav.append('<a href="index.html">All seasons</a>')
    if sy + 1 <= LAST_COMPLETE:
        nav.append(f'<a href="{season_label(sy + 1)}.html">{season_label(sy + 1)}</a>')
    sub = (f"All {n} teams of the {lab} season ranked by final NBA finish: the champion first"
           + (f", the runner-up second" if runner else "") + ", then by playoff round reached and regular-season win %. "
           "Teams with the same round and win % share a rank.")
    body = f"""<header><h1>{lab} NBA final standings</h1><p class="subtitle">{e(sub)}</p></header>
<p class="seasonnav">{' · '.join(nav)}</p>
<p class="lead">The {e(champ['name'])} finished #1 ({champ['w']}{EN}{champ['l']}){(', the ' + e(runner['name']) + ' #2 (' + str(runner['w']) + EN + str(runner['l']) + ')') if runner else ''}.</p>
<section><h2 id="cap-season">All {n} teams</h2>
<p class="note">Final NBA finish is the RNK of our standings table, the same number every player page shows. Regular-season standing is the conference and division place, a different measure. A highlighted row is the team you came from.</p>
{sortable("cap-season", "", heads, rows, "board")}</section>
<p class="note">League size this season: {n} teams. <a href="../how-we-count.html">How we count</a>.</p>
"""
    desc = (f"Every team in {lab} ranked by final NBA finish: {champ['name']} #1"
            + (f", {runner['name']} #2" if runner else "") + f", all {n} teams with records, playoff series and each team's most-used players.")
    return rel, page(rel, f"{lab} NBA final standings: all {n} teams ranked | HoopsMatic", desc, body, up)


def seasons_index(s):
    up = "../"
    rel = "seasons/index.html"
    items = []
    for sy in range(LAST_COMPLETE, 1946, -1):
        ts = [t for t in s.d.teams.values() if t["s"] == sy]
        if not ts:
            continue
        champ = min(ts, key=lambda t: t["rnk"])
        items.append(f'<li><a href="{season_label(sy)}.html"><strong class="mono">{season_label(sy)}</strong></a> '
                     f'<span class="det">{len(ts)} teams. #1 {e(champ["name"])} ({champ["w"]}{EN}{champ["l"]})</span></li>')
    body = f"""<header><h1>NBA final standings, every season</h1>
<p class="subtitle">Every season from {season_label(1947)} to {season_label(LAST_COMPLETE)}, all teams ranked by final NBA finish (champion first, then playoff round, then win %).</p></header>
<ul class="lists seasons">{''.join(items)}</ul>"""
    return rel, page(rel, "NBA final standings by season, 1946-47 to 2025-26 | HoopsMatic",
                     "Every NBA season since 1946-47 with all teams ranked by final finish: champion, runner-up, "
                     "playoff rounds and win %, with each team's records and most-used players.", body, up)


# ---------------------------------------------------------------------------
# Career leaderboards (the eight career cards), filterable in the browser
# ---------------------------------------------------------------------------
def board_cell(col, m):
    """(sort value, text): must match cell() in assets/boards.js."""
    if col == "w":
        return m["w"], f"{m['w']:,}"
    if col == "l":
        return m["l"], f"{m['l']:,}"
    if col == "pct":
        return m["pct"], pct1(m["pct"])
    if col == "gp":
        return m["gp"], f"{m['gp']:,}"
    if col == "gm":
        return m["gm"], f"{m['gm']:,}"
    if col == "wl":
        return m["wl"], signed(m["wl"])
    if col == "rec":
        return m["w"], wl(m["w"], m["l"])
    if col in ("winning", "seasons", "trips", "titles", "deepn"):
        return m[col], str(m[col])
    if col in ("wshare", "tshare"):
        return m[col], pct1(m[col])
    if col == "deep":
        return m["deep"], B.DEPTH_LABEL[m["deep"]]
    if col == "years":
        return len(m["years"]), ", ".join(season_label(y) for y in m["years"]) or "N/A"
    if col == "avg":
        return m["avg"], f"{m['avg']:.1f}"
    if col == "adj":
        return m["adj"], f"{m['adj']:.3f}"
    if col == "gap":
        return m["gap"], pp(m["gap"])
    if col == "with":
        return m["pct"], f"{wl(m['w'], m['l'])}, {pct1(m['pct'])}"
    if col == "without":
        p = (m["ow"] / m["gm"]) if m["gm"] else None
        return p, f"{wl(m['ow'], m['ol'])}, {pct1(p)}"
    raise KeyError(col)


def board_row_html(s, r, tied, m, cols, up):
    cells = [f'<td data-l="Rank" class="mono" data-value="{r}">{"T-" if tied else ""}{r}</td>',
             f'<td data-l="Player">{s.plink(m["pid"], up)}</td>']
    for c in cols:
        v, txt = board_cell(c, m)
        dv = "" if v is None else f' data-value="{e(v)}"'
        cells.append(f'<td data-l="{e(B.COL_LABEL[c])}" class="mono"{dv}>{e(txt)}</td>')
    return f'<tr id="p-{e(m["slug"])}">' + "".join(cells) + "</tr>"


def board_form(s, key):
    dfn = B.BOARDS[key]
    seasons = list(range(1947, LAST_COMPLETE + 1))
    so = "".join(f'<option value="{sy}">{season_label(sy)}</option>' for sy in seasons)
    latest = {}
    for t in s.d.teams.values():
        if t["f"] not in latest or t["s"] > latest[t["f"]][0]:
            latest[t["f"]] = (t["s"], t["name"])
    teams = "".join(f'<option value="{e(f)}">{e(n)}</option>' for f, (_, n) in sorted(latest.items(), key=lambda x: x[1][1]))
    sorts = "".join(f'<option value="{k}">{e(v[0])}</option>' for k, v in dfn["sorts"].items())
    extra = ""
    if any("ms" in v[2] for v in dfn["sorts"].values()) or key in ("winning-seasons", "playoff-trips"):
        extra += '<label>Min seasons<input name="ms" type="number" min="1" inputmode="numeric" placeholder="default"></label>'
    if key == "gap-career":
        extra += ('<label>Min games played<input name="mp" type="number" min="1" inputmode="numeric" placeholder="200"></label>'
                  '<label>Min games missed<input name="mm" type="number" min="1" inputmode="numeric" placeholder="50"></label>')
    return f"""<form id="board-form" class="filters" action="{key}.html" method="get">
<label>Rank by<select name="sort">{sorts}</select></label>
<label>From<select name="from"><option value="">{season_label(1947)}</option>{so}</select></label>
<label>To<select name="to"><option value="">{season_label(LAST_COMPLETE)}</option>{so}</select></label>
<label>One season<select name="season"><option value="">Any</option>{so}</select></label>
<label>Team<select name="team"><option value="">Any team</option>{teams}</select></label>
<fieldset><legend>Games in a team-season</legend><select data-preset="ts" name="tsp" aria-label="Preset"><option value="">Preset</option><option value="1">Any</option><option value="20">20+</option><option value="41">41+</option><option value="60">60+</option></select><input name="ts" type="number" min="1" inputmode="numeric" placeholder="1" aria-label="Minimum games in a team-season"></fieldset>
<fieldset><legend>Career games</legend><select data-preset="cg" name="cgp" aria-label="Preset"><option value="">Preset</option><option value="1">Any</option><option value="100">100+</option><option value="400">400+</option><option value="1000">1,000+</option></select><input name="cg" type="number" min="1" inputmode="numeric" placeholder="1" aria-label="Minimum career games"></fieldset>
<label>All-Stars<select name="as"><option value="">Everyone</option><option value="ever">Ever an All-Star</option><option value="season">All-Star in the selected season</option></select></label>
<label>Status<select name="st"><option value="">Active and retired</option><option value="active">Active ({season_label(CURRENT_SEASON)})</option><option value="retired">Retired</option></select></label>
{extra}
<button type="submit">Apply</button> <a href="{key}.html">Reset</a>
</form>
<p class="note">Scope: "Games in a team-season" drops the team-seasons where he played fewer games, before anything is counted. "Career games" sets who qualifies, after. "One season" and "All-Star in the selected season" work together. Filters run in your browser; the URL keeps them, so a filtered view can be shared.</p>"""


def career_board_page(s, key):
    up = "../"
    rel = f"lists/{key}.html"
    dfn = B.BOARDS[key]
    ranked, sort, mins = s.board_default[key]
    cols = dfn["cols"]
    heads = ['<th scope="col">Rank</th>', '<th scope="col">Player</th>']
    for c in cols:
        if c in dfn["sorts"]:
            a = ' aria-sort="' + ("ascending" if dfn["sorts"][c][1] == "asc" else "descending") + '"' if c == sort else ""
            heads.append(f'<th scope="col" data-sort="{c}"{a}><button type="button">{e(B.COL_LABEL[c])}</button></th>')
        else:
            heads.append(f'<th scope="col">{e(B.COL_LABEL[c])}</th>')
    rows = [board_row_html(s, r, tied, m, cols, up) for r, tied, m in ranked[:100]]
    defjs = json.dumps({"sorts": {k: list(v) for k, v in dfn["sorts"].items()}, "cols": cols,
                        "labels": B.COL_LABEL}, ensure_ascii=False, separators=(",", ":"))
    mtxt = []
    if mins.get("cg", 1) > 1:
        mtxt.append(f"{mins['cg']:,}+ career games")
    if mins.get("ms"):
        mtxt.append(f"{mins['ms']}+ seasons")
    if mins.get("mp"):
        mtxt.append(f"{mins['mp']}+ games played")
    if mins.get("mm"):
        mtxt.append(f"{mins['mm']}+ games missed")
    pop = (f"{len(ranked):,} players qualify" + (f" ({', '.join(mtxt)})" if mtxt else "")
           + f". Ranked by {dfn["sorts"][sort][0]}; equal values share a rank (T-).")
    others = " · ".join(f'<a href="{k}.html">{e(B.BOARDS[k]["h1"])}</a>' for k in B.BOARDS if k != key)
    body = f"""<header><h1>{e(dfn['h1'])}</h1><p class="subtitle">{e(dfn['desc'])}</p></header>
{board_form(s, key)}
<p id="board-pop" class="pop" aria-live="polite">{e(pop)}</p>
<div class="tblwrap"><table id="board" class="tt board" data-board="{key}" data-up="{up}" data-def="{e(defjs)}" aria-labelledby="board-pop">
<thead><tr>{''.join(heads)}</tr></thead><tbody>{''.join(rows)}</tbody></table>
<p id="board-status" class="vh" role="status"></p></div>
<p><button type="button" id="board-more" class="more-btn"{' hidden' if len(ranked) <= 100 else ''}>Show 100 more</button></p>
<p class="note">Regular seasons {season_label(1947)} through {season_label(LAST_COMPLETE)}, games he played. One team per season for season counts (the team he played the most games for); a playoff trip or title also counts the team he finished the season with. <a href="../how-we-count.html">How we count</a>.</p>
<p class="more">Other career boards: {others}</p>
<script src="../assets/boards.js" defer></script>"""
    desc = dfn["desc"]
    return rel, page(rel, f"{dfn['title']} | HoopsMatic", desc, body, up)


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
<section><h2>Career boards</h2><ul class="lists">{''.join(f'<li><a href="lists/{k}.html"><strong>{e(B.BOARDS[k]["h1"])}</strong></a><span class="det">{e(B.BOARDS[k]["desc"])}</span></li>' for k in B.BOARDS)}
<li><a href="seasons/index.html"><strong>Final standings, every season</strong></a><span class="det">All teams ranked by final NBA finish, {season_label(1947)} to {season_label(LAST_COMPLETE)}.</span></li></ul></section>
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
    for d in ("", "player", "lists", "players", "seasons"):
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
    if not args.current:
        for key in B.BOARDS:
            write(*career_board_page(s, key))
        for sy in range(1947, LAST_COMPLETE + 1):
            write(*season_page(s, sy))
        write(*seasons_index(s))
    write("assets/board.json", json.dumps(s.board_data, ensure_ascii=False, separators=(",", ":")))
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
    if s.lead_rules:
        print("player leads by rule:", dict(sorted(s.lead_rules.items())))


if __name__ == "__main__":
    main()

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
                    dump_json, franchise_name, load_json, season_label)

BASE = "https://hoopsmatic.com/team-success/"
CM_TEAM = "https://hoopsmatic.com/nba-career-map/team/{}.html"
CM_PLAYER = "https://hoopsmatic.com/nba-career-map/player/{}.html"
TERMS = "https://hoopsmatic.com/terms"
# Social cards drawn by hoopsmatic-og-card (live Nov 2026). Only patterns that answered 200 image/png
# when checked are used; everything else keeps assets/og-team-success.png.
OG = "https://hoopsmatic.com/og/team-success/"
OG_LISTS = {"average-finish", "career-wins", "deepest-run", "gap-career", "no-allstar-teammate", "playoff-trips",
            "titles", "winning-seasons", "wins-minus-losses"}
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
CURRENT_NAMES = {"Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets", "Chicago Bulls",
                 "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets", "Detroit Pistons", "Golden State Warriors",
                 "Houston Rockets", "Indiana Pacers", "LA Clippers", "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
                 "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks",
                 "Oklahoma City Thunder", "Orlando Magic", "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
                 "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors", "Utah Jazz", "Washington Wizards"}
HIST_LOGO = {"Charlotte Bobcats": "charlotte-bobcats", "New Orleans Hornets": "new-orleans-hornets",
             "New Jersey Nets": "new-jersey-nets", "Seattle SuperSonics": "seattle-supersonics",
             "San Diego Clippers": "san-diego-clippers", "Vancouver Grizzlies": "vancouver-grizzlies",
             "Washington Bullets": "washington-bullets"}
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
    if rel.endswith(".html") and "/" not in rel:
        # root-level pages: team logos are drawn with the ../ prefix of the subfolders
        text = text.replace('src="../assets/logos/', 'src="assets/logos/')
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
    """A win-rate gap as a signed number of points: +26.0 (the difference of two percentages)."""
    if g is None:
        return "N/A"
    v = round(100 * g, 1)
    if v == 0:
        return "0.0"
    return ("+" if v > 0 else MINUS) + f"{abs(v):.1f}"


def pts_txt(g):
    """The same gap in words: '26.0 points higher', '3.1 points lower', 'even'."""
    if g is None:
        return "N/A"
    v = round(100 * g, 1)
    if v == 0:
        return "even"
    return f"{abs(v):.1f} points {'higher' if v > 0 else 'lower'}"


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


def eq30(adj):
    """League-size-adjusted finish (0 = champion, 1 = last) as a 30-team equivalent: 1 + adj x 29."""
    return 1 + 29 * adj


def cls_gap(g):
    if g is None:
        return "flat"
    return "up" if g > 0.0005 else ("down" if g < -0.0005 else "flat")


TWO_WORD_NICK = ("Trail Blazers", "Red Skins")


def city_of(name):
    """'Cleveland Cavaliers' -> 'Cleveland'; 'Kansas City-Omaha Kings' -> 'Kansas City-Omaha'.
    Los Angeles is always 'LA Lakers' / 'LA Clippers' (two teams share the city)."""
    if name in ("Los Angeles Lakers",):
        return "LA Lakers"
    if name in ("Los Angeles Clippers", "LA Clippers"):
        return "LA Clippers"
    for nick in TWO_WORD_NICK:
        if name.endswith(" " + nick):
            return name[:-len(nick) - 1]
    return name.rsplit(" ", 1)[0] if " " in name else name


# ---------------------------------------------------------------------------
# Site context
# ---------------------------------------------------------------------------
class Site:
    def __init__(self):
        self.d = A.Data(live=True)
        self.through = self.d.through
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
        # tables and cards name a team by its city that season; two teams in one city that season
        # (1976-77 New York Knicks and New York Nets) keep city + nickname for both
        per = defaultdict(int)
        for t in self.d.teams.values():
            per[(t["s"], city_of(t["name"]))] += 1
        self.cities = {(t["s"], t["name"]): (t["name"] if per[(t["s"], city_of(t["name"]))] > 1 else city_of(t["name"]))
                       for t in self.d.teams.values()}
        # career leaderboards: one compact data set, default ranks for the career cards
        self.help = load_json(os.path.join(DATA, "help.json"), {"season": {}, "avg": {}, "peers": {}})
        self.partial_years = set(self.help.get("missing_years", []))
        self.board_data = B.compact(self.d, self.cur, self.help, self.partial_years)
        self.ranks, self.rank_n, self.board_default = {}, {}, {}
        for key in B.BOARDS:
            ranked, sort, mins = B.compute(self.board_data, key)
            self.board_default[key] = (ranked, sort, mins)
            self.ranks[key] = {m["pid"]: (r, tied) for r, tied, m in ranked}
            self.rank_n[key] = len(ranked)
        self.lead_rules = {}
        self.opp_take = {}
        pool = sorted((a["help"], pid) for pid, a in self.help["avg"].items() if a["g"] >= 300)
        self.help_rank = {}
        for i, (v, pid) in enumerate(sorted(pool, key=lambda x: -x[0])):
            self.help_rank[pid] = (i + 1, len(pool))
        self.avg_rnk = {}
        for pid in self.help["avg"]:
            if pid in self.d.players:
                sm = A.summary(self.d, pid)
                if sm["rnk"]:
                    self.avg_rnk[pid] = sm["rnk"]
        self.compare_pages = set()
        for pid, lst in self.help["peers"].items():
            for q, dist in lst:
                if pid in self.ids and q in self.ids:
                    self.compare_pages.add(compare_rel(self.ids[pid]["slug"], self.ids[q]["slug"]))
        self.pgames = None
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

    def city(self, f, sy, name=None):
        """The name tables and cards show: the team's city that season (see city_of)."""
        t = self.d.team(f, sy)
        nm = name or (t["name"] if t else None) or franchise_name(f, sy) or f
        return self.cities.get((sy, nm)) or city_of(nm)

    def tlink(self, f, sy, name=None, full=False):
        """Logo + name on one line. Tables and cards show the city (full=False); headings and prose
        keep the full name. The full name is always the link's title."""
        t = self.d.team(f, sy)
        nm = name or (t["name"] if t else None)
        if not nm:
            nm = franchise_name(f, sy) or f
        lg = self.logo(f, sy, getattr(self, "_up", "../"), nm)
        shown = nm if full else self.city(f, sy, nm)
        if f in TEAM_SLUG:
            return f'<span class="tmn">{lg}<a href="{CM_TEAM.format(TEAM_SLUG[f])}" title="{e(nm)}">{e(shown)}</a></span>'
        return f'<span class="tmn">{lg}<span class="tn" title="{e(nm)}">{e(shown)}</span></span>'

    def logo(self, f, sy, up, name=None):
        """H2H rule (nba-head-to-head src/core.js logoKey): the current logo only when the team's name
        that season is the franchise's current name; a historical file for 8 exact old names; else none."""
        nm = name or ((self.d.team(f, sy) or {}).get("name")) or franchise_name(f, sy) or ""
        if f == "CHA" and nm == "Charlotte Hornets" and sy <= 2002:
            k = "h-charlotte-hornets-original"
        elif nm in HIST_LOGO:
            k = "h-" + HIST_LOGO[nm]
        elif nm in CURRENT_NAMES:
            k = "c-" + re.sub(r"[^a-z0-9]+", "-", nm.lower()).strip("-")
        else:
            return ""
        return f'<img class="lg" src="{up}assets/logos/{k}.svg" alt="" width="18" height="18" loading="lazy" decoding="async">'

    def pic(self, pid, up, size=""):
        v = self.ids.get(pid, {})
        hs = v.get("hs")
        cls = f"hs {size}".strip()
        if hs and os.path.exists(os.path.join(ROOT, "assets", "hs", hs)):
            return (f'<span class="{cls}"><img src="{up}assets/hs/{e(hs)}" alt="" width="160" height="160" '
                    f'loading="lazy" decoding="async"></span>')
        # H2H placeholder: the player's initials on the light grey disc
        nm = v.get("name") or ""
        w = [x for x in re.sub(r"\.", " ", nm).split() if x.lower().strip(",") not in ("jr", "sr", "ii", "iii", "iv", "v")]
        ini = (w[0][0] + (w[-1][0] if len(w) > 1 else "")).upper() if w else "?"
        return f'<span class="{cls} nohs" aria-hidden="true">{e(ini)}</span>'


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------
TD_RE = re.compile(r'(<td data-l="[^"]*"[^>]*>)(.*?)(</td>)', re.S)


def page(rel, title, desc, body, up, robots=None, og=None):
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
<link rel="canonical" href="{e(url)}">{('<meta name="robots" content="' + e(robots) + '">') if robots else ''}
<meta property="og:type" content="website">
<meta property="og:site_name" content="HoopsMatic">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(og or BASE + 'assets/og-team-success.png')}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(og or BASE + 'assets/og-team-success.png')}">
<link rel="preload" href="{up}assets/fonts/dm-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{up}assets/ts.css">
</head>
<body>
<div class="wrap">
<form class="finder top" role="search" data-mode="go" data-up="{up}" data-index="{up}assets/players.json" action="{up}players/a.html">
<label for="pf" class="vh">Find a player</label><input id="pf" type="search" autocomplete="off" placeholder="Find a player, e.g. Bill Russell">
<ul class="results"></ul></form>
{body}
<form class="finder bottom" role="search" data-mode="go" data-up="{up}" data-index="{up}assets/players.json" action="{up}players/a.html">
<label for="pf2">Find a player</label><input id="pf2" type="search" autocomplete="off" placeholder="Find a player, e.g. Bill Russell">
<ul class="results"></ul></form>
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


PO_SHORT = {"Champion": "Title", "Finalist": "Lost Finals", "Conf Finalist": "Lost conf finals",
            "Conf Semis": "Lost conf semis", "First Round": "Lost 1st round", "Play-In": "Lost in the play-in",
            "": "Missed the playoffs"}


def era_code(f, sy):
    """The abbreviation a team used that season (SEA, VAN, NJN...), from the franchise eras."""
    from common import ERAS
    for c, a, b, ff, n in ERAS:
        if ff == f and a <= sy <= b:
            return c
    return f


def playoff_short(s, t, up):
    """One short line: 'Title · 4–2 UTA' or 'Lost conf semis · 2–4 ORL' (logo + that season's code)."""
    po = t["po"]
    sr = None
    if po == "Champion" and t["series"]:
        sr = t["series"][-1]
    elif t.get("elim"):
        sr = t["elim"]
    if not sr:
        return e(PO_SHORT.get(po, po))
    o = sr["opp"]
    return (f'{e(PO_SHORT.get(po, po))} <span class="sub mono">{sr["w"]}{EN}{sr["l"]} '
            f'{s.logo(o, t["s"], up)}{e(era_code(o, t["s"]))}</span>')


def short_standing(t):
    if t.get("confPos") and t.get("conf"):
        return f'{t["confPos"]} {t["conf"]}'
    return ""


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


CELL_RE = re.compile(r"<td\b[^>]*>.*?</td>", re.S)
ROW_RE = re.compile(r"(<tr\b[^>]*>)(.*)(</tr>)$", re.S)


def cell_text(c):
    return html.unescape(re.sub(r"<[^>]+>", "", c)).strip()


def na_columns(heads, rows):
    """Indexes of the columns whose every cell reads N/A (nothing to show)."""
    parsed = []
    for r in rows:
        m = ROW_RE.match(r)
        if not m:
            return []
        parsed.append(CELL_RE.findall(m.group(2)))
    if not parsed or any(len(c) != len(heads) for c in parsed):
        return []
    return [i for i in range(len(heads)) if all(cell_text(c[i]) == "N/A" for c in parsed)]


def drop_columns(heads, rows, drop):
    if not drop:
        return heads, rows
    out = []
    for r in rows:
        m = ROW_RE.match(r)
        cells = CELL_RE.findall(m.group(2))
        out.append(m.group(1) + "".join(c for i, c in enumerate(cells) if i not in drop) + m.group(3))
    return [h for i, h in enumerate(heads) if i not in drop], out


def sortable(cap_id, caption, heads, rows, extra_cls=""):
    # a column with nothing but N/A is left out (the opponents table is redrawn by opp.js with
    # every column, so it keeps them)
    if "opp" not in extra_cls.split():
        heads, rows = drop_columns(heads, rows, na_columns(heads, rows))
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
    # tint the best and the worst final finish (rank relative to league size; ties: the latest)
    fins = [(s.d.team(m["f"], sy)["rnk"] / s.sizes[sy], sy, s.d.team(m["f"], sy)["rnk"]) for sy, m in mains.items()]
    best_fin = (min(fins, key=lambda x: (x[0], -x[1]))[2], min(fins, key=lambda x: (x[0], -x[1]))[1]) if len(fins) > 1 else None
    worst_fin = (max(fins, key=lambda x: (x[0], x[1]))[2], max(fins, key=lambda x: (x[0], x[1]))[1]) if len(fins) > 1 else None
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
                drives = " · summary" if mains.get(sy) is st else ""
                note = (f'<span class="sub blk mono">stint {i + 1}/{len(lst)}, {e(st["first"][5:])} to '
                        f'{e(st["last"][5:])}{drives}</span>')
            depth = A.PO_DEPTH[t["po"]] + (0.5 if t["po"] == "Play-In" else 0)
            rows.append("<tr>" + "".join([
                td("Season", season_label(sy), sy, "mono"),
                td("Team", f'{s.tlink(st["f"], sy)}{note}<span class="sub blk mono">{e(short_standing(t))}</span>', t["name"]),
                td("Final NBA finish", finish_cell(s, t, up), t["rnk"],
                   "best" if (t["rnk"], sy) == best_fin else ("worst" if (t["rnk"], sy) == worst_fin else "")),
                td("Team W–L", rec_cell(t["w"], t["l"]), fval(A.pct(t["w"], t["l"]))),
                td("Playoffs", playoff_short(s, t, up), depth),
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
        deep_sub = f'Best: {season_label(t["s"])}, {e(s.city(t["f"], t["s"]))}'
    else:
        deep_txt, deep_sub = "Missed the playoffs", "in every season"
    gap = sm["gap"]
    sgap = (A.pct(w, l) - A.pct(sm["sw"], sm["sl"])) if (w + l) and (sm["sw"] + sm["sl"]) else None
    live = s.through and s.cur and pid in s.cur["players"]
    thru = f"through {nice_date(s.through)}" if live else f"through {season_label(LAST_COMPLETE)}"
    hero = [
        ("career-wins", "Career record in his games", f'{w}{EN}{l}', f"{pct1(A.pct(w, l))} · {w + l:,} games · {thru}"),
        ("wins-minus-losses", "Wins minus losses", signed(w - l), f"{w:,} W · {l:,} L · {thru}"),
        ("average-finish", "Average final NBA finish", f'{eq30(adj):.1f} of 30',
         f"adjusted for league size · raw average {sm['rnk']:.1f} · {sm['seasons']} completed seasons"),
    ]
    small = [
        ("winning-seasons", "Winning seasons", str(sm["winning"]), f'of {sm["seasons"]} ({pct1(sm["winning"] / sm["seasons"])})'),
        ("playoff-trips", "Playoff trips", str(sm["trips"]), f'of {sm["seasons"]} ({pct1(sm["trips"] / sm["seasons"])})'),
        ("deepest-run", "Deepest playoff run", deep_txt, deep_sub),
        ("titles", "Titles", str(sm["titles"]), (season_label(sm["titleYears"][0]) + (f' to {season_label(sm["titleYears"][-1])}' if len(sm["titleYears"]) > 1 else '')) if sm["titleYears"] else "None"),
        ("gap-career", "With vs without", f'{pct1(A.pct(w, l))} · {pct1(A.pct(sm["ow"], sm["ol"]))}',
         f'with him · without. {pts_txt(gap)}'),
    ]

    def card(c, cls):
        board, lab, big, sub = c
        return (f'<a class="card {cls}" href="{href(board)}"><span class="lbl">{e(lab)}</span>'
                f'<span class="big{" mono" if any(ch.isdigit() for ch in big) else ""}">{e(big)}</span>'
                f'<span class="sub">{sub}</span>{rank_txt(s, board, pid)}</a>')
    return ('<div class="cards hero3">' + "".join(card(c, "hc") for c in hero) + "</div>"
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


ROUND_WORDS = {"First Round": "first round", "Conf Semis": "conference semifinals",
               "Conf Finalist": "conference finals", "Finalist": "NBA Finals"}


def result_words(s, t, up):
    """The season's playoff result in full words: 'Missed the playoffs', 'Lost in the play-in',
    'Lost in the first round 1–4 to [logo] Minnesota', 'Won the title 4–2 over [logo] Utah'."""
    po = t["po"]
    if po == "":
        return "Missed the playoffs"
    if po == "Play-In":
        return "Lost in the play-in"
    if po == "Champion":
        fin = t["series"][-1] if t["series"] else None
        if not fin:
            return "Won the title"
        return (f'Won the title <span class="mono">{fin["w"]}{EN}{fin["l"]}</span> over '
                f'{s.tlink(fin["opp"], t["s"])}')
    rnd = ROUND_WORDS.get(po, po)
    el = t.get("elim")
    if not el:
        return f"Lost in the {rnd}"
    return f'Lost in the {rnd} <span class="mono">{el["w"]}{EN}{el["l"]}</span> to {s.tlink(el["opp"], t["s"])}'


def latest_seasons(s, pid, up, pts):
    """One compact card per season: season · logo + city · #23 of 30, then 26–56 · the result."""
    if not pts:
        return ""
    items = []
    for p in sorted(pts, key=lambda p: -p["sy"])[:3]:
        t = s.d.team(p["f"], p["sy"])
        # each separator travels with the item after it, so no line can start or end with a lone "·"
        items.append(f'<li><span class="l1"><a class="mono" href="{board_link(up, p["sy"], p["f"])}">{season_label(p["sy"])}</a>'
                     f'<span class="it"><i>·</i>{s.tlink(p["f"], p["sy"])}</span>'
                     f'<span class="it"><i>·</i><strong class="mono">#{p["rnk"]} of {p["size"]}</strong></span></span>'
                     f'<span class="l2"><span class="mono">{t["w"]}{EN}{t["l"]}</span> · {result_words(s, t, up)}</span></li>')
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
            td("Result", result_words(s, t, up), A.PO_DEPTH[t["po"]]),
            td("Final NBA finish", finish_cell(s, t, up), t["rnk"]),
            td("His games", f'{po["g"]} of {po["g"] + po["ow"] + po["ol"]}', po["g"], "mono"),
            td("With him", rec_cell(po["w"], po["l"]), fval(A.pct(po["w"], po["l"]))),
            td("Without him", rec_cell(po["ow"], po["ol"]), fval(A.pct(po["ow"], po["ol"]))),
            td("Gap", pp(gap), fval(gap), f"mono {cls_gap(gap)}")]) + "</tr>")
    if not rows:
        return ""
    heads = [th("Season", sort="descending"), th("Team", "text"), th("Result"), th("Final NBA finish", first="ascending"),
             th("His games"), th("With him"), th("Without him"), th("Gap")]
    na = na_columns(heads, rows)
    note = ('<p class="note">He played every playoff game for these teams, so there is no "without him" record.</p>'
            if 6 in na else "")
    return ('<section><h2 id="cap-po">Playoffs, with and without him</h2>' + sortable("cap-po", "", heads, rows) + note + "</section>")


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


# ---------------------------------------------------------------------------
# Record against each opponent (PR C). Games load on demand from assets/pg/<slug>.json;
# no per-opponent pages (no N x N URL sets).
# ---------------------------------------------------------------------------
def load_games(s):
    """pid -> [(sy, date, team, opp, home, team score, opp score, type, gid, side)] (completed seasons)."""
    if getattr(s, "pgames", None) is not None:
        return
    s.pgames = defaultdict(list)
    s.app = {}
    for sy in range(1947, LAST_COMPLETE + 1):
        lg = load_json(os.path.join(DATA, "gamelog", f"{sy}.json"), None)
        if not lg:
            continue
        for gid, date, h, a, hc, ac, hs, as_ in lg["games"]:
            hp, ap = lg["app"].get(gid, [[], []])
            s.app[gid] = (hp, ap)
            t = gid[2]
            for pid in hp:
                s.pgames[str(pid)].append((sy, date, h, a, 1, hs, as_, t, gid, 0))
            for pid in ap:
                s.pgames[str(pid)].append((sy, date, a, h, 0, as_, hs, t, gid, 1))


def latest_name(s, f):
    if not hasattr(s, "_latest"):
        s._latest = {}
        for t in s.d.teams.values():
            if t["f"] not in s._latest or t["s"] > s._latest[t["f"]][0]:
                s._latest[t["f"]] = (t["s"], t["name"])
    return s._latest[f][1]


def team_link_latest(s, f):
    return s.tlink(f, s._latest[f][0], latest_name(s, f))


def opp_rows(s, pid, kind="2"):
    """franchise -> dict of counts for one game type."""
    out = defaultdict(lambda: {"w": 0, "l": 0, "names": set(), "first": 9999, "last": 0})
    for sy, date, f, o, home, ts, os_, t, gid, side in s.pgames.get(pid, []):
        if t != kind:
            continue
        r = out[o]
        r["w" if ts > os_ else "l"] += 1
        r["names"].add(s.city(o, sy))
        r["first"] = min(r["first"], sy)
        r["last"] = max(r["last"], sy)
    return out


def opp_series(s, pid):
    """franchise -> [won, lost] playoff series he played in (pairs decided by a series only)."""
    out = defaultdict(lambda: [0, 0])
    seen = set()
    for sy, date, f, o, home, ts, os_, t, gid, side in s.pgames.get(pid, []):
        if t != "4" or (sy, o) in seen:
            continue
        seen.add((sy, o))
        tm = s.d.team(f, sy)
        for sr in (tm["series"] if tm else []):
            if sr["opp"] == o and sr["w"] != sr["l"]:
                out[o][0 if sr["won"] else 1] += 1
    return out


def rival(s, pid, opp):
    """The opposing player he shared the most regular-season games with, against that franchise."""
    c = defaultdict(int)
    for sy, date, f, o, home, ts, os_, t, gid, side in s.pgames.get(pid, []):
        if o != opp or t != "2":
            continue
        for q in s.app[gid][1 - side]:
            c[q] += 1
    if not c:
        return None
    q, n = max(c.items(), key=lambda kv: (kv[1], -kv[0]))
    return str(q), n


def opponent_takeaways(s, pid, rs, ser, up):
    """Template takeaways (docs/story-rules.md, 'Opponents'). Only when the sample supports them."""
    out = []
    big = [(f, r) for f, r in rs.items() if r["w"] + r["l"] >= 20]
    if len(big) >= 3:
        best = max(big, key=lambda x: (x[1]["w"] / (x[1]["w"] + x[1]["l"]), x[1]["w"] + x[1]["l"]))
        worst = min(big, key=lambda x: (x[1]["w"] / (x[1]["w"] + x[1]["l"]), -(x[1]["w"] + x[1]["l"])))
        for lab, (f, r) in (("Best regular-season record against one franchise", best),
                            ("Toughest regular-season record against one franchise", worst)):
            g = r["w"] + r["l"]
            txt = (f'{lab}: <a href="?vs={e(f)}#vs-{e(f)}">{wl(r["w"], r["l"])} ({pct1(r["w"] / g)}) against the '
                   f'{e(latest_name(s, f))}</a> in {g} games.')
            out.append(("best" if lab.startswith("Best") else "worst", f, txt))
    if ser:
        f, (sw, sl) = max(ser.items(), key=lambda kv: (kv[1][0] + kv[1][1], kv[1][0], kv[0]))
        if sw + sl >= 2:
            po = opp_rows(s, pid, "4")[f]
            out.append(("rivalry", f, f'Most playoff series against one franchise: <a href="?vs={e(f)}&amp;k=4#vs-{e(f)}">'
                        f'{sw + sl} against the {e(latest_name(s, f))}</a>, {sw}{EN}{sl} in series and '
                        f'{wl(po["w"], po["l"])} in games.'))
    return out


def opponents_section(s, pid, up):
    load_games(s)
    rs = opp_rows(s, pid, "2")
    if not rs:
        return ""
    po = opp_rows(s, pid, "4")
    ser = opp_series(s, pid)
    slug = s.ids[pid]["slug"]
    rows = []
    big = [(r["w"] / (r["w"] + r["l"]), f) for f, r in rs.items() if r["w"] + r["l"] >= 10]
    best_o = max(big)[1] if len(big) > 2 else None
    worst_o = min(big)[1] if len(big) > 2 else None
    for f in sorted(rs, key=lambda f: (-(rs[f]["w"] + rs[f]["l"]), latest_name(s, f))):
        r = rs[f]
        g = r["w"] + r["l"]
        ln = latest_name(s, f)
        names = sorted(r["names"] - {s.city(f, s._latest[f][0], ln)})
        sub = f'<span class="sub blk">as {e(", ".join(names))}</span>' if names else ""
        sw, sl = ser.get(f, [0, 0])
        p = po.get(f)
        series_txt = (f'{sw}{EN}{sl} <span class="sub">({wl(p["w"], p["l"])} in games)</span>'
                      if (sw + sl) else ("N/A" if not p else f'<span class="sub">{wl(p["w"], p["l"])} in games</span>'))
        rv = rival(s, pid, f)
        h2h = ""
        if rv and rv[0] in s.ids:
            h2h = (f'<span class="sub blk">Most-faced: {s.plink(rv[0], up)} ({rv[1]} games) · '
                   f'<a href="https://hoopsmatic.com/head-to-head/?a={e(pid)}&amp;b={e(rv[0])}">Head-to-Head</a></span>')
        rows.append(f'<tr id="vs-{e(f)}" data-opp="{e(f)}">' + "".join([
            td("Opponent", team_link_latest(s, f) + sub + h2h, latest_name(s, f)),
            td("Games", f"{g:,}", g, "mono"),
            td("W–L", wl(r["w"], r["l"]), r["w"], "mono"),
            td("Win %", pct1(r["w"] / g), fval(r["w"] / g), "mono" + (" best" if f == best_o else (" worst" if f == worst_o else ""))),
            td("W − L", signed(r["w"] - r["l"]), r["w"] - r["l"], "mono"),
            td("Playoff series", series_txt, sw - sl if (sw + sl) else None),
            td("Seasons", f'{season_label(r["first"])} to {season_label(r["last"])}' if r["first"] != r["last"] else season_label(r["first"]), r["first"], "mono"),
            f'<td data-l="Games list"><button type="button" class="opp-open" aria-expanded="false" aria-controls="games-{e(f)}">Show games</button></td>',
        ]) + "</tr>")
    heads = [th("Opponent", "text"), th("Games", sort="descending"), th("W–L"), th("Win %"), th("W − L"),
             th("Playoff series"), th("Seasons", first="ascending"), '<th scope="col">Games list</th>']
    tk = opponent_takeaways(s, pid, rs, ser, up)
    s.opp_take[pid] = tk
    takes = ("<ul class=\"takes\">" + "".join(f"<li>{t}</li>" for _, _, t in tk) + "</ul>") if tk else ""
    stints = sorted({st["f"] for st in s.d.stints(pid)})
    team_opts = "".join(f'<option value="{e(f)}">{e(latest_name(s, f))}</option>' for f in stints)
    yrs = sorted({st["s"] for st in s.d.stints(pid)} | {x[0] for x in s.pgames.get(pid, [])})
    yo = "".join(f'<option value="{y}">{season_label(y)}</option>' for y in yrs)
    tg = sum(r["w"] + r["l"] for r in rs.values())
    tw = sum(r["w"] for r in rs.values())
    return f"""<section id="opp"><h2 id="cap-opp">Record against each opponent</h2>
{takes}
<form id="opp-form" class="filters" data-src="{up}assets/pg/{e(slug)}.json" data-names="{up}assets/teamnames.json" data-up="{up}">
<label>Games<select name="k"><option value="2">Regular season</option><option value="4">Playoffs</option><option value="b">Both</option></select></label>
<label>From<select name="from"><option value="">First season</option>{yo}</select></label>
<label>To<select name="to"><option value="">Last season</option>{yo}</select></label>
<label>His team<select name="team"><option value="">Any</option>{team_opts}</select></label>
<label>Where<select name="ha"><option value="">Home and away</option><option value="h">Home</option><option value="a">Away</option></select></label>
<label>Min games<input name="min" type="number" min="1" inputmode="numeric" placeholder="1"></label>
<a href="#opp" class="opp-reset">Reset</a>
</form>
<p class="pop" id="opp-pop">Regular season, completed seasons: {tg:,} games, {wl(tw, tg - tw)}, against {len(rs)} franchises. Grouped by franchise (named as today); game lists keep each team's name that season.</p>
{sortable("cap-opp", "", heads, rows, "opp")}
<p class="note">Rows add up to his career record in his games. A playoff series counts when he played in it; early round-robin games show as games only. <a href="../how-we-count.html">How we count</a>.</p>
<script src="{up}assets/opp.js" defer></script>
</section>"""


def player_games_json(s, pid):
    """assets/pg/<slug>.json: {season: [[team, [[mmdd, opp, home, team pts, opp pts, type], ...]], ...]}"""
    load_games(s)
    by = defaultdict(lambda: defaultdict(list))
    for sy, date, f, o, home, ts, os_, t, gid, side in sorted(s.pgames.get(pid, [])):
        by[sy][f].append([int(date[5:7] + date[8:10]), o, home, ts, os_, int(t)])
    # playoff series he played in: [opp, won 1/0, series wins, series losses] (best-of series only)
    ps = defaultdict(list)
    seen = set()
    for sy, date, f, o, home, ts, os_, t, gid, side in s.pgames.get(pid, []):
        if t != "4" or (sy, o) in seen:
            continue
        seen.add((sy, o))
        tm = s.d.team(f, sy)
        for sr in (tm["series"] if tm else []):
            if sr["opp"] == o and sr["w"] != sr["l"]:
                ps[str(sy)].append([o, 1 if sr["won"] else 0, sr["w"], sr["l"], f])
    doc = {"v": 1, "s": {str(sy): [[f, g] for f, g in teams.items()] for sy, teams in sorted(by.items())},
           "ps": dict(ps),
           "h": {str(r["sy"]): [r["help"], r["enter"], r["partial"]] for r in career_rows(s, pid)},
           "sum": compare_summary(s, pid)}
    return f"assets/pg/{s.ids[pid]['slug']}.json", json.dumps(doc, separators=(",", ":"))


def team_names_json(s):
    # display names for the browser tables (opp.js, compare.js): the city that season (rule 5)
    names = {f"{t['f']}-{t['s']}": s.city(t["f"], t["s"]) for t in s.d.teams.values()}
    latest = {}
    for t in s.d.teams.values():
        if t["f"] not in latest or t["s"] > latest[t["f"]][0]:
            latest[t["f"]] = (t["s"], s.city(t["f"], t["s"]))
    return "assets/teamnames.json", json.dumps({"season": names, "latest": {f: v[1] for f, v in latest.items()},
                                                "cm": TEAM_SLUG}, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":"))


# ---------------------------------------------------------------------------
# Teammate help, compare with a peer, cohort views (PR D)
# ---------------------------------------------------------------------------
AWARD_ABBR = {"Most Valuable Player": "MVP", "Finals MVP": "Finals MVP", "All-NBA First Team": "All-NBA 1st",
              "All-NBA Second Team": "All-NBA 2nd", "All-NBA Third Team": "All-NBA 3rd",
              "Defensive Player of the Year": "DPOY", "All-Star": "All-Star", "All-Defensive First Team": "All-Def 1st",
              "All-Defensive Second Team": "All-Def 2nd", "Rookie of the Year": "ROY",
              "Sixth Man of the Year": "Sixth Man", "All-Star MVP": "All-Star MVP", "Most Improved Player": "MIP",
              "All-Rookie First Team": "All-Rookie 1st", "All-Rookie Second Team": "All-Rookie 2nd"}


def hfmt(v, partial=0):
    """Help points: '7.5', '0' (no honored teammate), '7.5+' when a teammate's record is missing."""
    if v is None:
        return "N/A"
    t = "0" if v == 0 else f"{v:.1f}"
    return t + ("+" if partial else "")


def career_rows(s, pid):
    """One row per completed season: the team he played most games for (season summary rule)."""
    out = []
    hs = s.help["season"].get(pid, {})
    for sy, (main, end, lst) in sorted(s.d.season_main(pid).items()):
        t = s.d.team(main["f"], sy)
        pr = A.playoff_result(s.d, end, lst)
        h = hs.get(f"{main['f']}-{sy}", [None, None, 0, []])
        out.append({"sy": sy, "f": main["f"], "team": t["name"], "rnk": t["rnk"], "size": s.sizes[sy],
                    "w": sum(x["w"] for x in lst), "l": sum(x["l"] for x in lst),
                    "po": pr[0]["po"] if pr else "", "help": h[0], "enter": h[1], "partial": h[2]})
    return out


def help_panel(s, pid, up):
    a = s.help["avg"].get(pid)
    if not a:
        return ""
    rows = career_rows(s, pid)
    tot = defaultdict(lambda: [0.0, 0])
    for r in rows:
        for q, shared, ps, pe, aws in s.help["season"][pid].get(f"{r['f']}-{r['sy']}", [0, 0, 0, []])[3]:
            if ps:
                tot[q][0] += ps
                tot[q][1] += 1
    top = sorted(tot.items(), key=lambda kv: -kv[1][0])[:3]
    tops = "".join(f'<li>{s.pic(q, up, "sm")}<span class="who">{s.plink(q, up)}</span>'
                   f'<span class="num">{v[0]:.1f}<small>{v[1]} season{"s" if v[1] != 1 else ""}</small></span></li>'
                   for q, v in top if q in s.ids)
    hv = sorted(r["help"] for r in rows if r["help"] is not None)
    sim = ""
    if len(hv) >= 5:
        med = hv[len(hv) // 2]
        lo, hi = med * 0.75, med * 1.25 if med else 0.5
        band = [r for r in rows if r["help"] is not None and lo <= r["help"] <= hi]
        if len(band) >= 3:
            b = min(band, key=lambda r: (r["rnk"] / r["size"], -r["sy"]))
            w = max(band, key=lambda r: (r["rnk"] / r["size"], r["sy"]))
            sim = (f'<p class="note">Seasons with help {lo:.1f} to {hi:.1f} ({len(band)}): best finish '
                   f'<a href="{board_link(up, b["sy"], b["f"])}">#{b["rnk"]} of {b["size"]}, {season_label(b["sy"])}</a>, worst '
                   f'<a href="{board_link(up, w["sy"], w["f"])}">#{w["rnk"]} of {w["size"]}, {season_label(w["sy"])}</a>.</p>')
    rk = s.help_rank.get(pid)
    rank = f'<span class="rk">#{rk[0]:,} of {rk[1]:,} (300+ games, most help = #1)</span>' if rk else ""
    return f"""<section class="help"><h2>Teammate help</h2>
<div class="cards"><div class="card"><span class="lbl">Help per season</span><span class="big">{a['help']:.1f}</span><span class="sub">same-season honors of teammates</span>{rank}</div>
<div class="card"><span class="lbl">Help coming in</span><span class="big">{a['enter']:.1f}</span><span class="sub">teammates' honors the season before</span></div></div>
{('<div class="box" style="margin-top:.45rem"><div class="boxhead">Most of it came from <a href="#cap-help">by season</a></div><ul class="rows">' + tops + '</ul></div>') if tops else '<p class="note">No honored teammate in any season: help 0.</p>'}
{sim}
</section>"""


def stint_mates(s, pid, f, sy):
    """Teammates who shared regular-season games with him for that team-season: {pid: games}."""
    load_games(s)
    c = defaultdict(int)
    for x in s.pgames.get(pid, ()):
        if x[0] == sy and x[2] == f and x[7] == "2":
            for q in s.app[x[8]][x[9]]:
                if str(q) != pid:
                    c[str(q)] += 1
    return c


def award_badges(aws):
    order = ["Most Valuable Player", "Finals MVP", "Defensive Player of the Year", "All-NBA First Team",
             "All-NBA Second Team", "All-NBA Third Team", "All-Star", "All-Defensive First Team",
             "All-Defensive Second Team", "Sixth Man of the Year", "Rookie of the Year", "Most Improved Player",
             "All-Star MVP", "All-Rookie First Team", "All-Rookie Second Team"]
    aws = sorted(aws, key=lambda a: order.index(a) if a in order else 99)
    top = {"Most Valuable Player", "Finals MVP", "Defensive Player of the Year", "All-NBA First Team"}
    return "".join(f'<span class="aw{" top" if a in top else ""}">{e(AWARD_ABBR.get(a, a))}</span>' for a in aws)


def help_table(s, pid, up):
    hs = s.help["season"].get(pid)
    if not hs:
        return ""
    sts = sorted(s.d.stints(pid), key=lambda x: (-x["s"], x.get("first") or ""))
    vals = [hs.get(f"{st['f']}-{st['s']}", [0])[0] for st in sts]
    top = max(vals + [1])
    items = []

    def who(q):
        return s.plink(q, up) if q in s.ids else e(q)
    for st in sts:
        h = hs.get(f"{st['f']}-{st['s']}")
        if not h:
            continue
        same, enter, partial, mates = h
        honored = [m for m in mates if m[2]]
        prev = [m for m in mates if m[3] and not m[2]]
        head = (f'<span class="hs-y">{season_label(st["s"])}</span>'
                f'<span class="hs-t">{s.tlink(st["f"], st["s"])}</span>')
        coming = (f'<p class="more">Help coming in (teammates\' honors the season before): '
                  f'<strong class="mono">{hfmt(enter, partial)}</strong>'
                  + (" · from " + ", ".join(f'{who(q)} ({pe:.1f})' for q, shared, ps, pe, aws in prev[:4]) if prev else "")
                  + "</p>")
        if st["s"] in s.partial_years:
            # honors for this season are not in the awards file yet: say so, no bar
            items.append(f'<li class="slim">{head}<span class="hnote">Honors not in the data yet</span></li>')
            continue
        if not honored:
            # one slim row; a toggle only when last season's honors give something to show
            more = (f'<details><summary>More: last season\'s honors</summary>{coming}</details>' if prev else "")
            items.append(f'<li class="slim">{head}<span class="hnote">No honored teammate'
                         f'{" <span class=\"aw\">partial</span>" if partial else ""}</span>{more}</li>')
            continue
        chips = "".join(
            f'<span class="mchip">{s.pic(q, up, "sm")}<span class="mn">{who(q)}</span> {award_badges(aws)}'
            f'<span class="gtog">{shared} g</span></span>'
            for q, shared, ps, pe, aws in honored)
        allm = stint_mates(s, pid, st["f"], st["s"])
        hon = {m[0] for m in honored}
        rest = sorted(((g, q) for q, g in allm.items() if q not in hon), reverse=True)
        others = ((f'<p class="more">Other teammates (no honors that season): ' + ", ".join(
            f'{who(q)} {g} g' for g, q in rest[:14]) + (f" and {len(rest) - 14} more" if len(rest) > 14 else "") + "</p>")
            if rest else "")
        w = max(0.2, round(6 * same / top, 2))
        val = hfmt(same, partial) + (' <span class="aw">partial</span>' if partial else "")
        items.append(f"""<li>{head}
<span class="hbar"><i style="width:{w}rem"></i>{val}</span>
<span class="chipsrow">{chips}</span>
<details><summary>More: last season's honors and other teammates</summary>{coming}{others}</details></li>""")
    return (f'<section><h2 id="cap-help">Teammate help by season</h2>'
            f'<p class="note">Help = Teammates Score points for honors won that season by teammates who shared a game with him. '
            f'<a href="../comparison-rules.html">How help works</a>.</p><ul class="helprows">{"".join(items)}</ul></section>')


def peer_reason(s, a, b, dist):
    A_, B_ = s.help["avg"][a], s.help["avg"][b]
    base = (f"Careers centered on {season_label(round(A_['mid']))} and {season_label(round(B_['mid']))}; "
            f"help {A_['help']:.1f} and {B_['help']:.1f} points per season; own honors {A_['own']:.1f} and "
            f"{B_['own']:.1f} per season; {A_['g']:,} and {B_['g']:,} games.")
    return ("Closest by the same rules, outside the usual limits. " if dist >= 100 else "") + base


def compare_rel(a_slug, b_slug):
    x, y = sorted((a_slug, b_slug))
    return f"compare/{x}--{y}.html"


def peer_section(s, pid, up):
    peers = s.help["peers"].get(pid, [])
    slug = s.ids[pid]["slug"]
    items = []
    for q, dist in peers:
        if q not in s.ids:
            continue
        rel = compare_rel(slug, s.ids[q]["slug"])
        items.append(f'<li>{s.pic(q, up, "sm")}<div><strong><a href="{up}{rel}">{e(s.ids[pid]["name"])} vs {e(s.ids[q]["name"])}</a></strong>'
                     f'<span class="det">{e(peer_reason(s, pid, q, dist))}</span></div></li>')
    sugg = ('<ul class="feat peers">' + "".join(items) + "</ul>") if items else \
        '<p class="note">Suggested peers need 300+ career games. Pick anyone below.</p>'
    return f"""<section id="compare"><h2>Compare with a peer</h2>
{sugg}
<form class="finder" role="search" data-mode="peer" data-up="{up}" data-index="{up}assets/players.json" action="#compare">
<label for="peer-q">Compare {e(s.ids[pid]['name'])} with anyone</label>
<input id="peer-q" type="search" autocomplete="off" placeholder="Type a name">
<ul class="results"></ul></form>
<div id="cmp" data-a="{e(slug)}" data-up="{up}"></div>
<script src="{up}assets/compare.js" defer></script>
</section>"""


def compare_summary(s, pid):
    sm = A.summary(s.d, pid)
    a = s.help["avg"].get(pid, {})
    rows = career_rows(s, pid)
    deep = max((A.PO_DEPTH[r["po"]] for r in rows), default=0)
    deep_po = next((r["po"] for r in rows if A.PO_DEPTH[r["po"]] == deep), "")
    return {"name": s.ids[pid]["name"], "slug": s.ids[pid]["slug"], "hs": s.ids[pid].get("hs") or "",
            "w": sm["w"], "l": sm["l"], "wl": sm["w"] - sm["l"], "pct": A.pct(sm["w"], sm["l"]),
            "avg": sm["rnk"], "adj30": round(eq30(s.adj_avg(pid)), 4), "titles": sm["titles"], "trips": sm["trips"],
            "seasons": sm["seasons"], "deep": deep, "deepLabel": A.PO_LABEL[deep_po] if deep else "Missed the playoffs",
            "gap": round(sm["gap"], 4) if sm["gap"] is not None else None,
            "help": a.get("help"), "enter": a.get("enter"),
            "span": season_label(min(r["sy"] for r in rows)) + " to " + season_label(max(r["sy"] for r in rows))}


def short_name(name, other):
    """Last name for the scoreboard columns ('Malone'); the full name when both share it."""
    def last(n):
        w = [x for x in n.split() if x.lower().strip(".,") not in ("jr", "sr", "ii", "iii", "iv")]
        return w[-1] if w else n
    return name if last(name) == last(other) else last(name)


def scoreboard(s, a, b, ca, cb, up):
    """H2H-style scoreboard: one row per category, the leader's cell tinted, a tally line.
    Records and finishes only; 'leads' means the larger number, or the smaller one where it says so."""
    na, nb = short_name(ca["name"], cb["name"]), short_name(cb["name"], ca["name"])

    def gap_txt(g):
        return "N/A" if g is None else pp(g)
    # (label, how it counts, value A, value B, text A, text B, lower leads)
    cats = [
        ("Career record", "win % in his games", round(ca["pct"] or 0, 3), round(cb["pct"] or 0, 3),
         f'{wl(ca["w"], ca["l"])}<small>{pct1(ca["pct"])}</small>', f'{wl(cb["w"], cb["l"])}<small>{pct1(cb["pct"])}</small>', False),
        ("W \u2212 L", "", ca["wl"], cb["wl"], signed(ca["wl"]), signed(cb["wl"]), False),
        ("Titles", "", ca["titles"], cb["titles"], str(ca["titles"]), str(cb["titles"]), False),
        ("Playoff trips", "", ca["trips"], cb["trips"], str(ca["trips"]), str(cb["trips"]), False),
        ("Deepest run", "", ca["deep"], cb["deep"], e(ca["deepLabel"]), e(cb["deepLabel"]), False),
        ("Average finish", "adjusted for league size, lower leads", round(ca["adj30"], 1), round(cb["adj30"], 1),
         f'{ca["adj30"]:.1f} of 30', f'{cb["adj30"]:.1f} of 30', True),
        ("With vs without", "win-rate gap in points", None if ca["gap"] is None else round(100 * ca["gap"], 1),
         None if cb["gap"] is None else round(100 * cb["gap"], 1), gap_txt(ca["gap"]), gap_txt(cb["gap"]), False),
        ("Help per season", "teammates' honors, less help leads", None if ca["help"] is None else round(ca["help"], 1),
         None if cb["help"] is None else round(cb["help"], 1), hfmt(ca["help"]), hfmt(cb["help"]), True),
    ]
    rows = []
    la = lb = even = 0
    for lab, how, va, vb, ta, tb, low in cats:
        if va is None or vb is None or va == vb:
            ka = kb = ""
            even += 1
        elif (va < vb) == low:
            ka, kb = ' class="la"', ""
            la += 1
        else:
            ka, kb = "", ' class="lb"'
            lb += 1
        rows.append(f'<tr{" class=\"txt\"" if lab == "Deepest run" else ""}><th scope="row">{e(lab)}{("<small>" + e(how) + "</small>") if how else ""}</th>'
                    f'<td{ka}>{ta}</td><td{kb}>{tb}</td></tr>')
    n = len(cats)
    tally = f"{e(na)} leads {la} of {n} · {e(nb)} leads {lb} of {n}" + (f" · {even} even" if even else "")
    help_line = ""
    if ca["help"] is not None and cb["help"] is not None and round(ca["help"], 1) != round(cb["help"], 1):
        lo, hi = (ca, cb) if ca["help"] < cb["help"] else (cb, ca)
        help_line = (f'<p class="note">Less help: {e(short_name(lo["name"], hi["name"]))} '
                     f'({lo["help"]:.1f} per season vs {hi["help"]:.1f}). Help is the Teammates Score of the '
                     f'teammates he shared games with; the smaller number is tinted.</p>')
    return f"""<section class="sboard"><h2 id="cap-sb">Head to head</h2>
<div class="sbhead"><div class="sbp a">{s.pic(a, up, 'md')}<b>{e(ca['name'])}</b><small>{e(ca['span'])}</small></div>
<span class="vs">vs</span><div class="sbp b">{s.pic(b, up, 'md')}<b>{e(cb['name'])}</b><small>{e(cb['span'])}</small></div></div>
<table class="sbt" aria-labelledby="cap-sb"><thead><tr><th scope="col">Category</th><th scope="col">{e(na)}</th><th scope="col">{e(nb)}</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p class="tally">{tally}</p>
{help_line}<p class="note">The leader's cell is tinted: the larger number, except average finish and help, where the smaller one leads. These are team records and finishes, not a measure of who was better.</p>
</section>"""


def compare_page(s, a, b, dist):
    """Static comparison for a suggested pair: noindex, not in the sitemap, own share card."""
    up = "../"
    sa, sb = s.ids[a]["slug"], s.ids[b]["slug"]
    if sb < sa:
        a, b, sa, sb = b, a, sb, sa
    rel = compare_rel(sa, sb)
    ra, rb = career_rows(s, a), career_rows(s, b)
    ca, cb = compare_summary(s, a), compare_summary(s, b)
    na, nb = ca["name"], cb["name"]
    sna, snb = short_name(na, nb), short_name(nb, na)
    n = max(len(ra), len(rb))

    def adj(r):
        return (r["rnk"] - 1) / (r["size"] - 1) if r["size"] > 1 else 0.0
    trs, cards = [], []
    ta = tb = 0
    for k in range(n):
        x = ra[k] if k < len(ra) else None
        y = rb[k] if k < len(rb) else None
        lead = None
        if x and y and abs(adj(x) - adj(y)) > 1e-9:
            lead = "a" if adj(x) < adj(y) else "b"
            ta += lead == "a"
            tb += lead == "b"
        tally = f"{ta}{EN}{tb}" if (x and y) else ""

        def cells(r, side):
            if not r:
                return '<td colspan="5" class="none">No season</td>'
            tint = f' class="l{side}"' if lead == side else ""
            return (f'<td class="cs"><span class="mono">{season_label(r["sy"])}</span> {s.tlink(r["f"], r["sy"])}</td>'
                    f'<td{tint}><a class="mono" href="{board_link(up, r["sy"], r["f"])}">#{r["rnk"]} of {r["size"]}</a></td>'
                    f'<td class="mono">{wl(r["w"], r["l"])}</td>'
                    f'<td class="po">{e(A.PO_LABEL[r["po"]])}</td>'
                    f'<td class="mono">{hfmt(r["help"], r["partial"])}</td>')

        def card(r, side, nm):
            if not r:
                return f'<div class="cc {side} none"><span class="cc-n">{e(nm)}</span><span>No season</span></div>'
            tint = " lead" if lead == side else ""
            return (f'<div class="cc {side}{tint}"><span class="cc-n">{e(nm)}</span>'
                    f'<span class="mono">{season_label(r["sy"])}</span>{s.tlink(r["f"], r["sy"])}'
                    f'<a class="mono fin" href="{board_link(up, r["sy"], r["f"])}">#{r["rnk"]} of {r["size"]}</a>'
                    f'<span class="mono">{wl(r["w"], r["l"])}</span><span>{e(A.PO_LABEL[r["po"]])}</span>'
                    f'<span class="mono">Help {hfmt(r["help"], r["partial"])}</span></div>')
        trs.append(f'<tr><td class="mono">{k + 1}</td>{cells(x, "a")}{cells(y, "b")}<td class="mono">{tally}</td></tr>')
        cards.append(f'<li><div class="cc-h"><b>Career season {k + 1}</b>'
                     + (f'<span class="mono">better finish so far: {e(sna)} {ta}{EN}{tb} {e(snb)}</span>' if tally else "")
                     + f'</div><div class="cc-g">{card(x, "a", sna)}{card(y, "b", snb)}</div></li>')
    sub = "<th scope=\"col\">Season</th><th scope=\"col\">Finish</th><th scope=\"col\">W\u2013L</th><th scope=\"col\">Playoffs</th><th scope=\"col\">Help</th>"
    table = (f'<div class="cmpwide"><table class="cmpt" aria-labelledby="cap-cmp"><thead>'
             f'<tr><th scope="col" rowspan="2">#</th><th scope="colgroup" colspan="5" class="ga">{e(na)}</th>'
             f'<th scope="colgroup" colspan="5" class="gb">{e(nb)}</th><th scope="col" rowspan="2">Better finish<br>{e(sna)}{EN}{e(snb)}</th></tr>'
             f'<tr>{sub}{sub}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'
             f'<ol class="cmpcards">{"".join(cards)}</ol>')
    card_data = json.dumps([ca, cb], ensure_ascii=False, separators=(",", ":"))
    body = f"""<header class="ent">{s.pic(a, up, 'md')}{s.pic(b, up, 'md')}<div><h1>{e(na)} vs {e(nb)}</h1>
<p class="subtitle">Team success, aligned by career season: final NBA finish, record in his games, playoffs and teammate help.</p></div></header>
{scoreboard(s, a, b, ca, cb, up)}
<p><button type="button" class="more-btn" id="card-dl" data-card="{e(card_data)}" data-up="{up}">Download image</button> <span class="note">Share this page's link; the image states the comparison and its scope.</span></p>
<section><h2 id="cap-cmp">Season by season</h2>
<p class="note">Career season 1 next to career season 1. Each player's season is the team he played the most games for; W–L is his teams' record in his games that season. The tinted finish is the team that finished higher that season, on the league-size-adjusted scale; the last column keeps the running count. Help counts honors won that season by teammates who shared a game with him. <a href="../comparison-rules.html">Comparison rules</a>.</p>
{table}</section>
<p class="note">Why these two: {e(peer_reason(s, a, b, dist))}</p>
<p class="more">{s.plink(a, up)} · {s.plink(b, up)} · <a href="../lists/same-help-different-results.html">Same help, different results</a></p>
<script src="../assets/compare.js" defer></script>"""
    desc = (f"{na} and {nb} compared: {wl(ca['w'], ca['l'])} vs {wl(cb['w'], cb['l'])} in their games, average final finish "
            f"{ca['adj30']:.1f} vs {cb['adj30']:.1f} of 30 (adjusted for league size), help {ca['help']:.1f} vs {cb['help']:.1f} points per season.")
    og = f"{OG}compare/{sa}--{sb}.png"
    return rel, page(rel, f"{na} vs {nb}: team success compared | HoopsMatic", desc, body, up,
                     robots="noindex, follow", og=og)


def comparison_rules_page(s):
    body = f"""<header><h1>How teammate help and peer comparisons work</h1>
<p class="subtitle">The rules behind "Teammate help", "Compare with a peer" and the cohort lists.</p></header>
<section class="prose">
<h2>Teammate help</h2>
<p>Help uses the HoopsMatic Teammates Score weights: MVP and Finals MVP 10; All-NBA First Team and Defensive Player of the Year 4; All-NBA Second Team 3; All-NBA Third Team 2; All-Star and All-Defensive First Team 1; Rookie of the Year, Sixth Man, All-Defensive Second Team and All-Star MVP 0.5; Most Improved and All-Rookie First Team 0.25; All-Rookie Second Team 0.125. An MVP already covers that season's All-NBA nod and a DPOY that season's All-Defensive nod.</p>
<p>A season's help adds up the honors won that season by the teammates who shared at least one regular-season game with him for that team. We check every game, so a player traded in February gets only the teammates he played with. Players are joined on their NBA person ID, team and season.</p>
<p><strong>Zero and missing are different.</strong> 0 means no teammate he played with was honored. A "+" after a number means a teammate with 10 or more shared games has no award record in our player database (his name did not match), so the true number may be higher.</p>
<p><strong>Per season, not career totals.</strong> A player's help is the average over his seasons (one team per season, the one he played the most games for). A long career does not raise it.</p>
<p><strong>Entering the season.</strong> Same-season honors can reflect the winning they are being compared against: a 60-win team gets more All-Stars. "Entering" uses the same teammates' honors from the season before, which the season's results cannot have influenced.</p>
<h2>Suggested peers</h2>
<p>Every player with {300} or more career games gets three suggested peers, chosen from the same pool by four measures: era (the game-weighted middle of the career, within 4 seasons), help (average per season, within a log distance of 0.35), his own honors per season (within 0.5) and career length (games, within a log distance of 0.7). The three with the smallest combined distance (era / 4 + help / 0.35 + career length / 0.7 + honors / 0.5) are shown. When fewer than three pass those limits, the closest players within 6 seasons of era fill the list and say so.</p>
<p>Each suggestion states the numbers it was matched on. Comparisons align the two careers by career season (season 1 with season 1), so players from different eras can be compared the same way. A comparison states records and finishes, not what a player caused.</p>
<h2>Cohort lists</h2>
<ul>
<li><a href="lists/low-help-all-stars.html">Best finishes among low-help All-Stars</a>: All-Stars with 300+ games and 5+ seasons whose average help is in the lowest quarter of that group, ranked by average final finish; a second table uses help entering the season.</li>
<li><a href="lists/same-help-different-results.html">Same help, different results</a>: pairs of players from the same era (career middles within 4 seasons) with help within 15% of each other and 500+ games each, ranked by the difference in average final finish.</li>
<li>On every player page: his best and worst final finish among the seasons with help within 25% of his median.</li>
</ul>
<h2>Share images</h2>
<p>Each player's three suggested comparisons (players with 300+ games) have their own page and social card. On any comparison, the "Download image" button builds a card in your browser from the page's data, with this site's fonts and headshots.</p>
</section>"""
    rel = "comparison-rules.html"
    return rel, page(rel, "How teammate help and peer comparisons work | HoopsMatic",
                     "The rules behind Team Success teammate help and peer comparisons: Teammates Score weights, "
                     "game-by-game overlap, zero vs missing, help entering the season and how peers are matched.", body, "")


def cohort_pages(s):
    up = "../"
    av = s.help["avg"]
    out = []
    # 1. low-help All-Stars
    pool = []
    for pid, a in av.items():
        if a["g"] < 300 or a["n"] < 5 or not s.d.players[pid].get("as"):
            continue
        sm = A.summary(s.d, pid)
        pool.append((pid, a, sm))
    def low_table(key, cap):
        vals = sorted(x[1][key] for x in pool)
        q1 = vals[len(vals) // 4] if vals else 0
        rows = [x for x in pool if x[1][key] <= q1]
        rows.sort(key=lambda x: (x[2]["rnk"], x[1][key], s.ids[x[0]]["name"]))
        trs = []
        for i, (pid, a, sm) in enumerate(rows[:100]):
            trs.append("<tr>" + "".join([td("Rank", str(i + 1), i + 1, "mono"), td("Player", s.plink(pid, up), s.ids[pid]["name"]),
                       td("Average final finish", f'{sm["rnk"]:.1f}', fval(sm["rnk"]), "mono"),
                       td("Help per season", f'{a["help"]:.1f}', a["help"], "mono"),
                       td("Entering", f'{a["enter"]:.1f}', a["enter"], "mono"),
                       td("Seasons", str(a["n"]), a["n"], "mono"), td("Titles", str(sm["titles"]), sm["titles"], "mono"),
                       td("W–L", wl(sm["w"], sm["l"]), sm["w"] - sm["l"], "mono")]) + "</tr>")
        heads = [th("Rank", first="ascending"), th("Player", "text"), th("Average final finish", sort="ascending", first="ascending"),
                 th("Help per season"), th("Entering"), th("Seasons"), th("Titles"), th("W–L")]
        return (f"<p class=\"pop\">{len(rows)} of {len(pool)} All-Stars (300+ games, 5+ seasons) have {key == 'help' and 'help' or 'help entering the season'} "
                f"of {q1:.1f} points per season or less (the lowest quarter).</p>" + sortable(cap, "", heads, trs))
    body = f"""<header><h1>Best finishes among low-help All-Stars</h1>
<p class="subtitle">All-Stars whose teammates were honored least, ranked by their teams' average final NBA finish (1 = champion). Help is the Teammates Score of the teammates they shared games with, per season.</p></header>
<section><h2 id="cap-low">By help in the same season</h2>{low_table('help', 'cap-low')}</section>
<section><h2 id="cap-low2">By help entering the season</h2><p class="note">Teammates' honors from the season before, which the season's own results cannot have influenced.</p>{low_table('enter', 'cap-low2')}</section>
<p class="note"><a href="../comparison-rules.html">How help works</a>.</p>"""
    rel = "lists/low-help-all-stars.html"
    out.append((rel, page(rel, "Best team finishes among low-help NBA All-Stars | HoopsMatic",
                          "NBA All-Stars with the least teammate help (Teammates Score per season), ranked by their teams' "
                          "average final finish, with help entering the season as a second view.", body, up)))
    # 2. same help, different results
    big = [(pid, a) for pid, a in av.items() if a["g"] >= 500]
    pairs = []
    for i, (p, a) in enumerate(big):
        for q, b in big[i + 1:]:
            if abs(a["mid"] - b["mid"]) > 4:
                continue
            hi, lo = max(a["help"], b["help"]), min(a["help"], b["help"])
            if hi == 0 or (hi - lo) / hi > 0.15:
                continue
            ra, rb = s.avg_rnk[p], s.avg_rnk[q]
            pairs.append((abs(ra - rb), p, q))
    pairs.sort(key=lambda x: (-x[0], s.ids[x[1]]["name"]))
    seen = defaultdict(int)
    trs = []
    for dlt, p, q in pairs:
        if seen[p] >= 2 or seen[q] >= 2:
            continue
        seen[p] += 1
        seen[q] += 1
        better, worse = (p, q) if s.avg_rnk[p] < s.avg_rnk[q] else (q, p)
        rel_c = compare_rel(s.ids[better]["slug"], s.ids[worse]["slug"])
        link = (f'<a href="{up}{rel_c}">Compare</a>' if rel_c in s.compare_pages else
                f'<a href="{up}player/{e(s.ids[better]["slug"])}.html?peer={e(s.ids[worse]["slug"])}#compare">Compare</a>')
        trs.append("<tr>" + "".join([
            td("Rank", str(len(trs) + 1), len(trs) + 1, "mono"),
            td("Better average finish", s.plink(better, up) + f' <span class="sub">{s.avg_rnk[better]:.1f}, help {av[better]["help"]:.1f}</span>', s.avg_rnk[better]),
            td("Worse average finish", s.plink(worse, up) + f' <span class="sub">{s.avg_rnk[worse]:.1f}, help {av[worse]["help"]:.1f}</span>', s.avg_rnk[worse]),
            td("Difference", f"{dlt:.1f} places", fval(dlt), "mono"),
            td("Eras", f'{season_label(round(av[better]["mid"]))} / {season_label(round(av[worse]["mid"]))}', None, "mono"),
            td("Comparison", link)]) + "</tr>")
        if len(trs) >= 60:
            break
    heads = [th("Rank", first="ascending"), th("Better average finish", first="ascending"), th("Worse average finish"),
             th("Difference", sort="descending"), '<th scope="col">Eras</th>', '<th scope="col">Comparison</th>']
    body = f"""<header><h1>Same help, different results</h1>
<p class="subtitle">Pairs of players from the same era with nearly the same teammate help (within 15% per season, 500+ games each) whose teams' average final finishes were furthest apart. Each player appears at most twice.</p></header>
<p class="pop">{len(pairs):,} pairs qualify; the {len(trs)} furthest apart are listed.</p>
{sortable("cap-same", "", heads, trs)}
<p class="note">Records and finishes, not what a player caused. <a href="../comparison-rules.html">Comparison rules</a>.</p>"""
    rel = "lists/same-help-different-results.html"
    out.append((rel, page(rel, "Same teammate help, different results: NBA player pairs | HoopsMatic",
                          "NBA players from the same era with nearly identical teammate help whose teams' average final "
                          "finishes were furthest apart, each with a side-by-side comparison.", body, up)))
    return out


def card_files(s):
    """assets/card/*.json: small, stable data for the hoopsmatic-og-card repo to draw social cards.
    Values are numbers and short strings from the same functions as the pages (no prose)."""
    out = []
    thr = s.through
    for pid in s.ids:
        if not s.has_hist(pid):
            continue
        v = s.ids[pid]
        sm = A.summary(s.d, pid)
        if not sm["seasons"]:
            continue
        rk = s.ranks["wins-minus-losses"].get(pid)
        best = None
        for sy, (main, end, lst) in s.d.season_main(pid).items():
            t = s.d.team(main["f"], sy)
            if best is None or (t["rnk"] / s.sizes[sy], -sy) < (best[0], -best[1]):
                best = (t["rnk"] / s.sizes[sy], sy, t["rnk"], s.sizes[sy], t["name"])
        a = s.help["avg"].get(pid, {})
        hr = s.help_rank.get(pid)
        peers = s.help["peers"].get(pid, [])
        hs = v.get("hs") if v.get("hs") and os.path.exists(os.path.join(ROOT, "assets", "hs", v["hs"])) else None
        yrs = sorted({st["s"] for st in s.d.stints(pid, upto=CURRENT_SEASON)})
        doc = {"v": 1, "slug": v["slug"], "name": v["name"], "url": f"{BASE}player/{v['slug']}.html",
               "headshot": f"assets/hs/{hs}" if hs else None, "through": thr,
               "span": [season_label(yrs[0]), season_label(yrs[-1])],
               "record": {"w": sm["w"], "l": sm["l"], "pct": round(A.pct(sm["w"], sm["l"]) or 0, 4),
                          "wl": sm["w"] - sm["l"], "wl_rank": rk[0] if rk else None, "wl_tied": bool(rk and rk[1]),
                          "wl_of": s.rank_n["wins-minus-losses"]},
               "titles": sm["titles"], "title_seasons": [season_label(y) for y in sm["titleYears"]],
               "best_finish": {"rank": best[2], "of": best[3], "season": season_label(best[1]), "team": best[4]} if best else None,
               "with_without": {"with_pct": round(A.pct(sm["w"], sm["l"]) or 0, 4),
                                "without_pct": round(A.pct(sm["ow"], sm["ol"]), 4) if sm["ow"] + sm["ol"] else None,
                                "gap_points": round(100 * sm["gap"], 1) if sm["gap"] is not None else None,
                                "without_games": sm["ow"] + sm["ol"]},
               "help": {"per_season": round(a["help"], 2) if a else None, "rank": hr[0] if hr else None,
                        "of": hr[1] if hr else None},
               "top_peer": s.ids[peers[0][0]]["slug"] if peers and peers[0][0] in s.ids else None}
        out.append((f"assets/card/{v['slug']}.json", json.dumps(doc, ensure_ascii=False, separators=(",", ":"))))
    for key, dfn in B.BOARDS.items():
        ranked, sort, mins = s.board_default[key]
        rows = [{"rank": r, "tied": tied, "slug": m["slug"], "name": m["name"],
                 "headshot": (f"assets/hs/{s.ids[m['pid']]['hs']}" if s.ids[m["pid"]].get("hs") and
                              os.path.exists(os.path.join(ROOT, "assets", "hs", s.ids[m["pid"]]["hs"])) else None),
                 "value": board_cell(sort, m)[1], "w": m["w"], "l": m["l"]} for r, tied, m in ranked[:5]]
        out.append((f"assets/card/lists/{key}.json", json.dumps(
            {"v": 1, "list": key, "title": dfn["h1"], "url": f"{BASE}lists/{key}.html", "through": thr,
             "sort": dfn["sorts"][sort][0], "rows": rows}, ensure_ascii=False, separators=(",", ":"))))
    for sy in range(1947, LAST_COMPLETE + 1):
        ts = sorted((t for t in s.d.teams.values() if t["s"] == sy), key=lambda t: (t["rnk"], t["name"]))
        rows = [{"rank": t["rnk"], "team": t["name"], "code": era_code(t["f"], sy), "w": t["w"], "l": t["l"],
                 "playoffs": PO_SHORT.get(t["po"], t["po"])} for t in ts[:5]]
        out.append((f"assets/card/seasons/{season_label(sy)}.json", json.dumps(
            {"v": 1, "season": season_label(sy), "teams": len(ts), "url": f"{BASE}seasons/{season_label(sy)}.html",
             "rows": rows}, ensure_ascii=False, separators=(",", ":"))))
    return out


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
                f"finish {eq30(s.adj_avg(pid)):.1f} of 30 (adjusted for league size). Every season ranked, playoffs, with and without him.")
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
<p class="note legend"><span class="key title"></span>Title <span class="key finals"></span>Finals <span class="key playoffs"></span>Other playoffs <span class="key missed"></span>Missed the playoffs. #1 = champion; the dashed line is last place that season. Each point opens that season's final standings.</p>
{nxt}</section>
{help_panel(s, pid, up)}
</div>
<section class="sum"><h2>Career</h2>{summary_cards(s, pid, up)}
<p class="note">Regular seasons {season_label(1947)} to {season_label(CURRENT_SEASON)}, games through {e(nice_date(s.through))}. Records include {season_label(CURRENT_SEASON)} to date; season counts and finishes use completed seasons. Each card opens its board. <a href="../how-we-count.html">How we count</a>.</p></section>""")
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
        parts.append(help_table(s, pid, up))
        parts.append(peer_section(s, pid, up))
        parts.append(opponents_section(s, pid, up))
        parts.append(playoff_table(s, pid, up))
        parts.append(arrival_departure(s, pid, up))
        parts.append(trades(s, pid, up))
        parts.append(duos(s, pid, up))
        b = s.badges.get(pid)
        if b:
            parts.append('<section><h2>Lists he is on</h2><ul class="badges">' + "".join(
                f'<li><a class="badge" href="../lists/{e(k)}.html">{e(t)}</a></li>' for k, t in b) + "</ul></section>")
    body = "\n".join(p for p in parts if p)
    # the card needs assets/card/<slug>.json, written for players with a completed season
    og = f"{OG}player/{v['slug']}.png" if has_hist else None
    return rel, page(rel, title, desc, body, up, og=og)


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------
def season_chips(s, seasons, up):
    """One line of chips, logo + two-digit year ('71 = 1970-71); his games per season behind one click."""
    chips = "".join(
        f'<span class="yc" title="{season_label(x["s"])} {e((s.d.team(x["f"], x["s"]) or {}).get("name", x["f"]))}">'
        f'{s.logo(x["f"], x["s"], up)}\u2019{x["s"] % 100:02d}</span>' for x in seasons)
    games = ", ".join(f'{season_label(x["s"])} {e(s.city(x["f"], x["s"]))} {x["g"]} g' for x in seasons)
    return (f'<details class="ychips"><summary><span class="vh">Seasons: </span>{chips}'
            f'<span class="ymore">games</span></summary><p class="yg">{games}</p></details>')


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
                blocks.append(f'<h2 class="fr">{s.tlink(f, last_season, full=True)}</h2>' + rows_html(s, items, up))
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
    chip_note = (" Each chip is one season: the team's logo and the year the season ended (\u201971 = 1970-71). "
                 "Tap a row's chips for his games with each team." if key in ("worst-team", "best-team", "sixty-win-pace") else "")
    body = f"""<header><h1>{e(title)}</h1><p class="subtitle">{e(desc)}</p></header>
{toggles(True, 'l')}
{extra}
{body_panels}
<p class="note">Regular season, 1946-47 through 2025-26. A player was on a team-season if he played at least one game for it; "Only team-seasons where he played 20+ games" drops the others before counting.{chip_note} <a href="../how-we-count.html">How we count</a>.</p>
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
            td("Playoffs", playoff_short(s, t, up), depth),
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
    return rel, page(rel, f"{lab} NBA final standings: all {n} teams ranked | HoopsMatic", desc, body, up,
                     og=f"{OG}season/{lab}.png")


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
                     f'<span class="det">{len(ts)} teams. #1 {e(s.city(champ["f"], sy))} ({champ["w"]}{EN}{champ["l"]})</span></li>')
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
        return m["adj"], ("N/A" if m["adj"] is None else f"{eq30(m['adj']):.1f}")
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
             f'<td data-l="Player"><span class="tmn">{s.pic(m["pid"], up, "sm")} {s.plink(m["pid"], up)}</span></td>']
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
    if dfn.get("noas"):
        extra += ('<label>He was an All-Star that season<select name="self"><option value="">Either</option>'
                  '<option value="yes">He was</option><option value="no">He wasn\'t</option></select></label>')
    if key == "gap-career":
        extra += ('<label>Min games played<input name="mp" type="number" min="1" inputmode="numeric" placeholder="200"></label>'
                  '<label>Min games missed<input name="mm" type="number" min="1" inputmode="numeric" placeholder="50"></label>')
    return f"""<form id="board-form" class="filters" action="{key}.html" method="get">
<label>Rank by<select name="sort">{sorts}</select></label>
<label>From<select name="from"><option value="">{season_label(1947)}</option>{so}</select></label>
<label>To<select name="to"><option value="">{season_label(CURRENT_SEASON)} to date</option><option value="{LAST_COMPLETE}">Completed seasons only</option>{so}</select></label>
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


def noas_note(s):
    """The seasons the no-All-Star board leaves out, worked out from the data on every build."""
    miss = B.honors_missing(s.d, s.help)
    if not miss:
        return ""
    if miss == list(range(miss[0], CURRENT_SEASON + 1)):
        what = f"{season_label(miss[0])} onward"
    else:
        what = ", ".join(season_label(y) for y in miss)
    return (f'<p class="note"><strong>{what} not counted yet: honors missing from the awards data.</strong> '
            'Those team-seasons are left out (not counted as "no All-Star teammate") until the awards file has them.</p>')


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
                        "labels": B.COL_LABEL, "noas": 1 if dfn.get("noas") else 0}, ensure_ascii=False, separators=(",", ":"))
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
{('<p class="note">' + e(dfn['explain']) + '</p>') if dfn.get('explain') else ''}
{noas_note(s) if dfn.get("noas") else ''}
<div class="tblwrap"><table id="board" class="tt board" data-board="{key}" data-up="{up}" data-def="{e(defjs)}" aria-labelledby="board-pop">
<thead><tr>{''.join(heads)}</tr></thead><tbody>{''.join(rows)}</tbody></table>
<p id="board-status" class="vh" role="status"></p></div>
<p><button type="button" id="board-more" class="more-btn"{' hidden' if len(ranked) <= 100 else ''}>Show 100 more</button></p>
<p class="note">Regular seasons {season_label(1947)} to {season_label(CURRENT_SEASON)}, games he played through {e(nice_date(s.through))}; "Completed seasons only" stops at {season_label(LAST_COMPLETE)}. One team per season for season counts (the team he played the most games for); a playoff trip or title also counts the team he finished the season with. <a href="../how-we-count.html">How we count</a>.</p>
<p class="more">Other career boards: {others}</p>
<script src="../assets/boards.js" defer></script>"""
    desc = dfn["desc"]
    og = f"{OG}list/{key}.png" if key in OG_LISTS else None
    return rel, page(rel, f"{dfn['title']} | HoopsMatic", desc, body, up, og=og)


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
        if st["g"] >= 3 and st["ow"] + st["ol"] >= 3:
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


def gap_table(s, rows, up, cap, desc_first=True):
    """Current-season with/without rows with both samples; filtered in the page by separate
    minimums for games played and missed (data-gp / data-gm), default 5 and 5."""
    trs = []
    for g, pid, st in rows:
        gm = st["ow"] + st["ol"]
        hid = " hidden" if st["g"] < 5 or gm < 5 else ""        # default minimums, 5 and 5
        trs.append(f'<tr data-gp="{st["g"]}" data-gm="{gm}"{hid}>' + "".join([
            td("Player", s.pic(pid, up, "sm") + " " + s.plink(pid, up), s.ids[pid]["name"]),
            td("Team", s.tlink(st["f"], CURRENT_SEASON), st["f"]),
            td("Gap", pp(g), fval(g), f"mono {cls_gap(g)}"),
            td("Games he played", f'{wl(st["w"], st["l"])} <span class="sub">{pct1(A.pct(st["w"], st["l"]))}, {st["g"]} g</span>', st["g"]),
            td("Games he missed", f'{wl(st["ow"], st["ol"])} <span class="sub">{pct1(A.pct(st["ow"], st["ol"]))}, {gm} g</span>', gm),
        ]) + "</tr>")
    heads = [th("Player", "text"), th("Team", "text"), th("Gap", sort="descending" if desc_first else "ascending",
             first="descending" if desc_first else "ascending"), th("Games he played"), th("Games he missed")]
    return sortable(cap, "", heads, trs, "minfilter")


def board_page(s, key):
    up = "../"
    gaps, movers, baseline = current_rows(s)
    through = s.cur["through"] if s.cur else None
    if key == "without-him":
        rel = "lists/winning-without-him.html"
        title = f"{season_label(CURRENT_SEASON)} with and without: team win rate in games he played vs missed"
        desc = (f"Every active player's {season_label(CURRENT_SEASON)} team record in the games he played and the games he "
                f"missed, with both samples and separate minimums. Updated every morning; games through "
                f"{nice_date(through) if through else 'N/A'}.")
        pos = [x for x in gaps if x[0] > 0]
        neg = sorted([x for x in gaps if x[0] < 0], key=lambda x: x[0])
        body = f"""<header><h1>{e(title)}</h1><p class="subtitle">{e(desc)}</p></header>
<form class="filters" id="minf"><label>Min games played<input name="mp" type="number" min="1" value="5" inputmode="numeric"></label>
<label>Min games missed<input name="mm" type="number" min="1" value="5" inputmode="numeric"></label>
<span class="note">Rows below both minimums are hidden. The homepage uses 8 and 8.</span></form>
<p class="note">Gap = team win % in games he played minus in games he missed, in percentage points (pp). This is a different unit from on/off per 100 possessions (<a href="on-off-movers.html">last 30 days board</a>). It is a team record: it does not say what he caused.</p>
<section><h2 id="cap-up">Higher win rate in games he played</h2>{gap_table(s, pos, up, "cap-up")}</section>
<section><h2 id="cap-down">Higher win rate in games he missed</h2>{gap_table(s, neg, up, "cap-down", False)}</section>"""
    else:
        rel = "lists/on-off-movers.html"
        lab = "the rest of the season" if baseline == "earlier" else "2025-26"
        title = f"Last 30 days movers: on/off per 100, {season_label(CURRENT_SEASON)}"
        desc = (f"Biggest change in on/off per 100 possessions over the last 30 days compared with {lab}. "
                f"From Ramiro's lineup data, updated every morning; games through {nice_date(through) if through else 'N/A'}.")
        note = ("" if baseline == "earlier" else
                "<p class=\"note\">Early in the season the last 30 days are the whole season, so the comparison is "
                "with his 2025-26 on/off (any team). It switches to the earlier part of this season once enough "
                "games are played.</p>")
        body = f"""<header><h1>{e(title)}</h1><p class="subtitle">{e(desc)}</p></header>{note}
<p class="note">On/off = team net points per 100 possessions with him on the floor minus with him off, in the games he played: possession-based, a different unit from the win-rate gaps in pp on the <a href="winning-without-him.html">with and without board</a>. Minimum 250 on-court possessions in the last 30 days.</p>
<section><h2>Biggest risers</h2>{rows_html(s, mover_items(s, movers[:TOP_N], up, baseline), up)}</section>
<section><h2>Biggest fallers</h2>{rows_html(s, mover_items(s, movers[::-1][:TOP_N], up, baseline), up)}</section>"""
    return rel, page(rel, f"{title} | HoopsMatic", desc, body, up)


# ---------------------------------------------------------------------------
# Today in Team Success: daily lead, permalinks (noindex) and archive (indexed)
# ---------------------------------------------------------------------------
def stories(s):
    return load_json(os.path.join(DATA, "stories.json"), {"stories": []})["stories"]


def story_html(s, st, up, heading_level=2, permalink=True):
    """The story block: headline as normal text under the section heading (no kicker)."""
    if not st:
        return ""
    body = " ".join(e(x) for x in st["body"])
    links = [f'<a class="next" href="{up}{e(st["link"]["href"])}">{e(st["link"]["text"])}</a>']
    if st.get("more"):
        links.append(f'<a href="{up}{e(st["more"]["href"])}">{e(st["more"]["text"])}</a>')
    sup = "".join(f'<li><a href="{up}{e(x["href"])}">{e(x["text"])}</a></li>' for x in st.get("supporting", []))
    perma = (f' · <a href="{up}stories/{st["date"]}.html">Permalink and share image</a>' if permalink else "")
    return f"""<p class="story-head">{e(st['headline'])}</p>
<p class="story-body">{body}</p>
<p class="note">{e(nice_date(st['date']))}. Data through {e(nice_date(st['cutoff']))} (last game in the nightly data){perma}.</p>
<p class="story-links">{' '.join(links)}</p>
{('<ul class="takes">' + sup + '</ul>') if sup else ''}"""


def story_pages(s):
    out = []
    all_st = stories(s)
    for i, st in enumerate(all_st):
        up = "../"
        rel = f"stories/{st['date']}.html"
        nav = []
        if i + 1 < len(all_st):
            nav.append(f'<a href="{all_st[i + 1]["date"]}.html">Previous story</a>')
        nav.append('<a href="index.html">All stories</a>')
        if i > 0:
            nav.append(f'<a href="{all_st[i - 1]["date"]}.html">Next story</a>')
        img = st.get("img")
        og = BASE + img if img and os.path.exists(os.path.join(ROOT, img)) else None
        body = f"""<header><h1>Today in Team Success: {e(nice_date(st['date']))}</h1></header>
{story_html(s, st, up, permalink=False)}
{('<p><img class="storyimg" src="' + up + e(img) + '" alt="' + e(st['headline']) + '" width="1200" height="630" loading="lazy"></p>') if og else ''}
<p class="seasonnav">{' · '.join(nav)}</p>"""
        out.append((rel, page(rel, f"{st['headline']} ({nice_date(st['date'])}) | HoopsMatic",
                              " ".join(st["body"])[:300], body, up, robots="noindex, follow", og=og)))
    items = "".join(f'<li><a href="{x["date"]}.html"><strong>{e(x["headline"])}</strong></a>'
                    f'<span class="det">{e(nice_date(x["date"]))}. Data through {e(nice_date(x["cutoff"]))}.</span></li>'
                    for x in all_st)
    body = f"""<header><h1>Today in Team Success: every story</h1>
<p class="subtitle">One dated story each morning from the nightly data, newest first. Each is built from templates; the rules are published with the methodology.</p></header>
<ul class="lists seasons">{items or '<li>No stories yet.</li>'}</ul>"""
    out.append(("stories/index.html", page("stories/index.html", "Today in Team Success: story archive | HoopsMatic",
                                           "Every daily Team Success story: career milestones, tonight's matchups, team "
                                           "records during absences and historical comparisons, with the data cutoff.", body, "../")))
    return out


def prow(s, pid, up, sub="", num="", rk=None, cls=""):
    """H2H entity row: rank, face, name over a small mono line, the number at the right."""
    r = f'<span class="rk">{rk}</span>' if rk is not None else ""
    return (f'<li>{r}{s.pic(pid, up, "")}<span class="who">{s.plink(pid, up)}<small>{sub}</small></span>'
            f'<span class="num {cls}">{num}</span></li>')


def board_preview(s, key, up, n=5, title=None):
    ranked, sort, mins = s.board_default[key]
    dfn = B.BOARDS[key]
    items = []
    for r, tied, m in ranked[:n]:
        if key in ("career-wins", "no-allstar-teammate"):
            num, sub = f"{m['w']:,}", f"{wl(m['w'], m['l'])} · {pct1(m['pct'])}"
        elif key == "wins-minus-losses":
            num, sub = signed(m["wl"]), f"{wl(m['w'], m['l'])} · {m['gp']:,} games"
        elif key == "titles":
            num, sub = str(m["titles"]), ", ".join(season_label(y) for y in m["years"][:3]) + (" ..." if len(m["years"]) > 3 else "")
        else:
            num, sub = "", ""
        items.append(prow(s, m["pid"], up, sub, num, ("T-" if tied else "") + str(r)))
    return (f'<div class="box"><div class="boxhead">{e(title or dfn["h1"])} <a href="{up}lists/{key}.html">full board</a></div>'
            f'<ul class="rows">{"".join(items)}</ul></div>')


def list_preview(s, up, title, href, rows):
    return (f'<div class="box"><div class="boxhead">{e(title)} <a href="{up}{href}">full list</a></div>'
            f'<ul class="rows">{"".join(rows)}</ul></div>')


def featured_pair(s, up, date):
    hp = s.help
    pairs = sorted({tuple(sorted((a, b))) for a, lst in hp["peers"].items() for b, dist in lst
                    if dist < 100 and hp["avg"].get(a, {}).get("g", 0) >= 800 and hp["avg"].get(b, {}).get("g", 0) >= 800})
    if not pairs:
        return ""
    k = (dt.date.fromisoformat(date).toordinal() + 2) % len(pairs)
    a, b = pairs[k]
    ca, cb = compare_summary(s, a), compare_summary(s, b)

    def cell(lab, va, vb, ta, tb, low=False):
        la = "la" if (va < vb if low else va > vb) else ""
        lb = "lb" if (vb < va if low else vb > va) else ""
        return f'<div><span class="l">{lab}</span><span class="v"><b class="{la}">{ta}</b><i>·</i><b class="{lb}">{tb}</b></span></div>'
    cells = "".join([
        cell("Record in his games", ca["pct"], cb["pct"], wl(ca["w"], ca["l"]), wl(cb["w"], cb["l"])),
        cell("Win %", ca["pct"], cb["pct"], pct1(ca["pct"]), pct1(cb["pct"])),
        cell("Average finish (of 30)", round(ca["adj30"], 1), round(cb["adj30"], 1), f"{ca['adj30']:.1f}", f"{cb['adj30']:.1f}", low=True),
        cell("Titles", ca["titles"], cb["titles"], str(ca["titles"]), str(cb["titles"])),
        cell("Help per season", ca["help"] or 0, cb["help"] or 0, f"{ca['help']:.1f}", f"{cb['help']:.1f}", low=True),
    ])
    rel = compare_rel(ca["slug"], cb["slug"])
    return f"""<a class="h2hrow" href="{up}{rel}"><span class="side">{s.pic(a, up)}<span class="nm">{e(ca['name'])}</span><span class="vs">{e(ca['span'])}</span></span>
<span class="vs">vs</span><span class="side">{s.pic(b, up)}<span class="nm">{e(cb['name'])}</span><span class="vs">{e(cb['span'])}</span></span>
<span class="h2hcells">{cells}</span></a>
<p class="note">Same era, similar teammate help. Lower help and lower finish numbers are tinted as the leader. Tap for the two careers season by season.</p>"""


def live_season_page(s):
    """seasons/2026-27.html: the season in progress, every team by win % to date (not a final finish)."""
    up = "../"
    sy = CURRENT_SEASON
    rel = f"seasons/{season_label(sy)}.html"
    ts = sorted((t for t in s.d.teams.values() if t["s"] == sy), key=lambda t: (-t["pct"], -t["w"], t["name"]))
    rows = []
    for i, t in enumerate(ts):
        mates = sorted(((x["g"], pid) for pid, sts in (s.cur or {}).get("players", {}).items() for x in sts if x["f"] == t["f"]),
                       reverse=True)[:3]
        who = ", ".join(s.plink(pid, up) for g, pid in mates if pid in s.ids)
        rows.append(f'<tr id="t-{e(t["f"])}">' + "".join([
            td("Rank", str(i + 1), i + 1, "mono"), td("Team", s.tlink(t["f"], sy), t["name"]),
            td("W–L", wl(t["w"], t["l"]), t["w"] - t["l"], "mono"),
            td("Win %", pct1(t["pct"]), t["pct"], "mono" + (" best" if i == 0 else (" worst" if i == len(ts) - 1 else ""))),
            td("Most games", who or "N/A")]) + "</tr>")
    heads = [th("Rank", first="ascending"), th("Team", "text"), th("W–L"), th("Win %", sort="descending"),
             '<th scope="col">Most games</th>']
    body = f"""<header><h1>{season_label(sy)} so far: every team by win %</h1>
<p class="subtitle">Standings to date, games through {e(nice_date(s.through))}. Not a final finish: that needs the playoffs.</p></header>
{sortable("cap-live", "", heads, rows, "board")}
<p class="seasonnav"><a href="{season_label(LAST_COMPLETE)}.html">{season_label(LAST_COMPLETE)} final standings</a> · <a href="index.html">All seasons</a></p>"""
    return rel, page(rel, f"{season_label(sy)} NBA standings so far, all 30 teams | HoopsMatic",
                     f"Every NBA team in {season_label(sy)} by win % to date, games through {nice_date(s.through)}, "
                     "updated every morning.", body, up)


def hub(s):
    up = ""
    gaps, movers, baseline = current_rows(s)
    st = stories(s)
    through = s.through
    # 1. Today in Team Success: the story, its share image, the two supporting items as rows
    today = ""
    if st:
        x = st[0]
        img = x.get("img")
        pic = (f'<img class="storyimg" src="{e(img)}" alt="{e(x["headline"])}" width="1200" height="630" loading="lazy">'
               if img and os.path.exists(os.path.join(ROOT, img)) else "")
        by_slug = {v["slug"]: k for k, v in s.ids.items()}
        sup = []
        for y in x.get("supporting", []):
            m_ = re.search(r"compare/([a-z0-9-]+?)--([a-z0-9-]+)\.html", y["href"]) or re.search(r"player/([a-z0-9-]+)\.html", y["href"])
            slugs = list(m_.groups()) if m_ else []
            faces = "".join(s.pic(by_slug[g], up, "sm") for g in slugs[:2] if g in by_slug)
            sup.append(f'<li><span class="rf">{faces}</span><span class="who"><a href="{e(y["href"])}">{e(y["text"])}</a></span></li>')
        lead_faces = "".join(s.pic(by_slug[g], up, "md") for g in x.get("players", [])[:1] if g in by_slug)
        today = f"""<div class="today"><div class="story"><div>
<div class="ent">{lead_faces}<p class="story-head">{e(x['headline'])}</p></div>
<p class="story-body">{' '.join(e(b) for b in x['body'])}</p>
<p class="note">{e(nice_date(x['date']))} · data through {e(nice_date(x['cutoff']))} · <a href="stories/{x['date']}.html">permalink</a> · <a href="stories/index.html">earlier stories</a></p>
<p class="story-links"><a class="next" href="{e(x['link']['href'])}">{e(x['link']['text'])}</a>{(' <a class="next" href="' + e(x['more']['href']) + '">' + e(x['more']['text']) + '</a>') if x.get('more') else ''}</p></div>
{pic}</div>{('<ul class="rows">' + ''.join(sup) + '</ul>') if sup else ''}</div>"""

    def gap_rows(rows):
        out = []
        for g, pid, t in rows:
            if pid not in s.ids:
                continue
            gm = t["ow"] + t["ol"]
            out.append(prow(s, pid, up, f'{s.logo(t["f"], CURRENT_SEASON, up)}{wl(t["w"], t["l"])} in {t["g"]} played · '
                            f'{wl(t["ow"], t["ol"])} in {gm} missed', f'{pp(g)}<small>points</small>', None, "up" if g > 0 else "down"))
        return out
    ok = [x for x in gaps if x[2]["g"] >= 5 and x[2]["ow"] + x[2]["ol"] >= 5]
    missed = sorted([x for x in ok if x[0] < 0], key=lambda x: x[0])[:5]
    played = [x for x in ok if x[0] > 0][:5]
    mov = []
    for ch, pid, t, now, base in movers[:5]:
        if pid in s.ids:
            mov.append(prow(s, pid, up, f'{s.logo(t["f"], CURRENT_SEASON, up)}{fnum(now)} last 30 days · {fnum(base)} before',
                            f'{fnum(ch)}<small>per 100</small>', None, "up" if ch > 0 else "down"))
    # current standings, all teams
    ts = sorted((t for t in s.d.teams.values() if t["s"] == CURRENT_SEASON), key=lambda t: (-t["pct"], -t["w"], t["name"]))
    trows = "".join(f'<li><span class="rk">{i + 1}</span><span class="who"><span class="tmn">{s.tlink(t["f"], CURRENT_SEASON)}</span></span>'
                    f'<span class="num">{wl(t["w"], t["l"])}<small>{pct1(t["pct"])}</small></span></li>' for i, t in enumerate(ts))
    half = (len(ts) + 1) // 2
    tl = [f'<li><span class="rk">{i + 1}</span><span class="who">{s.tlink(t["f"], CURRENT_SEASON)}</span>'
          f'<span class="num">{wl(t["w"], t["l"])}<small>{pct1(t["pct"])}</small></span></li>' for i, t in enumerate(ts)]
    # leaderboard previews
    bl = A.list_bad_luck(s.d, 1947, 1)[:5]
    bad = [prow(s, r["pid"], up, f"{r['n']} seasons · teams {pct1(r['avg'])} · accolades {r['acc']:g}", f"{r['idx']:.1f}", i + 1)
           for i, r in enumerate(bl)]
    wt = A.list_flag(s.d, "worst", 1947, 1)[:5]
    worst = [prow(s, r["pid"], up, ", ".join(season_label(x["s"]) for x in r["seasons"][:3]) + (" ..." if r["n"] > 3 else ""),
                  str(r["n"]), i + 1) for i, r in enumerate(wt)]
    az = " ".join(f'<a href="players/{c}.html">{c.upper()}</a>' for c in "abcdefghijklmnopqrstuvwxyz")
    feat = featured_pair(s, up, st[0]["date"] if st else dt.date.today().isoformat())
    body = f"""<header><h1>Team Success</h1>
<p class="subtitle">How much every NBA player won and how much help he had. Records in his games, final finishes, teammate help, every opponent, since 1946-47. Games through {e(nice_date(through))}.</p></header>
<section><h2>Today in Team Success</h2>{today or '<p class="note">The first story appears after the next nightly update.</p>'}</section>
<section><h2>{season_label(CURRENT_SEASON)} so far: with and without</h2>
<div class="dgrid"><div class="box"><div class="boxhead">Higher win rate in games he missed <a href="lists/winning-without-him.html">full board</a></div><ul class="rows">{''.join(gap_rows(missed))}</ul></div>
<div class="box"><div class="boxhead">Higher win rate in games he played <a href="lists/winning-without-him.html">full board</a></div><ul class="rows">{''.join(gap_rows(played))}</ul></div></div>
<p class="note">Team win % in the games he played minus in the games he missed, in points; 5+ games each side. A team record, not what he caused.</p></section>
<section><h2>Last 30 days: on/off movers</h2>
<div class="box"><div class="boxhead">Biggest change in on/off per 100 possessions <a href="lists/on-off-movers.html">full board</a></div><ul class="rows">{''.join(mov)}</ul></div>
<p class="note">Last 30 days vs {'earlier this season' if baseline == 'earlier' else season_label(LAST_COMPLETE)}. Possession-based: a different unit from the win-rate gaps.</p></section>
<section><h2>{season_label(CURRENT_SEASON)} standings</h2>
<div class="dgrid"><div class="box"><ul class="rows">{''.join(tl[:half])}</ul></div><div class="box"><ul class="rows">{''.join(tl[half:])}</ul></div></div>
<p class="note">By win % to date. <a href="seasons/{season_label(CURRENT_SEASON)}.html">All teams with their most-used players</a> · <a href="seasons/{season_label(LAST_COMPLETE)}.html">{season_label(LAST_COMPLETE)} final standings</a></p></section>
<section><h2>Leaderboards</h2>
<div class="dgrid three">{board_preview(s, 'career-wins', up)}{board_preview(s, 'wins-minus-losses', up)}{board_preview(s, 'titles', up)}
{board_preview(s, 'no-allstar-teammate', up)}{list_preview(s, up, 'Bad Luck Index', 'lists/bad-luck.html', bad)}{list_preview(s, up, 'Played for the worst team the most', 'lists/worst-team.html', worst)}</div>
<p class="note">Career boards count {season_label(CURRENT_SEASON)} games to date. <a href="lists/winning-seasons.html">Winning seasons</a> · <a href="lists/playoff-trips.html">Playoff trips</a> · <a href="lists/average-finish.html">Average finish</a> · <a href="lists/gap-career.html">With vs without</a> · <a href="lists/low-help-all-stars.html">Low-help All-Stars</a> · <a href="seasons/index.html">Every season's standings</a></p></section>
<section><h2>Comparison of the day</h2>{feat}</section>
<p class="az">Players A-Z: {az}</p>"""
    desc = ("How much every NBA player won and how much help he had: team records in his games, final NBA finishes, "
            "teammate help, every opponent and a daily story, since 1946-47.")
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
        items.append(f"<li>{nm}, {season_label(sy)}, {s.tlink(f, sy, full=True)}: {len(dates)} "
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
        teams = " and ".join(s.tlink(f, sy, full=True) for f in sorted(fs, key=lambda f: -fs[f]))
        ex.append(f"{season_label(sy)} rows that put {s.plink(pid, '')} on the {teams}")
    examples_html = (" (for example, " + "; ".join(ex) + ")") if ex else ""
    removed_html = (f'<details><summary>{dropped} removed appearances, by player</summary><ul>{"".join(items)}</ul></details>'
                    if items else "")
    size_txt = ", ".join(f"{season_label(int(y))}: {n}" for y, n in sorted(sizes.items(), key=lambda x: int(x[0]))
                         if int(y) in (1947, 1950, 1951, 1954, 1962, 1967, 1968, 1977, 1981, 1989, 1996, 2005))
    body = f"""<header><h1>How we count</h1><p class="subtitle">The rules behind every number in Team Success, traced to the data and code that produce them.</p></header>
<section class="prose">
<h2>What each page covers</h2>
<p><strong>Career records</strong> (W{EN}L, win %, W {MINUS} L, with and without) count every regular season from {season_label(1947)} through {season_label(CURRENT_SEASON)}, with {season_label(CURRENT_SEASON)} games through {e(nice_date(through))}, the last game in the nightly data; the nightly job recomputes them. <strong>Season counts and finishes</strong> (winning seasons, playoff trips, titles, final NBA finish, teammate help) use completed seasons, {season_label(1947)} through {season_label(LAST_COMPLETE)}, because a season in progress has no final finish. The career boards have a "Completed seasons only" option.</p>
<h2>Formats</h2>
<p>Records use an en dash (706{EN}366). Win rates read 65.9%. With and without is shown as the two win rates, "65.9% with him · 39.9% without", and the gap as "26.0 points higher": the difference between the two win percentages (percentage points), worked out from the unrounded rates. It is not a relative change: +26.0 does not mean 26% more wins. Possession-based on/off is in points per 100 possessions, a different unit, and is always labeled that way. An empty sample (no games) shows N/A, never 0.0%.</p>
<h2>Final NBA finish</h2>
<p>Each team-season's final finish is the RNK column of our standings table. The champion is #1 and the runner-up #2; the other teams follow by playoff round reached, then by regular-season win %. Teams with the same round and win % share a rank. We re-derived every RNK from that rule: {len(rk.get('mismatches', [])) if rk else 'N/A'} of {sum(sizes.values()):,} team-seasons differ, and {rk.get('tied_rows', 0):,} share a rank.</p>
<p>A finish always comes with that season's league size: "#8 of 30". League sizes changed a lot ({e(size_txt)}; 30 since 2004-05), so the league-size-adjusted finish puts every season on one scale: (rank {MINUS} 1) / (teams {MINUS} 1), where 0 is the champion and 1 is last. <strong>Average final finish</strong> is shown on that scale by default, as a 30-team equivalent: 1 + adjusted × 29, one decimal ("4.1 of 30, adjusted for league size"), so 3rd of 9 teams in 1964-65 counts as 8.25 of 30, not 3rd. The raw average of the ranks is the second view on the board and the small line on the player card. Live standings and conference seeds are labeled as such and never mixed with the final finish.</p>
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
<p>With him: <span class="mono">{jw}{EN}{jl}</span> in {jw + jl:,} games ({pct1(jw / (jw + jl)) if jw + jl else 'N/A'}), wins minus losses <span class="mono">{signed(jw - jl)}</span>. Without him, team-season window: <span class="mono">{wl(ow, ol)}</span> in {ow + ol} games ({pct1(ow / (ow + ol)) if ow + ol else 'N/A'}), <span class="mono">{pts_txt((jw / (jw + jl)) - (ow / (ow + ol))) if ow + ol else 'N/A'}</span> with him. Without him, appearance span: <span class="mono">{wl(sw, sl)}</span> in {sw + sl} games ({pct1(sw / (sw + sl)) if sw + sl else 'N/A'}), <span class="mono">{pts_txt((jw / (jw + jl)) - (sw / (sw + sl))) if sw + sl else 'N/A'}</span> with him.</p>
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
        tms = []
        for x in sorted(st, key=lambda x: x["s"]):
            if x["g"] and x["s"] <= LAST_COMPLETE and s.d.team(x["f"], x["s"]):
                nm_ = s.d.team(x["f"], x["s"])["name"]
                if nm_ not in tms:
                    tms.append(nm_)
        if s.cur and pid in s.cur["players"]:
            for x in s.cur["players"][pid]:
                from common import franchise_name
                nm_ = franchise_name(x["f"], CURRENT_SEASON) or x["f"]
                if nm_ not in tms:
                    tms.append(nm_)
        tt = ", ".join(tms[:3]) + (f" +{len(tms) - 3}" if len(tms) > 3 else "")
        hsf = v.get("hs") if v.get("hs") and os.path.exists(os.path.join(ROOT, "assets", "hs", v["hs"])) else ""
        rows.append([v["name"], v["slug"], season_label(ys[0]) if ys else "", season_label(ys[-1]) if ys else "", hsf, tt])
    rows.sort(key=lambda r: r[0])
    return "assets/players.json", json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def sitemap(pages_rel):
    path = os.path.join(DATA, "sitemap_lastmod.json")
    lm = load_json(path, {})
    today = dt.date.today().isoformat()
    urls = []
    # noindex pages stay out of the sitemap: daily story permalinks (stories/<date>.html)
    pages_rel = [r for r in pages_rel if not re.match(r"stories/\d{4}-\d{2}-\d{2}\.html$", r)]
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
    for d in ("", "player", "lists", "players", "seasons", "stories"):
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
        write(*comparison_rules_page(s))
        for rel, txt in cohort_pages(s):
            write(rel, txt)
        done = set()
        for pid, lst in s.help["peers"].items():
            for q, dist in lst:
                rel = compare_rel(s.ids[pid]["slug"], s.ids[q]["slug"])
                if rel not in done:
                    done.add(rel)
                    write(*compare_page(s, pid, q, dist))
    write(*live_season_page(s))
    write("assets/board.json", json.dumps(s.board_data, ensure_ascii=False, separators=(",", ":")))
    write(*hub(s))
    for rel, txt in story_pages(s):
        write(rel, txt)
    for rel, txt in az_pages(s):
        write(rel, txt)
    write(*search_index(s))
    if args.current:
        targets = list(s.cur["players"]) if s.cur else []
    else:
        targets = [p for p in s.ids if s.has_page(p)]
    for pid in targets:
        write(*player_page(s, pid))
        if s.has_hist(pid):
            write(*player_games_json(s, pid))
    write(*team_names_json(s))
    for rel, txt in card_files(s):
        write(rel, txt)
    # robots + sitemap
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n")
    write(".nojekyll", "")
    sitemap(all_page_paths())
    print(f"wrote {len(written)} files, {skipped} unchanged")
    if s.lead_rules:
        print("player leads by rule:", dict(sorted(s.lead_rules.items())))


if __name__ == "__main__":
    main()

# (c) 2026 HoopsMatic. All rights reserved.
# Team Success: shared helpers (paths, names, franchise eras, slugs).
"""Shared helpers for the Team Success data pipeline and site build."""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
# Source checkouts live outside git (see scripts/fetch_sources.sh). Override with TS_SRC.
SRC = os.environ.get("TS_SRC", os.path.join(ROOT, "_src"))

FIRST_SEASON = 1947
LAST_COMPLETE = 2026          # last season in data/team_standings.csv (2025-26)
CURRENT_SEASON = 2027         # 2026-27, in progress
RAMIRO_FIRST = 1997           # 1996-97, first season of Ramiro's lineup data
MODERN_FROM = 1977            # "since 1976-77" era toggle


def season_label(sy):
    """Ending year -> '1996-97'."""
    sy = int(sy)
    return f"{sy - 1}-{str(sy)[-2:]}"


def norm_name(s):
    """Lowercase ASCII, no accents/punctuation, single spaces."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


SUFFIX_RE = re.compile(r"\s+(jr|sr|ii|iii|iv|v)$")


def base_name(s):
    """Normalized name without '(1975)' birth-year tags and Jr/Sr/II suffixes."""
    s = re.sub(r"\(\s*\d{4}\s*\)", "", s or "")
    n = norm_name(s)
    n = SUFFIX_RE.sub("", n)
    return n


def slugify(name):
    """Career Map's slug rule: 'Nikola Jokić' -> 'nikola-jokic'."""
    s = "".join(c for c in unicodedata.normalize("NFKD", name or "")
                if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or "player"


# ---------------------------------------------------------------------------
# Franchise eras. nba-boxscores uses NBA.com era tricodes; team_standings.csv and
# RS-Stats.csv use the CURRENT franchise code (HoopsHype tricode). Each row:
# (era code in nba-boxscores, first season, last season, franchise code, real name).
# Seasons are ending years. Defunct franchises keep their own franchise code.
# ---------------------------------------------------------------------------
ERAS = [
    ("AND", 1950, 1950, "AND", "Anderson Packers"),
    ("ATL", 1969, 9999, "ATL", "Atlanta Hawks"),
    ("BAL", 1948, 1954, "BAL", "Baltimore Bullets"),
    ("BKN", 2013, 9999, "BKN", "Brooklyn Nets"),
    ("BLT", 1964, 1973, "WAS", "Baltimore Bullets"),
    ("BOM", 1947, 1950, "STB", "St. Louis Bombers"),
    ("BOS", 1947, 9999, "BOS", "Boston Celtics"),
    ("BUF", 1971, 1978, "LAC", "Buffalo Braves"),
    ("CAP", 1974, 1974, "WAS", "Capital Bullets"),
    ("CHA", 2005, 2014, "CHA", "Charlotte Bobcats"),
    ("CHA", 2015, 9999, "CHA", "Charlotte Hornets"),
    ("CHH", 1989, 2002, "CHA", "Charlotte Hornets"),
    ("CHI", 1967, 9999, "CHI", "Chicago Bulls"),
    ("CHP", 1962, 1962, "WAS", "Chicago Packers"),
    ("CHS", 1947, 1950, "CHS", "Chicago Stags"),
    ("CHZ", 1963, 1963, "WAS", "Chicago Zephyrs"),
    ("CIN", 1958, 1972, "SAC", "Cincinnati Royals"),
    ("CLE", 1971, 9999, "CLE", "Cleveland Cavaliers"),
    ("CLR", 1947, 1947, "CLR", "Cleveland Rebels"),
    ("DAL", 1981, 9999, "DAL", "Dallas Mavericks"),
    ("DEF", 1947, 1947, "DTF", "Detroit Falcons"),
    ("DEN", 1977, 9999, "DEN", "Denver Nuggets"),
    ("DET", 1958, 9999, "DET", "Detroit Pistons"),
    ("DN", 1950, 1950, "DNN", "Denver Nuggets"),
    ("FTW", 1949, 1957, "DET", "Fort Wayne Pistons"),
    ("GOS", 1972, 1996, "GSW", "Golden State Warriors"),
    ("GSW", 1997, 9999, "GSW", "Golden State Warriors"),
    ("HOU", 1972, 9999, "HOU", "Houston Rockets"),
    ("HUS", 1947, 1947, "TOH", "Toronto Huskies"),
    ("IND", 1977, 9999, "IND", "Indiana Pacers"),
    ("INO", 1950, 1953, "INO", "Indianapolis Olympians"),
    ("JET", 1949, 1949, "INJ", "Indianapolis Jets"),
    ("KCK", 1973, 1975, "SAC", "Kansas City-Omaha Kings"),
    ("KCK", 1976, 1985, "SAC", "Kansas City Kings"),
    ("LAC", 1985, 2015, "LAC", "Los Angeles Clippers"),
    ("LAC", 2016, 9999, "LAC", "LA Clippers"),
    ("LAL", 1961, 9999, "LAL", "Los Angeles Lakers"),
    ("MEM", 2002, 9999, "MEM", "Memphis Grizzlies"),
    ("MIA", 1989, 9999, "MIA", "Miami Heat"),
    ("MIH", 1952, 1955, "ATL", "Milwaukee Hawks"),
    ("MIL", 1969, 9999, "MIL", "Milwaukee Bucks"),
    ("MIN", 1990, 9999, "MIN", "Minnesota Timberwolves"),
    ("MNL", 1949, 1960, "LAL", "Minneapolis Lakers"),
    ("NJN", 1978, 2012, "BKN", "New Jersey Nets"),
    ("NOH", 2003, 2005, "NOP", "New Orleans Hornets"),
    ("NOH", 2008, 2013, "NOP", "New Orleans Hornets"),
    ("NOJ", 1975, 1979, "UTA", "New Orleans Jazz"),
    ("NOK", 2006, 2007, "NOP", "New Orleans/Oklahoma City Hornets"),
    ("NOP", 2014, 9999, "NOP", "New Orleans Pelicans"),
    ("NYK", 1947, 9999, "NYK", "New York Knicks"),
    ("NYN", 1977, 1977, "BKN", "New York Nets"),
    ("OKC", 2009, 9999, "OKC", "Oklahoma City Thunder"),
    ("ORL", 1990, 9999, "ORL", "Orlando Magic"),
    ("PHI", 1997, 9999, "PHI", "Philadelphia 76ers"),
    ("PHL", 1964, 1996, "PHI", "Philadelphia 76ers"),
    ("PHW", 1947, 1962, "GSW", "Philadelphia Warriors"),
    ("PHX", 1969, 9999, "PHX", "Phoenix Suns"),
    ("PIT", 1947, 1947, "PIT", "Pittsburgh Ironmen"),
    ("POR", 1971, 9999, "POR", "Portland Trail Blazers"),
    ("PRO", 1947, 1949, "PRO", "Providence Steamrollers"),
    ("ROC", 1949, 1957, "SAC", "Rochester Royals"),
    ("SAC", 1986, 9999, "SAC", "Sacramento Kings"),
    ("SAN", 1977, 1996, "SAS", "San Antonio Spurs"),
    ("SAS", 1997, 9999, "SAS", "San Antonio Spurs"),
    ("SDC", 1979, 1984, "LAC", "San Diego Clippers"),
    ("SDR", 1968, 1971, "HOU", "San Diego Rockets"),
    ("SEA", 1968, 2008, "OKC", "Seattle SuperSonics"),
    ("SFW", 1963, 1971, "GSW", "San Francisco Warriors"),
    ("SHE", 1950, 1950, "SHE", "Sheboygan Red Skins"),
    ("STL", 1956, 1968, "ATL", "St. Louis Hawks"),
    ("SYR", 1950, 1963, "PHI", "Syracuse Nationals"),
    ("TCB", 1950, 1951, "ATL", "Tri-Cities Blackhawks"),
    ("TOR", 1996, 9999, "TOR", "Toronto Raptors"),
    ("UTA", 1997, 9999, "UTA", "Utah Jazz"),
    ("UTH", 1980, 1996, "UTA", "Utah Jazz"),
    ("VAN", 1996, 2001, "MEM", "Vancouver Grizzlies"),
    ("WAS", 1947, 1951, "WSC", "Washington Capitols"),
    ("WAS", 1975, 1997, "WAS", "Washington Bullets"),
    ("WAS", 1998, 9999, "WAS", "Washington Wizards"),
    ("WAT", 1950, 1950, "WAT", "Waterloo Hawks"),
]

# Franchise names that are not one of today's 30 (no Career Map team page).
DEFUNCT = {"AND", "BAL", "CHS", "CLR", "DNN", "DTF", "INJ", "INO", "PIT", "PRO",
           "SHE", "STB", "TOH", "WAT", "WSC"}

# Box score name -> RS-Stats / Career Map name, where the two sources disagree.
NAME_ALIASES = {
    "Enes Freedom": "Enes Kanter",
    "Timothe Luwawu-Cabarrot": "Timothe Luwawu",
    "Ron Sobie": "Ron Sobiezczyk",
    "Ha Ha": "Ha Seung-Jin",
    "Nigel Hayes-Davis": "Nigel Hayes",
    "Horacio Llamas": "Horacio Llamas Grey",
    "Sergei Monia": "Sergey Monya",
    "Charlie Shipp": "Charley Shipp",
}

# team_standings.csv uses BRK for Brooklyn in 2024-25 and 2025-26.
STANDINGS_CODE_FIX = {"BRK": "BKN"}


def era_lookup(code, season):
    """(era code, season) -> (franchise, name) or None."""
    for c, a, b, f, n in ERAS:
        if c == code and a <= season <= b:
            return f, n
    return None


def franchise_name(franchise, season):
    """The franchise's real name in that season, from any era row."""
    for c, a, b, f, n in ERAS:
        if f == franchise and a <= season <= b:
            return n
    return None


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path, obj, compact=True):
    """Write JSON deterministically; returns True if the file changed."""
    if compact:
        txt = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        txt = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1)
    txt += "\n"
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
    if old == txt:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return True


def pct(w, l):
    """Win % = W / (W + L); None when no games."""
    return (w / (w + l)) if (w + l) else None


SIXTY_PACE = 60 / 82   # .7317: a 60-win pace

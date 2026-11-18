# (c) 2026 HoopsMatic. All rights reserved.
# Team Success nightly current-season update. Fingerprint: hm-ts-7f3a91c2-current
"""Pull ONLY the current season and write data/current.json (+ any new headshots).

Sources (public, no keys):
  - Ramiro's 2026-27 Parquet files: pbp (game dates + final scores), lineup_stats (who was on
    the floor, on/off, starters), possessions (close games).
  - aderoa/nba-boxscores data/<season>/games.ndjson + boxscores.ndjson, used for results and
    appearances as soon as that season exists there (it does not yet on 2026-11-18).
Writes data/current.json only when something changed. Prints CHANGED or UNCHANGED.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (CURRENT_SEASON, DATA, ROOT, SRC, dump_json, era_lookup, load_json,  # noqa: E402
                    slugify)
import build_history as bh  # noqa: E402
from fetch_ramiro import fetch  # noqa: E402

BOX_RAW = "https://raw.githubusercontent.com/aderoa/nba-boxscores/main/data/{s}/{f}"
PBP_URL = "https://github.com/ramirobentes/nba_data/releases/download/pbp/pbp_regular_{s}.parquet"
HS_LIST = ("https://raw.githubusercontent.com/jsierrahoopshype/nba-headshots/main/"
           "players/headshots/face-fill/.hashes.json")
HS_FILE = ("https://raw.githubusercontent.com/jsierrahoopshype/nba-headshots/main/"
           "players/headshots/face-fill/{f}")
HS_DIR = os.path.join(ROOT, "assets", "hs")
NAME_RE = re.compile(r"(\d+) ([^,]+)")


def get(url, timeout=120):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
    return None


def games_from_boxscores(sy):
    """Use nba-boxscores when it has the season. Returns (games, appearances) or None."""
    g_raw = get(BOX_RAW.format(s=sy, f="games.ndjson"))
    b_raw = get(BOX_RAW.format(s=sy, f="boxscores.ndjson"))
    if not g_raw or not b_raw:
        return None
    games = {}
    for line in g_raw.decode().splitlines():
        g = json.loads(line)
        if g["gameId"][2] != "2" or g.get("homeScore") in (None, 0) or not g.get("home"):
            continue
        h, a = era_lookup(g["home"], sy), era_lookup(g["away"], sy)
        if h and a:
            games[g["gameId"]] = {"gid": g["gameId"], "sy": sy, "t": "2", "date": g["date"],
                                  "h": h[0], "a": a[0], "hs": g["homeScore"], "as": g["awayScore"]}
    app = {}
    names = {}
    for line in b_raw.decode().splitlines():
        b = json.loads(line)
        if b["gameId"] not in games:
            continue
        fr = era_lookup(b["team"], sy)
        if not fr:
            continue
        anystat = any((b.get(k) or 0) > 0 for k in bh.STATS)
        if (b.get("min") or 0) > 0 or anystat:
            app[(b["personId"], b["gameId"])] = fr[0]
        names[b["personId"]] = b["name"]
    return games, app, names


def games_from_ramiro(sy):
    import pyarrow.parquet as pq
    raw = get(PBP_URL.format(s=sy), timeout=300)
    if not raw:
        return None
    path = os.path.join(SRC, "ramiro", f"pbp_regular_{sy}.parquet")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(raw)
    t = pq.read_table(path, columns=["game_id", "game_date", "team_home", "team_away",
                                     "hs", "vs"]).to_pylist()
    games = {}
    for r in t:
        gid = r["game_id"]
        if gid[2] != "2":
            continue
        g = games.get(gid)
        if not g:
            h, a = era_lookup(r["team_home"], sy), era_lookup(r["team_away"], sy)
            if not (h and a):
                continue
            g = games[gid] = {"gid": gid, "sy": sy, "t": "2", "date": str(r["game_date"]),
                              "h": h[0], "a": a[0], "hs": 0, "as": 0}
        g["hs"] = max(g["hs"], r["hs"] or 0)
        g["as"] = max(g["as"], r["vs"] or 0)
    return {k: v for k, v in games.items() if v["hs"] != v["as"]}


def lineup_names(sy):
    import pyarrow.parquet as pq
    path = os.path.join(SRC, "ramiro", f"lineup_stats_regular_{sy}.parquet")
    names = {}
    for r in pq.read_table(path, columns=["lineup_team"]).to_pylist():
        for pid, nm in NAME_RE.findall(r["lineup_team"] or ""):
            names[int(pid)] = nm.strip()
    return names


def add(a, b):
    for i in range(4):
        a[i] += b[i]


def build(sy=CURRENT_SEASON):
    for t in ("lineup_stats", "possessions"):
        fetch(t, "regular", sy, force=True)
    box = games_from_boxscores(sy)
    if box:
        games, app_box, names = box
        source = "nba-boxscores + Ramiro lineups"
    else:
        games = games_from_ramiro(sy)
        app_box, names = {}, {}
        source = "Ramiro lineups (nba-boxscores has no 2026-27 data yet)"
    if not games:
        print("no games found; leaving data/current.json as it is")
        return False
    r = bh.ramiro_season(sy, "regular", games)
    names = {**lineup_names(sy), **names}
    # appeared = on the floor in Ramiro's lineups (any stint), or a box-score row with minutes/stats
    app = dict(app_box)
    for (pid, gid), fr in r["pteam"].items():
        app.setdefault((pid, gid), fr)
    dates = sorted(g["date"] for g in games.values())
    start, through = dates[0], dates[-1]
    cutoff = (dt.date.fromisoformat(through) - dt.timedelta(days=29)).isoformat()
    team_games = defaultdict(list)
    for g in games.values():
        team_games[g["h"]].append(g)
        team_games[g["a"]].append(g)
    for k in team_games:
        team_games[k].sort(key=lambda x: (x["date"], x["gid"]))
    by_pid = defaultdict(list)
    for (pid, gid), fr in app.items():
        by_pid[pid].append((games[gid]["date"], gid, fr))
    out = {}
    for pid, lst in by_pid.items():
        lst.sort()
        stints = []
        for d, gid, fr in lst:
            if stints and stints[-1]["fr"] == fr:
                stints[-1]["games"].append((d, gid))
            else:
                stints.append({"fr": fr, "games": [(d, gid)]})
        per = {}
        for i, st in enumerate(stints):
            a = start if i == 0 else (dt.date.fromisoformat(stints[i - 1]["games"][-1][0])
                                      + dt.timedelta(days=1)).isoformat()
            b = through if i == len(stints) - 1 else (dt.date.fromisoformat(stints[i + 1]["games"][0][0])
                                                      - dt.timedelta(days=1)).isoformat()
            mine = {gid for _, gid in st["games"]}
            pt = per.setdefault(st["fr"], {"f": st["fr"], "s": sy, "g": 0, "w": 0, "l": 0, "ow": 0,
                                           "ol": 0, "on": [0, 0, 0, 0], "off": [0, 0, 0, 0],
                                           "on30": [0, 0, 0, 0], "off30": [0, 0, 0, 0],
                                           "st": [0, 0], "bn": [0, 0], "cl": [0, 0],
                                           "last": st["games"][-1][0]})
            pt["last"] = max(pt["last"], st["games"][-1][0])
            for g in team_games[st["fr"]]:
                if not (a <= g["date"] <= b):
                    continue
                won = bh.team_won(g, st["fr"])
                gid = g["gid"]
                if gid not in mine:
                    pt["o" + ("w" if won else "l")] += 1
                    # appearance span: missed games between his first and last game of this stint
                    if st["games"][0][0] <= g["date"] <= st["games"][-1][0]:
                        pt["s" + ("w" if won else "l")] = pt.get("s" + ("w" if won else "l"), 0) + 1
                    continue
                pt["g"] += 1
                pt["w" if won else "l"] += 1
                o = r["on"].get((pid, gid), [0, 0, 0, 0])
                tm = r["team"].get((gid, st["fr"]), [0, 0, 0, 0])
                off = [tm[i] - o[i] for i in range(4)]
                add(pt["on"], o)
                add(pt["off"], off)
                if g["date"] >= cutoff:
                    add(pt["on30"], o)
                    add(pt["off30"], off)
                if pid in r["starters"].get((gid, st["fr"]), ()):
                    pt["st"][0 if won else 1] += 1
                else:
                    pt["bn"][0 if won else 1] += 1
                if gid in r["clutch_games"] and (pid, gid) in r["clutch_on"]:
                    pt["cl"][0 if won else 1] += 1
        ends = [st["fr"] for st in stints]
        for fr, pt in per.items():
            pt["endTeam"] = fr == ends[-1]
        out[str(pid)] = sorted(per.values(), key=lambda x: x["last"])
    # identities for players with no history page yet
    ids = load_json(os.path.join(DATA, "player_ids.json"), {})
    taken = {v["slug"] for v in ids.values()}
    hs_stems = None
    raw = get(HS_LIST)
    if raw:
        hs_stems = sorted(json.loads(raw)["files"])
    new_ids = {}
    for pid in sorted(out, key=int):
        if pid in ids:
            continue
        nm = names.get(int(pid), f"Player {pid}")
        slug = slugify(nm)
        if slug in taken:
            slug = f"{slug}-{pid}"
        taken.add(slug)
        hs = None
        if hs_stems:
            pick = [s for s in hs_stems if s.startswith(f"{pid}-")]
            hs = (pick[0] + ".webp") if pick else None
        new_ids[pid] = {"slug": slug, "name": nm, "rsName": None, "bxName": nm, "cm": False, "hs": hs}
    # download any headshot we do not have yet
    os.makedirs(HS_DIR, exist_ok=True)
    for pid, v in {**{k: ids[k] for k in out if k in ids}, **new_ids}.items():
        f = v.get("hs")
        if f and not os.path.exists(os.path.join(HS_DIR, f)):
            body = get(HS_FILE.format(f=f))
            if body:
                with open(os.path.join(HS_DIR, f), "wb") as fh:
                    fh.write(body)
            else:
                v["hs"] = None
    # team records to date (the current-season standings)
    trec = {}
    for f, gl in team_games.items():
        w = sum(1 for g in gl if bh.team_won(g, f))
        trec[f] = [w, len(gl) - w]
    for sts in out.values():
        for pt in sts:
            pt.setdefault("sw", 0)
            pt.setdefault("sl", 0)
    doc = {"season": sy, "source": source, "start": start, "through": through, "teams": trec,
           "cutoff30": cutoff, "games": len(games), "players": out, "newIds": new_ids}
    changed = dump_json(os.path.join(DATA, "current.json"), doc)
    print("CHANGED" if changed else "UNCHANGED", f"{len(games)} games through {through}")
    return changed


if __name__ == "__main__":
    build()

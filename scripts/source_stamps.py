# (c) 2026 HoopsMatic. All rights reserved.
# Team Success: has Ramiro published new current-season files? Fingerprint: hm-ts-7f3a91c2-stamps
"""HEAD-request Ramiro's current-season Parquet files (the ones update_current.py downloads) and compare
their ETag / Last-Modified with the stamps data/current.json was built from ("sources").

python scripts/source_stamps.py            # print the live stamps as JSON
python scripts/source_stamps.py --check    # exit 0 = unchanged, 10 = changed, 2 = could not read them

A GitHub release download answers 302 to a storage URL; urllib would follow that with a GET (the whole
file), so the redirect is followed by hand with HEAD requests only. Public URLs, no tokens.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CURRENT_SEASON, DATA, load_json  # noqa: E402

FILES = ("pbp", "lineup_stats", "possessions")      # update_current.py: pbp (games), lineups, possessions
URL = "https://github.com/ramirobentes/nba_data/releases/download/{t}/{t}_regular_{s}.parquet"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None                                   # surface the 3xx so we can HEAD the Location ourselves


def head(url, timeout=30, hops=5):
    """{etag, last_modified, size} of a URL with HEAD requests only, or None."""
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(hops):
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "team-success-watcher"})
        try:
            with opener.open(req, timeout=timeout) as r:
                h = r.headers
                return {"etag": h.get("ETag"), "last_modified": h.get("Last-Modified"),
                        "size": int(h.get("Content-Length") or 0)}
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = e.headers["Location"]
                continue
            return None
        except Exception:
            return None
    return None


def live_stamps(season=CURRENT_SEASON):
    """{file: {etag, last_modified, size} or None}"""
    return {t: head(URL.format(t=t, s=season)) for t in FILES}


def key(stamp):
    """What identifies one published version of a file (size alone is not enough)."""
    return None if not stamp else (stamp.get("etag"), stamp.get("last_modified"))


def compare(stored, live):
    """'changed' if any file readable now differs from what the data was built from (or was never
    recorded), 'unchanged' if all match, 'unknown' if none could be read."""
    stored = stored or {}
    readable = {t: s for t, s in live.items() if s}
    if not readable:
        return "unknown"
    for t, s in readable.items():
        if key(stored.get(t)) != key(s):
            return "changed"
    return "unchanged"


def merged(stored, live):
    """Stamps to record: the live ones, keeping the stored stamp of any file that could not be read."""
    return {t: (live.get(t) or (stored or {}).get(t)) for t in FILES}


def main():
    live = live_stamps()
    if "--check" not in sys.argv:
        print(json.dumps(live, indent=1))
        return 0
    cur = load_json(os.path.join(DATA, "current.json"), {}) or {}
    state = compare(cur.get("sources"), live)
    for t in FILES:
        print(f"{t}: built from {key((cur.get('sources') or {}).get(t))}, live {key(live[t])}")
    print(state.upper())
    return {"unchanged": 0, "changed": 10}.get(state, 2)


if __name__ == "__main__":
    sys.exit(main())

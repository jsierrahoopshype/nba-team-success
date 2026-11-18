# (c) 2026 HoopsMatic. All rights reserved.
"""Download Ramiro Bentes' public lineup/possession Parquet files (no key needed).

Usage: python scripts/fetch_ramiro.py 1997 2026      # every season in range, both types
       python scripts/fetch_ramiro.py 2027 2027 --force   # refresh the current season
"""
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SRC  # noqa: E402

URL = "https://github.com/ramirobentes/nba_data/releases/download/{t}/{t}_{k}_{s}.parquet"
TABLES = ("lineup_stats", "possessions")
KINDS = ("regular", "playoffs")


def fetch(table, kind, season, force=False):
    out_dir = os.path.join(SRC, "ramiro")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{table}_{kind}_{season}.parquet")
    if os.path.exists(path) and not force:
        return path
    url = URL.format(t=table, k=kind, s=season)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                body = r.read()
            with open(path + ".tmp", "wb") as fh:
                fh.write(body)
            os.replace(path + ".tmp", path)
            return path
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None          # e.g. playoffs not played yet
            time.sleep(2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    print(f"ramiro: could not download {url}", file=sys.stderr)
    return None


def main():
    a, b = int(sys.argv[1]), int(sys.argv[2])
    force = "--force" in sys.argv
    for s in range(a, b + 1):
        for t in TABLES:
            for k in KINDS:
                p = fetch(t, k, s, force)
                print(s, t, k, "ok" if p else "missing")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
# (c) 2026 HoopsMatic. All rights reserved.
# Shallow-clone the public source repos into _src/ (git-ignored). No tokens needed.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${TS_SRC:-_src}"
mkdir -p "$SRC"
for r in aderoa/nba-boxscores jsierrahoopshype/nba-player-data jsierrahoopshype/hh-teammates \
         jsierrahoopshype/nba-headshots jsierrahoopshype/nba-career-map; do
  d="$SRC/$(basename "$r")"
  if [ -d "$d/.git" ]; then git -C "$d" pull -q --depth 1 || true; else git clone -q --depth 1 "https://github.com/$r.git" "$d"; fi
done
python3 scripts/fetch_ramiro.py 1997 2026

# (c) 2026 HoopsMatic. All rights reserved.
# Team Success: refresh honors when awards.json changes. Fingerprint: hm-ts-7f3a91c2-awards
"""Nightly: has nba-player-data's awards.json changed since the last refresh? Only then re-read it.

python scripts/awards_refresh.py            # nightly Action, after update_current.py

Fetches only awards.json (sparse clone of jsierrahoopshype/nba-player-data) and the Teammates Score
weights (data/teammates.json of jsierrahoopshype/hh-teammates) into _src/, and compares the file's
SHA-256 with data/awards_source.json. When it differs it runs, in order:
    build_history.py --awards-only   (honors, Hall of Fame and accolade scores into the data)
    build_help.py                    (teammate help and peers)
    step0_report.py                  (docs/step0-report.md names the new awards.json version)
and stores the new hash and commit. build_site.py runs after it in the workflow.
Prints CHANGED or UNCHANGED. Public repos, no tokens.
"""
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, ROOT, SRC, dump_json, load_json  # noqa: E402

STATE = os.path.join(DATA, "awards_source.json")
SPARSE = (("jsierrahoopshype/nba-player-data", "nba-player-data", "/awards.json"),
          ("jsierrahoopshype/hh-teammates", "hh-teammates", "/data/teammates.json"))


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def fetch():
    """Shallow sparse clones (only the files we read), or a pull of an existing one."""
    os.makedirs(SRC, exist_ok=True)
    for repo, name, path in SPARSE:
        d = os.path.join(SRC, name)
        if os.path.isdir(os.path.join(d, ".git")):
            try:
                git("pull", "-q", "--depth", "1", cwd=d)
            except subprocess.CalledProcessError:
                pass
            continue
        git("clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", f"https://github.com/{repo}.git", d)
        git("sparse-checkout", "set", "--no-cone", path, cwd=d)


def main():
    fetch()
    path = os.path.join(SRC, "nba-player-data", "awards.json")
    with open(path, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    # the repo commit the file was read at (a depth-1 clone has only that commit)
    commit = git("log", "-1", "--format=%h %cs", cwd=os.path.join(SRC, "nba-player-data"))
    # data/hof_extra.json (Hall of Famers awards.json misses) is merged in by --awards-only too:
    # an edit to it re-runs the refresh like a new awards.json would
    with open(os.path.join(DATA, "hof_extra.json"), "rb") as fh:
        extra = hashlib.sha256(fh.read()).hexdigest()
    old = load_json(STATE, {})
    if old.get("sha256") == sha and old.get("extra_sha256", extra) == extra:
        print("UNCHANGED awards.json", commit, sha[:12])
        return False
    for cmd in (["build_history.py", "--awards-only"], ["build_help.py"], ["step0_report.py"]):
        print("run", " ".join(cmd), flush=True)
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", cmd[0]), *cmd[1:]], check=True)
    dump_json(STATE, {"sha256": sha, "extra_sha256": extra, "commit": commit,
                      "refreshed": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}, compact=False)
    print("CHANGED awards.json", commit, sha[:12], "(was", (old.get("commit") or "none") + ")")
    return True


if __name__ == "__main__":
    main()

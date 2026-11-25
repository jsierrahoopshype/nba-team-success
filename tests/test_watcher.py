# (c) 2026 HoopsMatic. All rights reserved.
"""The watcher (.github/workflows/watch-and-update.yml + scripts/source_stamps.py): change detection,
the stamps current.json records, the workflow's guards, and no repeats between "Last night" and the
fun facts."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import source_stamps as SS  # noqa: E402

A = {"etag": '"0x1"', "last_modified": "Wed, 25 Nov 2026 12:49:47 GMT", "size": 10}
B = {"etag": '"0x2"', "last_modified": "Thu, 26 Nov 2026 12:51:02 GMT", "size": 11}


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_change_detection():
    stored = {"pbp": A, "lineup_stats": A, "possessions": A}
    assert SS.compare(stored, dict(stored)) == "unchanged"
    assert SS.compare(stored, {**stored, "pbp": B}) == "changed"                  # a new pbp file
    assert SS.compare(stored, {**stored, "possessions": B}) == "changed"          # or a new lineup file
    assert SS.compare(stored, {**stored, "pbp": dict(A, size=99)}) == "unchanged"  # same version, size ignored
    assert SS.compare(stored, {"pbp": None, "lineup_stats": A, "possessions": A}) == "unchanged"  # unreadable: no change
    assert SS.compare(stored, {"pbp": None, "lineup_stats": None, "possessions": None}) == "unknown"
    assert SS.compare(None, stored) == "changed"                                  # never recorded
    assert SS.merged(stored, {"pbp": B, "lineup_stats": None, "possessions": A}) == {"pbp": B, "lineup_stats": A, "possessions": A}


def test_redirect_is_followed_with_head_only():
    src = read("scripts/source_stamps.py")
    assert 'method="HEAD"' in src and "_NoRedirect" in src and ".read()" not in src
    assert set(SS.FILES) == {"pbp", "lineup_stats", "possessions"}
    up = read("scripts/update_current.py")
    assert '"sources": sources' in up and "SS.merged(" in up
    cur = json.loads(read("data/current.json"))
    assert set(cur["sources"]) == set(SS.FILES) and all(v and v["etag"] for v in cur["sources"].values())


def test_watcher_workflow_guards():
    y = read(".github/workflows/watch-and-update.yml")
    assert "permissions: {}" in y                                   # nothing by default
    assert y.count("actions: write") == 1 and y.count("contents: write") == 1
    assert "group: watch-and-update" in y and "cancel-in-progress: false" in y
    assert "workflow_dispatch:" in y and 'cron: "17 12-23,2,5 * * *"' in y
    assert "m * 60" in y and "sleep 600" in y and "timeout-minutes: 340" in y and '-gt 330 ]; then m=330' in y
    assert "MINUTES: ${{ inputs.minutes || '330' }}" in y
    assert "actions/workflows/watch-and-update.yml/dispatches" in y and "${{ github.token }}" in y
    assert '"$failures" -ge 3' in y and "!cancelled()" in y
    assert "uses: ./.github/workflows/nightly.yml" in y
    assert "secrets." not in y and "${{ github.event" not in y and "pull_request_target" not in y
    # inputs reach the shell only through env and are cut to digits
    assert "PREV: ${{ inputs.failures || '0' }}" in y and "tr -cd '0-9'" in y
    n = read(".github/workflows/nightly.yml")
    assert "workflow_call:" in n and "workflow_dispatch:" in n and 'cron: "17 12-23,2,5 * * *"' in n


def test_fun_facts_skip_the_latest_list():
    """Nothing in the fun facts about a player or team in the latest "Last night" list, whatever its
    date, and the set records which list it was checked against."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import fun_facts as F
    stories = json.loads(read("data/stories.json"))["stories"]
    latest = max(stories, key=lambda x: x["date"])
    facts = json.loads(read("data/facts.json"))
    in_list = {F.subjects(it) for it in latest.get("items", []) if F.subjects(it)}
    if facts.get("against") == f"{latest['date']}|{latest['cutoff']}":
        for f in facts["facts"]:
            assert F.subjects(f) not in in_list, f["key"]
    src = read("scripts/fun_facts.py")
    assert "story = [latest] if latest else []" in src and '"against": against' in src
    assert 'doc.get("against", against) == against' in src
    assert re.search(r"def latest_list\(\):", src)

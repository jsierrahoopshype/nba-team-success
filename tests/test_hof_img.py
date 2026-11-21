# (c) 2026 HoopsMatic. All rights reserved.
"""Hall of Fame gaps (data/hof_extra.json) and share images redrawn only when their text changes."""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import daily_story as D  # noqa: E402

HOF_TOTAL = 155 + 22     # awards.json's 155 + hof_extra.json's 22 (both "check" rows kept)


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def test_hof_extra_rows():
    rows = load("data/hof_extra.json")["rows"]
    ids = load("data/player_ids.json")
    assert len(rows) == 22
    for r in rows:
        assert ids[r["id"]]["slug"] == r["slug"] and ids[r["id"]]["name"] == r["name"]
        assert r["role"] in ("player", "coach", "contributor") and 1959 <= r["year"] <= 2026
        assert r["source"] == "https://www.nba.com/news/basketball-hall-of-fame-all-time"


def test_hof_count_and_roles():
    players = load("data/players.json")
    hof = {k: v for k, v in players.items() if v.get("hof")}
    assert len(hof) == HOF_TOTAL
    assert all(v.get("hofRole") in ("player", "coach", "contributor") for v in hof.values())
    assert not any("hofRole" in v for k, v in players.items() if not v.get("hof"))


def test_heinsohn_is_a_player_inductee():
    p = load("data/players.json")["76988"]
    assert p["hof"] == 1 and p["hofRole"] == "player"
    assert D.note_of(p) == " (Hall of Famer)"


def test_pat_riley_coach_label():
    p = load("data/players.json")["77962"]
    assert p["hofRole"] == "coach"
    assert D.note_of(p) == " (Hall of Famer as a coach)"
    assert D.is_notable(p, 10 ** 6)
    assert D.note_of({"hof": 1, "hofRole": "contributor"}) == " (Hall of Famer as a contributor)"


def test_all_star_beats_coach_inductee():
    riley = load("data/players.json")["77962"]
    five = {"hof": 0, "as": [1990, 1991, 1992, 1993, 1994]}
    player_hof = {"hof": 1, "hofRole": "player", "as": []}
    nobody = {"hof": 0, "as": []}
    cands = [("riley", riley, 5), ("five", five, 90), ("nobody", nobody, 1)]
    best = min(cands, key=lambda c: D.notable_key(c[1], c[2]))
    assert best[0] == "five"
    cands.append(("hof", player_hof, 200))
    assert min(cands, key=lambda c: D.notable_key(c[1], c[2]))[0] == "hof"
    # a coach inductee still beats a non-All-Star who only ranks better
    assert D.notable_key(riley, 50) < D.notable_key(nobody, 1)


def test_published_images_match_their_text():
    """Every share image was drawn from its entry's current text (hash on file) and exists."""
    stories = load("data/stories.json")["stories"]
    hashes = load("data/story_img_hash.json")
    for st in stories:
        assert os.path.exists(os.path.join(ROOT, st["img"])), st["img"]
        assert hashes.get(st["date"]) == D.img_hash(st), st["date"]


def test_changed_body_redraws_only_that_image(tmp_path, monkeypatch):
    """Editing an old entry's body redraws that image; the others stay byte-identical."""
    stories = copy.deepcopy(load("data/stories.json")["stories"])
    (tmp_path / "stories" / "img").mkdir(parents=True)
    for st in stories:
        with open(os.path.join(ROOT, st["img"]), "rb") as fh:
            (tmp_path / st["img"]).write_bytes(fh.read())
    hash_file = tmp_path / "story_img_hash.json"
    hash_file.write_text(json.dumps(load("data/story_img_hash.json")), encoding="utf-8")

    def fake_draw(st):            # Pillow isn't needed to test which images get redrawn
        (tmp_path / st["img"]).write_bytes(b"redrawn " + st["date"].encode())
    monkeypatch.setattr(D, "ROOT", str(tmp_path))
    monkeypatch.setattr(D, "IMG_HASH", str(hash_file))
    monkeypatch.setattr(D, "draw", fake_draw)
    monkeypatch.setattr(D, "draw_single", fake_draw)
    before = {st["date"]: (tmp_path / st["img"]).read_bytes() for st in stories}

    assert D.sync_images(stories) == []                      # nothing changed: nothing redrawn
    old = stories[-1]
    old["body"][0] = old["body"][0] + " Edited."
    assert D.sync_images(stories) == [old["date"]]
    for st in stories:
        now = (tmp_path / st["img"]).read_bytes()
        assert (now != before[st["date"]]) == (st["date"] == old["date"]), st["date"]
    assert D.sync_images(stories) == []                      # hash stored: no second redraw

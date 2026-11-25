# (c) 2026 HoopsMatic. All rights reserved.
"""Sentence templates for the "Last night" list and the fun facts (scripts/phrasing.py)."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import daily_story as D  # noqa: E402
import phrasing as PH  # noqa: E402

BANNED = ("to date", "on the board", "—", "his games", "reached -", "reached −")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_every_type_has_7_plus_templates():
    for kind, tpls in PH.SETS.items():
        assert len(tpls) >= 7, kind
        assert len(set(tpls)) == len(tpls), kind                  # all different


def test_every_type_used_by_the_code_has_a_set():
    src = read("scripts/daily_story.py") + read("scripts/fun_facts.py")
    for k in PH.SETS:
        # some kinds are built with f-strings: f"start-fr-ever-{kind}", f"streak-{w}-{scope}", ...
        forms = {k, re.sub(r"(best|worst)$", "{kind}", k), "start-{'fr' if whose else 'lg'}-since-{kind}"
                 if re.match(r"start-(fr|lg)-since-", k) else k}
        assert any(f in src for f in forms) or k.startswith(("streak-", "split-", "tonight-", "archive-",
                                                             "wl-mark-", "career-")), k


def test_every_template_keeps_its_links():
    for kind, tpls in PH.SETS.items():
        need = set(PH.REQUIRED[kind])
        for t in tpls:
            # a required slot may not sit inside an optional [[...]] block
            core = PH.OPT_RE.sub("", t)
            assert need <= PH.slots_of(core), (kind, t)


def test_no_banned_wording():
    for kind, tpls in PH.SETS.items():
        for t in tpls:
            low = t.lower()
            assert not any(b in low for b in BANNED), (kind, t)
            assert not re.search(r":\s*\{?\d", t), (kind, t)        # no "300, No. 859" style colon lists
            assert not re.search(r"\{names\}\s*\(", t), (kind, t)  # no "(label) (639)" double parentheses


def test_pick_is_deterministic_and_never_repeats_in_a_block():
    a = PH.pick("wins-mark", "2026-11-25", "123", set())
    b = PH.pick("wins-mark", "2026-11-25", "123", set())
    assert a == b
    assert any(PH.pick("wins-mark", d, "123", set())[0] != a[0] for d in ("2026-11-26", "2026-11-27", "2026-11-28"))
    used = set()
    got = [PH.pick("wins-mark", "2026-11-25", str(s), used)[0] for s in range(len(PH.SETS["wins-mark"]))]
    assert sorted(got) == list(range(len(PH.SETS["wins-mark"])))  # every pick in a block is a new template


def test_optional_rank_block_drops_out():
    P, M = D.L("A B", "player/a-b.html", True), D.L("300", "lists/career-wins.html#p-1")
    for t in PH.SETS["wins-mark"]:
        with_rank = PH.text(PH.render(t, {"P": P, "M": M, "rank": D.L("No. 859", "x")}))
        without = PH.text(PH.render(t, {"P": P, "M": M, "rank": None}))
        assert "859" in with_rank and "859" not in without and "  " not in without, t


def test_negative_milestones_read_plainly():
    P, M = D.L("A B", "player/a-b.html", True), D.L("100", "x")
    for t in PH.SETS["wl-mark-down"]:
        s = PH.text(PH.render(t, {"P": P, "M": M, "rank": None}))
        assert "100" in s and "-100" not in s and "\u2212100" not in s and "minus losses" not in s, s


def test_ap_possessive():
    s = PH.text(PH.render("{P}'s teams", {"P": D.L("Aaron Wiggins", "x", True)}))
    assert s == "Aaron Wiggins' teams"


def test_passed_rule_at_1_5_6_9():
    def names(n):
        return [(D.L(f"P{i}", f"player/p{i}.html"), "") for i in range(1, n + 1)]
    assert PH.text(D.join_names(names(1), "x")) == "P1"
    assert PH.text(D.join_names(names(5), "x")) == "P1, P2, P3, P4 and P5"
    assert PH.text(D.join_names(names(6), "x")) == "P1, P2 and 4 others"
    assert PH.text(D.join_names(names(9), "x")) == "P1, P2 and 7 others"


def test_rank_cutoff_is_1000():
    assert D.RANK_SHOWN_MAX == 1000


def test_published_blocks_never_share_a_template():
    """Lists and strips written with templates carry tpl ("kind#i"); none repeats inside one block."""
    blocks = [st.get("items") or [] for st in json.loads(read("data/stories.json")).get("stories", [])]
    blocks.append(json.loads(read("data/facts.json")).get("facts") or [])
    for b in blocks:
        tpls = [it["tpl"] for it in b if isinstance(it, dict) and it.get("tpl")]
        assert len(tpls) == len(set(tpls)), tpls


def test_docs_list_every_template():
    doc = read("docs/story-rules.md")
    for kind, tpls in PH.SETS.items():
        assert f"**`{kind}`**" in doc, kind
        for t in tpls:
            assert f"1. {t}\n" in doc, (kind, t)

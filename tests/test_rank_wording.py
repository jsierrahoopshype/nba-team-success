# (c) 2026 HoopsMatic. All rights reserved.
"""Rank wording: a rank in a sentence reads "No. 128" (a shared rank too, never "T-128"); a table's
rank column shows the plain number; share-card data carries the same labels. Ties still share a number
(standard competition ranking)."""
import glob
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import boards as B  # noqa: E402

pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "index.html")), reason="site not built")

# "T-128", but not team codes like "DET-1949" (a letter right before the T)
T_RANK = re.compile(r"(?<![A-Za-z])T-\d")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_rank_label():
    assert B.rank_label(128, True) == "No. 128"
    assert B.rank_label(128, False) == "No. 128"
    assert B.rank_label(1714, True) == "No. 1,714"


def test_no_t_rank_in_pages_scripts_or_data():
    files = (glob.glob(os.path.join(ROOT, "*.html")) + glob.glob(os.path.join(ROOT, "*", "*.html"))
             + glob.glob(os.path.join(ROOT, "assets", "*.js"))
             + [os.path.join(ROOT, "data", "stories.json"), os.path.join(ROOT, "data", "facts.json")]
             + glob.glob(os.path.join(ROOT, "assets", "card", "**", "*.json"), recursive=True))
    assert len(files) > 5000
    bad = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            m = T_RANK.search(fh.read())
        if m:
            bad.append(os.path.relpath(f, ROOT))
    assert not bad, bad[:10]


def test_stored_sentences_say_no():
    for st in json.loads(read("data/stories.json"))["stories"]:
        for it in st.get("items", []):
            if it["type"].endswith("-pass"):
                txt = "".join(p[0] for p in it["parts"])
                assert re.search(r"No\. [\d,]+ (in career|among)", txt), txt
                assert not re.search(r"#\d", txt), txt


def test_board_rank_column_plain_and_ties_share():
    board = read("lists/career-wins.html")
    cells = re.findall(r'<td data-l="Rank" class="mono" data-value="(\d+)"><span class="v">([^<]*)</span>', board)
    assert len(cells) >= 100
    assert all(v == dv for dv, v in cells), [c for c in cells if c[0] != c[1]][:5]
    ranks = [int(dv) for dv, _ in cells]
    # standard competition ranking: 1, 2, 2, 4 ... (a shared rank repeats, the next one skips ahead)
    for i, r in enumerate(ranks):
        assert r == (ranks[i - 1] if i and r == ranks[i - 1] else i + 1)


def test_card_data_labels():
    card = json.loads(read("assets/card/harrison-barnes.json"))
    rec, hlp = card["record"], card["help"]
    assert rec["wl_rank_label"] == B.rank_label(rec["wl_rank"], rec["wl_tied"]) == f"No. {rec['wl_rank']:,}"
    assert hlp["rank_label"] == f"No. {hlp['rank']:,}"
    rows = json.loads(read("assets/card/lists/career-wins.json"))["rows"]
    assert all(r["rank_label"] == str(r["rank"]) for r in rows)

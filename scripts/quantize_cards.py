# (c) 2026 HoopsMatic. All rights reserved.
"""Shrink the pre-rendered share PNGs (compare/img/) to a 64-colour palette (about 30 KB each).
python scripts/quantize_cards.py      # only touches files not yet quantized (mode != 'P')"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = os.path.join(ROOT, "compare", "img")
n = 0
for f in sorted(os.listdir(d)):
    p = os.path.join(d, f)
    with Image.open(p) as im:
        if im.mode == "P":
            continue
        q = im.convert("RGB").quantize(colors=64, method=Image.Quantize.FASTOCTREE)
    q.save(p, optimize=True)
    n += 1
print(f"quantized {n} images", file=sys.stderr)

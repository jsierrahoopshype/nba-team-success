# (c) 2026 HoopsMatic. All rights reserved.
# Team Success hand-written SVG charts (no chart library). Fingerprint: hm-ts-7f3a91c2-charts
"""Final NBA finish by season: #1 at the top, one point per season, each point a link.

points: [{"sy": 1998, "rnk": 1, "size": 29, "kind": "title|finals|playoffs|missed",
          "href": "...", "label": "1997-98: Chicago Bulls, #1 of 29"}]
Colors come from CSS classes (ts.css), so the chart follows the page theme.
"""
import html


def _e(x):
    return html.escape(str(x), quote=True)


def season_label(sy):
    return f"{sy - 1}-{str(sy)[-2:]}"


def finish_chart(points, title_id):
    if not points:
        return ""
    W, H = 640, 250
    L, R, T, B = 56, 14, 16, 38
    first, last = min(p["sy"] for p in points), max(p["sy"] for p in points)
    span = max(last - first, 1)
    ymax = max(max(p["size"] for p in points), 10)

    def x(sy):
        return L + (W - L - R) * ((sy - first) / span if last > first else 0.5)

    def y(r):
        return T + (H - T - B) * ((r - 1) / (ymax - 1))

    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-labelledby="{_e(title_id)}" '
           f'preserveAspectRatio="xMidYMid meet">']
    # grid: #1, then every 5 or 10 places
    step = 5 if ymax <= 20 else 10
    ticks = [1] + list(range(step, ymax + 1, step))
    for t in ticks:
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                   f'<text class="ax" x="{L - 8}" y="{y(t) + 4:.1f}" text-anchor="end">#{t}</text>')
    # last place each season (league size), as a step line
    by = {p["sy"]: p for p in points}
    seg = []
    for sy in range(first, last + 1):
        if sy in by:
            seg.append(f'{x(sy):.1f},{y(by[sy]["size"]):.1f}')
    if len(seg) > 1:
        out.append(f'<polyline class="lastplace" points="{" ".join(seg)}"/>')
    # connect consecutive seasons
    run = []
    for sy in range(first, last + 2):
        if sy in by:
            run.append(f'{x(sy):.1f},{y(by[sy]["rnk"]):.1f}')
        else:
            if len(run) > 1:
                out.append(f'<polyline class="path" points="{" ".join(run)}"/>')
            run = []
    # x labels: first, last and every 5th season in between
    lab = {first, last} | {sy for sy in range(first, last + 1) if sy % 5 == 0 and last - first > 6}
    placed = []
    for sy in sorted(lab, key=lambda y: (y not in (first, last), y)):
        if any(abs(x(sy) - x(o)) < 78 for o in placed):     # keep labels from colliding
            continue
        placed.append(sy)
    for sy in sorted(placed):
        anchor = "start" if sy == first else ("end" if sy == last else "middle")
        out.append(f'<text class="ax" x="{x(sy):.1f}" y="{H - 12}" text-anchor="{anchor}">{season_label(sy)}</text>')
    for p in sorted(points, key=lambda p: p["sy"]):
        cx, cy = x(p["sy"]), y(p["rnk"])
        out.append(f'<a href="{_e(p["href"])}" aria-label="{_e(p["label"])}"><title>{_e(p["label"])}</title>'
                   f'<circle class="pt {p["kind"]}" cx="{cx:.1f}" cy="{cy:.1f}" r="6"/>'
                   f'<circle class="hit" cx="{cx:.1f}" cy="{cy:.1f}" r="13"/></a>')
    out.append(f'<text class="ax" x="{W - R}" y="{y(ymax) - 6:.1f}" text-anchor="end">dashes: last place</text>')
    out.append("</svg>")
    return "".join(out)

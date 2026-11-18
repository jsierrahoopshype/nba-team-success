# (c) 2026 HoopsMatic. All rights reserved.
# Team Success player leads: templates filled from data. Fingerprint: hm-ts-7f3a91c2-leads
"""Every sentence here is a template; docs/story-rules.md lists the rules in this order.

No model-written prose: each template states only what its fields prove, and never says a player
made, lifted, carried or dragged a team. The input is plain data (see player_facts in build_site).
"""

EN = "–"
MINUS = "−"


def season_label(sy):
    return f"{sy - 1}-{str(sy)[-2:]}"


def _list(xs):
    xs = list(xs)
    if len(xs) <= 2:
        return " and ".join(xs)
    return ", ".join(xs[:-1]) + " and " + xs[-1]


def _years(ys):
    """[1991, 1992, 1993, 1996] -> '1990-91 to 1992-93 and 1995-96' (runs collapse)."""
    ys = sorted(ys)
    runs = []
    for y in ys:
        if runs and y == runs[-1][1] + 1:
            runs[-1][1] = y
        else:
            runs.append([y, y])
    parts = [season_label(a) if a == b else f"{season_label(a)} to {season_label(b)}" for a, b in runs]
    return _list(parts)


def _signed(n):
    return ("+" if n > 0 else (MINUS if n < 0 else "")) + f"{abs(n):,}"


def lead(f):
    """f: dict of facts. Returns (rule id, list of sentences)."""
    n, k = f["seasons"], f["teams"]
    w, l = f["w"], f["l"]
    g = w + l
    seasons_txt = f"{n} season{'s' if n != 1 else ''}"
    teams_txt = f"{k} team{'s' if k != 1 else ''}"
    # R0 plain: not enough for a distinctive lead
    if n < 3 or g < 82:
        return "R0", [f"Played {seasons_txt} for {teams_txt}; his teams went {w}{EN}{l} in his games."]
    out = []
    rule = None
    if f["titles"] >= 2:
        rule = "R1"
        out.append(f"His teams won {f['titles']} titles: {_years(f['title_years'])}.")
    elif f["titles"] == 1:
        rule = "R2"
        ty = f["title_years"][0]
        out.append(f"His teams won one title, with the {season_label(ty)} {f['title_team']}.")
    elif f["finals"]:
        rule = "R3"
        c = len(f["finals"])
        out.append(f"His teams reached the NBA Finals {'once' if c == 1 else f'{c} times'} "
                   f"({_years(f['finals'])}) without winning the title.")
    elif f["trips"]:
        rule = "R4"
        b = f["best"]
        out.append(f"His best final NBA finish was #{b['rnk']} of {b['size']}, with the "
                   f"{season_label(b['sy'])} {b['team']}.")
    else:
        rule = "R5"
        b = f["best"]
        out.append(f"His teams missed the playoffs in all {n} of his seasons; the best final finish was "
                   f"#{b['rnk']} of {b['size']}, with the {season_label(b['sy'])} {b['team']}.")
    over = "over" if w > l else ("under" if w < l else "at")
    wl_txt = f"{_signed(w - l)} games {over} .500" if w != l else "exactly .500"
    out.append(f"In his {g:,} games for {teams_txt} over {seasons_txt} they went {w}{EN}{l} "
               f"({100 * w / g:.1f}%), {wl_txt}, with an average final finish of {f['avg']:.1f}.")
    j = f.get("jump")
    if j and j["gain"] >= 8:
        out.append(f"The biggest one-season rise in his career: the {j['team']} went from #{j['a']} in "
                   f"{season_label(j['sy'] - 1)} to #{j['b']} in {season_label(j['sy'])}.")
    return rule, out

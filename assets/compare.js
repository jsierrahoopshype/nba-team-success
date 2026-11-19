// (c) 2026 HoopsMatic. All rights reserved.
// Team Success peer comparison and share card, hm-ts-7f3a91c2-compare.
// - Player pages: "Compare with anyone" builds the comparison in the page (no pop-up) from
//   assets/board.json and both players' assets/pg/<slug>.json; ?peer=<slug> keeps it in the URL
//   (a noindex variant).
// - "Download image" draws the share card on a canvas with this site's own fonts and headshots,
//   (the pages' social cards come from hoopsmatic-og-card; no PNGs are pre-rendered here).
// Every value goes in through textContent; nothing is parsed as HTML.
(function () {
  var EN = "–", MINUS = "−";
  var PO = ["Missed the playoffs", "Lost in the play-in", "First round", "Conference semifinals", "Conference finals", "NBA Finals", "Won the title"];
  var DEPTH = [0, 0, 1, 2, 3, 4, 5];
  function label(sy) { return (sy - 1) + "-" + String(sy).slice(-2); }
  // one decimal exactly like Python's f"{x:.1f}" (build_site.py): the double's exact decimal
  // expansion, ties to even, so the in-page view prints the same numbers as the static pages
  function fix1(v) {
    var neg = v < 0, x = Math.abs(v).toFixed(40), i = x.indexOf(".");
    var n = parseInt(x.slice(0, i), 10) * 10 + parseInt(x[i + 1], 10), rest = x.slice(i + 2);
    var tie = /^50*$/.test(rest), up = rest[0] > "5" || (rest[0] === "5" && !tie);
    if (up || (tie && n % 2 === 1)) n++;
    var s = Math.floor(n / 10) + "." + (n % 10);
    return (neg && n ? "-" : "") + s;
  }
  function pct1(p) { return p === null || p === undefined ? "N/A" : fix1(100 * p) + "%"; }
  function wl(w, l) { return (w + l) ? w + EN + l : "N/A"; }
  function signed(n) { return (n > 0 ? "+" : (n < 0 ? MINUS : "")) + Math.abs(n).toLocaleString("en-US"); }
  function hfmt(v, p) { if (v === null || v === undefined) return "N/A"; return (v === 0 ? "0" : fix1(v)) + (p ? "+" : ""); }

  // ---- share card (1200 x 630) -------------------------------------------------------------
  var fontsReady = null;
  function fonts(up) {
    if (fontsReady) return fontsReady;
    var a = new FontFace("DM Sans", "url(" + up + "assets/fonts/dm-sans-latin.woff2)", { weight: "100 1000" });
    var b = new FontFace("JetBrains Mono", "url(" + up + "assets/fonts/jetbrains-mono-latin.woff2)", { weight: "400 800" });
    fontsReady = Promise.all([a.load(), b.load()]).then(function (f) { f.forEach(function (x) { document.fonts.add(x); }); });
    return fontsReady;
  }
  function img(src) {
    return new Promise(function (res) {
      if (!src) return res(null);
      var i = new Image();
      i.onload = function () { res(i); };
      i.onerror = function () { res(null); };
      i.src = src;
    });
  }
  function fit(ctx, text, size, weight, family, max) {
    var s = size;
    do { ctx.font = weight + " " + s + "px '" + family + "'"; s -= 2; } while (ctx.measureText(text).width > max && s > 14);
  }
  function draw(card, up) {
    return fonts(up).then(function () {
      return Promise.all(card.map(function (c) { return img(c.hs ? up + "assets/hs/" + c.hs : null); }));
    }).then(function (pics) {
      var cv = document.createElement("canvas");
      cv.width = 1200; cv.height = 630;
      var x = cv.getContext("2d");
      x.fillStyle = "#f5f5f7"; x.fillRect(0, 0, 1200, 630);
      x.fillStyle = "#ffffff";
      x.beginPath(); x.roundRect(36, 36, 1128, 558, 24); x.fill();
      x.strokeStyle = "#d1d1d6"; x.lineWidth = 2; x.stroke();
      x.fillStyle = "#6e6e73"; x.font = "600 24px 'DM Sans'"; x.fillText("Team Success", 76, 92);
      x.fillStyle = "#1d1d1f";
      var title = card[0].name + " vs " + card[1].name;
      fit(x, title, 50, "700", "DM Sans", 1048); x.fillText(title, 76, 150);
      card.forEach(function (c, i) {
        var X = 76 + i * 548, Y = 200;
        x.save();
        x.beginPath(); x.arc(X + 56, Y + 56, 56, 0, Math.PI * 2); x.closePath();
        x.fillStyle = "#e8e8ed"; x.fill(); x.clip();
        if (pics[i]) x.drawImage(pics[i], X, Y, 112, 112);
        x.restore();
        x.fillStyle = "#1d1d1f"; fit(x, c.name, 34, "700", "DM Sans", 380); x.fillText(c.name, X + 132, Y + 50);
        x.fillStyle = "#6e6e73"; x.font = "500 22px 'DM Sans'"; x.fillText(c.span, X + 132, Y + 84);
        var lines = [wl(c.w, c.l) + " (" + pct1(c.pct) + ")", "W " + MINUS + " L " + signed(c.wl),
          "Average finish " + (c.adj30 !== undefined ? fix1(c.adj30) + " of 30" : fix1(c.avg)), c.titles + " titles, " + c.trips + " playoff trips",
          "Help " + (c.help === null || c.help === undefined ? "N/A" : fix1(c.help)) + " per season"];
        x.fillStyle = "#1d1d1f";
        lines.forEach(function (t, k) { x.font = (k === 0 ? "700 32px" : "500 26px") + " 'JetBrains Mono'"; x.fillText(t, X, Y + 158 + k * 40); });
      });
      x.fillStyle = "#6e6e73"; x.font = "500 19px 'DM Sans'";
      x.fillText("Regular seasons through 2025-26. Records are his teams' in his games; help is Teammates Score points per season.", 76, 572);
      x.fillStyle = "#3b82f6"; x.font = "600 20px 'DM Sans'";
      x.textAlign = "right"; x.fillText("hoopsmatic.com/team-success", 1124, 92);
      return cv;
    });
  }
  function download(card, up) {
    draw(card, up).then(function (cv) {
      cv.toBlob(function (b) {
        var a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = card[0].slug + "-vs-" + card[1].slug + ".png";
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
      }, "image/png");
    });
  }
  window.TSCompare = { draw: draw, download: download };
  var dl = document.getElementById("card-dl");
  if (dl) dl.addEventListener("click", function () { download(JSON.parse(dl.getAttribute("data-card")), dl.getAttribute("data-up")); });

  // ---- in-page comparison (player pages) -----------------------------------------------------
  var box = document.getElementById("cmp");
  if (!box) return;
  var up = box.getAttribute("data-up"), A = box.getAttribute("data-a");
  var board = null, names = null;
  function getJSON(u) { return fetch(u, { credentials: "same-origin" }).then(function (r) { return r.json(); }); }
  function rowsFor(slug, pg) {
    var row = board.p.filter(function (r) { return r[1] === slug; })[0];
    if (!row) return [];
    var by = {}, order = [];
    row[5].forEach(function (s) { if (!by[s[0]]) { by[s[0]] = []; order.push(s[0]); } by[s[0]].push(s); });
    order.sort(function (a, b) { return a - b; });
    // completed seasons only, like the static pages (a season in progress has no final finish)
    order = order.filter(function (sy) { return !board.t[by[sy][0][1] + "-" + sy][5]; });
    return order.map(function (sy) {
      var lst = by[sy], main = lst[0], end = null, i;
      for (i = 1; i < lst.length; i++) if (lst[i][2] > main[2] || (lst[i][2] === main[2] && lst[i][9] > main[9])) main = lst[i];
      for (i = 0; i < lst.length; i++) if (lst[i][7]) { end = lst[i]; break; }
      if (!end) { end = lst[0]; for (i = 1; i < lst.length; i++) if (lst[i][9] > end[9]) end = lst[i]; }
      var best = null;
      lst.forEach(function (y) { if (y === end || y[8]) { var tt = board.t[y[1] + "-" + sy]; if (!best || DEPTH[tt[4]] > DEPTH[best[4]]) best = tt; } });
      var t = board.t[main[1] + "-" + sy], h = (pg.h || {})[String(sy)] || [null, null, 0];
      return { sy: sy, f: main[1], team: names.season[main[1] + "-" + sy] || main[1], rnk: t[2], size: t[3],
        w: lst.reduce(function (a, s) { return a + s[3]; }, 0), l: lst.reduce(function (a, s) { return a + s[4]; }, 0),
        po: best ? best[4] : 0, help: h[0], partial: h[2] };
    });
  }
  function el(tag, text, cls) { var x = document.createElement(tag); if (text !== undefined) x.textContent = text; if (cls) x.className = cls; return x; }
  // ---- same scoreboard and season table as the static comparison pages (build_site.py
  // scoreboard() and compare_page()); keep the two in step
  function pp(g) {
    if (g === null || g === undefined) return "N/A";
    var t = fix1(100 * g);                       // build_site.pp(): round(100 * g, 1)
    if (parseFloat(t) === 0) return "0.0";
    return (t[0] === "-" ? MINUS : "+") + t.replace("-", "");
  }
  function shortName(n, other) {
    function last(x) {
      var w = x.split(/\s+/).filter(function (y) { return !/^(jr|sr|ii|iii|iv)[.,]?$/i.test(y); });
      return w.length ? w[w.length - 1] : x;
    }
    return last(n) === last(other) ? n : last(n);
  }
  function face(c) {
    var f = el("span", undefined, "hs md" + (c.hs ? "" : " nohs"));
    if (c.hs) {
      var im = document.createElement("img");
      im.src = up + "assets/hs/" + c.hs; im.alt = ""; im.width = 160; im.height = 160; im.loading = "lazy";
      f.appendChild(im);
    } else {
      var w = c.name.replace(/\./g, " ").split(/\s+/).filter(function (x) { return x && !/^(jr|sr|ii|iii|iv|v),?$/i.test(x); });
      f.textContent = w.length ? (w[0][0] + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase() : "?";
      f.setAttribute("aria-hidden", "true");
    }
    return f;
  }
  function team(f, sy) {
    var k = f + "-" + sy, wrap = el("span", undefined, "tmn"), lg = (names.lg || {})[k];
    if (lg) {
      var im = document.createElement("img");
      im.className = "lg"; im.src = up + "assets/logos/" + lg + ".svg"; im.alt = ""; im.width = 18; im.height = 18; im.loading = "lazy";
      wrap.appendChild(im);
    }
    var full = (names.full || {})[k] || names.season[k] || f, txt = names.season[k] || f, a;
    if (names.cm[f]) {
      a = el("a", txt); a.href = "https://hoopsmatic.com/nba-career-map/team/" + names.cm[f] + ".html";
    } else a = el("span", txt, "tn");
    a.title = full;
    wrap.appendChild(a);
    return wrap;
  }
  function boardLink(r) {
    var a = el("a", "#" + r.rnk + " of " + r.size, "mono");
    a.href = up + "seasons/" + label(r.sy) + ".html#t-" + r.f;
    return a;
  }
  function r1(x) { return x === null || x === undefined ? null : parseFloat(fix1(x)); }
  function scoreboard(ca, cb) {
    var na = shortName(ca.name, cb.name), nb = shortName(cb.name, ca.name);
    var sec = el("section", undefined, "sboard");
    var h = el("h3", "Head to head"); h.id = "cap-sb-peer"; sec.appendChild(h);
    var head = el("div", undefined, "sbhead");
    [[ca, "a"], [cb, "b"]].forEach(function (p, i) {
      var d = el("div", undefined, "sbp " + p[1]);
      d.appendChild(face(p[0])); d.appendChild(el("b", p[0].name)); d.appendChild(el("small", p[0].span));
      head.appendChild(d);
      if (i === 0) head.appendChild(el("span", "vs", "vs"));
    });
    sec.appendChild(head);
    function rec(c) { var f = document.createDocumentFragment(); f.appendChild(document.createTextNode(wl(c.w, c.l))); f.appendChild(el("small", pct1(c.pct))); return f; }
    // [label, how, value A, value B, text A, text B, lower leads (null = shown, never a lead)]
    var cats = [
      ["Career record", "win % in his games", Math.round((ca.pct || 0) * 1000) / 1000, Math.round((cb.pct || 0) * 1000) / 1000, rec(ca), rec(cb), false],
      ["W " + MINUS + " L", "", ca.wl, cb.wl, signed(ca.wl), signed(cb.wl), false],
      ["Titles", "", ca.titles, cb.titles, String(ca.titles), String(cb.titles), false],
      ["Playoff trips", "", ca.trips, cb.trips, String(ca.trips), String(cb.trips), false],
      ["Deepest run", "", ca.deep, cb.deep, ca.deepLabel, cb.deepLabel, false],
      ["Average finish", "adjusted for league size, lower leads", r1(ca.adj30), r1(cb.adj30), fix1(ca.adj30) + " of 30", fix1(cb.adj30) + " of 30", true],
      ["With vs without", "win-rate gap in points, not a lead category", null, null, pp(ca.gap), pp(cb.gap), null],
      ["Help per season", "teammates' honors, less help leads", r1(ca.help), r1(cb.help), hfmt(ca.help), hfmt(cb.help), true]
    ];
    var tbl = el("table", undefined, "sbt"), thead = el("thead"), hr = el("tr");
    tbl.setAttribute("aria-labelledby", "cap-sb-peer");
    ["Category", na, nb].forEach(function (t) { var x = el("th", t); x.scope = "col"; hr.appendChild(x); });
    thead.appendChild(hr); tbl.appendChild(thead);
    var tb = el("tbody"), la = 0, lb = 0, even = 0, n = 0;
    cats.forEach(function (c) {
      var ka = "", kb = "";
      if (c[6] !== null) {
        n++;
        if (c[2] === null || c[3] === null || c[2] === c[3]) even++;
        else if ((c[2] < c[3]) === c[6]) { ka = "la"; la++; }
        else { kb = "lb"; lb++; }
      }
      var tr = el("tr", undefined, c[0] === "Deepest run" ? "txt" : undefined), th = el("th", c[0]);
      th.scope = "row";
      if (c[1]) th.appendChild(el("small", c[1]));
      tr.appendChild(th);
      [[c[4], ka], [c[5], kb]].forEach(function (v) {
        var d = el("td", undefined, v[1] || undefined);
        if (typeof v[0] === "string") d.textContent = v[0]; else d.appendChild(v[0]);
        tr.appendChild(d);
      });
      tb.appendChild(tr);
    });
    tbl.appendChild(tb); sec.appendChild(tbl);
    sec.appendChild(el("p", na + " leads " + la + " of " + n + " · " + nb + " leads " + lb + " of " + n + (even ? " · " + even + " even" : ""), "tally"));
    if (ca.help !== null && cb.help !== null && r1(ca.help) !== r1(cb.help)) {
      var lo = ca.help < cb.help ? ca : cb, hi = lo === ca ? cb : ca;
      sec.appendChild(el("p", "Less help: " + shortName(lo.name, hi.name) + " (" + fix1(lo.help) + " per season vs " + fix1(hi.help) +
        "). Help is the Teammates Score of the teammates he shared games with; the smaller number is tinted.", "note"));
    }
    sec.appendChild(el("p", "The leader's cell is tinted: the larger number, except average finish and help, where the smaller one leads. " +
      "With vs without is shown for reference and is not counted. These are team records and finishes, not a measure of who was better.", "note"));
    return sec;
  }
  function seasonTable(ca, cb, ra, rb) {
    var na = shortName(ca.name, cb.name), nb = shortName(cb.name, ca.name);
    function adj(r) { return r.size > 1 ? (r.rnk - 1) / (r.size - 1) : 0; }
    var wide = el("div", undefined, "cmpwide"), tbl = el("table", undefined, "cmpt"), thead = el("thead");
    var h1 = el("tr"), h2 = el("tr");
    var c0 = el("th", "#"); c0.scope = "col"; c0.rowSpan = 2; h1.appendChild(c0);
    [[ca.name, "ga"], [cb.name, "gb"]].forEach(function (g) { var x = el("th", g[0], g[1]); x.scope = "colgroup"; x.colSpan = 5; h1.appendChild(x); });
    var cl = el("th", "Better finish"); cl.scope = "col"; cl.rowSpan = 2; cl.appendChild(el("br")); cl.appendChild(document.createTextNode(na + EN + nb)); h1.appendChild(cl);
    for (var g = 0; g < 2; g++) ["Season", "Finish", "W" + EN + "L", "Playoffs", "Help"].forEach(function (t) { var x = el("th", t); x.scope = "col"; h2.appendChild(x); });
    thead.appendChild(h1); thead.appendChild(h2); tbl.appendChild(thead);
    var tb = el("tbody"), cards = el("ol", undefined, "cmpcards"), ta = 0, tbn = 0;
    for (var k = 0; k < Math.max(ra.length, rb.length); k++) {
      var x = ra[k], y = rb[k], lead = null;
      if (x && y && Math.abs(adj(x) - adj(y)) > 1e-9) { lead = adj(x) < adj(y) ? "a" : "b"; if (lead === "a") ta++; else tbn++; }
      var tally = (x && y) ? ta + EN + tbn : "";
      var tr = el("tr");
      tr.appendChild(el("td", String(k + 1), "mono"));
      var li = el("li"), hd = el("div", undefined, "cc-h"), grid = el("div", undefined, "cc-g");
      hd.appendChild(el("b", "Career season " + (k + 1)));
      if (tally) hd.appendChild(el("span", "better finish so far: " + na + " " + ta + EN + tbn + " " + nb, "mono"));
      [[x, "a", na], [y, "b", nb]].forEach(function (p) {
        var r = p[0], side = p[1];
        if (!r) {
          var none = el("td", "No season", "none"); none.colSpan = 5; tr.appendChild(none);
          var cn = el("div", undefined, "cc " + side + " none"); cn.appendChild(el("span", p[2], "cc-n")); cn.appendChild(el("span", "No season"));
          grid.appendChild(cn);
          return;
        }
        var cs = el("td", undefined, "cs"); cs.appendChild(el("span", label(r.sy), "mono")); cs.appendChild(document.createTextNode(" ")); cs.appendChild(team(r.f, r.sy)); tr.appendChild(cs);
        var fin = el("td", undefined, lead === side ? "l" + side : undefined); fin.appendChild(boardLink(r)); tr.appendChild(fin);
        tr.appendChild(el("td", wl(r.w, r.l), "mono"));
        tr.appendChild(el("td", PO[r.po], "po"));
        tr.appendChild(el("td", hfmt(r.help, r.partial), "mono"));
        var cc = el("div", undefined, "cc " + side + (lead === side ? " lead" : ""));
        cc.appendChild(el("span", p[2], "cc-n")); cc.appendChild(el("span", label(r.sy), "mono")); cc.appendChild(team(r.f, r.sy));
        var bl = boardLink(r); bl.className = "mono fin"; cc.appendChild(bl);
        cc.appendChild(el("span", wl(r.w, r.l), "mono")); cc.appendChild(el("span", PO[r.po]));
        cc.appendChild(el("span", "Help " + hfmt(r.help, r.partial), "mono"));
        grid.appendChild(cc);
      });
      tr.appendChild(el("td", tally, "mono"));
      tb.appendChild(tr);
      li.appendChild(hd); li.appendChild(grid); cards.appendChild(li);
    }
    tbl.appendChild(tb); wide.appendChild(tbl);
    var frag = document.createDocumentFragment();
    frag.appendChild(el("h3", "Season by season"));
    frag.appendChild(el("p", "Career season 1 next to career season 1. Each player's season is the team he played the most games for; W" + EN +
      "L is his teams' record in his games that season. The tinted finish is the team that finished higher that season, on the " +
      "league-size-adjusted scale; the last column keeps the running count.", "note"));
    frag.appendChild(wide); frag.appendChild(cards);
    return frag;
  }
  function render(B, pa, pb) {
    while (box.firstChild) box.removeChild(box.firstChild);
    var ca = pa.sum, cb = pb.sum, ra = rowsFor(A, pa), rb = rowsFor(B, pb);
    box.appendChild(scoreboard(ca, cb));
    var btn = el("button", "Download image", "more-btn");
    btn.type = "button";
    btn.addEventListener("click", function () { download([ca, cb], up); });
    var bp = el("p"); bp.appendChild(btn); box.appendChild(bp);
    box.appendChild(seasonTable(ca, cb, ra, rb));
    box.appendChild(el("p", "Records and finishes, not what a player caused. Help counts honors won that season by teammates who shared a game with him.", "note"));
  }
  function pick(B) {
    if (!B || B === A) return;
    var q = new URLSearchParams(location.search);
    q.set("peer", B);
    history.replaceState(null, "", location.pathname + "?" + q.toString() + "#compare");
    Promise.all([board ? board : getJSON(up + "assets/board.json"), names ? names : getJSON(up + "assets/teamnames.json"),
      getJSON(up + "assets/pg/" + encodeURIComponent(A) + ".json"), getJSON(up + "assets/pg/" + encodeURIComponent(B) + ".json")])
      .then(function (x) { board = x[0]; names = x[1]; render(B, x[2], x[3]); box.scrollIntoView({ block: "start" }); })
      .catch(function () { while (box.firstChild) box.removeChild(box.firstChild); box.appendChild(el("p", "No completed seasons to compare for that player yet.", "note")); });
  }
  window.TSCompare.pick = pick;
  var peer = new URLSearchParams(location.search).get("peer");
  if (peer) pick(peer);
})();

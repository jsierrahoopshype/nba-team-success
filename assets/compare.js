// (c) 2026 HoopsMatic. All rights reserved.
// Team Success peer comparison and share card, hm-ts-7f3a91c2-compare.
// - Player pages: "Compare with anyone" builds the comparison in the page (no pop-up) from
//   assets/board.json and both players' assets/pg/<slug>.json; ?peer=<slug> keeps it in the URL
//   (a noindex variant).
// - "Download image" draws the share card on a canvas with this site's own fonts and headshots,
//   and the same function pre-renders the PNGs of the suggested comparisons (scripts/render_cards.js).
// Every value goes in through textContent; nothing is parsed as HTML.
(function () {
  var EN = "–", MINUS = "−";
  var PO = ["Missed the playoffs", "Lost in the play-in", "First round", "Conference semifinals", "Conference finals", "NBA Finals", "Won the title"];
  var DEPTH = [0, 0, 1, 2, 3, 4, 5];
  function label(sy) { return (sy - 1) + "-" + String(sy).slice(-2); }
  function pct1(p) { return p === null || p === undefined ? "N/A" : (100 * p).toFixed(1) + "%"; }
  function wl(w, l) { return (w + l) ? w + EN + l : "N/A"; }
  function signed(n) { return (n > 0 ? "+" : (n < 0 ? MINUS : "")) + Math.abs(n).toLocaleString("en-US"); }
  function hfmt(v, p) { if (v === null || v === undefined) return "N/A"; return (v === 0 ? "0" : v.toFixed(1)) + (p ? "+" : ""); }

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
          "Average finish " + c.avg.toFixed(1), c.titles + " titles, " + c.trips + " playoff trips",
          "Help " + (c.help === null || c.help === undefined ? "N/A" : c.help.toFixed(1)) + " per season"];
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
  function render(B, pa, pb) {
    while (box.firstChild) box.removeChild(box.firstChild);
    var ca = pa.sum, cb = pb.sum, ra = rowsFor(A, pa), rb = rowsFor(B, pb);
    box.appendChild(el("h3", ca.name + " vs " + cb.name));
    var ul = el("ul", undefined, "takes");
    [ca, cb].forEach(function (c) {
      ul.appendChild(el("li", c.name + " (" + c.span + "): " + wl(c.w, c.l) + " (" + pct1(c.pct) + "), W " + MINUS + " L " + signed(c.wl) +
        ", average final finish " + c.avg.toFixed(1) + ", " + c.trips + " playoff trips, " + c.titles + " titles, help " +
        (c.help === null ? "N/A" : c.help.toFixed(1)) + " per season."));
    });
    box.appendChild(ul);
    var btn = el("button", "Download image", "more-btn");
    btn.type = "button";
    btn.addEventListener("click", function () { download([ca, cb], up); });
    box.appendChild(btn);
    var tbl = el("table", undefined, "tt cmp");
    var thead = el("thead"), hr = el("tr");
    ["Career season", ca.name + ": season", "Final finish", "W" + EN + "L", "Playoffs", "Help",
      cb.name + ": season", "Final finish", "W" + EN + "L", "Playoffs", "Help"].forEach(function (h) { var x = el("th", h); x.scope = "col"; hr.appendChild(x); });
    thead.appendChild(hr); tbl.appendChild(thead);
    var tb = el("tbody");
    for (var k = 0; k < Math.max(ra.length, rb.length); k++) {
      var tr = el("tr");
      var c0 = el("td", String(k + 1), "mono"); c0.setAttribute("data-l", "Career season"); tr.appendChild(c0);
      [[ra[k], ca.name], [rb[k], cb.name]].forEach(function (p) {
        var r = p[0], lab = p[1];
        var cells = r ? [label(r.sy) + " " + r.team, "#" + r.rnk + " of " + r.size, wl(r.w, r.l), PO[r.po], hfmt(r.help, r.partial)]
          : ["N/A", "N/A", "N/A", "N/A", "N/A"];
        ["season", "final finish", "W" + EN + "L", "playoffs", "help"].forEach(function (h, i) {
          var c = el("td", cells[i], (i === 1 || i === 2 || i === 4) ? "mono" : ""); c.setAttribute("data-l", lab + " " + h); tr.appendChild(c);
        });
      });
      tb.appendChild(tr);
    }
    tbl.appendChild(tb);
    box.appendChild(tbl);
    box.appendChild(el("p", "Aligned by career season; each season is the team he played the most games for. Records and finishes, not what a player caused.", "note"));
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

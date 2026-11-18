// (c) 2026 HoopsMatic. All rights reserved.
// Team Success: record against each opponent, hm-ts-7f3a91c2-opp. The table in the page is the
// default view (regular season, every season). Filters and game lists come from this player's
// own file (assets/pg/<slug>.json), fetched once on demand. Game lists open inline under their
// row (no pop-up). Every value goes in through textContent.
(function () {
  var form = document.getElementById("opp-form");
  var table = document.querySelector("table.opp");
  if (!form || !table) return;
  var tbody = table.tBodies[0];
  var games = null, names = null;
  var EN = "–", MINUS = "−";
  var MON = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."];

  function load(cb) {
    if (games && names) return cb();
    Promise.all([fetch(form.getAttribute("data-src")).then(function (r) { return r.json(); }),
                 fetch(form.getAttribute("data-names")).then(function (r) { return r.json(); })])
      .then(function (x) { games = x[0]; names = x[1]; cb(); });
  }
  function label(sy) { return (sy - 1) + "-" + String(sy).slice(-2); }
  function pct1(p) { return p === null ? "N/A" : (100 * p).toFixed(1) + "%"; }
  function signed(n) { return (n > 0 ? "+" : (n < 0 ? MINUS : "")) + Math.abs(n).toLocaleString("en-US"); }
  function wl(w, l) { return (w + l) ? w + EN + l : "N/A"; }
  function nm(f, sy) { return names.season[f + "-" + sy] || names.latest[f] || f; }
  function date(sy, md) {
    var m = Math.floor(md / 100), d = md % 100, y = m >= 8 ? sy - 1 : sy;
    return MON[m - 1] + " " + d + ", " + y;
  }
  function filt() {
    var f = {};
    new FormData(form).forEach(function (v, k) { if (v !== "") f[k] = v; });
    f.k = f.k || "2";
    return f;
  }
  // every game that passes the filters: {sy, team, md, opp, home, ts, os, t}
  function rowsFor(f) {
    var out = [];
    Object.keys(games.s).forEach(function (k) {
      var sy = +k;
      if (f.from && sy < +f.from) return;
      if (f.to && sy > +f.to) return;
      games.s[k].forEach(function (tg) {
        if (f.team && tg[0] !== f.team) return;
        tg[1].forEach(function (g) {
          var t = String(g[5]);
          if (f.k !== "b" && t !== f.k) return;
          if (f.ha === "h" && !g[2]) return;
          if (f.ha === "a" && g[2]) return;
          out.push({ sy: sy, team: tg[0], md: g[0], opp: g[1], home: g[2], ts: g[3], os: g[4], t: t });
        });
      });
    });
    return out;
  }
  function seriesFor(f) {
    var out = {};
    Object.keys(games.ps || {}).forEach(function (k) {
      var sy = +k;
      if (f.from && sy < +f.from) return;
      if (f.to && sy > +f.to) return;
      games.ps[k].forEach(function (x) {
        if (f.team && x[4] !== f.team) return;
        var o = out[x[0]] || (out[x[0]] = [0, 0]);
        o[x[1] ? 0 : 1]++;
      });
    });
    return out;
  }
  function td(lab, text, value, cls) {
    var c = document.createElement("td");
    c.setAttribute("data-l", lab);
    if (cls) c.className = cls;
    if (value !== null && value !== undefined) c.setAttribute("data-value", value);
    if (text instanceof Node) c.appendChild(text); else c.textContent = text;
    return c;
  }
  function oppCell(f, seenNames) {
    var frag = document.createDocumentFragment(), latest = names.latest[f];
    if (names.cm[f]) {
      var a = document.createElement("a");
      a.href = "https://hoopsmatic.com/nba-career-map/team/" + names.cm[f] + ".html";
      a.textContent = latest;
      frag.appendChild(a);
    } else frag.appendChild(document.createTextNode(latest));
    var other = Object.keys(seenNames).filter(function (n) { return n !== latest; }).sort();
    if (other.length) {
      var sp = document.createElement("span");
      sp.className = "sub blk";
      sp.textContent = "as " + other.join(", ");
      frag.appendChild(sp);
    }
    return frag;
  }
  function render() {
    var f = filt(), list = rowsFor(f), by = {}, order = [];
    var ser = seriesFor(f);
    list.forEach(function (g) {
      var r = by[g.opp];
      if (!r) { r = by[g.opp] = { w: 0, l: 0, names: {}, first: 9999, last: 0 }; order.push(g.opp); }
      if (g.ts > g.os) r.w++; else r.l++;
      r.names[nm(g.opp, g.sy)] = 1;
      r.first = Math.min(r.first, g.sy); r.last = Math.max(r.last, g.sy);
    });
    var min = +(f.min || 1);
    var keep = order.filter(function (o) { return by[o].w + by[o].l >= min; });
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    keep.sort(function (a, b) { return (by[b].w + by[b].l) - (by[a].w + by[a].l) || (names.latest[a] < names.latest[b] ? -1 : 1); });
    var tw = 0, tg = 0;
    keep.forEach(function (o) {
      var r = by[o], g = r.w + r.l, s = ser[o] || [0, 0];
      tw += r.w; tg += g;
      var tr = document.createElement("tr");
      tr.id = "vs-" + o;
      tr.setAttribute("data-opp", o);
      tr.appendChild(td("Opponent", oppCell(o, r.names), names.latest[o]));
      tr.appendChild(td("Games", g.toLocaleString("en-US"), g, "mono"));
      tr.appendChild(td("W" + EN + "L", wl(r.w, r.l), r.w, "mono"));
      tr.appendChild(td("Win %", pct1(r.w / g), (r.w / g).toFixed(6), "mono"));
      tr.appendChild(td("W " + MINUS + " L", signed(r.w - r.l), r.w - r.l, "mono " + (r.w > r.l ? "up" : (r.w < r.l ? "down" : "flat"))));
      tr.appendChild(td("Playoff series", (s[0] + s[1]) ? s[0] + EN + s[1] : "N/A", (s[0] + s[1]) ? s[0] - s[1] : null));
      tr.appendChild(td("Seasons", r.first === r.last ? label(r.first) : label(r.first) + " to " + label(r.last), r.first, "mono"));
      var b = document.createElement("button");
      b.type = "button"; b.className = "opp-open"; b.textContent = "Show games";
      b.setAttribute("aria-expanded", "false"); b.setAttribute("aria-controls", "games-" + o);
      tr.appendChild(td("Games list", b));
      tbody.appendChild(tr);
    });
    var kind = { "2": "Regular season", "4": "Playoffs", "b": "Regular season and playoffs" }[f.k];
    document.getElementById("opp-pop").textContent = kind + ": " + tg.toLocaleString("en-US") + " games, " + wl(tw, tg - tw) +
      ", against " + keep.length + " franchises" + (min > 1 ? " (" + min + "+ games)" : "") + ".";
    var sorted = table.tHead.querySelector("th[aria-sort]");
    if (sorted && window.TS) window.TS.sortTable(table, sorted, sorted.getAttribute("aria-sort"));
  }
  function openGames(tr, btn) {
    var o = tr.getAttribute("data-opp");
    var next = tr.nextElementSibling;
    if (next && next.classList.contains("detail")) {
      next.parentNode.removeChild(next);
      btn.setAttribute("aria-expanded", "false"); btn.textContent = "Show games";
      return;
    }
    var f = filt(), list = rowsFor(f).filter(function (g) { return g.opp === o; });
    if (+(f.min || 1) > 1 && list.length < +f.min) list = [];
    var det = document.createElement("tr");
    det.className = "detail";
    det.id = "games-" + o;
    var cell = document.createElement("td");
    cell.colSpan = 8;
    var bySy = {};
    list.forEach(function (g) { (bySy[g.sy] = bySy[g.sy] || []).push(g); });
    Object.keys(bySy).sort(function (a, b) { return b - a; }).forEach(function (sy) {
      var h = document.createElement("h4");
      var gl = bySy[sy], w = gl.filter(function (g) { return g.ts > g.os; }).length;
      h.textContent = label(+sy) + ": " + wl(w, gl.length - w);
      var ps = (games.ps && games.ps[sy] || []).filter(function (x) { return x[0] === o; });
      if (ps.length && f.k !== "2") h.textContent += " (playoff series " + (ps[0][1] ? "won " : "lost ") + ps[0][2] + EN + ps[0][3] + ")";
      cell.appendChild(h);
      var ol = document.createElement("ol");
      ol.className = "glist";
      gl.sort(function (a, b) { return ((a.md < 800 ? a.md + 10000 : a.md) - (b.md < 800 ? b.md + 10000 : b.md)); });
      gl.forEach(function (g) {
        var li = document.createElement("li");
        var won = g.ts > g.os;
        li.textContent = date(g.sy, g.md) + (g.t === "4" ? " (playoffs)" : "") + ": " + nm(g.team, g.sy) +
          (g.home ? " vs " : " at ") + nm(g.opp, g.sy) + ", " + (won ? "W " : "L ") + g.ts + EN + g.os;
        li.className = won ? "w" : "l";
        ol.appendChild(li);
      });
      cell.appendChild(ol);
    });
    if (!list.length) cell.textContent = "No games with these filters.";
    det.appendChild(cell);
    tr.parentNode.insertBefore(det, tr.nextSibling);
    btn.setAttribute("aria-expanded", "true"); btn.textContent = "Hide games";
  }
  table.addEventListener("click", function (ev) {
    var b = ev.target.closest ? ev.target.closest("button.opp-open") : null;
    if (!b) return;
    var tr = b.closest("tr");
    load(function () { openGames(tr, b); });
  });
  form.addEventListener("change", function () { load(render); });
  form.addEventListener("submit", function (ev) { ev.preventDefault(); load(render); });
  var reset = form.querySelector(".opp-reset");
  if (reset) reset.addEventListener("click", function () { form.reset(); load(render); });
  // ?vs=BOS (&k=4): open that opponent's games (links from the takeaways and the daily lead)
  var q = new URLSearchParams(location.search), vs = q.get("vs");
  if (vs) {
    load(function () {
      if (q.get("k")) { form.querySelector('[name="k"]').value = q.get("k"); }
      render();
      var tr = document.getElementById("vs-" + vs);
      if (tr) { openGames(tr, tr.querySelector("button.opp-open")); tr.scrollIntoView({ block: "start" }); }
    });
  }
})();

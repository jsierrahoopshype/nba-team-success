// (c) 2026 HoopsMatic. All rights reserved.
// Team Success career leaderboards, hm-ts-7f3a91c2-boards. Mirrors scripts/boards.py compute()
// rule for rule (tests/test_boards.py runs both on the same data and compares). Filters live in the
// URL; the page HTML holds the default view, this script redraws the ranked rows for any filter.
// Every value goes in through textContent; nothing is parsed as HTML.
(function () {
  var isNode = typeof module !== "undefined" && module.exports;
  var root = isNode ? null : document.getElementById("board");
  if (!root && !isNode) return;
  var DEF = root ? JSON.parse(root.getAttribute("data-def")) : null;
  var UP = root ? root.getAttribute("data-up") : "";
  var DEPTH = [0, 0, 1, 2, 3, 4, 5];
  var DEPTH_LABEL = { 5: "Won the title", 4: "NBA Finals", 3: "Conference finals", 2: "Conference semifinals", 1: "First round", 0: "Missed playoffs" };
  var EN = "–", MINUS = "−";
  var data = null;
  var shown = 100;

  function params() {
    var q = new URLSearchParams(location.search), f = {};
    ["from", "to", "season", "ts", "cg", "ms", "mp", "mm"].forEach(function (k) {
      var v = q.get(k);
      if (v !== null && v !== "" && !isNaN(parseInt(v, 10))) f[k] = parseInt(v, 10);
    });
    ["team", "as", "st", "sort", "hl", "self"].forEach(function (k) { var v = q.get(k); if (v) f[k] = v; });
    if (f.season) { f.from = f.season; f.to = f.season; }
    return f;
  }

  function metrics(row, teams, f) {
    var lo = f.from || data.first, hi = f.to || data.last, ts = f.ts || 1, team = f.team || "";
    var active = row[3], allstar = row[4], stints = row[5];
    var inc = stints.filter(function (s) { return lo <= s[0] && s[0] <= hi && s[2] >= ts && (!team || s[1] === team); });
    if (f.noas) {                                    // winning without an All-Star teammate
      inc = inc.filter(function (s) { return s[10] && !s[12]; });   // seasons with no honors data are left out
      if (f.self === "yes") inc = inc.filter(function (s) { return s[11]; });
      else if (f.self === "no") inc = inc.filter(function (s) { return !s[11]; });
    }
    if (!inc.length) return null;
    if (f.st === "active" && !active) return null;
    if (f.st === "retired" && active) return null;
    if (f.as === "ever" && !allstar.length) return null;
    if (f.as === "season" && !(lo === hi && allstar.indexOf(lo) >= 0)) return null;
    var w = 0, l = 0, ow = 0, ol = 0, by = {}, order = [];
    inc.forEach(function (s) {
      w += s[3]; l += s[4]; ow += s[5]; ol += s[6];
      if (!by[s[0]]) { by[s[0]] = []; order.push(s[0]); }
      by[s[0]].push(s);
    });
    order.sort(function (a, b) { return a - b; });
    var winning = 0, trips = 0, titles = 0, deep = -1, deepn = 0, rk = 0, adj = 0, years = [], liveN = 0;
    order.forEach(function (sy) {
      var lst = by[sy], main = lst[0], end = null, i;
      if (teams[lst[0][1] + "-" + sy][5]) { liveN++; return; }   // season in progress: W-L only
      // Python max() keeps the FIRST maximal element: replace only on a strictly greater key
      for (i = 1; i < lst.length; i++) {
        if (lst[i][2] > main[2] || (lst[i][2] === main[2] && lst[i][9] > main[9])) main = lst[i];
      }
      for (i = 0; i < lst.length; i++) if (lst[i][7]) { end = lst[i]; break; }
      if (!end) {
        end = lst[0];
        for (i = 1; i < lst.length; i++) if (lst[i][9] > end[9]) end = lst[i];
      }
      var t = teams[main[1] + "-" + sy];
      if (t[0] / (t[0] + t[1]) > 0.5) winning++;
      rk += t[2];
      adj += t[3] > 1 ? (t[2] - 1) / (t[3] - 1) : 0;
      var best = null;
      for (i = 0; i < lst.length; i++) {
        var y = lst[i];
        if (y === end || y[8]) {
          var tt = teams[y[1] + "-" + sy];
          if (best === null || DEPTH[tt[4]] > DEPTH[best[4]]) best = tt;
        }
      }
      var d = best ? DEPTH[best[4]] : 0;
      if (d >= 1) trips++;
      if (best && best[4] === 6) { titles++; years.push(sy); }
      if (d > deep) { deep = d; deepn = 1; } else if (d === deep) deepn++;
    });
    var n = order.length - liveN;
    return { pid: row[0], slug: row[1], name: row[2], hs: row[6] || "", w: w, l: l, ow: ow, ol: ol, gp: w + l, gm: ow + ol, wl: w - l,
      pct: (w + l) ? w / (w + l) : null, seasons: f.noas ? n + liveN : n, winning: winning, wshare: n ? winning / n : null, trips: trips,
      tshare: n ? trips / n : null, titles: titles, years: years, deep: n ? deep : 0, deepn: deepn, avg: n ? rk / n : null, adj: n ? adj / n : null,
      gap: ((w + l) && (ow + ol)) ? (w / (w + l)) - (ow / (ow + ol)) : null };
  }

  function r9(v) { return Math.round(v * 1e9) / 1e9; }
  function cmpName(a, b) { return a < b ? -1 : (a > b ? 1 : 0); }   // Python str order

  function key(sort, m) {
    var v = m[sort];
    if (sort === "deep") return [-v, [-m.deepn, m.name]];
    if (sort === "avg" || sort === "adj") return [r9(v), [m.name]];
    if (sort === "w") return [-v, [m.l, m.name]];
    if (sort === "wl") return [-v, [-m.w, m.name]];
    if (sort === "pct" || sort === "wshare" || sort === "tshare" || sort === "gap") {
      var sec = { pct: -m.gp, wshare: -m.seasons, tshare: -m.seasons, gap: -m.gp }[sort];
      return [-r9(v), [sec, m.name]];
    }
    return [-v, [-m.seasons, m.name]];
  }
  function cmpKey(a, b) {
    if (a[0] !== b[0]) return a[0] < b[0] ? -1 : 1;
    for (var i = 0; i < a[1].length; i++) {
      var x = a[1][i], y = b[1][i];
      if (x === y) continue;
      if (typeof x === "string") return cmpName(x, y);
      return x < y ? -1 : 1;
    }
    return 0;
  }

  function compute(f) {
    if (DEF.noas) f.noas = 1;
    var sorts = DEF.sorts, sort = f.sort && sorts[f.sort] ? f.sort : Object.keys(sorts)[0];
    var mins = {}, base = sorts[sort][2];
    Object.keys(base).forEach(function (k) { mins[k] = base[k]; });
    ["cg", "ms", "mp", "mm"].forEach(function (k) { if (k in f) mins[k] = f[k]; });
    if (!("cg" in mins)) mins.cg = 1;
    var out = [];
    data.p.forEach(function (row) {
      var m = metrics(row, data.t, f);
      if (!m || m.gp < mins.cg) return;
      if (m.seasons < (mins.ms || 0)) return;
      if (m.gp < (mins.mp || 0) || m.gm < (mins.mm || 0)) return;
      if (m[sort] === null) return;
      m._k = key(sort, m);
      out.push(m);
    });
    out.sort(function (a, b) { return cmpKey(a._k, b._k); });
    var rank = 0, prev = null, cnt = {};
    out.forEach(function (m, i) {
      if (prev === null || m._k[0] !== prev) { rank = i + 1; prev = m._k[0]; }
      m._rank = rank; cnt[rank] = (cnt[rank] || 0) + 1;
    });
    out.forEach(function (m) { m._tied = cnt[m._rank] > 1; });
    return { rows: out, sort: sort, mins: mins };
  }

  if (isNode) {
    // tests/test_boards.py: node -e 'require("./assets/boards.js").run(data, def, filter)'
    module.exports = { run: function (d, def, f) { data = d; DEF = def; if (f.season) { f.from = f.season; f.to = f.season; } return compute(f); } };
    return;
  }

  // ---- formatting (same as build_site.py)
  function pct1(p) { return p === null ? "N/A" : (100 * p).toFixed(1) + "%"; }
  function pp(g) {           // the gap between two win %s, in points (no unit sign: "+26.0")
    if (g === null) return "N/A";
    var v = Math.round(1000 * g) / 10;
    if (v === 0) return "0.0";
    return (v > 0 ? "+" : MINUS) + Math.abs(v).toFixed(1);
  }
  function signed(n) { return (n > 0 ? "+" : (n < 0 ? MINUS : "")) + Math.abs(n).toLocaleString("en-US"); }
  function wl(w, l) { return (w + l) ? w + EN + l : "N/A"; }
  function label(sy) { return (sy - 1) + "-" + String(sy).slice(-2); }
  function cell(col, m) {
    switch (col) {
      case "w": return [m.w, m.w.toLocaleString("en-US")];
      case "l": return [m.l, m.l.toLocaleString("en-US")];
      case "pct": return [m.pct, pct1(m.pct)];
      case "gp": return [m.gp, m.gp.toLocaleString("en-US")];
      case "gm": return [m.gm, m.gm.toLocaleString("en-US")];
      case "wl": return [m.wl, signed(m.wl)];
      case "rec": return [m.w, wl(m.w, m.l)];
      case "winning": return [m.winning, String(m.winning)];
      case "seasons": return [m.seasons, String(m.seasons)];
      case "wshare": return [m.wshare, pct1(m.wshare)];
      case "trips": return [m.trips, String(m.trips)];
      case "tshare": return [m.tshare, pct1(m.tshare)];
      case "deep": return [m.deep, DEPTH_LABEL[m.deep]];
      case "deepn": return [m.deepn, String(m.deepn)];
      case "titles": return [m.titles, String(m.titles)];
      case "years": return [m.years.length, m.years.map(label).join(", ") || "N/A"];
      case "avg": return [m.avg, m.avg === null ? "N/A" : m.avg.toFixed(1)];
      case "adj": return [m.adj, m.adj === null ? "N/A" : (1 + 29 * m.adj).toFixed(1)];   // 30-team scale
      case "gap": return [m.gap, pp(m.gap)];
      case "with": return [m.pct, wl(m.w, m.l) + ", " + pct1(m.pct)];
      case "without": return [m.gm ? m.ow / m.gm : null, wl(m.ow, m.ol) + ", " + pct1(m.gm ? m.ow / m.gm : null)];
    }
    return [null, ""];
  }

  function row(m, hl) {
    var tr = document.createElement("tr");
    tr.id = "p-" + m.slug;
    if (hl) tr.className = "hl";
    var td = document.createElement("td");
    td.setAttribute("data-l", "Rank");
    td.className = "mono";
    td.setAttribute("data-value", m._rank);
    td.textContent = (m._tied ? "T-" : "") + m._rank;
    tr.appendChild(td);
    td = document.createElement("td");
    td.setAttribute("data-l", "Player");
    var wrapN = document.createElement("span");
    wrapN.className = "tmn";
    var face = document.createElement("span");
    face.className = "hs sm" + (m.hs ? "" : " nohs");
    if (m.hs) {
      var im = document.createElement("img");
      im.src = UP + "assets/hs/" + m.hs; im.alt = ""; im.width = 160; im.height = 160; im.loading = "lazy";
      face.appendChild(im);
    } else {
      var w = m.name.replace(/\./g, " ").split(/\s+/).filter(function (x) { return x && !/^(jr|sr|ii|iii|iv|v),?$/i.test(x); });
      face.textContent = w.length ? (w[0][0] + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase() : "?";
    }
    var a = document.createElement("a");
    a.href = UP + "player/" + encodeURIComponent(m.slug) + ".html";
    a.textContent = m.name;
    wrapN.appendChild(face); wrapN.appendChild(document.createTextNode(" ")); wrapN.appendChild(a);
    td.appendChild(wrapN);
    tr.appendChild(td);
    DEF.cols.forEach(function (c) {
      var v = cell(c, m), x = document.createElement("td");
      x.setAttribute("data-l", DEF.labels[c]);
      x.className = "mono";
      if (v[0] !== null) x.setAttribute("data-value", v[0]);
      x.textContent = v[1];
      tr.appendChild(x);
    });
    return tr;
  }

  function render() {
    var f = params();
    var res = compute(f);
    var tbody = document.querySelector("#board tbody");
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    var hlAt = -1;
    if (f.hl) res.rows.forEach(function (m, i) { if (m.slug === f.hl) hlAt = i; });
    var lim = Math.min(shown, res.rows.length);
    for (var i = 0; i < lim; i++) tbody.appendChild(row(res.rows[i], i === hlAt));
    if (hlAt >= lim) {
      var gap = document.createElement("tr");
      gap.className = "gaprow";
      var g = document.createElement("td");
      g.colSpan = DEF.cols.length + 2;
      g.textContent = "…";
      gap.appendChild(g);
      tbody.appendChild(gap);
      for (i = Math.max(lim, hlAt - 3); i < Math.min(res.rows.length, hlAt + 4); i++) tbody.appendChild(row(res.rows[i], i === hlAt));
    }
    // sort state in the header (visible on phones too)
    var ths = document.querySelectorAll("#board thead th[data-sort]");
    for (i = 0; i < ths.length; i++) {
      var s = ths[i].getAttribute("data-sort");
      if (s === res.sort) ths[i].setAttribute("aria-sort", DEF.sorts[s][1] === "asc" ? "ascending" : "descending");
      else ths[i].removeAttribute("aria-sort");
    }
    var pop = document.getElementById("board-pop");
    if (pop) {
      var minTxt = [];
      if (res.mins.cg > 1) minTxt.push(res.mins.cg.toLocaleString("en-US") + "+ career games");
      if (res.mins.ms) minTxt.push(res.mins.ms + "+ seasons");
      if (res.mins.mp) minTxt.push(res.mins.mp + "+ games played");
      if (res.mins.mm) minTxt.push(res.mins.mm + "+ games missed");
      pop.textContent = res.rows.length.toLocaleString("en-US") + " players qualify" + (minTxt.length ? " (" + minTxt.join(", ") + ")" : "") + ". Ranked by " + DEF.sorts[res.sort][0] + "; equal values share a rank (T-).";
    }
    var more = document.getElementById("board-more");
    if (more) more.hidden = shown >= res.rows.length;
    var st = document.getElementById("board-status");
    if (st) st.textContent = res.rows.length + " players, ranked by " + DEF.sorts[res.sort][0];
    if (hlAt >= 0) {
      var el = document.getElementById("p-" + f.hl);
      if (el) el.scrollIntoView({ block: "center" });
    }
  }

  function load(cb) {
    if (data) return cb();
    fetch(UP + "assets/board.json", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (j) { data = j; cb(); });
  }

  // filter form: apply in place and keep the state in the URL
  var form = document.getElementById("board-form");
  function apply() {
    var q = new URLSearchParams();
    var fd = new FormData(form);
    fd.forEach(function (v, k) { if (v !== "" && !(k === "cgp" || k === "tsp")) q.set(k, v); });
    // presets write into the number boxes
    var keep = new URLSearchParams(location.search).get("hl");
    if (keep) q.set("hl", keep);
    history.replaceState(null, "", location.pathname + (q.toString() ? "?" + q.toString() : ""));
    shown = 100;
    load(render);
  }
  if (form) {
    form.addEventListener("submit", function (ev) { ev.preventDefault(); apply(); });
    form.addEventListener("change", function (ev) {
      var t = ev.target;
      if (t.getAttribute("data-preset")) {
        var box = form.querySelector('[name="' + t.getAttribute("data-preset") + '"]');
        if (box && t.value) box.value = t.value;
      }
      apply();
    });
    // fill the form from the URL
    var f0 = new URLSearchParams(location.search);
    f0.forEach(function (v, k) { var el = form.querySelector('[name="' + k + '"]'); if (el) el.value = v; });
  }
  var head = document.querySelector("#board thead");
  if (head) head.addEventListener("click", function (ev) {
    var b = ev.target.closest ? ev.target.closest("th[data-sort] > button") : null;
    if (!b) return;
    var s = b.parentNode.getAttribute("data-sort");
    var sel = form && form.querySelector('[name="sort"]');
    if (sel) sel.value = s;
    apply();
  });
  var more = document.getElementById("board-more");
  if (more) more.addEventListener("click", function () { shown += 100; load(render); });
  if (location.search) load(render);
})();

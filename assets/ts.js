// (c) 2026 HoopsMatic. All rights reserved.
// Team Success shared script, hm-ts-7f3a91c2-ts. No third-party code, no network beyond this site.
// 1) A URL with a query string is a filtered/sorted view of a page: tell crawlers not to index it
//    (the canonical already points at the unfiltered page).
// 2) Sortable tables (Chrome Modern Web Guidance "sortable-table"): a <button> in each sortable
//    <th>, aria-sort on the sorted header only, raw values from data-value, Intl.Collator for text,
//    existing rows moved (never re-rendered), one role="status" message per sort.
(function () {
  // old in-page comparison links (player/<slug>.html?peer=<slug>) now open the compare page
  var pr = document.querySelector("[data-peer-redirect]"), peer = new URLSearchParams(location.search).get("peer");
  if (pr && peer) {
    location.replace(pr.getAttribute("data-up") + "compare/?a=" + encodeURIComponent(pr.getAttribute("data-peer-redirect")) +
      "&b=" + encodeURIComponent(peer));
    return;
  }
  if (location.search && !document.querySelector('meta[name="robots"]')) {
    var m = document.createElement("meta");
    m.name = "robots";
    m.content = "noindex, follow";
    document.head.appendChild(m);
  }

  var collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });

  function cellValue(row, i) {
    var c = row.cells[i];
    if (!c) return "";
    var v = c.getAttribute("data-value");
    return v !== null ? v : c.textContent.trim();
  }

  function sortTable(table, th, direction) {
    var tbody = table.tBodies[0];
    var head = table.tHead.rows[0].cells;
    var i = Array.prototype.indexOf.call(head, th);
    var type = th.getAttribute("data-type") || "text";
    var factor = direction === "ascending" ? 1 : -1;
    // an opened detail row (class "detail") travels with the row above it
    var rows = Array.prototype.slice.call(tbody.rows).filter(function (r) {
      return !r.classList.contains("detail");
    }).map(function (r, k) {
      var v = cellValue(r, i);
      return { r: r, k: k, v: type === "number" ? (v === "" ? NaN : parseFloat(v)) : v };
    });
    rows.sort(function (a, b) {
      var d;
      if (type === "number") {
        var an = isNaN(a.v), bn = isNaN(b.v);
        if (an || bn) return an === bn ? a.k - b.k : (an ? 1 : -1);   // N/A always last
        d = a.v - b.v;
      } else {
        d = collator.compare(a.v, b.v);
      }
      return d ? factor * d : a.k - b.k;                               // stable
    });
    for (var h = 0; h < head.length; h++) head[h].removeAttribute("aria-sort");
    th.setAttribute("aria-sort", direction);
    rows.forEach(function (x) {
      var det = x.r.nextElementSibling && x.r.nextElementSibling.classList.contains("detail") ? x.r.nextElementSibling : null;
      if (tbody.moveBefore) tbody.moveBefore(x.r, null); else tbody.appendChild(x.r);
      if (det) { if (tbody.moveBefore) tbody.moveBefore(det, null); else tbody.appendChild(det); }
    });
    var st = table.parentNode.querySelector(".sort-status");
    var label = th.querySelector("button");
    if (st) st.textContent = "Sorted by " + (label ? label.textContent.trim() : "") + ", " + direction + ", " + rows.length + " rows";
  }

  function wire(table) {
    table.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("th > button") : null;
      if (!b || !table.contains(b)) return;
      var th = b.parentNode;
      var cur = th.getAttribute("aria-sort");
      // first click: the column's natural direction (numbers high to low unless data-first says asc)
      var first = th.getAttribute("data-first") || (th.getAttribute("data-type") === "number" ? "descending" : "ascending");
      var dir = cur ? (cur === "ascending" ? "descending" : "ascending") : first;
      sortTable(table, th, dir);
    });
  }

  var tables = document.querySelectorAll("table.sortable");
  for (var t = 0; t < tables.length; t++) wire(tables[t]);
  window.TS = window.TS || {};
  window.TS.sortTable = sortTable;
})();

// 3) Player finder (combobox + listbox, WAI-ARIA pattern). The suggestions render IN THE PAGE
//    FLOW under the input (they push content down; no pop-up, no floating dropdown). Arrow keys
//    move, Enter opens, Esc clears. Headshots and years/teams tell same-name players apart.
//    data-mode="go" opens the player page; "cmp" opens compare/?a=<data-a>&b=<slug>; "side" fills
//    one side of the compare page (TSCompare.set).
(function () {
  var boxes = document.querySelectorAll(".finder");
  if (!boxes.length) return;
  var index = null, waiting = [];
  function fold(s) {
    return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/['’.]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  }
  function load(src, cb) {
    if (index) return cb();
    waiting.push(cb);
    if (waiting.length > 1) return;
    fetch(src, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (rows) {
      index = rows.map(function (r) { return { n: r[0], s: r[1], a: r[2], b: r[3], h: r[4] || "", t: r[5] || "", f: fold(r[0]) }; });
      var w = waiting; waiting = []; w.forEach(function (f) { f(); });
    });
  }
  Array.prototype.forEach.call(boxes, function (box, k) {
    var input = box.querySelector("input");
    var list = box.querySelector("ul");
    var up = box.getAttribute("data-up") || "";
    var mode = box.getAttribute("data-mode") || "go";
    var active = -1, hits = [];
    list.id = list.id || "finder-list-" + k;
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", list.id);
    input.setAttribute("aria-expanded", "false");
    list.setAttribute("role", "listbox");
    function choose(h) {
      if (!h) return;
      if (mode === "cmp") {            // player page block: open the compare page with him on the left
        location.href = up + "compare/?a=" + encodeURIComponent(box.getAttribute("data-a")) + "&b=" + encodeURIComponent(h.s);
        return;
      }
      if (mode === "side" && window.TSCompare) {   // compare page: fill one side, stay on the page
        input.value = h.n; clear(); window.TSCompare.set(box.getAttribute("data-side"), h.s); return;
      }
      location.href = up + "player/" + encodeURIComponent(h.s) + ".html";
    }
    function clear() {
      while (list.firstChild) list.removeChild(list.firstChild);
      hits = []; active = -1;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }
    function mark() {
      Array.prototype.forEach.call(list.children, function (li, i) {
        li.setAttribute("aria-selected", i === active ? "true" : "false");
      });
      if (active >= 0 && list.children[active]) input.setAttribute("aria-activedescendant", list.children[active].id);
      else input.removeAttribute("aria-activedescendant");
    }
    function render() {
      var q = fold(input.value);
      clear();
      if (q.length < 2) return;
      var words = q.split(" "), found = [];
      for (var i = 0; i < index.length; i++) {
        var f = index[i].f, ok = true, starts = 0;
        for (var j = 0; j < words.length; j++) {
          var at = f.indexOf(words[j]);
          if (at === -1) { ok = false; break; }
          if (at === 0 || f.charAt(at - 1) === " " || (" " + f).indexOf(" " + words[j]) >= 0) starts++;
        }
        if (!ok) continue;
        // rank: full name starts with the query, every word starts a name part, longer careers first
        var span = index[i].a ? (+index[i].b.slice(0, 4) - +index[i].a.slice(0, 4)) : 0;
        found.push({ h: index[i], k: (f.indexOf(q) === 0 ? 2 : 0) + (starts === words.length ? 1 : 0), span: span });
      }
      found.sort(function (x, y) { return (y.k - x.k) || (y.span - x.span) || (x.h.n < y.h.n ? -1 : 1); });
      hits = found.slice(0, 8).map(function (x) { return x.h; });
      if (!hits.length) {
        var none = document.createElement("li");
        none.className = "none"; none.textContent = "No player found.";
        list.appendChild(none);
        return;
      }
      hits.forEach(function (h, i) {
        var li = document.createElement("li");
        li.id = list.id + "-o" + i;
        li.setAttribute("role", "option");
        var pic = h.h ? document.createElement("img") : document.createElement("span");
        pic.className = "hs sm" + (h.h ? "" : " nohs");
        if (h.h) { pic.src = up + "assets/hs/" + h.h; pic.alt = ""; pic.width = 36; pic.height = 36; pic.loading = "lazy"; }
        li.appendChild(pic);
        var txt = document.createElement("span");
        var nm = document.createElement("strong"); nm.textContent = h.n;
        var ctx = document.createElement("span"); ctx.className = "sub blk";
        ctx.textContent = (h.a ? h.a + (h.b && h.b !== h.a ? " to " + h.b : "") : "") + (h.t ? " · " + h.t : "");
        txt.appendChild(nm); txt.appendChild(ctx);
        li.appendChild(txt);
        li.addEventListener("click", function () { choose(h); });
        list.appendChild(li);
      });
      input.setAttribute("aria-expanded", "true");
    }
    input.addEventListener("input", function () { load(box.getAttribute("data-index"), render); });
    input.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowDown" && hits.length) { active = (active + 1) % hits.length; mark(); ev.preventDefault(); }
      else if (ev.key === "ArrowUp" && hits.length) { active = (active - 1 + hits.length) % hits.length; mark(); ev.preventDefault(); }
      else if (ev.key === "Enter") {
        if (ev.isComposing) return;
        ev.preventDefault();
        load(box.getAttribute("data-index"), function () { if (!hits.length) render(); choose(hits[active >= 0 ? active : 0]); });
      }
      else if (ev.key === "Escape") { input.value = ""; clear(); }
    });
    var form = box.closest("form");
    if (form) form.addEventListener("submit", function (ev) { ev.preventDefault(); });
  });
})();

// 4) Separate minimums for games played and missed (current with/without board). Rows carry
//    data-gp / data-gm; rows below either minimum are hidden. State is kept in the URL.
(function () {
  var f = document.getElementById("minf");
  if (!f) return;
  var q = new URLSearchParams(location.search);
  ["mp", "mm"].forEach(function (k) { if (q.get(k)) f.querySelector('[name="' + k + '"]').value = q.get(k); });
  function apply() {
    var mp = +f.querySelector('[name="mp"]').value || 1, mm = +f.querySelector('[name="mm"]').value || 1;
    var rows = document.querySelectorAll("table.minfilter tbody tr");
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      r.hidden = (+r.getAttribute("data-gp") < mp) || (+r.getAttribute("data-gm") < mm);
    }
    var p = new URLSearchParams(location.search);
    p.set("mp", mp); p.set("mm", mm);
    history.replaceState(null, "", location.pathname + "?" + p.toString());
  }
  f.addEventListener("input", apply);
  // ?hl=<slug>: highlight that player's row (links from the homepage list)
  var hl = q.get("hl"), hr = hl && document.getElementById("p-" + hl);
  if (hr) { hr.classList.add("hl"); setTimeout(function () { if (!hr.hidden) hr.scrollIntoView({ block: "center" }); }, 50); }
  f.addEventListener("submit", function (ev) { ev.preventDefault(); apply(); });
  // the defaults come from the page (data-mp / data-mm, the same constants as the initial HTML)
  if (q.get("mp") || q.get("mm")) apply(); else {
    var dmp = +f.getAttribute("data-mp") || 1, dmm = +f.getAttribute("data-mm") || 1;
    var rows = document.querySelectorAll("table.minfilter tbody tr");
    for (var i = 0; i < rows.length; i++) rows[i].hidden = (+rows[i].getAttribute("data-gp") < dmp) || (+rows[i].getAttribute("data-gm") < dmm);
  }
})();

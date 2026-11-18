// (c) 2026 HoopsMatic. All rights reserved.
// Team Success shared script, hm-ts-7f3a91c2-ts. No third-party code, no network beyond this site.
// 1) A URL with a query string is a filtered/sorted view of a page: tell crawlers not to index it
//    (the canonical already points at the unfiltered page).
// 2) Sortable tables (Chrome Modern Web Guidance "sortable-table"): a <button> in each sortable
//    <th>, aria-sort on the sorted header only, raw values from data-value, Intl.Collator for text,
//    existing rows moved (never re-rendered), one role="status" message per sort.
(function () {
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
    var rows = Array.prototype.slice.call(tbody.rows).map(function (r, k) {
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
      if (tbody.moveBefore) tbody.moveBefore(x.r, null); else tbody.appendChild(x.r);
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

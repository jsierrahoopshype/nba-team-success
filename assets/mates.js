// (c) 2026 HoopsMatic. All rights reserved.
// Team Success, hm-ts-7f3a91c2-mates. Player page, "With and without his teammates": two sort buttons
// over the same 12 rows (built in the page by build_site.py mates_section). "Most games together" is
// the order the page ships with; "Biggest gap" sorts by the size of the gap, rows with too few games
// without him last. The buttons stay hidden without JavaScript. No data is fetched.
(function () {
  var sec = document.getElementById("mates");
  if (!sec) return;
  var bar = sec.querySelector(".msort"), list = sec.querySelector("ol.mates");
  if (!bar || !list) return;
  var rows = Array.prototype.slice.call(list.children);
  rows.forEach(function (li, i) { li.setAttribute("data-i", String(i)); });
  function num(li, k) { var v = li.getAttribute(k); return v === "" || v === null ? null : parseFloat(v); }
  function sortBy(k) {
    var out = rows.slice();
    if (k === "gap") {
      out.sort(function (a, b) {
        var x = num(a, "data-gap"), y = num(b, "data-gap");
        if (x === null && y === null) return num(a, "data-i") - num(b, "data-i");
        if (x === null) return 1;
        if (y === null) return -1;
        return y - x || num(a, "data-i") - num(b, "data-i");
      });
    } else {
      out.sort(function (a, b) { return num(a, "data-i") - num(b, "data-i"); });
    }
    out.forEach(function (li) { list.appendChild(li); });
    Array.prototype.forEach.call(bar.querySelectorAll("button"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-k") === k ? "true" : "false");
    });
  }
  bar.addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-k]");
    if (b) sortBy(b.getAttribute("data-k"));
  });
  bar.hidden = false;
})();

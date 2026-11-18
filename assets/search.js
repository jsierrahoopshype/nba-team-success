// (c) 2026 HoopsMatic. All rights reserved.
// Team Success player search, hm-ts-7f3a91c2-search. Results are listed in the page under
// the box (no pop-up). Every value goes in through textContent; nothing is parsed as HTML.
(function () {
  var form = document.getElementById("ts-search");
  var input = document.getElementById("q");
  var list = document.getElementById("results");
  if (!form || !input || !list) return;
  var index = null;
  var loading = false;
  function fold(s) {
    return s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
      .replace(/['\u2019.]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  }
  var pending = null;
  function load(cb) {
    if (index) return cb();
    pending = cb;              // the latest request runs once the index arrives
    if (loading) return;
    loading = true;
    fetch(input.getAttribute("data-index"), { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (rows) {
        index = rows.map(function (r) { return { n: r[0], s: r[1], a: r[2], b: r[3], f: fold(r[0]) }; });
        if (pending) pending();
        pending = null;
      })
      .catch(function () { loading = false; });
  }
  function render() {
    var q = fold(input.value);
    while (list.firstChild) list.removeChild(list.firstChild);
    if (q.length < 2) return;
    var words = q.split(" ");
    var hits = [];
    for (var i = 0; i < index.length && hits.length < 25; i++) {
      var ok = true;
      for (var j = 0; j < words.length; j++) {
        if (index[i].f.indexOf(words[j]) === -1) { ok = false; break; }
      }
      if (ok) hits.push(index[i]);
    }
    if (!hits.length) {
      var li0 = document.createElement("li");
      li0.textContent = "No player found.";
      list.appendChild(li0);
      return;
    }
    hits.forEach(function (h) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "player/" + encodeURIComponent(h.s) + ".html";
      a.textContent = h.n;
      var span = document.createElement("span");
      span.className = "sub";
      span.textContent = h.a ? " " + h.a + (h.b && h.b !== h.a ? " to " + h.b : "") : "";
      li.appendChild(a);
      li.appendChild(span);
      list.appendChild(li);
    });
  }
  input.addEventListener("input", function () { load(render); });
  input.addEventListener("focus", function () { load(function () {}); });
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    load(function () {
      render();
      var first = list.querySelector("a");
      if (first) window.location.href = first.href;
    });
  });
})();

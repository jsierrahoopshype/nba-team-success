// (c) 2026 HoopsMatic. All rights reserved.
// Team Success, hm-ts-7f3a91c2-swings. "Biggest teammate swings": the three views are CSS radio pills
// (they work without JavaScript); this keeps the chosen one in the address (?f=both, ?f=all; the default
// view has no parameter) so a filtered view can be shared. ts.js marks any filtered address noindex.
(function () {
  var VIEWS = ["as", "both", "all"];
  var radios = VIEWS.map(function (k) { return document.getElementById("tsw-" + k); });
  if (radios.some(function (r) { return !r; })) return;
  var f = new URLSearchParams(location.search).get("f");
  var i = VIEWS.indexOf(f);
  if (i > 0) radios[i].checked = true;
  radios.forEach(function (r, j) {
    r.addEventListener("change", function () {
      if (!r.checked) return;
      var q = new URLSearchParams(location.search);
      if (j === 0) q.delete("f"); else q.set("f", VIEWS[j]);
      var qs = q.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    });
  });
})();

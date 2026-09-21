(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("metrics-data").textContent);

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function renderTiles() {
    var host = document.getElementById("tiles");
    var refs = data.referrals || {};
    var tiles = [
      { value: data.totals.applications, label: "applications tracked" },
      { value: data.totals.companies, label: "companies in the pipeline" },
      { value: refs.needed || 0, label: "needed a warm intro" },
      { value: (refs.conversion_pct || 0) + "%", label: "referral conversion" }
    ];
    tiles.forEach(function (t) {
      var tile = el("div", "tile");
      tile.appendChild(el("div", "value", t.value));
      tile.appendChild(el("div", "label", t.label));
      host.appendChild(tile);
    });
  }

  function renderBars(hostId, entries) {
    var host = document.getElementById(hostId);
    var max = entries.reduce(function (m, e) { return Math.max(m, e[1]); }, 0) || 1;
    entries.forEach(function (entry) {
      var row = el("div", "bar-row");
      row.appendChild(el("div", "name", entry[0]));
      var track = el("div", "bar-track");
      var bar = el("div", "bar");
      bar.style.width = Math.round((entry[1] / max) * 100) + "%";
      track.appendChild(bar);
      row.appendChild(track);
      row.appendChild(el("div", "count", entry[1]));
      host.appendChild(row);
    });
  }

  renderTiles();
  renderBars("funnel", Object.keys(data.funnel).map(function (k) { return [k, data.funnel[k]]; }));
  renderBars("activity", (data.activity || []).map(function (a) { return [a.month, a.applied]; }));
  renderBars("channels", Object.keys(data.channels || {}).slice(0, 8).map(function (k) {
    return [k, data.channels[k]];
  }));

  document.getElementById("generated").textContent = data.generated_at || "";
})();

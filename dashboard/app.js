(function () {
  "use strict";

  var FUNNEL_STEPS = ["To Apply", "Applied", "Recruiter Call", "Phone Screen", "Onsite", "Offer"];
  var OUTCOME_KEYS = ["Rejected", "Withdrew"];
  var REDUCED_MOTION = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function withAlpha(color, alpha) {
    return "color-mix(in srgb, " + color + " " + Math.round(alpha * 100) + "%, transparent)";
  }

  function chartTheme() {
    return {
      fg: cssVar("--fg"),
      muted: cssVar("--muted"),
      cyan: cssVar("--cyan"),
      magenta: cssVar("--magenta"),
      line: cssVar("--line"),
      surface: cssVar("--surface"),
      ui: cssVar("--font-ui"),
      mono: cssVar("--font-mono")
    };
  }

  function chartAnimation() {
    return REDUCED_MOTION ? false : { duration: 600, easing: "easeOutQuart" };
  }

  function wholeNumberTick(value) {
    return Number.isInteger(value) ? value : null;
  }

  function baseGridOptions(theme) {
    return {
      grid: { color: theme.line, drawTicks: false },
      ticks: { color: theme.muted, font: { size: 12, family: theme.ui } },
      border: { color: theme.line }
    };
  }

  function tooltipOptions(theme, labelFn) {
    var opts = {
      backgroundColor: theme.surface,
      titleColor: theme.fg,
      bodyColor: theme.fg,
      borderColor: theme.line,
      borderWidth: 1,
      padding: 10,
      titleFont: { family: theme.mono, size: 12 },
      bodyFont: { family: theme.ui, size: 13 }
    };
    if (labelFn) opts.callbacks = { label: labelFn };
    return opts;
  }

  // Prints each bar's value past its end, so horizontal bar charts read
  // without hovering (touch screens have no hover).
  var barValueLabels = {
    id: "barValueLabels",
    afterDatasetsDraw: function (chart) {
      var ctx = chart.ctx;
      var theme = chart.options.plugins.barValueLabels || {};
      chart.data.datasets.forEach(function (dataset, i) {
        chart.getDatasetMeta(i).data.forEach(function (bar, j) {
          ctx.save();
          ctx.fillStyle = theme.color;
          ctx.font = "600 12px " + theme.family;
          ctx.textBaseline = "middle";
          ctx.fillText(String(dataset.data[j]), bar.x + 6, bar.y);
          ctx.restore();
        });
      });
    }
  };

  // ---- accessible data tables -----------------------------------------------

  // Every chart gets a visually hidden table of the same numbers, so screen
  // readers get the data rather than a one-line canvas label.
  function renderDataTable(canvasId, caption, headers, rows) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) return;
    var frame = canvas.closest(".chart-frame");
    var tableId = canvasId + "-table";
    var old = document.getElementById(tableId);
    if (old) old.remove();

    var table = el("table", "sr-only");
    table.id = tableId;
    table.appendChild(el("caption", null, caption));
    var head = el("tr");
    headers.forEach(function (h) {
      var th = el("th", null, h);
      th.scope = "col";
      head.appendChild(th);
    });
    var thead = el("thead");
    thead.appendChild(head);
    table.appendChild(thead);
    var tbody = el("tbody");
    rows.forEach(function (r) {
      var tr = el("tr");
      var th = el("th", null, r[0]);
      th.scope = "row";
      tr.appendChild(th);
      tr.appendChild(el("td", null, r[1]));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    frame.insertAdjacentElement("afterend", table);
  }

  // ---- tiles ----------------------------------------------------------------

  function animateCount(node, target, suffix) {
    if (REDUCED_MOTION || typeof target !== "number" || !isFinite(target) || !target) {
      node.textContent = String(target) + suffix;
      return;
    }
    var decimals = Number.isInteger(target) ? 0 : 1;
    var duration = 700;
    var start = null;
    function tick(ts) {
      if (start === null) start = ts;
      var progress = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      node.textContent = (target * eased).toFixed(decimals) + suffix;
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // The ladder shows one answer three ways; fill it from the same payload so
  // the claim "identical" is literally true on the page.
  function renderAnswers(data) {
    var nodes = document.querySelectorAll(".js-total");
    Array.prototype.forEach.call(nodes, function (node) {
      node.textContent = String(data.totals.applications);
    });
  }

  // The funnel bars show where each application is now, so a rejection after
  // an onsite counts as Rejected. Say how many ever reached an interview.
  function renderFunnelNote(data) {
    var node = document.getElementById("funnel-note");
    if (!node) return;
    var i = interviewedTotal(data);
    var closed = i.total - i.active;
    node.textContent = i.total + " reached an interview" +
      (closed > 0 ? ", and " + closed + " of those have since closed" : "") +
      ". \"Applied or engaged\" counts everything past To Apply, including roles where someone reached out first.";
    node.hidden = false;
  }

  function renderTiles(data) {
    var host = document.getElementById("tiles");
    host.textContent = "";
    var refs = data.referrals || {};
    var tiles = [
      { value: data.totals.applications, label: "applications tracked" },
      { value: data.totals.companies, label: "companies in the pipeline" },
      { value: data.totals.interviewed, label: "reached an interview" },
      { value: refs.needed || 0, label: "needed a warm intro" },
      { value: refs.conversion_pct || 0, label: "referral conversion", suffix: "%" }
    ].filter(function (t) { return typeof t.value === "number"; });
    tiles.forEach(function (t, index) {
      var suffix = t.suffix || "";
      var tile = el("div", "tile");
      tile.style.transitionDelay = (index * 40) + "ms";
      var valueNode = el("div", "value", (REDUCED_MOTION ? t.value : 0) + suffix);
      tile.appendChild(valueNode);
      tile.appendChild(el("div", "label", t.label));
      host.appendChild(tile);
      requestAnimationFrame(function () {
        tile.classList.add("is-visible");
        animateCount(valueNode, t.value, suffix);
      });
    });
  }

  // ---- charts ---------------------------------------------------------------

  function horizontalBar(canvas, theme, labels, values, color, unit) {
    return new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: unit,
          data: values,
          backgroundColor: withAlpha(color, 0.85),
          hoverBackgroundColor: color,
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      plugins: [barValueLabels],
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: chartAnimation(),
        layout: { padding: { right: 36 } },
        scales: {
          x: Object.assign({ beginAtZero: true }, baseGridOptions(theme), {
            ticks: { callback: wholeNumberTick, color: theme.muted, font: { size: 12, family: theme.ui } }
          }),
          y: Object.assign({}, baseGridOptions(theme), { grid: { display: false } })
        },
        plugins: {
          legend: { display: false },
          barValueLabels: { color: theme.fg, family: theme.ui },
          tooltip: tooltipOptions(theme, function (ctx) {
            return ctx.parsed.x + " " + unit + (ctx.parsed.x === 1 ? "" : "s");
          })
        }
      }
    });
  }

  function interviewedTotal(data) {
    var f = data.funnel || {};
    var active = ["Recruiter Call", "Phone Screen", "Onsite", "Offer"].reduce(function (sum, k) {
      return sum + (f[k] || 0);
    }, 0);
    var n = data.totals && data.totals.interviewed;
    return { total: typeof n === "number" ? n : active, active: active };
  }

  // A true funnel: how many ever reached each step. Status alone cannot give
  // this, because a rejection after an interview is recorded as Rejected.
  function renderFunnelChart(data, theme) {
    var canvas = document.getElementById("funnel-chart");
    var f = data.funnel || {};
    var total = data.totals.applications;
    var steps = [
      ["Tracked", total],
      ["Applied or engaged", total - (f["To Apply"] || 0)],
      ["Reached an interview", interviewedTotal(data).total],
      ["Offer", f.Offer || 0]
    ];
    renderDataTable("funnel-chart", "How many applications reached each step", ["Step", "Applications"], steps);
    if (!canvas || !window.Chart) return null;
    return horizontalBar(canvas, theme,
      steps.map(function (s) { return s[0]; }),
      steps.map(function (s) { return s[1]; }),
      theme.cyan, "application");
  }

  function renderStandingChart(data, theme) {
    var canvas = document.getElementById("standing-chart");
    var f = data.funnel || {};
    var labels = FUNNEL_STEPS.concat(OUTCOME_KEYS).filter(function (s) {
      return Object.prototype.hasOwnProperty.call(f, s);
    });
    var values = labels.map(function (s) { return f[s] || 0; });
    renderDataTable("standing-chart", "Current status of every application", ["Status", "Applications"],
      labels.map(function (l, i) { return [l, values[i]]; }));
    if (!canvas || !window.Chart) return null;
    return horizontalBar(canvas, theme, labels, values, theme.magenta, "application");
  }

  function renderActivityChart(data, theme) {
    var canvas = document.getElementById("activity-chart");
    var activity = data.activity || [];
    var labels = activity.map(function (a) { return a.month; });
    var values = activity.map(function (a) { return a.applied; });
    renderDataTable("activity-chart", "Applications submitted per month", ["Month", "Applied"],
      labels.map(function (l, i) { return [l, values[i]]; }));
    if (!canvas || !window.Chart) return null;

    return new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Applied",
          data: values,
          borderColor: theme.magenta,
          backgroundColor: withAlpha(theme.magenta, 0.16),
          pointBackgroundColor: theme.magenta,
          pointBorderColor: theme.surface,
          pointRadius: 4,
          pointHoverRadius: 6,
          cubicInterpolationMode: "monotone",
          fill: true,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: chartAnimation(),
        interaction: { mode: "index", intersect: false },
        scales: {
          x: Object.assign({}, baseGridOptions(theme), { grid: { display: false } }),
          y: Object.assign({ beginAtZero: true }, baseGridOptions(theme), {
            ticks: { callback: wholeNumberTick, color: theme.muted, font: { size: 12, family: theme.ui } }
          })
        },
        plugins: {
          legend: { display: false },
          tooltip: tooltipOptions(theme, function (ctx) { return ctx.parsed.y + " applied"; })
        }
      }
    });
  }

  function renderChannelsChart(data, theme) {
    var canvas = document.getElementById("channels-chart");
    var channels = data.channels || {};
    var entries = Object.keys(channels)
      .map(function (k) { return [k, channels[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; })
      .slice(0, 8);
    renderDataTable("channels-chart", "Top application channels", ["Channel", "Applications"], entries);
    if (!canvas || !window.Chart) return null;
    return horizontalBar(canvas, theme,
      entries.map(function (e) { return e[0]; }),
      entries.map(function (e) { return e[1]; }),
      theme.cyan, "application");
  }

  function renderCharts(data) {
    var theme = chartTheme();
    if (window.Chart) {
      Chart.defaults.font.family = theme.ui;
      Chart.defaults.color = theme.muted;
    }
    renderFunnelChart(data, theme);
    renderStandingChart(data, theme);
    renderActivityChart(data, theme);
    renderChannelsChart(data, theme);
  }

  // ---- refreshed timestamp --------------------------------------------------

  function renderGenerated(raw) {
    var node = document.getElementById("generated");
    if (!raw) return;
    var parsed = new Date(raw);
    if (isNaN(parsed.getTime())) {
      node.textContent = raw;
      return;
    }
    node.setAttribute("datetime", parsed.toISOString());
    // dateStyle cannot be combined with timeZoneName, so spell the fields out.
    node.textContent = new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short"
    }).format(parsed);
  }

  // ---- data loading: fetch first, inline script tag as fallback -------------

  function readInlineData() {
    return JSON.parse(document.getElementById("metrics-data").textContent);
  }

  function setLoading(isLoading) {
    document.body.classList.toggle("is-loading", isLoading);
  }

  function render(data) {
    renderTiles(data);
    renderAnswers(data);
    renderFunnelNote(data);
    renderGenerated(data.generated_at);
    // Canvas text uses whatever font is loaded at draw time, so wait for Sora.
    var fontsReady = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
    fontsReady.then(function () {
      renderCharts(data);
      setLoading(false);
    });
  }

  function boot() {
    setLoading(true);
    fetch("./metrics.json?v=" + Date.now(), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("metrics.json responded " + res.status);
        return res.json();
      })
      .then(render)
      .catch(function () {
        // Offline, opened via file://, or metrics.json missing: fall back to
        // the inline, build-time guarded payload so the page still works.
        try {
          render(readInlineData());
        } catch (err) {
          setLoading(false);
        }
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

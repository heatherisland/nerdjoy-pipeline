(function () {
  "use strict";

  var FUNNEL_STEPS = ["To Apply", "Applied", "Recruiter Call", "Phone Screen", "Onsite", "Offer"];
  var OUTCOME_KEYS = ["Rejected", "Withdrew"];

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
    // Chart.js accepts any valid CSS color string, so blend with the page
    // background via color-mix() rather than assuming a particular color
    // notation for the custom property value.
    return "color-mix(in srgb, " + color + " " + Math.round(alpha * 100) + "%, transparent)";
  }

  function chartTheme() {
    return {
      fg: cssVar("--fg"),
      muted: cssVar("--muted"),
      accent: cssVar("--accent"),
      accentSoft: cssVar("--accent-soft"),
      line: cssVar("--line"),
      bg: cssVar("--bg")
    };
  }

  function wholeNumberTick(value) {
    return Number.isInteger(value) ? value : null;
  }

  function baseGridOptions(theme) {
    return {
      grid: { color: theme.line, drawTicks: false },
      ticks: { color: theme.muted, font: { size: 12 } },
      border: { color: theme.line }
    };
  }

  // ---- tiles, with a count-up reveal ----------------------------------

  function animateCount(node, target, opts) {
    opts = opts || {};
    var suffix = opts.suffix || "";
    var duration = opts.duration || 900;
    var start = null;

    if (!target || typeof target !== "number" || !isFinite(target)) {
      node.textContent = String(target) + suffix;
      return;
    }

    function tick(ts) {
      if (start === null) start = ts;
      var progress = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var value = Math.round(target * eased);
      node.textContent = value + suffix;
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function renderTiles(data) {
    var host = document.getElementById("tiles");
    host.textContent = "";
    var refs = data.referrals || {};
    var tiles = [
      { value: data.totals.applications, label: "applications tracked" },
      { value: data.totals.companies, label: "companies in the pipeline" },
      { value: refs.needed || 0, label: "needed a warm intro" },
      { value: refs.conversion_pct || 0, label: "referral conversion", suffix: "%" }
    ];
    tiles.forEach(function (t, index) {
      var tile = el("div", "tile");
      tile.style.transitionDelay = (index * 60) + "ms";
      var valueNode = el("div", "value", "0" + (t.suffix || ""));
      tile.appendChild(valueNode);
      tile.appendChild(el("div", "label", t.label));
      host.appendChild(tile);
      // Force layout before adding the visible class so the CSS transition runs.
      requestAnimationFrame(function () {
        tile.classList.add("is-visible");
        animateCount(valueNode, t.value, { suffix: t.suffix || "" });
      });
    });
  }

  // ---- charts -----------------------------------------------------------

  function destroyChart(chart) {
    if (chart) chart.destroy();
  }

  function renderFunnelChart(data, theme) {
    var canvas = document.getElementById("funnel-chart");
    if (!canvas || !window.Chart) return null;
    var funnel = data.funnel || {};
    var labels = FUNNEL_STEPS.filter(function (step) {
      return Object.prototype.hasOwnProperty.call(funnel, step);
    });
    var values = labels.map(function (step) { return funnel[step] || 0; });

    return new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Applications",
          data: values,
          backgroundColor: withAlpha(theme.accent, 0.85),
          hoverBackgroundColor: theme.accent,
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 900, easing: "easeOutQuart" },
        scales: {
          x: Object.assign({ beginAtZero: true }, baseGridOptions(theme)),
          y: Object.assign({}, baseGridOptions(theme), { grid: { display: false } })
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: theme.bg,
            titleColor: theme.fg,
            bodyColor: theme.fg,
            borderColor: theme.line,
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: function (ctx) { return ctx.parsed.x + " application" + (ctx.parsed.x === 1 ? "" : "s"); }
            }
          }
        }
      }
    });
  }

  function renderFunnelOutcomesChart(data, theme) {
    var canvas = document.getElementById("funnel-outcomes-chart");
    if (!canvas || !window.Chart) return null;
    var funnel = data.funnel || {};
    var labels = OUTCOME_KEYS.filter(function (step) {
      return Object.prototype.hasOwnProperty.call(funnel, step);
    });
    var values = labels.map(function (step) { return funnel[step] || 0; });
    if (!labels.length) return null;

    return new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Count",
          data: values,
          backgroundColor: withAlpha(theme.muted, 0.7),
          hoverBackgroundColor: theme.muted,
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 900, easing: "easeOutQuart" },
        scales: {
          x: Object.assign({ beginAtZero: true }, baseGridOptions(theme)),
          y: Object.assign({}, baseGridOptions(theme), { grid: { display: false } })
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: theme.bg,
            titleColor: theme.fg,
            bodyColor: theme.fg,
            borderColor: theme.line,
            borderWidth: 1,
            padding: 10
          }
        }
      }
    });
  }

  function renderActivityChart(data, theme) {
    var canvas = document.getElementById("activity-chart");
    if (!canvas || !window.Chart) return null;
    var activity = data.activity || [];
    var labels = activity.map(function (a) { return a.month; });
    var values = activity.map(function (a) { return a.applied; });

    return new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Applied",
          data: values,
          borderColor: theme.accent,
          backgroundColor: withAlpha(theme.accent, 0.18),
          pointBackgroundColor: theme.accent,
          pointBorderColor: theme.bg,
          pointRadius: 4,
          pointHoverRadius: 6,
          tension: 0.35,
          fill: true,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 900, easing: "easeOutQuart" },
        interaction: { mode: "index", intersect: false },
        scales: {
          x: Object.assign({}, baseGridOptions(theme), { grid: { display: false } }),
          y: Object.assign({ beginAtZero: true, ticks: { callback: wholeNumberTick, color: theme.muted } }, baseGridOptions(theme))
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: theme.bg,
            titleColor: theme.fg,
            bodyColor: theme.fg,
            borderColor: theme.line,
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: function (ctx) { return ctx.parsed.y + " applied"; }
            }
          }
        }
      }
    });
  }

  function renderChannelsChart(data, theme) {
    var canvas = document.getElementById("channels-chart");
    if (!canvas || !window.Chart) return null;
    var channels = data.channels || {};
    var entries = Object.keys(channels)
      .map(function (k) { return [k, channels[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; })
      .slice(0, 8);
    var labels = entries.map(function (e) { return e[0]; });
    var values = entries.map(function (e) { return e[1]; });

    return new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Applications",
          data: values,
          backgroundColor: withAlpha(theme.accent, 0.85),
          hoverBackgroundColor: theme.accent,
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 900, easing: "easeOutQuart" },
        scales: {
          x: Object.assign({ beginAtZero: true, ticks: { callback: wholeNumberTick } }, baseGridOptions(theme)),
          y: Object.assign({}, baseGridOptions(theme), { grid: { display: false } })
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: theme.bg,
            titleColor: theme.fg,
            bodyColor: theme.fg,
            borderColor: theme.line,
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: function (ctx) { return ctx.parsed.x + " application" + (ctx.parsed.x === 1 ? "" : "s"); }
            }
          }
        }
      }
    });
  }

  var charts = [];

  function renderCharts(data) {
    charts.forEach(destroyChart);
    charts = [];
    var theme = chartTheme();
    charts.push(renderFunnelChart(data, theme));
    charts.push(renderFunnelOutcomesChart(data, theme));
    charts.push(renderActivityChart(data, theme));
    charts.push(renderChannelsChart(data, theme));
  }

  // Re-render charts when the OS color scheme flips, so dark mode colors
  // apply without a page reload.
  function watchColorScheme(data) {
    if (!window.matchMedia) return;
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var handler = function () { renderCharts(data); };
    if (mq.addEventListener) mq.addEventListener("change", handler);
    else if (mq.addListener) mq.addListener(handler);
  }

  // ---- scroll reveal ------------------------------------------------------

  function revealOnScroll() {
    var targets = document.querySelectorAll("main > section, main > footer");
    if (!("IntersectionObserver" in window) || !targets.length) {
      targets.forEach(function (t) { t.classList.add("is-visible"); });
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    targets.forEach(function (t) {
      t.classList.add("reveal");
      observer.observe(t);
    });
  }

  // ---- data loading: fetch first, inline script tag as fallback ---------

  function readInlineData() {
    var node = document.getElementById("metrics-data");
    return JSON.parse(node.textContent);
  }

  function setLoading(isLoading) {
    document.body.classList.toggle("is-loading", isLoading);
  }

  function render(data) {
    renderTiles(data);
    renderCharts(data);
    watchColorScheme(data);
    document.getElementById("generated").textContent = data.generated_at || "";
    setLoading(false);
    revealOnScroll();
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
        // Offline, opened via file://, or metrics.json missing/stale: fall
        // back to the inline, build-time guarded payload so the page still
        // works standalone.
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

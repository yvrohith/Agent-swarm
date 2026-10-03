"use strict";

(() => {
  const ORDER = ["writes", "identity", "requests", "delivery", "context"];
  const REGIMES = {
    writes: { label: "Writes", detail: "Artifact writes and their timing." },
    identity: { label: "+ Identity", detail: "Writes linked to persistent run identities." },
    requests: { label: "+ Requests", detail: "Evidence of information requests." },
    delivery: { label: "+ Delivery", detail: "Evidence of information delivery." },
    context: { label: "+ Context", detail: "Shared-channel context chunks, not full harness state." },
  };
  const METHODS = {
    temporal: { label: "Temporal", detail: "Nearby same-page writes, filtered by evidence." },
    witness: { label: "Witness", detail: "Exact witness-token overlap, filtered by evidence." },
  };
  const METRICS = {
    precision: { label: "Edge precision", percent: true, direction: "Higher is better." },
    recall: { label: "Edge recall", percent: true, direction: "Higher is better." },
    absolute_error: { label: "Mean absolute θ error", percent: false, direction: "Lower is better." },
    false_attributed_target_fraction: { label: "False-attributed targets", percent: true, direction: "Lower is better." },
    false_positive_edges_per_target: { label: "False-positive edges / target", percent: false, direction: "Lower is better." },
  };
  const $ = (id) => document.getElementById(id);
  const controls = { transmission: $("transmission"), shock: $("shock"), method: $("method"), regime: $("regime") };
  let rows = [];

  const isNumber = (value) => typeof value === "number" && Number.isFinite(value);
  const orderedRegimes = (values) => [...new Set(values)].sort((a, b) => {
    const ai = ORDER.indexOf(a);
    const bi = ORDER.indexOf(b);
    return (ai < 0 ? ORDER.length : ai) - (bi < 0 ? ORDER.length : bi) || a.localeCompare(b);
  });
  const labelRegime = (value) => REGIMES[value]?.label || value;
  const labelMethod = (value) => METHODS[value]?.label || value;
  const format = (value, metric, digits = 1) => {
    if (!isNumber(value)) return "—";
    return METRICS[metric].percent ? `${(100 * value).toFixed(digits)}%` : value.toFixed(3);
  };
  const formatInterval = (metric, name) => isNumber(metric?.ci_low) && isNumber(metric?.ci_high)
    ? `${format(metric.ci_low, name)}–${format(metric.ci_high, name)}` : "Unavailable";
  const count = (value) => Number.isInteger(value) && value >= 0 ? value : null;

  function populate(select, values, label, preferred) {
    const previous = select.value || preferred;
    select.replaceChildren(...values.map((value) => {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = label(value);
      return option;
    }));
    if (values.some((value) => String(value) === previous)) select.value = previous;
  }

  function selectScenario() {
    const numeric = (values) => [...new Set(values)].sort((a, b) => a - b);
    populate(controls.transmission, numeric(rows.map((row) => row.transmission_probability)), (v) => `${(v * 100).toFixed(0)}%`, "0.3");
    const transmissionRows = rows.filter((row) => row.transmission_probability === Number(controls.transmission.value));
    populate(controls.shock, numeric(transmissionRows.map((row) => row.shock_strength)), (v) => v.toFixed(2), "0.5");
    const scenarioRows = transmissionRows.filter((row) => row.shock_strength === Number(controls.shock.value));
    populate(controls.method, [...new Set(scenarioRows.map((row) => row.method))].sort(), labelMethod, "witness");
    const methodRows = scenarioRows.filter((row) => row.method === controls.method.value);
    populate(controls.regime, orderedRegimes(methodRows.map((row) => row.regime)), labelRegime, "context");
    render(methodRows);
  }

  function render(comparisonRows) {
    const selected = comparisonRows.find((row) => row.regime === controls.regime.value);
    $("method-detail").textContent = METHODS[controls.method.value]?.detail || "Method supplied by this artifact.";
    $("regime-detail").textContent = REGIMES[controls.regime.value]?.detail || "Observation regime supplied by this artifact.";
    const seeds = count(selected?.n_seeds);
    $("scenario-summary").textContent = `${labelMethod(controls.method.value)} attribution · ${labelRegime(controls.regime.value)} · ${seeds === null ? "Seed count unavailable" : `${seeds} simulation seeds`}. θ is the fraction of all writes with a true cross-run source, including initial writes in the denominator.`;
    for (const name of ["precision", "recall", "absolute_error", "false_attributed_target_fraction"]) {
      const metric = selected?.metrics[name];
      $(`${name}-value`).textContent = format(metric?.mean, name);
      const n = count(metric?.n);
      $(`${name}-interval`).textContent = !isNumber(metric?.mean)
        ? `Undefined / unavailable${n === null ? "" : ` · n = ${n}`}`
        : `95% interval: ${formatInterval(metric, name)}${n === null ? "" : ` · n = ${n}`}`;
    }
    renderChart(comparisonRows);
  }

  function svgElement(tag, attributes, content) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [name, value] of Object.entries(attributes || {})) element.setAttribute(name, String(value));
    if (content !== undefined) element.textContent = content;
    return element;
  }

  function renderChart(comparisonRows) {
    const metricName = $("chart-metric").value;
    const metricInfo = METRICS[metricName];
    const regimes = orderedRegimes(comparisonRows.map((row) => row.regime));
    const points = regimes.map((regime) => comparisonRows.find((row) => row.regime === regime));
    const title = `${metricInfo.label} across observation regimes`;
    $("chart-description").textContent = `${labelMethod(controls.method.value)} attribution at ${(100 * Number(controls.transmission.value)).toFixed(0)}% transmission probability and ${Number(controls.shock.value).toFixed(2)} shared shock strength. ${metricInfo.direction}`;
    const mobile = window.matchMedia("(max-width: 600px)").matches;
    const svg = svgElement("svg", { viewBox: mobile ? "0 0 360 305" : "0 0 940 305", role: "img", "aria-labelledby": "plot-title plot-description" });
    svg.append(svgElement("title", { id: "plot-title" }, title));
    svg.append(svgElement("desc", { id: "plot-description" }, "Points show means across simulation seeds; vertical bars show 95% bootstrap intervals. The selected evidence regime is highlighted. Exact measurements are in the data table below."));
    const bounds = { left: mobile ? 40 : 72, right: mobile ? 348 : 915, top: 32, bottom: 241 };
    const chartWidth = bounds.right - bounds.left;
    const values = points.flatMap((point) => {
      const metric = point.metrics[metricName];
      return [metric?.mean, metric?.ci_low, metric?.ci_high].filter(isNumber);
    });
    const observedMax = values.length ? Math.max(...values) : 1;
    const maxValue = metricInfo.percent ? Math.max(1, observedMax) : Math.max(0.1, Math.ceil(observedMax * 1.15 * 20) / 20);
    const slot = chartWidth / Math.max(points.length, 1);
    const x = (index) => bounds.left + slot * (index + 0.5);
    const y = (value) => bounds.bottom - (value / maxValue) * (bounds.bottom - bounds.top);
    points.forEach((point, index) => {
      if (point.regime === controls.regime.value) svg.append(svgElement("rect", { x: x(index) - slot * .39, y: bounds.top - 14, width: slot * .78, height: bounds.bottom - bounds.top + 57, rx: 5, fill: "#eaf1e5" }));
    });
    for (let step = 0; step <= 4; step += 1) {
      const value = (maxValue * step) / 4;
      svg.append(svgElement("line", { x1: bounds.left, y1: y(value), x2: bounds.right, y2: y(value), stroke: "#dfe6da", "stroke-width": 1, "stroke-dasharray": step ? "3 5" : "none" }));
      const tick = metricInfo.percent ? `${(value * 100).toFixed(0)}%` : value.toFixed(maxValue < .2 ? 3 : 2);
      svg.append(svgElement("text", { x: bounds.left - 14, y: y(value) + 4, "text-anchor": "end", fill: "#5a6e69", "font-size": 12 }, tick));
    }
    let previous = null;
    points.forEach((point, index) => {
      const metric = point.metrics[metricName];
      if (isNumber(metric?.mean)) {
        if (previous) svg.append(svgElement("line", { x1: previous.x, y1: previous.y, x2: x(index), y2: y(metric.mean), stroke: "#7fa48c", "stroke-width": 1.6 }));
        previous = { x: x(index), y: y(metric.mean) };
      } else previous = null;
    });
    points.forEach((point, index) => {
      const metric = point.metrics[metricName];
      if (isNumber(metric?.mean)) {
        if (isNumber(metric.ci_low) && isNumber(metric.ci_high)) {
          const top = y(metric.ci_high), bottom = y(metric.ci_low);
          svg.append(svgElement("line", { x1: x(index), y1: top, x2: x(index), y2: bottom, stroke: "#247b68", "stroke-width": 2 }));
          [top, bottom].forEach((height) => svg.append(svgElement("line", { x1: x(index) - 7, y1: height, x2: x(index) + 7, y2: height, stroke: "#247b68", "stroke-width": 2 })));
        }
        const circle = svgElement("circle", { cx: x(index), cy: y(metric.mean), r: 5, fill: "#247b68", stroke: "#fffef9", "stroke-width": 2 });
        circle.append(svgElement("title", {}, `${labelRegime(point.regime)}: ${format(metric.mean, metricName)}; 95% interval ${formatInterval(metric, metricName)}; n = ${count(metric.n) ?? "unavailable"}`));
        svg.append(circle);
        const labelY = Math.max(13, y(isNumber(metric.ci_high) ? metric.ci_high : metric.mean) - 12);
        svg.append(svgElement("text", { x: x(index), y: labelY, "text-anchor": "middle", fill: "#183c39", "font-size": 12, "font-weight": 600 }, format(metric.mean, metricName)));
      } else {
        svg.append(svgElement("text", { x: x(index), y: (bounds.top + bounds.bottom) / 2, "text-anchor": "middle", fill: "#6e7b73", "font-size": 12 }, "Unavailable"));
      }
      svg.append(svgElement("text", { x: x(index), y: bounds.bottom + 29, "text-anchor": "middle", fill: "#183c39", "font-size": mobile ? 10.5 : 13, "font-weight": point.regime === controls.regime.value ? 650 : 400 }, labelRegime(point.regime)));
    });
    svg.append(svgElement("text", { x: (bounds.left + bounds.right) / 2, y: 301, "text-anchor": "middle", fill: "#5a6e69", "font-size": 11 }, mobile ? "Visible evidence →" : "Visible evidence (successively richer observation regimes)"));
    $("chart").replaceChildren(svg);
    $("table-caption").textContent = `${title}. Means and intervals across simulation seeds.`;
    const tableRows = points.map((point) => {
      const row = document.createElement("tr");
      if (point.regime === controls.regime.value) row.classList.add("selected");
      const metric = point.metrics[metricName];
      const cells = [labelRegime(point.regime), format(metric?.mean, metricName), formatInterval(metric, metricName), count(metric?.n) ?? "Unavailable"];
      cells.forEach((value, index) => {
        const cell = document.createElement(index === 0 ? "th" : "td");
        if (index === 0) cell.scope = "row";
        cell.textContent = String(value);
        row.append(cell);
      });
      return row;
    });
    $("chart-table").replaceChildren(...tableRows);
  }

  function validate(data) {
    if (data?.schema_version !== 1 || !Array.isArray(data.summary) || !data.summary.length) {
      throw new Error("The artifact has no supported summary. Expected schema_version 1 and a nonempty summary array.");
    }
    const seen = new Set();
    for (const row of data.summary) {
      if (!isNumber(row.transmission_probability) || !isNumber(row.shock_strength) || typeof row.regime !== "string" || typeof row.method !== "string" || !row.metrics || typeof row.metrics !== "object") {
        throw new Error("The artifact contains an incomplete scenario. Regenerate benchmark.json with the benchmark command below.");
      }
      const key = JSON.stringify([row.transmission_probability, row.shock_strength, row.method, row.regime]);
      if (seen.has(key)) throw new Error("The artifact contains duplicate scenario summaries. Regenerate it before comparing results.");
      seen.add(key);
    }
    return data.summary;
  }

  async function load() {
    $("explorer").hidden = true;
    $("load-state").hidden = false;
    $("load-state").classList.remove("is-error");
    $("recovery").hidden = true;
    $("load-title").textContent = "Loading local experiment results…";
    $("load-detail").textContent = "Reading results/benchmark.json. No example measurements are substituted.";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("../results/benchmark.json", { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error(`The local result artifact could not be loaded (HTTP ${response.status}).`);
      const data = await response.json();
      rows = validate(data);
      const seedCount = Array.isArray(data.metadata?.seeds) ? data.metadata.seeds.length : null;
      const runs = count(data.metadata?.n_runs);
      $("dataset-status").textContent = [
        `${rows.length.toLocaleString()} measured combinations`,
        seedCount === null ? null : `${seedCount} seeds`,
        runs === null ? null : `${runs.toLocaleString()} runs / world`,
      ].filter(Boolean).join(" · ");
      selectScenario();
      $("load-state").hidden = true;
      $("explorer").hidden = false;
    } catch (error) {
      $("load-state").classList.add("is-error");
      $("load-title").textContent = "No experiment results to display yet.";
      $("load-detail").textContent = location.protocol === "file:"
        ? "This page needs a local HTTP server to read the generated benchmark artifact. Follow the commands below."
        : error.name === "AbortError" ? "Loading the local benchmark artifact timed out. Check your server and retry."
          : `Unable to read results/benchmark.json. ${error.message}`;
      $("recovery").hidden = false;
    } finally {
      clearTimeout(timeout);
    }
  }

  for (const control of Object.values(controls)) control.addEventListener("change", selectScenario);
  $("chart-metric").addEventListener("change", selectScenario);
  $("retry-button").addEventListener("click", load);
  window.matchMedia("(max-width: 600px)").addEventListener("change", () => { if (rows.length) selectScenario(); });
  load();
})();

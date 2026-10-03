"""Export shareable figures and a factual report from the measured results."""

from pathlib import Path

from .observe import Telemetry

REGIME_LABELS = ["Writes", "+ Identity", "+ Requests", "+ Delivery", "+ Context"]


def _number(value: float | None) -> str:
    return "undefined" if value is None else f"{value:.3f}"


def _interval(metric: dict) -> str:
    if metric["mean"] is None:
        return "undefined (n=0)"
    if metric["ci_low"] is None:
        return f"{metric['mean']:.3f} (n={metric['n']}; CI unavailable)"
    return f"{metric['mean']:.3f} [{metric['ci_low']:.3f}, {metric['ci_high']:.3f}]"


def write_figure(result: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "svg.hashsalt": "tracebench-v1"})
    summary, meta = result["summary"], result["metadata"]
    positive = min(meta["transmission_probabilities"], key=lambda p: abs(p - 0.3))
    null = min(meta["transmission_probabilities"])
    columns = [
        ("false_attributed_target_fraction", null, f"False target attribution · p={null:g}"),
        ("precision", positive, f"Edge precision · p={positive:g}"),
        ("recall", positive, f"Edge recall · p={positive:g}"),
        ("absolute_error", positive, f"Absolute θ error · p={positive:g}"),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(17, 8), constrained_layout=True)
    colors = ["#176b87", "#bd5a35", "#7461a8", "#39784b", "#9a650a"]
    for row_index, method in enumerate(("temporal", "witness")):
        for col_index, (metric, probability, title) in enumerate(columns):
            ax = axes[row_index, col_index]
            for shock_index, shock in enumerate(meta["shock_strengths"]):
                points = [next(item for item in summary if item["method"] == method
                               and item["transmission_probability"] == probability
                               and item["shock_strength"] == shock
                               and item["regime"] == regime.value)["metrics"][metric]
                          for regime in Telemetry]
                values = [p["mean"] if p["mean"] is not None else float("nan") for p in points]
                low = [p["ci_low"] if p["ci_low"] is not None else float("nan") for p in points]
                high = [p["ci_high"] if p["ci_high"] is not None else float("nan") for p in points]
                color = colors[shock_index % len(colors)]
                ax.plot(range(5), values, marker="o", markersize=4, color=color,
                        label=f"shock={shock:g}")
                ax.fill_between(range(5), low, high, alpha=0.14, color=color)
            ax.set_title(title)
            ax.set_xticks(range(5), REGIME_LABELS, rotation=35, ha="right")
            ax.set_ylim(-0.025, 1.025)
            ax.grid(axis="y", alpha=0.2)
            ax.spines[["top", "right"]].set_visible(False)
            if col_index == 0:
                ax.set_ylabel("Temporal proximity" if method == "temporal" else "Witness reuse")
            if row_index == 0 and col_index == 0:
                ax.legend(frameon=False, fontsize=8)
    fig.suptitle(
        "Trace completeness curves · synthetic realized source use\n"
        f"{len(meta['seeds'])} seeds/scenario · {meta['n_runs']} runs/world · "
        "shading: 95% seed-bootstrap interval\n"
        "Complete logs preserve true candidates; exposure does not establish use.",
        fontsize=14,
    )
    fig.savefig(output / "trace_completeness.png", dpi=170,
                metadata={"Software": "Trace Completeness Curves"})
    fig.savefig(output / "trace_completeness.svg", metadata={"Date": None})
    plt.close(fig)


def write_report(result: dict, output: Path) -> None:
    metadata = result["metadata"]
    probability = min(metadata["transmission_probabilities"], key=lambda p: abs(p - 0.3))
    shock = max(metadata["shock_strengths"])
    selected = [s for s in result["summary"] if s["transmission_probability"] == probability
                and s["shock_strength"] == shock]
    lines = [
        "# Initial synthetic benchmark results", "",
        "**These are measured synthetic results, not findings about a real agent incident.**", "",
        "Question: how well do simple investigators recover realized cross-run source use "
        "as shared-channel telemetry is revealed?", "",
        f"Evaluated **{metadata['n_worlds']} worlds**, {metadata['n_runs']} runs and "
        f"{metadata['writes_per_run']} writes per run, "
        f"{len(metadata['seeds'])} independent seeds per scenario. "
        f"There are {len(result['runs'])} method × telemetry evaluations.", "",
        "![Telemetry-ablation curves](trace_completeness.png)", "",
        "## Method", "",
        "Each fixed world is projected into writes, stable identity, requests, delivery, and "
        "channel-context provenance. Both investigators return candidate event-to-event edges; "
        "only the evaluator sees truth. All generated writes form the denominator. "
        "The input transmission probability is conditional on the generator having context "
        "available and is not the realized source-use fraction θ.", "",
        "Requests can fail, delivered content can be dropped before context, and context "
        "content can remain unused. Common scaffolds and same-run repetition can also "
        "produce matching content. Temporal proximity is a fixed-lag baseline, not a Hawkes fit.", "",
        "## Representative measured scenario", "",
        f"Configured transmission probability **{probability:g}**, shared-shock strength "
        f"**{shock:g}**. Values are seed means with 95% percentile bootstrap intervals "
        f"({metadata['bootstrap_samples']} resamples).", "",
        "| Method | Telemetry | Precision | Recall | Absolute θ error |",
        "|---|---|---:|---:|---:|",
    ]
    for method in ("temporal", "witness"):
        for regime in Telemetry:
            row = next(s for s in selected if s["method"] == method and s["regime"] == regime.value)
            metrics = row["metrics"]
            lines.append(f"| {method} | {regime.value} | {_interval(metrics['precision'])} | "
                         f"{_interval(metrics['recall'])} | {_interval(metrics['absolute_error'])} |")
    lines += ["", f"Mean realized θ in this scenario: **{_number(selected[0]['metrics']['theta']['mean'])}**.",
              "", "## Zero-transmission control", ""]
    null = [s for s in result["summary"] if s["transmission_probability"] == 0
            and s["shock_strength"] == shock]
    if null:
        lines += ["False-attributed target fraction counts writes with a predicted source "
                  "but no true cross-run source, divided by all writes. Recall is undefined "
                  "when there are no true edges.", "",
                  "| Method | Telemetry | False-attributed target fraction |",
                  "|---|---|---:|"]
        for method in ("temporal", "witness"):
            for regime in Telemetry:
                row = next(s for s in null if s["method"] == method and s["regime"] == regime.value)
                lines.append(f"| {method} | {regime.value} | "
                             f"{_interval(row['metrics']['false_attributed_target_fraction'])} |")
    else:
        lines += ["Not run in this invocation. Do not claim a zero-transmission control."]
    lines += [
        "", "## Interpretation and limitations", "",
        "- Under complete, correct logs, filters preserve true candidates: recall is constant "
        "and defined precision cannot decrease. Candidate/false-positive counts shrink "
        "**by construction**. These are model invariants, not discoveries. The measured "
        "magnitudes and residual errors are the result; absolute θ error can be nonmonotone.",
        "- Context logs describe channel insertions, not hidden source-selection labels or "
        "complete harness state. Unused context leaves residual false attribution.",
        "- `tracebench equivalence` verifies two worlds with identical observations at every "
        "regime and different source-use truth. Extra exposure logs do not generally identify use.",
        "- Intervals reflect variation across simulated worlds under this generator. "
        "They are not valid causal bounds or uncertainty about a real incident. Undefined "
        "precision/recall is omitted from means and its defined sample count is stored in JSON/CSV.",
        "- This initial grid uses one generator and fixed investigator thresholds. "
        "No real corpus, LLM agent, missing-log process, or adversarial telemetry is validated.",
        "- Synthetic findings should not be described as real-world incident findings in a submission.",
        "", "## Reproduction and audit", "", "```bash",
        "uv sync --frozen --extra dev",
        "uv run tracebench benchmark --output artifacts/replication "
        f"--seeds {len(metadata['seeds'])} --seed-start {metadata['seeds'][0]} "
        f"--runs {metadata['n_runs']} --writes-per-run {metadata['writes_per_run']} "
        f"--transmission {','.join(str(p) for p in metadata['transmission_probabilities'])} "
        f"--shocks {','.join(str(s) for s in metadata['shock_strengths'])} "
        f"--bootstrap-samples {metadata['bootstrap_samples']}",
        "uv run tracebench equivalence", "```", "",
        "`benchmark.json` includes per-seed rows, summaries, generator defaults, seed lists, "
        "runtime version and source digest; `runs.csv` and `summary.csv` support independent analysis. "
        "`manifest.json` records artifact SHA-256 checksums. Output files are protected "
        "against accidental replacement unless `--overwrite` is supplied.", "",
        f"Source digest: `{metadata['source_sha256']}`.", "",
    ]
    (output / "REPORT.md").write_text("\n".join(lines))

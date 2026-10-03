"""Measured follow-up report; no baseline artifacts or analysis plan are edited."""

from pathlib import Path

PROFILE_LABELS = {
    "drop_delivery": "Erase delivery records; retain context records",
    "drop_context": "Erase context records; retain upstream records",
}


def _mean(metric: dict) -> str:
    return "undefined" if metric["mean"] is None else f"{metric['mean']:.3f}"


def _interval(metric: dict) -> str:
    if metric["mean"] is None:
        return "undefined (n=0)"
    if metric["ci_low"] is None:
        return f"{metric['mean']:.3f} (n={metric['n']}; CI unavailable)"
    return f"{metric['mean']:.3f} [{metric['ci_low']:.3f}, {metric['ci_high']:.3f}]"


def write_receipt_figure(result: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    config = result["metadata"]["config"]
    probability = max(config["transmission_probabilities"])
    shock = max(config["shock_strengths"])
    levels = sorted(config["retentions"])
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    plt.rcParams["svg.hashsalt"] = "receipt-loss-followup-v1"
    styles = {
        "conjunction": {"color": "#b95b35", "linestyle": "--", "marker": "s"},
        "evidence_aware": {"color": "#176c72", "linestyle": "-", "marker": "o"},
    }
    for row_index, method in enumerate(config["methods"]):
        for col_index, profile in enumerate(config["profiles"]):
            ax = axes[row_index, col_index]
            for policy in config["policies"]:
                metrics = [next(item for item in result["summary"]
                                if item["transmission_probability"] == probability
                                and item["shock_strength"] == shock and item["method"] == method
                                and item["profile"] == profile and item["policy"] == policy
                                and item["retention"] == retention)["metrics"]["recall"]
                           for retention in levels]
                y = [m["mean"] if m["mean"] is not None else float("nan") for m in metrics]
                lo = [m["ci_low"] if m["ci_low"] is not None else float("nan") for m in metrics]
                hi = [m["ci_high"] if m["ci_high"] is not None else float("nan") for m in metrics]
                ax.plot(levels, y, label=policy.replace("_", " "), **styles[policy],
                        markerfacecolor="none" if policy == "evidence_aware" else styles[policy]["color"],
                        markersize=7 if policy == "evidence_aware" else 4)
                ax.fill_between(levels, lo, hi, color=styles[policy]["color"], alpha=0.13)
            ax.set_title(PROFILE_LABELS[profile], fontsize=11)
            ax.set_xlabel("Nominal record retention (actual fractions in report)")
            ax.set_ylabel(f"{method.capitalize()} · edge recall")
            ax.set_xticks(levels)
            ax.set_ylim(-0.03, 1.03)
            ax.grid(alpha=0.18)
            ax.spines[["top", "right"]].set_visible(False)
            ax.legend(frameon=False, loc="best", fontsize=9)
    fig.suptitle(
        f"Missing receipts · p={probability:g}, shock={shock:g} · "
        f"{len(config['world_seeds'])} paired worlds\n"
        "Observation loss only; context evidence supports exposure, not source use\n"
        "Shading: 95% world-bootstrap intervals; coincident curves overlap", fontsize=12,
    )
    fig.savefig(output / "recall_retention.png", dpi=170,
                metadata={"Software": "Trace Completeness Curves receipt-loss follow-up"})
    svg = output / "recall_retention.svg"
    fig.savefig(svg, metadata={"Date": None})
    # Preserve vector semantics while avoiding generator-only whitespace noise.
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)


def write_receipt_report(result: dict, output: Path) -> None:
    meta = result["metadata"]
    config = meta["config"]
    lines = [
        "# Missing-receipt follow-up stress test", "",
        "**Follow-up informed by baseline review; not a preregistered discovery. "
        "All results are synthetic.**", "",
        "The target remains direct, realized cross-run source selection by the structural "
        "simulator. The eligible denominator is every generated write, including initial "
        "writes. Exposure is not source use, and selected source use is not counterfactual necessity.",
        "", "## Frozen configuration and pairing", "",
        f"Reviewed baseline: `{config['reviewed_baseline_commit']}`. "
        "The original simulator, analysis plan and curated `results/` artifacts are preserved.", "",
        f"- World seeds: `{config['world_seeds']}`; {config['n_runs']} runs × "
        f"{config['writes_per_run']} writes per world.",
        f"- Transmission parameters: `{config['transmission_probabilities']}`; "
        f"shock: `{config['shock_strengths']}`; nominal retention: `{config['retentions']}`.",
        f"- {meta['n_worlds']} worlds, {meta['n_masked_observations']} masked observations, "
        f"{meta['n_evaluations']} policy/method evaluations. "
        "Each world is generated once before all receipt masks.",
        f"- Mask seed: `{meta['mask_seed_rule']}`. Per-record deterministic ranks are shared "
        "across retention levels, producing nested retained sets. No mask is an extra world.",
        "- Request records, writes, identities, truth edges and eligible targets are fixed. "
        "The unmodified generator still permits genuine request/delivery/context failure "
        "and unused exposure. No generation probability is changed to model log loss.",
        f"- Freeze evidence: `{config['freeze']}`.",
        f"- Configuration SHA-256: `{meta['config_sha256']}`.", "",
        "For each method/profile/retention/transmission/shock combination, policies receive "
        "the identical masked observation. Policy differences are computed within each "
        f"world before a 95% percentile bootstrap ({config['bootstrap_samples']} resamples). "
        "Summaries group every study dimension. Undefined values stay null and undefined "
        "pairs do not contribute to their metric's interval. Counts of defined worlds are "
        "in `study.json`. No edges, masks, methods or profiles are treated as independent worlds.",
        "", "## Evidence policies and assumptions", "",
        "- **Conjunction:** the existing filter is retained exactly. It requires a compatible "
        "request, delivery and context entry. Missing any stage rejects a candidate. Its "
        "zero unresolved burden reflects lack of an abstention category, not resolved knowledge.",
        "- **Evidence aware:** a trusted, semantically valid context-entry receipt supports "
        "exposure without an upstream receipt. Missing context excludes exposure only when "
        "context logging is declared complete, or complete relevant upstream logging rules "
        "out the required prior event. Otherwise exposure is unknown.",
        "- Authentication is an explicit coarse trust assumption about retained simulator "
        "receipts, not implemented cryptography. Source ID, recipient identity, event timing "
        "and recorded source content are checked; absent upstream records are not failures. "
        "Malformed or contradictory evidence is outside the loss-only experiment.",
        "- Completeness assurance is channel-wide and declared from the logging profile. "
        "Below nominal retention 1 the affected stream is declared incomplete even when "
        "a particular mask happens to retain every record. Investigators receive no "
        "per-edge loss labels, truth, original record counts or mask seed.",
        "- Both methods start with the same stable-identity candidate universe. Supported "
        "exposure plus the temporal/witness heuristic yields a **scored candidate**, never "
        "a verified source-use edge. Unknown candidates are not added to predictions.",
        "", "## Recall versus record retention", "",
        "![Recall versus record retention](recall_retention.png)", "",
        "The figure shows the positive-use condition. In the zero-use control recall is "
        "undefined, not zero. Actual record fractions are tabulated below.", "",
        "## Actual retained records", "",
        "Each row counts each masked world once, independent of the number of policies "
        "and methods applied. Fractions below are pooled retained/original record counts "
        "over the worlds in that scenario; per-world fractions and counts are in `retention.csv`.", "",
        "| p | Profile | Nominal retention | Delivery kept / original (fraction) | "
        "Context kept / original (fraction) | Requests kept / original |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for probability in config["transmission_probabilities"]:
        for shock in config["shock_strengths"]:
            for profile in config["profiles"]:
                for retention in config["retentions"]:
                    records = [r for r in result["retention_audit"]
                               if r["transmission_probability"] == probability
                               and r["shock_strength"] == shock and r["profile"] == profile
                               and r["retention"] == retention]
                    cells = []
                    for channel in ("delivery", "context", "request"):
                        original = sum(r[f"{channel}_records_original"] for r in records)
                        kept = sum(r[f"{channel}_records_retained"] for r in records)
                        fraction = f"{kept / original:.4f}" if original else "undefined"
                        cells.append(f"{kept} / {original} ({fraction})")
                    lines.append(f"| {probability:g} | {profile} | {retention:g} | "
                                 + " | ".join(cells) + " |")
    lines += [
        "", "## Measured attribution and unresolved burden", "",
        "All entries below are means across worlds. Precision/recall concern **edges**. "
        "FP/N counts targets with a prediction but no true cross-run source. FN counts true "
        "source-use targets with no predicted candidate. Wrong-source attribution to a "
        "truly copied target instead appears in edge errors. Signed error is θ̂−θ; target "
        "disagreement is (FP+FN)/N. Thus signed error can be small through cancellation.", "",
        "Unknown/N counts targets with at least one unresolved candidate, divided by all "
        "writes. Such a target may also have a supported candidate from a different source. "
        "This burden is not a count of additional verified source-use targets. "
        "Edge-level unknown counts/fractions and all edge errors remain in JSON/CSV.", "",
    ]
    for probability in config["transmission_probabilities"]:
        lines += [f"### Transmission parameter {probability:g}", "",
                  "| Profile | Retention | Method | Policy | Recall | Precision | "
                  "FP targets | FN targets | FP/N | Signed θ error | Disagreement | Unknown/N |",
                  "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for profile in config["profiles"]:
            for retention in config["retentions"]:
                for method in config["methods"]:
                    for policy in config["policies"]:
                        s = next(s for s in result["summary"]
                                 if s["transmission_probability"] == probability
                                 and s["profile"] == profile and s["retention"] == retention
                                 and s["method"] == method and s["policy"] == policy)
                        values = [_mean(s["metrics"][metric]) for metric in (
                            "recall", "precision", "false_positive_targets", "false_negative_targets",
                            "false_attributed_target_fraction", "signed_error", "target_disagreement",
                            "unresolved_target_fraction",
                        )]
                        lines.append(f"| {profile} | {retention:g} | {method} | {policy} | "
                                     + " | ".join(values) + " |")
        lines.append("")
    lines += [
        "## Paired policy differences", "",
        "**Evidence aware minus conjunction**, computed within each fixed world and "
        "masked observation; brackets are 95% world-bootstrap intervals. Zero, negative "
        "and reversed differences are reported without selecting favorable comparisons. "
        "Positive recall is higher coverage; positive false attribution or disagreement "
        "is more error. Signed-error differences have no universal better direction. "
        "Positive unknown burden exposes uncertainty the conjunction baseline does not represent.",
        "", "| p | Profile | Retention | Method | Δ recall | Δ FP/N | Δ signed θ error | "
        "Δ disagreement | Δ unknown/N |", "|---:|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for s in result["paired_summary"]:
        values = [_interval(s["metrics"][metric]) for metric in (
            "recall", "false_attributed_target_fraction", "signed_error", "target_disagreement",
            "unresolved_target_fraction",
        )]
        lines.append(f"| {s['transmission_probability']:g} | {s['profile']} | "
                     f"{s['retention']:g} | {s['method']} | " + " | ".join(values) + " |")
    lines += [
        "", "## Mechanical consequences, not discoveries", "",
        "Correctness tests establish clean-mode parity and immutable worlds under nested "
        "masks. With authentic context retained, the evidence-aware policy can retain "
        "positive exposure despite upstream logging loss. With context erased and no "
        "remaining positive context evidence, it abstains on candidates whose exposure "
        "cannot be excluded. These are consequences of the implemented policies and "
        "logging assumptions. The study measures their magnitudes and error costs in "
        "the fixed synthetic configuration; it does not discover a general superiority theorem.", "",
        "## Remaining limitations", "",
        "One deterministic record mask is used per world and stream, nested across levels. "
        "The bootstrap captures world-plus-mask variation under that protocol, not separate "
        "within-world mask uncertainty. Run-correlated outages, forged logs, uncertain "
        "completeness declarations and real incidents are untested. Direct selected-source "
        "truth is not indirect lineage: a same-run relay of previously copied content "
        "does not create a new direct cross-run truth edge. Candidate generation is "
        "unchanged and can already miss true sources through its lag or witness rule. "
        "No candidate is a certified causal claim; even authenticated exposure can be unused.", "",
        "## Reproduce", "", "```bash", "uv sync --frozen --extra dev", "uv run pytest",
        "uv run tracebench receipt-study --config studies/missing_receipts/config.json "
        "--output artifacts/missing-receipts-replication", "```", "",
        "Use a fresh output directory. The command refuses to overwrite existing outputs "
        "or write inside the curated baseline `results/` directory. `config.json` is copied "
        "into each output. `study.json` includes per-world provenance, per-mask observed "
        "fractions, raw scores, full summaries and paired differences. `manifest.json` "
        "records artifact and executed-source hashes. The original baseline source digest "
        "continues to refer to its reviewed commit, not the extended source tree.", "",
    ]
    (output / "REPORT.md").write_text("\n".join(lines))

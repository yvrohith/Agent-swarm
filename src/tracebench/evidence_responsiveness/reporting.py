"""Render the bounded responsiveness audit without inference or response repair.

Only mechanical scores and selected evaluator metadata enter the report. Exact
prompts, incident bodies, provider reasoning, and completion text are not rendered.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape
from math import isfinite

from .common import ROLES
from .scoring import PRIMARY_METRICS


def _cell(value: object) -> str:
    if value is None:
        return "unavailable"
    return escape(str(value), quote=False).replace("|", "\\|").replace("\n", " ")


def _number(value: object) -> str:
    if value is None:
        return "undefined"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "undefined"
    return f"{number:.3f}" if isfinite(number) else "undefined"


def _interval(metric: dict) -> str:
    if metric.get("mean") is None:
        return "undefined"
    estimate = _number(metric["mean"])
    if metric.get("ci_low") is None or metric.get("ci_high") is None:
        return f"{estimate} [interval unavailable]"
    return f"{estimate} [{_number(metric['ci_low'])}, {_number(metric['ci_high'])}]"


def _count(metric: dict) -> str:
    numerator, denominator = metric.get("numerator"), metric.get("denominator")
    if numerator is None or denominator is None:
        return "unavailable"
    return f"{numerator:g}/{denominator:g}"


def _groups(summary: dict | None) -> list[dict]:
    source = (summary or {}).get("summary", summary or {})
    return sorted(
        (group for group in source.get("groups", [])
         if group.get("split", "evaluation") == "evaluation"),
        key=lambda group: (group["model_id"], group["subset"]),
    )


def _table(lines: list[str], headers: tuple[str, ...], rows: list[list[object]]) -> None:
    lines.extend([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ])
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    if not rows:
        lines.extend(["", "No evaluation observations supplied; no result is inferred."])
    lines.append("")


def _family_table(lines: list[str], groups: list[dict], prefix: str = "") -> None:
    rows = []
    for group in groups:
        metrics = group.get("metrics", {})
        rows.append([
            group["model_id"], group["subset"], group.get("n_families"),
            group.get("n_clusters"),
            *[_interval(metrics.get(prefix + metric, {})) for metric in PRIMARY_METRICS],
        ])
    _table(lines, (
        "Requested model", "Substrate", "Families", "History clusters",
        "Decisive pair [95% CI]", "Invariant pair [95% CI]", "Whole family [95% CI]",
    ), rows)


def _money(value: object) -> str:
    if value is None:
        return "unknown"
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return "unknown"
    return str(amount) if amount.is_finite() else "unknown"


def _accounting(lines: list[str], execution: dict) -> None:
    account = {**execution.get("accounting", {}), **execution}
    preflight = execution.get("preflight", {})
    rows = [
        ["Follow-up development calls completed", account.get("development_completed")],
        ["Follow-up evaluation calls completed", account.get("evaluation_completed")],
        ["Follow-up potentially billable attempts", account.get("attempts")],
        ["Follow-up transport retry attempts", account.get("additional_retry_attempts")],
        ["Follow-up provider-reported known charges (USD)",
         _money(account.get("provider_reported_actual_cost_usd"))],
        ["Follow-up usage-based estimate (USD; not an invoice)",
         _money(account.get("known_usage_cost_usd"))],
        ["Follow-up actual total charge (USD)", _money(account.get("actual_total_cost_usd"))],
        ["Historical charged or reserved (USD)",
         _money(account.get("historical_charged_or_reserved_usd"))],
        ["Cumulative provider-reported known charges (USD)",
         _money(account.get("cumulative_known_actual_usd"))],
        ["Cumulative charged or reserved (USD)",
         _money(account.get("cumulative_charged_or_reserved_usd"))],
        ["Cumulative actual total charge (USD)",
         _money(account.get("cumulative_actual_total_cost_usd"))],
        ["Cumulative attempts without actual-charge metadata",
         account.get("cumulative_unknown_actual_attempts")],
    ]
    known = _money(account.get("cumulative_known_actual_usd"))
    accounted = _money(account.get("cumulative_charged_or_reserved_usd"))
    if known != "unknown" and accounted != "unknown":
        excess = Decimal(accounted) - Decimal(known)
        rows.append(["Cumulative accounting beyond known charges "
                     "(USD; estimates or held reservations)", str(excess)])
    if "cumulative_unresolved_reservation_usd" in account:
        rows.append(["Cumulative unresolved reservations (USD)",
                     _money(account["cumulative_unresolved_reservation_usd"])])
    cap = account.get("budget_usd", account.get("cumulative_budget_usd",
                      preflight.get("budget_usd")))
    rows.append(["Applicable cumulative budget (USD)", _money(cap) if cap is not None
                 else "25 maximum; any lower configured ceiling applies"])
    _table(lines, ("Accounting item", "Recorded value"), rows)
    lines.extend([
        "The USD 25 authorization is cumulative across the completed utility pilot and this "
        "follow-up, not a new allowance. Unknown charges retain their reservations. "
        "Known provider-reported charges, usage estimates, and held reservations are distinct; "
        "none constitutes invoice reconciliation. An unknown actual total is not zero.", "",
    ])


def _examples(lines: list[str], examples: list[dict] | tuple) -> None:
    selected = [item for item in examples if item.get("split", "evaluation") == "evaluation"]
    if not selected:
        lines.extend([
            "No example records supplied. This does not establish that no failures occurred.", "",
        ])
        return
    for example in selected:
        label = ", ".join(_cell(example.get(key)) for key in ("model_id", "subset", "category"))
        chosen = example.get("selection")
        if chosen is None:
            lines.append(f"- {label}: {_cell(example.get('absence', 'No selection supplied.'))}")
            continue
        variants = []
        for role in ROLES:
            value = chosen["variants"][role]
            flags = [name for name in ("invalid", "missing", "refused", "truncated", "citation_error")
                     if value.get(name)]
            details = "; ".join(flags) if flags else "no recorded failure flags"
            variants.append(
                f"{role} {_cell(value.get('case_id'))}: "
                f"{_cell(value.get('status'))} / gold {_cell(value.get('gold_status'))} "
                f"({details})"
            )
        lines.append(f"- {label}; family {_cell(chosen.get('family_id'))}. "
                     + "; ".join(variants) + ".")
    lines.append("")


def render_report(summary: dict, execution: dict, examples: list[dict] | tuple = (),
                  baseline_summary: dict | None = None, validation: dict | None = None) -> str:
    """Return a data-driven report; development is never pooled with evaluation."""
    groups = _groups(summary)
    status = _cell(execution.get("status", "unavailable"))
    lines = [
        "# Bounded evidence-responsiveness audit", "",
        "**Review-informed exploratory follow-up; not a preregistered discovery.**", "",
        f"Execution status: **{status}**.", "",
        "Question: does an investigator answer correctly when decisive evidence changes, "
        "while remaining correct when an irrelevant detail changes? One fixed investigation "
        "prompt is used in separate tool-free contexts. This is not another assistance-arm "
        "comparison; the completed utility pilot's null, adverse, and response-contract "
        "findings remain unchanged.", "",
    ]
    if not groups:
        lines.extend([
            "**No investigator evaluation summary is available.** Prepared families, oracle "
            "certificates, and analytic controls are not completed investigator research.", "",
        ])
    elif execution.get("status") != "completed":
        lines.extend([
            "Execution is not recorded as completed. Supplied scores retain frozen family "
            "denominators, including missing responses; these are not a completed evaluation.", "",
        ])
    for blocker in execution.get("blockers", []):
        lines.append(f"- Execution blocker: {_cell(blocker)}")
    if execution.get("blockers"):
        lines.append("")
    lines.extend([
        "## Design and scoring", "",
        "The fixed design contains eight receipt and four controlled wiki-derived evaluation "
        "families, plus one development family per substrate. Each family has base, irrelevant, "
        "and decisive variants and one Boolean claim. The base and irrelevant statuses agree; "
        "the decisive status differs. Oracle certification of these relationships is a design "
        "property, not an investigator result. Receipt labels exhaust an explicit finite "
        "contract; altered wiki-derived texts are controlled fixtures, not historical observations.",
        "",
        "A family, not a response, is the measurement unit. A two-model evaluation schedules "
        "72 calls across 12 families; those calls are not 72 independent problems. Models and "
        "substrates stay separate. Decisive-pair correctness requires both base and decisive "
        "answers to be correct; invariant-pair correctness requires both base and irrelevant "
        "answers to be correct; whole-family correctness requires all three. Correctness "
        "requires a valid response schema and excludes refused or truncated completions. "
        "A mere answer flip or a stable wrong answer is not success. Missing/invalid responses "
        "retain frozen denominators and do not earn successful-abstention credit.", "",
        f"Intervals use {summary.get('bootstrap_resamples', 'unavailable')} percentile bootstrap "
        f"resamples with seed {_cell(summary.get('bootstrap_seed'))}, retaining each triplet "
        "and resampling whole family/source-history clusters. These are descriptive intervals "
        "for small selected task strata, not guarantees for deployment or unseen motifs. "
        "Zero-width all-pass/all-fail intervals do not imply zero generalization uncertainty.", "",
    ])
    if validation:
        lines.append("Validation metadata are recorded separately from investigator scores.")
        for key in ("status", "valid", "family_counts", "case_counts", "families", "cases",
                    "variants", "certified_families", "certificates_reproduced",
                    "relationship_checks", "metadata_invariance_checks", "constant_baselines_pass",
                    "all_relationships_valid", "review_type", "frozen_at_utc",
                    "preservation_status"):
            if key in validation and not isinstance(validation[key], (list, tuple)):
                lines.append(f"- {_cell(key)}: {_cell(validation[key])}")
        preservation = validation.get("preservation", {})
        if preservation:
            lines.append(
                "- Historical preservation: all hashes match = "
                f"{_cell(preservation.get('all_match'))}; "
                f"{_cell(preservation.get('tracked_files'))} tracked files and "
                f"{_cell(preservation.get('historical_raw_files'))} historical raw files; "
                f"baseline {_cell(preservation.get('baseline_commit'))}."
            )
        lines.append("")
    lines.extend(["## Primary family correctness", "", "Rates range from 0 to 1; higher is better.", ""])
    _family_table(lines, groups)
    lines.extend([
        "## Strict mechanical-ID companion", "",
        "Every required answer must also cite at least one valid supplied evidence/assumption "
        "ID and no nonexistent IDs. Empty citations can pass status correctness but fail this "
        "companion. This checks identifier existence, not semantic entailment, explanation "
        "quality, or private reasoning faithfulness.", "",
    ])
    _family_table(lines, groups, "strict_")
    lines.extend(["## Per-variant accuracy and response failures", ""])
    rows = []
    for group in groups:
        for role in ROLES:
            metrics = group.get("per_variant", {}).get(role, {})
            rows.append([
                group["model_id"], group["subset"], role,
                _count(metrics.get("status_correct", {})),
                _count(metrics.get("strict_correct", {})),
                *[_count(metrics.get(field, {})) for field in (
                    "invalid", "missing", "refused", "truncated", "citation_error")],
            ])
    _table(lines, (
        "Requested model", "Substrate", "Variant", "Correct", "Strict-ID correct",
        "Invalid schema", "Missing", "Refused", "Truncated", "Citation error",
    ), rows)
    lines.extend([
        "Entries are numerator/denominator counts, not extra independent samples. Failure "
        "categories can overlap; refusal/truncation use provider metadata, and citation errors "
        "are separate from status errors. Exact first responses are final: no answer repair "
        "or answer-based retry is used.", "",
        "## Conditional incorrect stability and change", "",
        "These diagnostics apply only when both relevant responses are schema-valid, "
        "non-refused, and non-truncated. Excluded pairs remain failures in the primary "
        "metrics. Eligible counts and clusters below must accompany any conditional rate.", "",
    ])
    rows = []
    for group in groups:
        for metric, label in (
            ("incorrect_stability_decisive", "Incorrect stability on decisive edit"),
            ("incorrect_change_irrelevant", "Incorrect change on irrelevant edit"),
        ):
            value = group.get("metrics", {}).get(metric, {})
            rows.append([group["model_id"], group["subset"], label, _interval(value),
                         _count(value), value.get("n_clusters")])
    _table(lines, (
        "Requested model", "Substrate", "Diagnostic", "Rate [95% CI]",
        "Incorrect / eligible pairs", "Eligible clusters",
    ), rows)
    lines.extend([
        "## Analytic constant-status controls", "",
        "These are scoring controls with zero investigator calls. Because every decisive "
        "pair has different gold statuses, always-unresolved must fail decisive-pair and "
        "whole-family correctness. Avoiding a definite answer cannot win the primary task.", "",
    ])
    baselines = _groups(baseline_summary)
    _family_table(lines, baselines)
    controls = [group for group in baselines if group["model_id"] == "always_unresolved"]
    if controls:
        passed = all(group.get("metrics", {}).get(metric, {}).get("mean") == 0
                     for group in controls for metric in (
                         "decisive_pair_correct", "whole_family_correct"))
        lines.extend([
            "Always-unresolved control check: " + (
                "passed on every supplied evaluation substrate." if passed else
                "FAILED or unavailable; do not treat these controls as validated."
            ), "",
        ])
    lines.extend([
        "## Frozen-rule examples", "",
        "Within each model/substrate, the first failed decisive pair and first failed "
        "invariant pair are selected by SHA-256 of the base case ID, with family ID as a "
        "tie-breaker. Explicit absence means no qualifying failure was observed. Examples "
        "do not replace the fixed denominators or identify an internal cause of failure.", "",
    ])
    _examples(lines, examples)
    lines.extend(["## Execution and cumulative cost", ""])
    _accounting(lines, execution)
    lines.extend([
        "## Interpretation and reproduction", "",
        "An all-pass result applies only to these certified transformations and explicit "
        "contracts. A failed pair records behavior on this task, not a real incident's causal "
        "mechanism. Correct statuses and valid IDs do not prove private reasoning faithfulness. "
        "Gold and leakage checks are mechanical/AI-assisted; no independent human validation "
        "is claimed. Requested model aliases are not immutable model weights. "
        "The existing utility pilot is neither repaired nor reinterpreted by this study.", "",
        "Generate the report once from an authorized local checkout with its frozen artifacts "
        "and retained responses:", "",
        "```sh", "uv run python -m tracebench.evidence_responsiveness report", "```", "",
        "The CLI refuses an existing results directory and does not overwrite a completed run. "
        "Reporting/rescoring does not issue investigator calls. Inspect the "
        "[per-variant scores](per_variant.json), [evaluation per-family scores](per_family.json), "
        "[summary](summary.json), [analytic controls](baselines.json), "
        "[fixed examples](examples.json), [execution accounting](execution.json), and "
        "[validation/preservation record](validation.json). The per-variant file also retains "
        "development rows; the reported evaluation tables exclude them. The "
        "[response manifest](response_manifest.json) records requested/returned identities, "
        "termination metadata, and hashes without response text. Frozen preparation is in "
        "[the freeze record](../frozen/freeze.json), [public request manifest]"
        "(../frozen/public_manifest.json), [family manifest](../frozen/family_manifest.json), "
        "and [certificate manifest](../frozen/gold_manifest.json).", "",
        "Exact requests, responses, "
        "provider-private reasoning, full incident material, and transformed fixture bodies "
        "remain in ignored local artifacts under the release rules. Authorized local access "
        "can reproduce scores; public hashes alone do not provide that content and cannot "
        "enable a complete independent public reproduction. No raw response or incident "
        "material is published automatically.", "",
    ])
    return "\n".join(lines)

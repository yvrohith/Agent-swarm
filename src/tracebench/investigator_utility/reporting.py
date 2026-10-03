"""Deterministic utility-study report; missing execution is never a result."""

from collections import defaultdict
from pathlib import Path
from statistics import mean

from .scoring import METRICS


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _number(value: float | None) -> str:
    return "undefined" if value is None else f"{value:.3f}"


def _estimate(metric: dict) -> str:
    if metric["mean"] is None:
        return "undefined"
    if metric["ci_low"] is None:
        return f"{metric['mean']:.3f} (interval unavailable)"
    return f"{metric['mean']:.3f} [{metric['ci_low']:.3f}, {metric['ci_high']:.3f}]"


def render_report(summary: dict, *, execution: dict, examples: list[dict] = (),
                  sanity_baselines: list[dict] = ()) -> str:
    """Render without reading cases, credentials, raw completions, or gold files.

    execution supplies status, blockers, call counts, costs and preservation
    status. Unknown metadata stays explicitly unavailable. No timestamp is made
    here: execution/freeze records provide their own recorded times upstream.
    """
    has_results = bool(summary["groups"])
    lines = [
        "# Investigator utility under a bounded evidence contract", "",
        "**Review-informed exploratory follow-up; not a preregistered discovery.**", "",
        f"Execution status: **{_cell(execution.get('status', 'not recorded'))}**.", "",
    ]
    if not has_results:
        lines.extend([
            "**No investigator evaluation results exist. No C-minus-B effect is estimated, "
            "and the evidence does not establish additional investigator utility.** "
            "The prepared cases, harness, and analytic sanity checks are not a completed experiment.",
            "",
        ])
    else:
        lines.extend([
            "The primary contrast is C minus B: raw evidence plus the same strong checklist, "
            "with versus without deterministic provenance assistance. A, raw evidence with "
            "a competent investigation prompt, is a secondary baseline. Results below measure "
            "warranted conclusions under the supplied evidence contract, not recovery of hidden "
            "source-use labels or field reliability.", "",
            "A lower unjustified-certainty rate alone does not establish improvement. "
            "Warranted-answer accuracy and schema/citation failures must be considered together; "
            "all flat, adverse, and undefined effects remain visible.", "",
        ])
    blockers = execution.get("blockers", [])
    if isinstance(blockers, str):
        blockers = [blockers]
    if blockers:
        lines.extend(["## Execution blockers", ""])
        lines.extend(f"- {_cell(blocker)}" for blocker in blockers)
        lines.append("")
    lines.extend([
        "## Scope, denominators, and scoring", "",
        "Wiki and synthetic evidence are reported separately, as is each model. No pooled "
        "headline combines those populations. A case's applicable claims are averaged first. "
        "Arm estimates and paired differences then average cases; pooled claim counts are shown "
        "for auditing the fixed denominators, not substituted for the case-mean estimate.", "",
        "Unjustified certainty counts schema-valid definite answers to unresolved claims. "
        "Warranted-answer accuracy counts schema-valid correct definite answers among answerable "
        "claims. Three-class accuracy uses the same status/schema rule. Citation existence is "
        "a separate mechanical check and cannot establish semantic evidence support. A correct "
        "status can therefore coexist with a citation error. Correct unresolved answers require "
        "valid schema and citations; unjustified-certainty-or-invalid counts either definite "
        "answers or schema/citation failures on unresolved claims. Missing/invalid output never "
        "earns successful-abstention credit. Empty citation lists are allowed. Reasons must be "
        "nonempty strings of at most 400 characters. Explanations are "
        "not scored semantically and are never graded or repaired by another LLM.", "",
        "Missing/duplicate expected claims invalidate those claims. Malformed roots, unknown "
        "claim IDs, extra root fields, and mismatched case IDs invalidate the response. "
        "Missing responses use the same frozen claim denominators; they are not dropped.", "",
        f"Paired percentile intervals use {summary['resamples']} bootstrap resamples and seed "
        f"`{summary['bootstrap_seed']}`. Whole page/history clusters are resampled together, "
        "retaining all constituent cases and both arms. Claims, arms, retries, and models are "
        "not independent cases. Fewer than two eligible clusters yields an unavailable interval; "
        "no applicable claims yields an undefined estimate. These small-sample intervals describe "
        "this selected pilot, not guaranteed coverage or general deployment reliability.", "",
    ])
    for title, metric in (
        ("Unjustified certainty (lower is preferable)", "unjustified_certainty"),
        ("Warranted-answer accuracy (higher is preferable)", "warranted_answer_accuracy"),
    ):
        lines.extend([
            f"## {title}", "",
            "| Model | Subset | Arm | Case mean [95% interval] | Claims numerator / denominator | "
            "Applicable cases / clusters |",
            "|---|---|---|---:|---:|---:|",
        ])
        for group in summary["groups"]:
            outcome = group["metrics"][metric]
            lines.append(
                f"| {_cell(group['model_id'])} | {group['subset']} | {group['arm']} | "
                f"{_estimate(outcome)} | {outcome['numerator']} / {outcome['denominator']} | "
                f"{outcome['n_cases']} / {outcome['n_clusters']} |"
            )
        if not has_results:
            lines.extend(["", "No model observations; the table is intentionally empty."])
        lines.append("")
    lines.extend([
        "## Paired contrasts", "",
        "C−B is primary. B−A and C−A are secondary. Positive differences indicate an increase "
        "in the named rate, including error rates.", "",
        "| Model | Subset | Contrast | Outcome | Difference [95% interval] | Cases / clusters |",
        "|---|---|---|---|---:|---:|",
    ])
    for pair in summary["paired"]:
        for metric in METRICS:
            outcome = pair["metrics"][metric]
            lines.append(
                f"| {_cell(pair['model_id'])} | {pair['subset']} | {pair['comparison']}"
                f"{' (primary)' if pair['primary'] else ''} | {metric} | {_estimate(outcome)} | "
                f"{outcome['n_cases']} / {outcome['n_clusters']} |"
            )
        unmatched = pair["missing_treatment_case_ids"] + pair["missing_control_case_ids"]
        if unmatched:
            # This explicit warning prevents an incomplete arm from silently appearing paired.
            lines.extend(["", f"Unpaired rows for {_cell(pair['model_id'])}, {pair['subset']}, "
                          f"{pair['comparison']}: {_cell(', '.join(sorted(unmatched)))}.", ""])
    if not has_results:
        lines.extend(["", "No paired effects are available."])
    lines.extend([
        "", "## Accuracy, abstention, and failure diagnostics", "",
        "Entries give case means followed by pooled numerator/denominator counts.", "",
        "| Model | Subset | Arm | Three-class accuracy | Correct unresolved | Schema/missing "
        "failure | Citation error | Certainty or invalid on unresolved |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ])
    for group in summary["groups"]:
        cells = []
        for metric in METRICS[2:]:
            outcome = group["metrics"][metric]
            cells.append(f"{_number(outcome['mean'])} ({outcome['numerator']}/{outcome['denominator']})")
        lines.append(f"| {_cell(group['model_id'])} | {group['subset']} | {group['arm']} | "
                     + " | ".join(cells) + " |")
    lines.extend([
        "", "## Analytic constant-answer sanity baselines", "",
        "These are deterministic scoring checks with no API calls, not investigator evaluations. "
        "Always-unresolved can avoid definite errors but has zero warranted-answer accuracy "
        "whenever answerable claims exist.", "",
        "| Baseline | Subset | Cases | Unjustified certainty | Warranted-answer accuracy | "
        "Three-class accuracy |",
        "|---|---|---:|---:|---:|---:|",
    ])
    baseline_groups = defaultdict(list)
    for row in sanity_baselines:
        baseline_groups[(row["baseline"], row["subset"])].append(row)
    for (baseline, subset), rows in sorted(baseline_groups.items()):
        cells = []
        for metric in METRICS[:3]:
            values = [r["metrics"][metric]["value"] for r in rows
                      if r["metrics"][metric]["value"] is not None]
            numerator = sum(r["metrics"][metric]["numerator"] for r in rows)
            denominator = sum(r["metrics"][metric]["denominator"] for r in rows)
            cells.append(f"{_number(mean(values) if values else None)} ({numerator}/{denominator})")
        lines.append(f"| {baseline} | {subset} | {len(rows)} | " + " | ".join(cells) + " |")
    if not sanity_baselines:
        lines.extend(["", "No analytic baseline scores were supplied."])
    lines.extend([
        "", "## Frozen-rule examples", "",
        "For each model/subset, select the lowest SHA-256(case ID) among eligible C/B "
        "improvements, and separately among unsuccessful or disagreeing cases. Improvement "
        "requires a favorable primary change with no primary deterioration or increase in "
        "schema/citation failure. Examples illustrate selected-case behavior, not prevalence.", "",
    ])
    for example in examples:
        prefix = f"{_cell(example['model_id'])}, {example['subset']}, {example['category']}"
        selected = example["selection"]
        if selected is None:
            lines.append(f"- {prefix}: {_cell(example['absence'])}")
        else:
            delta = selected["differences"]
            lines.append(f"- {prefix}: `{_cell(selected['case_id'])}`; "
                         f"Δ unjustified certainty {_number(delta['unjustified_certainty'])}, "
                         f"Δ warranted-answer accuracy {_number(delta['warranted_answer_accuracy'])}. "
                         "See per-case scores and the saved first completion for the full record.")
    if not examples:
        lines.append("No evaluated examples exist; neither a success nor a failure is invented.")
    lines.extend(["", "## Calls, cost, and preservation", ""])
    fields = (
        ("Development calls completed", "development_calls_completed"),
        ("Evaluation calls completed", "evaluation_calls_completed"),
        ("Transport-only retry attempts", "transport_retry_attempts"),
        ("Total potentially billable attempts", "attempts"),
        ("Actual model cost (USD)", "actual_cost_usd"),
        ("Conservatively charged/reserved cost (USD)", "reserved_cost_usd"),
        ("Preserved-artifact hash verification", "preservation_status"),
    )
    for label, field in fields:
        value = execution.get(field)
        lines.append(f"- {label}: {_cell(value) if value is not None else 'unavailable (not recorded)' }.")
    lines.extend([
        "", "## Limits", "",
        "The evaluation contract concerns supplied evidence and explicitly bounded assumptions. "
        "Public wiki history is incomplete incident history; literal text insertion does not "
        "establish intent, exposure, stable actor identity, or source use. Public-corpus model "
        "contamination cannot be ruled out. Synthetic compatible constructions are not additional "
        "independent cases. Gold derivations and leakage checks are mechanical/AI-assisted unless "
        "a separately recorded real human review exists. Evidence-ID existence is not a semantic "
        "rationale check. Small selected case counts, shared histories, model availability, and "
        "resource failures limit inference. The three completed studies retain their original "
        "protocols, estimands, and curated results.", "",
    ])
    return "\n".join(lines)


def write_report(summary: dict, path: Path, *, execution: dict, examples: list[dict] = (),
                 sanity_baselines: list[dict] = ()) -> None:
    """Write a single specified report path; never modify another study."""
    path.write_text(render_report(summary, execution=execution, examples=examples,
                                 sanity_baselines=sanity_baselines), encoding="utf-8")

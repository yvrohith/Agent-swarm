# Investigator utility under a bounded evidence contract

**Review-informed exploratory follow-up; not a preregistered discovery.**

Execution status: **blocked**.

**No investigator evaluation results exist. No C-minus-B effect is estimated, and the evidence does not establish additional investigator utility.** The prepared cases, harness, and analytic sanity checks are not a completed experiment.

## Execution blockers

- No OpenAI, Anthropic, Gemini, OpenRouter or Azure model API credentials are configured in this environment.
- The available Codex conversation and same-family collaboration agents are not a configured metered, stateless investigator API with enforceable per-request USD bounds.
- No exact authorized model IDs, supported decoding limits and verified official prices are available to freeze.
- No frozen authorized models with verified official pricing and limits.

## Scope, denominators, and scoring

Wiki and synthetic evidence are reported separately, as is each model. No pooled headline combines those populations. A case's applicable claims are averaged first. Arm estimates and paired differences then average cases; pooled claim counts are shown for auditing the fixed denominators, not substituted for the case-mean estimate.

Unjustified certainty counts schema-valid definite answers to unresolved claims. Warranted-answer accuracy counts schema-valid correct definite answers among answerable claims. Three-class accuracy uses the same status/schema rule. Citation existence is a separate mechanical check and cannot establish semantic evidence support. A correct status can therefore coexist with a citation error. Correct unresolved answers require valid schema and citations; unjustified-certainty-or-invalid counts either definite answers or schema/citation failures on unresolved claims. Missing/invalid output never earns successful-abstention credit. Empty citation lists are allowed. Reasons must be nonempty strings of at most 400 characters. Explanations are not scored semantically and are never graded or repaired by another LLM.

Missing/duplicate expected claims invalidate those claims. Malformed roots, unknown claim IDs, extra root fields, and mismatched case IDs invalidate the response. Missing responses use the same frozen claim denominators; they are not dropped.

Paired percentile intervals use 2000 bootstrap resamples and seed `73021`. Whole page/history clusters are resampled together, retaining all constituent cases and both arms. Claims, arms, retries, and models are not independent cases. Fewer than two eligible clusters yields an unavailable interval; no applicable claims yields an undefined estimate. These small-sample intervals describe this selected pilot, not guaranteed coverage or general deployment reliability.

## Unjustified certainty (lower is preferable)

| Model | Subset | Arm | Case mean [95% interval] | Claims numerator / denominator | Applicable cases / clusters |
|---|---|---|---:|---:|---:|

No model observations; the table is intentionally empty.

## Warranted-answer accuracy (higher is preferable)

| Model | Subset | Arm | Case mean [95% interval] | Claims numerator / denominator | Applicable cases / clusters |
|---|---|---|---:|---:|---:|

No model observations; the table is intentionally empty.

## Paired contrasts

C−B is primary. B−A and C−A are secondary. Positive differences indicate an increase in the named rate, including error rates.

| Model | Subset | Contrast | Outcome | Difference [95% interval] | Cases / clusters |
|---|---|---|---|---:|---:|

No paired effects are available.

## Accuracy, abstention, and failure diagnostics

Entries give case means followed by pooled numerator/denominator counts.

| Model | Subset | Arm | Three-class accuracy | Correct unresolved | Schema/missing failure | Citation error | Certainty or invalid on unresolved |
|---|---|---|---:|---:|---:|---:|---:|

## Analytic constant-answer sanity baselines

These are deterministic scoring checks with no API calls, not investigator evaluations. Always-unresolved can avoid definite errors but has zero warranted-answer accuracy whenever answerable claims exist.

| Baseline | Subset | Cases | Unjustified certainty | Warranted-answer accuracy | Three-class accuracy |
|---|---|---:|---:|---:|---:|
| always_established | synthetic | 8 | 1.000 (10/10) | 0.679 (13/22) | 0.406 (13/32) |
| always_established | wiki | 16 | 1.000 (32/32) | 0.531 (17/32) | 0.266 (17/64) |
| always_ruled_out | synthetic | 8 | 1.000 (10/10) | 0.321 (9/22) | 0.281 (9/32) |
| always_ruled_out | wiki | 16 | 1.000 (32/32) | 0.469 (15/32) | 0.234 (15/64) |
| always_unresolved | synthetic | 8 | 0.000 (0/10) | 0.000 (0/22) | 0.312 (10/32) |
| always_unresolved | wiki | 16 | 0.000 (0/32) | 0.000 (0/32) | 0.500 (32/64) |

## Frozen-rule examples

For each model/subset, select the lowest SHA-256(case ID) among eligible C/B improvements, and separately among unsuccessful or disagreeing cases. Improvement requires a favorable primary change with no primary deterioration or increase in schema/citation failure. Examples illustrate selected-case behavior, not prevalence.

No evaluated examples exist; neither a success nor a failure is invented.

## Calls, cost, and preservation

- Development calls completed: 0.
- Evaluation calls completed: 0.
- Transport-only retry attempts: 0.
- Total potentially billable attempts: 0.
- Actual model cost (USD): 0.
- Conservatively charged/reserved cost (USD): 0.
- Preserved-artifact hash verification: All 70 baseline tracked-file hashes match..

## Limits

The evaluation contract concerns supplied evidence and explicitly bounded assumptions. Public wiki history is incomplete incident history; literal text insertion does not establish intent, exposure, stable actor identity, or source use. Public-corpus model contamination cannot be ruled out. Synthetic compatible constructions are not additional independent cases. Gold derivations and leakage checks are mechanical/AI-assisted unless a separately recorded real human review exists. Evidence-ID existence is not a semantic rationale check. Small selected case counts, shared histories, model availability, and resource failures limit inference. The three completed studies retain their original protocols, estimands, and curated results.

## Frozen preparation

Cases and evaluator certificates: [case manifest](../frozen/case_manifest.json), [gold certificates](../frozen/gold_certificates.json), [selection](../frozen/selection.json), [view hashes and size overhead](../frozen/view_manifest.json), and [freeze record](../frozen/freeze.json). Full selected texts, serialized requests, and provider responses stay in ignored artifacts.

No model IDs or pricing were invented. This blocked preparation freezes cases, prompts and scoring, but permits no API calls; model access and a versioned execution freeze must be established before evaluation. The original three studies, README and submission remain unchanged.

# Bounded evidence-responsiveness audit

**Review-informed exploratory follow-up; not a preregistered discovery.**

Execution status: **completed**.

Question: does an investigator answer correctly when decisive evidence changes, while remaining correct when an irrelevant detail changes? One fixed investigation prompt is used in separate tool-free contexts. This is not another assistance-arm comparison; the completed utility pilot's null, adverse, and response-contract findings remain unchanged.

## Design and scoring

The fixed design contains eight receipt and four controlled wiki-derived evaluation families, plus one development family per substrate. Each family has base, irrelevant, and decisive variants and one Boolean claim. The base and irrelevant statuses agree; the decisive status differs. Oracle certification of these relationships is a design property, not an investigator result. Receipt labels exhaust an explicit finite contract; altered wiki-derived texts are controlled fixtures, not historical observations.

A family, not a response, is the measurement unit. A two-model evaluation schedules 72 calls across 12 families; those calls are not 72 independent problems. Models and substrates stay separate. Decisive-pair correctness requires both base and decisive answers to be correct; invariant-pair correctness requires both base and irrelevant answers to be correct; whole-family correctness requires all three. Correctness requires a valid response schema and excludes refused or truncated completions. A mere answer flip or a stable wrong answer is not success. Missing/invalid responses retain frozen denominators and do not earn successful-abstention credit.

Intervals use 2000 percentile bootstrap resamples with seed 84104, retaining each triplet and resampling whole family/source-history clusters. These are descriptive intervals for small selected task strata, not guarantees for deployment or unseen motifs. Zero-width all-pass/all-fail intervals do not imply zero generalization uncertainty.

Validation metadata are recorded separately from investigator scores.
- family_counts: {'development/receipt': 1, 'development/wiki_derived': 1, 'evaluation/receipt': 8, 'evaluation/wiki_derived': 4}
- families: 14
- cases: 42
- certificates_reproduced: 42
- relationship_checks: 14
- metadata_invariance_checks: 42
- constant_baselines_pass: True
- review_type: mechanical and AI-assisted; no human validation claimed
- frozen_at_utc: 2026-10-03T22:08:41.458158+00:00
- Historical preservation: all hashes match = True; 138 tracked files and 415 historical raw files; baseline 88ad3cb7e10fe82a15e8c30400ea780b370663d3.

## Primary family correctness

Rates range from 0 to 1; higher is better.

| Requested model | Substrate | Families | History clusters | Decisive pair [95% CI] | Invariant pair [95% CI] | Whole family [95% CI] |
| --- | --- | --- | --- | --- | --- | --- |
| anthropic/claude-sonnet-5.5 | receipt | 8 | 8 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| anthropic/claude-sonnet-5.5 | wiki_derived | 4 | 4 | 0.000 [0.000, 0.000] | 0.250 [0.000, 0.750] | 0.000 [0.000, 0.000] |
| openai/gpt-5.6-terra | receipt | 8 | 8 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| openai/gpt-5.6-terra | wiki_derived | 4 | 4 | 1.000 [1.000, 1.000] | 0.750 [0.250, 1.000] | 0.750 [0.250, 1.000] |

## Strict mechanical-ID companion

Every required answer must also cite at least one valid supplied evidence/assumption ID and no nonexistent IDs. Empty citations can pass status correctness but fail this companion. This checks identifier existence, not semantic entailment, explanation quality, or private reasoning faithfulness.

| Requested model | Substrate | Families | History clusters | Decisive pair [95% CI] | Invariant pair [95% CI] | Whole family [95% CI] |
| --- | --- | --- | --- | --- | --- | --- |
| anthropic/claude-sonnet-5.5 | receipt | 8 | 8 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| anthropic/claude-sonnet-5.5 | wiki_derived | 4 | 4 | 0.000 [0.000, 0.000] | 0.250 [0.000, 0.750] | 0.000 [0.000, 0.000] |
| openai/gpt-5.6-terra | receipt | 8 | 8 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| openai/gpt-5.6-terra | wiki_derived | 4 | 4 | 1.000 [1.000, 1.000] | 0.750 [0.250, 1.000] | 0.750 [0.250, 1.000] |

## Per-variant accuracy and response failures

| Requested model | Substrate | Variant | Correct | Strict-ID correct | Invalid schema | Missing | Refused | Truncated | Citation error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| anthropic/claude-sonnet-5.5 | receipt | base | 0/8 | 0/8 | 8/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| anthropic/claude-sonnet-5.5 | receipt | irrelevant | 1/8 | 1/8 | 7/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| anthropic/claude-sonnet-5.5 | receipt | decisive | 4/8 | 4/8 | 4/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| anthropic/claude-sonnet-5.5 | wiki_derived | base | 1/4 | 1/4 | 3/4 | 1/4 | 1/4 | 0/4 | 0/4 |
| anthropic/claude-sonnet-5.5 | wiki_derived | irrelevant | 3/4 | 3/4 | 1/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| anthropic/claude-sonnet-5.5 | wiki_derived | decisive | 1/4 | 1/4 | 3/4 | 1/4 | 1/4 | 0/4 | 0/4 |
| openai/gpt-5.6-terra | receipt | base | 8/8 | 8/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| openai/gpt-5.6-terra | receipt | irrelevant | 8/8 | 8/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| openai/gpt-5.6-terra | receipt | decisive | 8/8 | 8/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| openai/gpt-5.6-terra | wiki_derived | base | 4/4 | 4/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| openai/gpt-5.6-terra | wiki_derived | irrelevant | 3/4 | 3/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| openai/gpt-5.6-terra | wiki_derived | decisive | 4/4 | 4/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |

Entries are numerator/denominator counts, not extra independent samples. Failure categories can overlap; refusal/truncation use provider metadata, and citation errors are separate from status errors. Exact first responses are final: no answer repair or answer-based retry is used.

## Conditional incorrect stability and change

These diagnostics apply only when both relevant responses are schema-valid, non-refused, and non-truncated. Excluded pairs remain failures in the primary metrics. Eligible counts and clusters below must accompany any conditional rate.

| Requested model | Substrate | Diagnostic | Rate [95% CI] | Incorrect / eligible pairs | Eligible clusters |
| --- | --- | --- | --- | --- | --- |
| anthropic/claude-sonnet-5.5 | receipt | Incorrect stability on decisive edit | undefined | 0/0 | 0 |
| anthropic/claude-sonnet-5.5 | receipt | Incorrect change on irrelevant edit | undefined | 0/0 | 0 |
| anthropic/claude-sonnet-5.5 | wiki_derived | Incorrect stability on decisive edit | undefined | 0/0 | 0 |
| anthropic/claude-sonnet-5.5 | wiki_derived | Incorrect change on irrelevant edit | 0.000 [interval unavailable] | 0/1 | 1 |
| openai/gpt-5.6-terra | receipt | Incorrect stability on decisive edit | 0.000 [0.000, 0.000] | 0/8 | 8 |
| openai/gpt-5.6-terra | receipt | Incorrect change on irrelevant edit | 0.000 [0.000, 0.000] | 0/8 | 8 |
| openai/gpt-5.6-terra | wiki_derived | Incorrect stability on decisive edit | 0.000 [0.000, 0.000] | 0/4 | 4 |
| openai/gpt-5.6-terra | wiki_derived | Incorrect change on irrelevant edit | 0.250 [0.000, 0.750] | 1/4 | 4 |

## Analytic constant-status controls

These are scoring controls with zero investigator calls. Because every decisive pair has different gold statuses, always-unresolved must fail decisive-pair and whole-family correctness. Avoiding a definite answer cannot win the primary task.

| Requested model | Substrate | Families | History clusters | Decisive pair [95% CI] | Invariant pair [95% CI] | Whole family [95% CI] |
| --- | --- | --- | --- | --- | --- | --- |
| always_established | receipt | 8 | 8 | 0.000 [0.000, 0.000] | 0.250 [0.000, 0.625] | 0.000 [0.000, 0.000] |
| always_established | wiki_derived | 4 | 4 | 0.000 [0.000, 0.000] | 0.500 [0.000, 1.000] | 0.000 [0.000, 0.000] |
| always_ruled_out | receipt | 8 | 8 | 0.000 [0.000, 0.000] | 0.250 [0.000, 0.500] | 0.000 [0.000, 0.000] |
| always_ruled_out | wiki_derived | 4 | 4 | 0.000 [0.000, 0.000] | 0.500 [0.000, 1.000] | 0.000 [0.000, 0.000] |
| always_unresolved | receipt | 8 | 8 | 0.000 [0.000, 0.000] | 0.500 [0.125, 0.875] | 0.000 [0.000, 0.000] |
| always_unresolved | wiki_derived | 4 | 4 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |

Always-unresolved control check: passed on every supplied evaluation substrate.

## Frozen-rule examples

Within each model/substrate, the first failed decisive pair and first failed invariant pair are selected by SHA-256 of the base case ID, with family ID as a tie-breaker. Explicit absence means no qualifying failure was observed. Examples do not replace the fixed denominators or identify an internal cause of failure.

- anthropic/claude-sonnet-5.5, receipt, first_failed_decisive_pair; family c_63a867f80cd53b008a7f7b02. base c_82e341a9ef55daf0567fb3bb: unavailable / gold ruled_out (invalid); irrelevant c_2bc9b3ea069a5ca58e6d4994: unavailable / gold ruled_out (invalid); decisive c_e7d6017a8f3e31c85bafbcda: unresolved / gold unresolved (no recorded failure flags).
- anthropic/claude-sonnet-5.5, receipt, first_failed_invariant_pair; family c_63a867f80cd53b008a7f7b02. base c_82e341a9ef55daf0567fb3bb: unavailable / gold ruled_out (invalid); irrelevant c_2bc9b3ea069a5ca58e6d4994: unavailable / gold ruled_out (invalid); decisive c_e7d6017a8f3e31c85bafbcda: unresolved / gold unresolved (no recorded failure flags).
- anthropic/claude-sonnet-5.5, wiki_derived, first_failed_decisive_pair; family f_2ab28bc02978a667b2db8ca2. base c_4c40584290eda792183972ba: unavailable / gold ruled_out (invalid); irrelevant c_85bedd41d15fbe265052725b: ruled_out / gold ruled_out (invalid); decisive c_5139cd08d3ae871b5c2aef60: established / gold established (no recorded failure flags).
- anthropic/claude-sonnet-5.5, wiki_derived, first_failed_invariant_pair; family f_2ab28bc02978a667b2db8ca2. base c_4c40584290eda792183972ba: unavailable / gold ruled_out (invalid); irrelevant c_85bedd41d15fbe265052725b: ruled_out / gold ruled_out (invalid); decisive c_5139cd08d3ae871b5c2aef60: established / gold established (no recorded failure flags).
- openai/gpt-5.6-terra, receipt, first_failed_decisive_pair: No failed decisive pair was observed.
- openai/gpt-5.6-terra, receipt, first_failed_invariant_pair: No failed invariant pair was observed.
- openai/gpt-5.6-terra, wiki_derived, first_failed_decisive_pair: No failed decisive pair was observed.
- openai/gpt-5.6-terra, wiki_derived, first_failed_invariant_pair; family f_9695d2661a05a12eced27723. base c_5d0eca8fa432a0bd5f37a404: established / gold established (no recorded failure flags); irrelevant c_bf88b0680f8898862c1cf548: ruled_out / gold established (no recorded failure flags); decisive c_796c25ca0ea2a0b5a0d6efcd: ruled_out / gold ruled_out (no recorded failure flags).

## Execution and cumulative cost

| Accounting item | Recorded value |
| --- | --- |
| Follow-up development calls completed | 12 |
| Follow-up evaluation calls completed | 72 |
| Follow-up potentially billable attempts | 84 |
| Follow-up transport retry attempts | 0 |
| Follow-up provider-reported known charges (USD) | 0.5853300 |
| Follow-up usage-based estimate (USD; not an invoice) | 0.5904060 |
| Follow-up actual total charge (USD) | unknown |
| Historical charged or reserved (USD) | 2.9989060 |
| Cumulative provider-reported known charges (USD) | 3.4468440 |
| Cumulative charged or reserved (USD) | 3.7827560 |
| Cumulative actual total charge (USD) | unknown |
| Cumulative attempts without actual-charge metadata | 3 |
| Cumulative accounting beyond known charges (USD; estimates or held reservations) | 0.3359120 |
| Cumulative unresolved reservations (USD) | 0.335912 |
| Applicable cumulative budget (USD) | 25 maximum; any lower configured ceiling applies |

The USD 25 authorization is cumulative across the completed utility pilot and this follow-up, not a new allowance. Unknown charges retain their reservations. Known provider-reported charges, usage estimates, and held reservations are distinct; none constitutes invoice reconciliation. An unknown actual total is not zero.

## Interpretation and reproduction

An all-pass result applies only to these certified transformations and explicit contracts. A failed pair records behavior on this task, not a real incident's causal mechanism. Correct statuses and valid IDs do not prove private reasoning faithfulness. Gold and leakage checks are mechanical/AI-assisted; no independent human validation is claimed. Requested model aliases are not immutable model weights. The existing utility pilot is neither repaired nor reinterpreted by this study.

Generate the report once from an authorized local checkout with its frozen artifacts and retained responses:

```sh
uv run python -m tracebench.evidence_responsiveness report
```

The CLI refuses an existing results directory and does not overwrite a completed run. Reporting/rescoring does not issue investigator calls. Inspect the [per-variant scores](per_variant.json), [evaluation per-family scores](per_family.json), [summary](summary.json), [analytic controls](baselines.json), [fixed examples](examples.json), [execution accounting](execution.json), and [validation/preservation record](validation.json). The per-variant file also retains development rows; the reported evaluation tables exclude them. The [response manifest](response_manifest.json) records requested/returned identities, termination metadata, and hashes without response text. Frozen preparation is in [the freeze record](../frozen/freeze.json), [public request manifest](../frozen/public_manifest.json), [family manifest](../frozen/family_manifest.json), and [certificate manifest](../frozen/gold_manifest.json).

Exact requests, responses, provider-private reasoning, full incident material, and transformed fixture bodies remain in ignored local artifacts under the release rules. Authorized local access can reproduce scores; public hashes alone do not provide that content and cannot enable a complete independent public reproduction. No raw response or incident material is published automatically.

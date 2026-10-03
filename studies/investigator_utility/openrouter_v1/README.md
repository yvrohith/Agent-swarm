# Investigator utility: completed OpenRouter pilot

The fixed evaluation completed **144 investigator calls** across two models on 24 fixed cases, following 24 development calls. The pilot does not establish a general reasoning advantage. Terra already reached the scoring ceiling; Sonnet's wiki warranted-answer accuracy was 93.75% in A, 75% in B and 93.75% in C. Its C−B advantage does not extend to the secondary C−A wiki comparison. **Every schema-valid status answer was correct in both models**: the observed differences concern response-contract reliability, including malformed output, missing claims, incorrect fields and refusals. Correctness conditional on validity does not validate malformed answers or their reasoning.

All arms had zero schema-valid unjustified certainty. Invalid answers remain failures: Sonnet's synthetic certainty-or-invalid rate was **40% in both B and C**. Zero certainty alone is therefore not successful uncertainty handling.

This is the completed execution of the [exploratory protocol](../ANALYSIS.md), not a preregistered discovery. The historical blocked preparation and the original studies remain preserved. See the [full report](results/REPORT.md), [paired summaries](results/paired_summary.json), [per-case scores](results/per_case_scores.json), and [exact visible answers and offline score verification](response_evidence/README.md).

## Comparison and outcomes

Each model received the same 16 wiki cases and eight synthetic reasoning fixtures in three arms:

- **A:** full raw records, assumptions, claims, and an evidence-grounded task.
- **B:** A plus a strong checklist addressing identity, inherited text, scoped logging completeness, and exposure versus use.
- **C:** B plus deterministic record indexing, full before/after character alignments, source locators, and equality groups. No additional historical facts, gold labels, or final verdicts are supplied.

**C−B is primary.** Unjustified certainty (UC, lower is preferable) counts schema-valid definite answers to unresolved claims. Warranted-answer accuracy (WAA, higher is preferable) counts schema-valid correct definite answers to answerable claims. Claims are averaged within cases before cases are averaged; failures retain their frozen denominators.

| Request model alias | Subset | UC B → C | UC C−B [95% interval] | WAA B → C | WAA C−B [95% interval] |
| --- | --- | ---: | ---: | ---: | ---: |
| `anthropic/claude-sonnet-5.5` | Wiki | 0 → 0 | 0 [0, 0] | 0.750 → 0.938 | +0.188 [0.000, 0.375] |
| `anthropic/claude-sonnet-5.5` | Synthetic | 0 → 0 | 0 [0, 0] | 0.429 → 0.714 | +0.286 [−0.286, 0.714] |
| `openai/gpt-5.6-terra` | Wiki | 0 → 0 | 0 [0, 0] | 1.000 → 1.000 | 0 [0, 0] |
| `openai/gpt-5.6-terra` | Synthetic | 0 → 0 | 0 [0, 0] | 1.000 → 1.000 | 0 [0, 0] |

Intervals use 2,000 paired whole-case/page-history bootstrap resamples. Wiki outcomes have 16 applicable cases each; synthetic UC has five and WAA seven. The remaining synthetic cases have no applicable claims for the respective metric. These small selected samples and zero-width observed intervals do not establish field reliability or absence of an effect elsewhere.

## Failures and adverse results

Sonnet's schema/missing-claim failure rate falls from B to C from `16/64` to `4/64` on wiki and `20/32` to `12/32` on synthetic claims. Zero UC therefore does not mean every response successfully withheld judgment. Its case-mean certainty-or-invalid rate on unresolved claims is `0.250 → 0.094` for wiki and `0.400 → 0.400` for synthetic. Terra has no schema or citation failures in this evaluation.

The adverse cases remain in the scores. On synthetic `s004`, Sonnet B answers correctly, but C's unknown-claim schema invalidates all four answers. Sonnet C also introduces one unknown evidence ID on wiki, despite correct statuses. In the secondary wiki comparison, Sonnet C's WAA equals A's (`0.938`); B underperforms A. The primary synthetic interval includes substantial deterioration as well as improvement. These results do not establish a general reasoning benefit from assistance.

## Execution and cost

All **168 calls returned**, with **zero retries**. Four evaluation responses were empty content-filter refusals. One of these, Sonnet wiki B, omitted usage metadata; it remains the final failed response and was not repaired or retried. The other 167 calls have provider-reported charges totaling **USD 2.8615140**. The unknown-charge call retains its full **USD 0.137392** reservation, giving **USD 2.9989060 charged or reserved**. **The actual total charge is unknown**; the reservation is not an actual cost and provider-reported charges are not an invoice reconciliation. See [execution accounting](results/execution.json) and [execution settings](EXECUTION.md).

The requested model IDs are aliases, not immutable dated revisions. Both routes used the configured native provider, preserved documented default reasoning/decoding, and capped total output including reasoning at 8,192 tokens. [Configuration](config.json), [metadata provenance](metadata_manifest.json), and the [evaluation freeze](frozen/freeze.json) record those choices before evaluation. No case, prompt, label, model, or threshold was changed in response to evaluation outcomes.

## Evidence limits

Gold derivations and leakage checks are mechanical and AI-assisted; no independent human validation is claimed. Wiki questions concern bounded supplied texts and a declared alignment rule, not proof of actual source exposure or use. Public-corpus model contamination cannot be excluded. Synthetic fixtures are finite reasoning cases, not new real incidents.

Citation scoring checks identifier existence only. Empty citation lists are allowed, and explanations are not graded for semantic support. Correct status scores can coexist with citation errors. Full corpus text, serialized prompts, and full provider responses remain in ignored local artifacts. The post-evaluation [response-evidence bundle](response_evidence/README.md) makes every first visible answer and refusal inspectable and reproduces the mechanical scores; it excludes provider reasoning and raw incident records. Its minimal case views do not independently establish the evidence or gold. The [submission addendum](SUBMISSION_ADDENDUM.md) and main [submission](../../../docs/SUBMISSION.md) state the bounded result.

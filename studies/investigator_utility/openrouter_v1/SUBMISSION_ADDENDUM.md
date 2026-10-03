# Submission addendum: investigator-utility pilot

We completed a bounded exploratory test of whether deterministic evidence organization helps an AI investigator beyond a strong checklist. Each model evaluated 16 wiki windows and eight synthetic fixtures in three arms: raw evidence (A), the same evidence plus a checklist (B), and B plus record indexing, character alignments, locators, and equality groups (C). The primary comparison is **C−B**. Assistance reorganizes the same facts; it does not supply hidden labels or exposure/use verdicts.

The two primary outcomes are unjustified certainty (UC: definite answers to unresolved claims) and warranted-answer accuracy (WAA: correct definite answers to answerable claims). Both require valid answer schemas. Results average claims within cases, then cases, keeping invalid answers in their denominators.

| Requested model alias | Subset | UC C−B | WAA B → C | WAA C−B [95% paired interval] |
| --- | --- | ---: | ---: | ---: |
| `anthropic/claude-sonnet-5.5` | Wiki | 0 | 0.750 → 0.938 | +0.188 [0.000, 0.375] |
| `anthropic/claude-sonnet-5.5` | Synthetic | 0 | 0.429 → 0.714 | +0.286 [−0.286, 0.714] |
| `openai/gpt-5.6-terra` | Wiki | 0 | 1.000 → 1.000 | 0 [0, 0] |
| `openai/gpt-5.6-terra` | Synthetic | 0 | 1.000 → 1.000 | 0 [0, 0] |

UC is zero in every arm, model, and subset, but Sonnet's synthetic certainty-or-invalid rate remains `0.400` in both B and C. Invalid answers are not successful abstentions. Every schema-valid status is correct, so Sonnet's WAA changes reflect response-contract reliability, including malformed answers, missing claims and refusals, not corrected wrong schema-valid conclusions. This conditional correctness does not establish that invalid answers contained correct reasoning. Sonnet's schema/missing-claim failures fall from B to C from `16/64` to `4/64` on wiki and `20/32` to `12/32` on synthetic claims. It nevertheless has adverse cases: C invalidates a previously correct synthetic response and introduces one wiki citation-ID error. Terra shows no measured additional benefit. Sonnet's wiki WAA is 93.75% in A, 75% in B and 93.75% in C; its secondary C−A comparison is flat. These results do not demonstrate a general improvement in forensic reasoning.

There were 24 development and 144 evaluation calls, with no retries. Four empty refusals were retained as failed responses. Provider-reported charges for 167 calls total **USD 2.8615140**. One refusal has no usage metadata; its retained **USD 0.137392** reservation brings charged-or-reserved accounting to **USD 2.9989060**. **Actual total cost remains unknown.**

The requested IDs are model aliases, not immutable revisions. This is an exploratory pilot, with 2,000 paired whole-case bootstrap resamples and small selected samples. Gold and leakage checks are mechanical/AI-assisted, with no independent human validation. Citation checks establish only ID existence; empty citations are allowed and explanation quality is ungraded. Public-wiki contamination and limited incident coverage remain unresolved. Wiki text alignment is not a causal source-use label.

The [complete report](results/REPORT.md), [per-case scores](results/per_case_scores.json), [paired summaries](results/paired_summary.json), and [execution accounting](results/execution.json) preserve flat, adverse, and failed responses alongside improvements. The [protocol](../ANALYSIS.md) and [frozen execution](frozen/freeze.json) document the fixed comparison. The [response-evidence bundle](response_evidence/README.md) supplies every first visible answer and refusal plus offline mechanical score verification, without redistributing full prompts, incident records or provider reasoning. It does not independently validate the gold or explanations. This addendum is integrated into the main [submission](../../../docs/SUBMISSION.md).

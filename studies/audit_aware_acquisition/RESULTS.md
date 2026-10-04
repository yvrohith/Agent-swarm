# Audit-aware acquisition: results

Constant-first auditing exposed more archive conflicts than cost-order auditing at the 25% and 50% budgets, but it did not uniformly improve cost, coverage, or warrant. At 50% of residual cost, C detected 18 of 39 new signatures versus B's 15, while spending more on the same all-signature population and covering less of the catalogue. At full budget, every active arm detected all 39 conflicts, a required mechanical endpoint. C's slightly higher equal-problem cost persisted despite its lower pooled cost. Model conflicts and justified conclusions remained separate: many original unsupported proposals could never be repaired through this catalogue.

## Scope and denominators

This review-informed follow-up uses the same 40 problems, three omission bounds (k=0,1,2), original stopping histories, catalogues, prices, and 30 structural groups as the preceding studies. The motivating results were known. The [protocol](ANALYSIS.md), [method](METHOD.md), and 27-dependency [freeze](freeze.json) preceded the new audit outcomes. No historical policy was reoptimized. All **1,920 conditions and 20,064 signature runs completed**, with no unavailable conditions or failures.

A preserves the nominal stopping history without further queries. B queries in cost/ID order. C prioritizes currently constant nominal queries, then falls back to B. D uses a fixed hypothetical k=2 signature envelope to prioritize immediate contradiction count per cost; it has additional model knowledge and is a secondary comparison. Budgets are floor(0%, 25%, 50%, or 100% of residual catalogue cost). An unaffordable next action ends a run without reranking. Active auditing stops at the first nominal conflict, even if budget remains.

At every k there are **392 original signatures**. Their nominal proposals comprise 271 definite claims and 121 archive-irreducibility conclusions. At k=1 and k=2, the same **39 new signatures** bring the population to 431. These have 26 definite proposals and 13 irreducibility conclusions. Initially, 96 original and 13 new definite proposals lack expanded-model support: 109 of 297 definite proposals. At k=0, all 271 definite proposals are supported and there are no new signatures.

Tables use exact saved arithmetic rounded for display. EP averages within each problem, then across problems equally; SB averages variants within each original structural group, then groups equally. Original/all-population estimates use 40 problems and 30 groups. New signatures occur in 22 problems and 17 groups; the other 18 problems and 13 groups have undefined conditional detection rates, not zero rates. Every k=0 conditional detection rate is undefined. Pooled counts are a separate descriptive weighting. Repeated k values, budgets, signatures, aliases, and certificate checks are not independent incidents; no sampling intervals or significance claims are made.

## Primary C-versus-B comparison

Detection paths and charges coincide at k=1 and k=2, so this table applies to each separately. Costs are added retrieval units, shown **EP / SB**. The original-signature costs also describe expenditure on nominal-compatible archives, where no alarm is possible. The all-population denominator remains 431; the new-population denominator remains 39.

| Budget % | Arm | Detected new | Added cost original | Added cost new | Added cost all |
| --- | --- | --- | --- | --- | --- |
| 0 | B | 0/39 | 0.0000 / 0.0000 | 0.0000 / 0.0000 | 0.0000 / 0.0000 |
| 0 | C | 0/39 | 0.0000 / 0.0000 | 0.0000 / 0.0000 | 0.0000 / 0.0000 |
| 25 | B | 6/39 | 1.4457 / 1.4427 | 1.4394 / 1.3775 | 1.4496 / 1.4453 |
| 25 | C | 7/39 | 0.9507 / 0.9312 | 1.0076 / 0.9804 | 0.9469 / 0.9259 |
| 50 | B | 15/39 | 3.7050 / 3.6578 | 3.4773 / 3.2206 | 3.6571 / 3.5836 |
| 50 | C | 18/39 | 3.8231 / 3.8065 | 3.1970 / 3.0343 | 3.7615 / 3.7229 |
| 100 | B | 39/39 | 10.1466 / 10.0618 | 6.3864 / 5.9559 | 9.7167 / 9.5490 |
| 100 | C | 39/39 | 10.1466 / 10.0618 | 6.1667 / 5.7304 | 9.7190 / 9.5503 |

A has zero added cost and zero detections at every budget. Every arm at zero budget reproduces that baseline. The primary paired contrast below is C minus B on identical problem/population inputs. Detection fractions condition on each problem's new signatures; cost and coverage use all signatures. Direction counts list lower / tied / higher problem values.

| Budget % | Δ cost EP / SB | Cost directions /40 | Δ detection EP / SB | Detection directions /22 | Δ coverage EP / SB |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.0000 / 0.0000 | 0/40/0 | 0.0000 / 0.0000 | 0/22/0 | 0.0000 / 0.0000 |
| 25 | -0.5026 / -0.5194 | 19/18/3 | 0.0227 / 0.0294 | 0/21/1 | -0.0800 / -0.0796 |
| 50 | 0.1045 / 0.1393 | 11/20/9 | 0.0379 / 0.0343 | 3/15/4 | -0.0539 / -0.0538 |
| 100 | 0.0022 / 0.0013 | 7/28/5 | 0.0000 / 0.0000 | 0/22/0 | -0.0041 / -0.0040 |

At 25%, C spends less on average but retrieves less of the catalogue; its detection improvement is confined to `acq_94215`. At 50%, C improves detection in four problems, ties in 15, and worsens it in three: `acq_94223`, `acq_94236`, and `acq_94238`. Its all-population mean cost increases by **117/1120 EP** and **39/280 SB**. Higher-cost cases are `acq_94212`, `94214`, `94216`, `94220`, `94221`, `94222`, `94225`, `94228`, and `94229` (all use the `acq_` prefix).

At 100%, C's pooled added cost is 4,476 versus B's 4,492, including 241 versus 257 units on new signatures. Nevertheless, the primary all-population paired mean increases by **1/450 EP** and **7/5400 SB**. Different problem signature counts and population weights explain this reversal. New-population EP cost improves by 29/132, while original-population cost is identical. C costs more in `acq_94219`, `acq_94223`, `acq_94233`, `acq_94236`, and `acq_94238`; seven problems cost less and 28 tie. Pooled savings do not establish lower average cost under the frozen primary aggregation.

The stratified table retains the adverse archive-ambiguity result. Each stratum contains ten problems; their SB group counts are 6, 8, 8, and 8 in the displayed order. New-signature denominators are 2, 11, 11, and 15 respectively. D is displayed for completeness but has extra model information.

| Stratum | Budget % | Detected B / C / D | C−B all-cost EP / SB |
| --- | --- | --- | --- |
| positive receipt | 25 | 0/0/0 of 2 | -0.3000 / -0.4167 |
| positive receipt | 50 | 0/0/0 of 2 | 0.0000 / 0.0000 |
| positive receipt | 100 | 2/2/2 of 2 | 0.0000 / 0.0000 |
| negative completeness | 25 | 0/1/1 of 11 | -1.0000 / -0.8500 |
| negative completeness | 50 | 1/3/4 of 11 | 0.2767 / 0.3021 |
| negative completeness | 100 | 11/11/11 of 11 | -0.0711 / -0.1014 |
| complementary candidates | 25 | 4/4/4 of 11 | -0.5206 / -0.5413 |
| complementary candidates | 50 | 7/10/10 of 11 | 0.3762 / 0.3921 |
| complementary candidates | 100 | 11/11/11 of 11 | -0.0800 / -0.0563 |
| archive ambiguity | 25 | 2/2/2 of 15 | -0.1900 / -0.2437 |
| archive ambiguity | 50 | 7/5/6 of 15 | -0.2350 / -0.1719 |
| archive ambiguity | 100 | 15/15/15 of 15 | 0.1600 / 0.1625 |

## D: additional model knowledge

The fixed k=2 envelope yields 20/39 detections at 50%, versus C's 18/39 and B's 15/39. It does not reveal the actual k or realized signature. Its score counts distinct possible signatures, not a calibrated probability. These results cannot be attributed solely to query ordering under equal information.

| Budget % | Detected new | Added cost original EP / SB | Added cost new EP / SB | Added cost all EP / SB |
| --- | --- | --- | --- | --- |
| 25 | 7/39 | 0.9337 / 0.9160 | 0.8864 / 0.8824 | 0.9244 / 0.9059 |
| 50 | 20/39 | 3.8234 / 3.8107 | 3.0455 / 2.9559 | 3.7540 / 3.7229 |
| 100 | 39/39 | 10.1466 / 10.0618 | 5.6364 / 5.1912 | 9.6815 / 9.5086 |

D's all-population cost is slightly lower than C's at all nonzero budgets under EP; at 50% their SB costs tie. It still spends more than B on the all-population mean at 50%. Its finite-budget detection gains do not remove the catalogue's inability to distinguish nominal-compatible opposite-claim alternatives.

## Warrant, withdrawal, and remaining ambiguity

Expanded warrant is computed retrospectively from **all** compatible worlds, not a selected hidden truth. Restoration requires the same original definite proposal to become supported. An alarm requires withholding a nominal definite proposal; withdrawal alone never counts as restoration. An opposite final definite answer also fails the restoration test. A genuine restoration and an alarm can coexist, so the table separates restoration without alarm.

The following pooled counts concern all 431 signatures at each nonzero k. Restoration has 109 initially unsupported proposals as its eligible population; final unsupported and definite withdrawals concern the 297 pre-audit definite proposals. “Silent unsupported” means no alarm, not a validated conclusion. Original and new remaining-unsupported counts are shown separately.

| k | Budget % | Arm | Restored /109 | Restored, no alarm | Definite withdrawals /297 | Unsupported original + new | Silent unsupported |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 25 | B | 2 | 2 | 4 | 94 + 13 | 103 |
| 1 | 25 | C | 0 | 0 | 5 | 96 + 13 | 104 |
| 1 | 25 | D | 0 | 0 | 5 | 96 + 13 | 104 |
| 1 | 50 | B | 6 | 4 | 9 | 92 + 11 | 97 |
| 1 | 50 | C | 5 | 3 | 14 | 93 + 11 | 96 |
| 1 | 50 | D | 5 | 3 | 15 | 93 + 11 | 95 |
| 1 | 100 | B | 28 | 25 | 26 | 71 + 10 | 71 |
| 1 | 100 | C | 27 | 25 | 26 | 71 + 11 | 71 |
| 1 | 100 | D | 27 | 25 | 26 | 71 + 11 | 71 |
| 2 | 25 | B | 0 | 0 | 4 | 96 + 13 | 105 |
| 2 | 25 | C | 0 | 0 | 5 | 96 + 13 | 104 |
| 2 | 25 | D | 0 | 0 | 5 | 96 + 13 | 104 |
| 2 | 50 | B | 1 | 1 | 9 | 95 + 13 | 100 |
| 2 | 50 | C | 3 | 3 | 14 | 93 + 13 | 96 |
| 2 | 50 | D | 3 | 3 | 15 | 93 + 13 | 95 |
| 2 | 100 | B | 10 | 10 | 26 | 86 + 13 | 86 |
| 2 | 100 | C | 10 | 10 | 26 | 86 + 13 | 86 |
| 2 | 100 | D | 10 | 10 | 26 | 86 + 13 | 86 |

At zero budget and for A at every budget, restoration and withdrawals are zero, and 96 + 13 proposals remain unsupported without alarm. All 188 initially supported definite proposals remain supported under additional truthful retrieval. None of the 134 initial archive-irreducibility conclusions becomes overstrong; these conclusions use the operational all-continuation criterion, not merely one opposite-claim witness.

The k=1, 50% comparison is adverse for warrant: B restores four original proposals and C/D restore three, leaving 92 versus 93 original unsupported conclusions despite C/D detecting more new conflicts. At k=2 the same paths restore one versus three original proposals, leaving 95 versus 93. Actual-k support can differ even when selection and cost cannot.

At full budget, original-signature restoration is exactly 25 at k=1 and ten at k=2, leaving 71 and 86 unsupported original conclusions with no alarm. These endpoints follow from the preserved complete-signature witnesses and are correctness checks. These remaining unsupported original proposals cannot be diagnosed by any permitted query because the entire observable signature is shared by opposite-claim worlds.

Full conflict coverage does not force identical final evidence. Early stopping at the first alarm leaves B with three mathematically restored new proposals at k=1, versus C/D's two. Every one is also withdrawn. Thus B restores 28 proposals overall and leaves 81 unsupported, versus C/D's 27 and 82. These are not retained auditor conclusions. At k=2 all arms restore ten and leave 99 unsupported, including 13 withdrawn new proposals. All full-budget arms raise 39 alarms, of which 26 withdraw definite proposals and 13 accompany initially warranted irreducibility conclusions.

An alarm also need not make a claim false: 13 new proposals already established at H0 remain established on alarm paths. Some initially ruled-out proposals instead become established, which correctly remains a failure to restore the original proposal. The complete joint alarm/proposal/final-status/disposition tables are retained in [summary.json.gz](results/summary.json.gz). Full-archive ambiguity covers 207 signatures at k=1 and 227 at k=2; it is distinct from pending uncertainty caused by stopping retrieval.

## Retrieval burden and controls

For k=1/2 all signatures, the base EP cost is 3.1239, with 1.6971 queries and 239.62 canonical returned bytes. The following means add to that same base; costs are retrieval units, not dollars. Coverage includes both base and added queries. Empty-result payloads count toward returned bytes.

| Budget % | Arm | Added cost EP | Total cost EP | Added queries EP | Added bytes EP | Coverage EP |
| --- | --- | --- | --- | --- | --- | --- |
| 25 | B | 1.4496 | 4.5735 | 1.1062 | 159.98 | 49.98% |
| 25 | C | 0.9469 | 4.0709 | 0.6311 | 90.65 | 41.98% |
| 25 | D | 0.9244 | 4.0484 | 0.6199 | 88.47 | 41.81% |
| 50 | B | 3.6571 | 6.7810 | 2.0519 | 295.36 | 66.66% |
| 50 | C | 3.7615 | 6.8855 | 1.7399 | 249.89 | 61.26% |
| 50 | D | 3.7540 | 6.8780 | 1.7324 | 247.96 | 61.10% |
| 100 | B | 9.7167 | 12.8407 | 3.7753 | 542.30 | 97.64% |
| 100 | C | 9.7190 | 12.8429 | 3.7513 | 538.16 | 97.23% |
| 100 | D | 9.6815 | 12.8054 | 3.7350 | 535.61 | 96.92% |

The same original 392 signatures are nominal-compatible at every k. Their base EP cost is 3.1534 and full-audit total cost is 13.3 for B/C/D; no alarm occurs. This signature-weighted base differs from the earlier original-prior expected cost of 3.369140625 because the estimand changed, not because the preserved nominal policy improved.

Aliases incur material redundant-record retrieval. At 50%, B spends 172 pooled units on 68 alias queries (9,418 bytes), whereas C/D spend 402 on 126 (17,370 bytes). At 100%, B/C spend 490 on 154 aliases (21,572 bytes); D spends 486 on 152 (21,376 bytes). These are separately charged catalogue actions, not independent receipts. No added lookup returns an initial record. At full budget the maximum added cost is 22, total cost 24, added query count six, and added returned bytes 1,147. Full per-problem maxima and totals remain in [per_condition.json.gz](results/per_condition.json.gz).

Conditional EP cost at detection at 50% is 3.6111 for B, 2.8000 for C, and 2.7273 for D. The arms detected different subsets, so these are not matched-archive cost improvements. The unconditional paired costs above keep the population fixed. At full budget every arm detects the same 39 signatures, permitting that population-specific comparison.

Zero budget, A, k=0 parity, zero false alarms, full-budget conflict coverage, same-signature k=1/2 paths, and preserved support are tested mechanical properties. The schedule retains 96 zero-residual run occurrences. There are 368 occurrences with a nonzero budget percentage but zero allowance: 72 also have zero residual cost, and 296 have positive residual cost with the allowance rounded down to zero. These overlapping counts do not create new independent cases. No budget, arm, stratum, or adverse outcome was removed.

## Validation, reproduction, and limits

Before freezing, **949 tests passed (883 historical plus 66 new)** and Ruff passed. The four development problems completed 192 conditions and 1,952 signature runs. Evaluation then completed all 1,920 cells and 20,064 runs without failures. Observed evaluation maxima were eight actions, two outcomes, 36 expanded worlds, and 20 signatures, within the preserved limits.

[Saved-output verification](OFFLINE_VERIFICATION.json) checked 80,256 certificate references, 6,021 unique certificates (1,521 nominal and 4,500 expanded), 25,079 paid prefixes, 380 first-conflict checks, 20,064 budget-prefix checks, 13,168 cross-k path checks, and 3,762 full-budget endpoint checks. [Independent arithmetic validation](INDEPENDENT_VALIDATION.json) recomputed 491,400 metric estimates, including all 2,880 summary rows and 4,320 per-problem paired rows. Counts describe verification occurrences, not independent samples; repeated verification passes are not added together.

Total local execution overhead was 109.963 seconds, including 1.662 seconds in selection, 2.712 in nominal compatibility checks, and 45.793 in independent reference verification. These are implementation measurements from this execution, not a new timing competition or monetary valuation. Certificate reuse is computational reuse, not additional investigator sessions. All 27 frozen dependencies and preservation hashes for 289 existing tracked and 509 local files matched. The [final validation record](FINAL_VALIDATION.json) records the completed artifact checks. This task made zero network requests or model calls and incurred zero spend.

From the repository root, verify retained outputs or reproduce into a fresh ignored directory:

```sh
.venv/bin/python -m studies.audit_aware_acquisition.analysis verify
.venv/bin/python -m studies.audit_aware_acquisition.analysis run --output artifacts/audit-aware-acquisition/replication
```

The [output manifest](results/manifest.json) pins the detailed [runs](results/runs.json.gz), [certificates](results/certificates.json.gz), [condition tables](results/per_condition.json.gz), [summaries](results/summary.json.gz), and [paired contrasts](results/paired.json.gz), including subtypes, undefined denominators, and all adverse problem values.

These finite synthetic constructions do not estimate deployment probabilities, real-world failure rates, or general model adequacy. Audit orders are budget-censored heuristics, not budget-optimal policies. D's envelope knowledge is extra information. A conflict cannot identify a unique omission cause or establish a claim's falsity; silence cannot establish model adequacy. Verification directly reconstructs observations and support but reuses the preserved physical validators, claim semantics, and certificate machinery, and does not independently reprove the original exact optimizer. The historical simulator chronology limitation, completed studies, and their null and adverse findings remain unchanged.

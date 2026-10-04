# Exact audit detection–cost limits: results

At the old 50% extra-budget cutoff, exact auditor E detects **32 of 39** archive conflicts, versus **20** for both D and D_affordable. The hindsight bound is also 32: seven cannot be certified within their allowance even with signature-specific hindsight, the count search gap is zero, and the greedy policy-selection gap is twelve. E spends **314** added retrieval units over the 431 design signatures versus D_affordable's **1,822**. This objective-specific improvement has an adverse consequence: E inspects less evidence and leaves more original target claims unsupported, including at full conflict coverage.

## Scope, completion, and denominators

The [protocol](ANALYSIS.md), [method](METHOD.md), and [configuration](config.json) were frozen before new evaluation decisions. This review-informed calculation retains the same 40 problems, 30 structural groups, original paid stopping histories H0, fixed k=2 hypothetical signature envelope, and hard budgets. Every distinct design signature has unit weight, including nominal-compatible signatures. This supplied census objective is not a calibrated deployment prior. No acquisition history, omission mechanism, price, or target changed.

All **169 roots**, **1,722 integer root/budget cells**, and **30,510 directly executed design-policy paths** completed. Percentage anchors reference those paths and apply actual-k support checks, producing **30,096 anchor views** in **2,880 aggregate cells**. Reuse across anchors or k conditions creates no additional paid session or independent trial. There were no caps, unavailable roots, missing cells, or failures. Budget-aware paths were executed independently at each allowance, not censored from a larger-budget path.

A does no added retrieval. B and C retain nominal-only cost-order and constant-first rules. D retains fixed-k=2 contradiction scoring and its unaffordable-next-action cutoff. D_affordable restricts the same rule to affordable actions. E has the same envelope and budget information as D_affordable and maximizes detection, then minimizes summed cost on every design signature. E versus D_affordable is primary; E versus D also changes budget awareness. B/C lack the extra envelope.

At every k there are 392 original signatures; k=1 and k=2 share the same 39 new signatures, giving 431 total. Each signature belongs to exactly one verified root. Equal-problem (EP) means first average within a problem. Structure-balanced (SB) means average variants within each original group, then groups equally. Original/all means use 40 problems and 30 groups; conditional new-signature means use 22 problems and 17 groups. Conditional metrics retain their own defined populations; conflict-detection fractions conditional on new signatures are undefined at k=0. Roots are not given equal weight. Repeated budgets and k values are not independent incidents.

## Detection ceiling and miss-count decomposition

The table applies to each nonzero k separately, counting the 39 conflicts once. An anchor is floor(percent × residual catalogue cost / 100) at each root, not one common absolute budget.

| Anchor % | Hindsight h /39 | E /39 | D_affordable /39 | D /39 | Hindsight-impossible | Search gap h−E | Policy gap E−D_affordable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 0 | 0 | 39 | 0 | 0 |
| 25 | 7 | 7 | 7 | 7 | 32 | 0 | 0 |
| 50 | 32 | 32 | 20 | 20 | 7 | 0 | 12 |
| 100 | 39 | 39 | 39 | 39 | 0 | 0 | 0 |

At 50%, D_affordable's 19 misses decompose as **19 = 7 + 0 + 12**. These are count differences, not disjoint named sets of missed signatures: policies can detect different members. E's detection fraction improves by **13/44 EP** and **9/34 SB**. Eight conflict-bearing problems improve, 14 tie, and none worsens. Improving IDs are `acq_94213`, `acq_94215`, `acq_94219`, `acq_94223`, `acq_94233`, `acq_94234`, `acq_94236`, and `acq_94238`.

The search gap is zero at **all 1,722 integer root/budget cells**. This is a numerical property of these inputs, not a theorem that prospective search is always free. Policy-selection gaps are positive in 55 cells, with maximum two per cell. D_affordable beats D's detection in only one integer cell: `acq_94233`, root `audit_root_68c2b86482c78944beede353`, allowance five, gains one. It gains no detections at the percentage anchors but spends more at 25% and 50%, an adverse affordability-control result.

All 39 new signatures have finite hindsight minima; all 392 original signatures have explicit `no_catalogue_contradiction`. Minimum costs range from one to nine, with frequencies {1:4, 2:7, 3:1, 4:18, 5:3, 6:4, 7:1, 9:1}. Zero count search gap does not imply minimum cost on every detected path. At 50%, E's detected paths cost 117 versus 115 for their hindsight subsets; at full budget they cost 152 versus 148. These exclude nominal-compatible expenditure, which remains charged in the policy objective.

At 50%, the stratum results are:

| Stratum | New N | D | D_affordable | E = h | Too costly in hindsight | Policy gap | Δ cost E−D_affordable EP / SB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| positive receipt | 2 | 0 | 0 | 0 | 2 | 0 | -2.6100 / -2.5917 |
| negative completeness | 11 | 4 | 4 | 8 | 3 | 4 | -3.9589 / -3.7486 |
| complementary candidates | 11 | 10 | 10 | 11 | 0 | 1 | -4.4667 / -4.1866 |
| archive ambiguity | 15 | 6 | 6 | 13 | 2 | 7 | -2.0550 / -1.9969 |

Each stratum contains ten problems, with respectively 6, 8, 8, and 8 groups. Positive-receipt detection is flat because both certificates exceed the 50% allowances. Archive ambiguity supplies seven of the twelve policy-gap detections. Complete strata/subtype tables at every anchor remain in saved summaries.

## Actual spending and comparable detection

Across the 431 signatures, summed allowances are 991, 2,228, and 4,654 at 25%, 50%, and 100%; individual allowances range from zero to 5, 11, and 22. These are counterfactual path totals, not a shared budget pool. Original acquisition costs separately total **1,617**, unchanged for every arm. Added costs include empty lookups and nominal-compatible paths. The cost columns are pooled sums over their stated signature populations; the final column separately reports EP/SB means.

| Anchor % | Arm | Detected /39 | Added original /392 | Added new /39 | Added all /431 | Base + added all | All-cost mean EP / SB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | D | 7 | 398 | 35 | 433 | 2050 | 0.9244 / 0.9059 |
| 25 | D_affordable | 7 | 658 | 63 | 721 | 2338 | 1.5504 / 1.5306 |
| 25 | E | 7 | 16 | 10 | 26 | 1643 | 0.0817 / 0.1089 |
| 50 | D | 20 | 1598 | 132 | 1730 | 3347 | 3.7540 / 3.7229 |
| 50 | D_affordable | 20 | 1681 | 141 | 1822 | 3439 | 3.9171 / 3.8595 |
| 50 | E | 32 | 197 | 117 | 314 | 1931 | 0.6444 / 0.6926 |
| 100 | D | 39 | 4235 | 223 | 4458 | 6075 | 9.6815 / 9.5086 |
| 100 | D_affordable | 39 | 4235 | 223 | 4458 | 6075 | 9.6815 / 9.5086 |
| 100 | E | 39 | 262 | 152 | 414 | 2031 | 0.8707 / 0.9034 |

E's 50% cost includes **197** units on nominal-compatible archives and **117** on new signatures. Its lower objective value does not hide nondetection expenditure. D_affordable spends 1,681 and 141 respectively. Relative to D, affordability filtering adds 92 units (83 original, nine new) without another detection; at 25% it adds 288 units with no detection gain. D and D_affordable coincide at full budget.

The unchanged nominal-only baselines at 50% are B: **15 detections, 1,706 added units** (1,563 original / 143 new), and C: **18 detections, 1,732 units** (1,596 original / 136 new). A detects zero at zero added cost. These comparisons with E are not matched in model knowledge: B/C do not receive the fixed k=2 envelope.

Population-specific 50% mean costs are:

| Arm | Original EP / SB | New EP / SB | All EP / SB |
| --- | --- | --- | --- |
| D | 3.8234 / 3.8107 | 3.0455 / 2.9559 | 3.7540 / 3.7229 |
| D_affordable | 3.9790 / 3.9426 | 3.3864 / 3.1912 | 3.9171 / 3.8595 |
| E | 0.5165 / 0.5590 | 2.6818 / 2.6765 | 0.6444 / 0.6926 |

Paired contrasts below are E minus D_affordable on identical populations. Lower coverage is retained alongside cost savings.

| Anchor % | Δ added cost EP / SB | Cost lower/tied/higher /40 | Δ detection EP / SB | Δ coverage EP / SB |
| --- | --- | --- | --- | --- |
| 0 | 0.0000 / 0.0000 | 0/40/0 | 0.0000 / 0.0000 | 0.0000 / 0.0000 |
| 25 | -1.4688 / -1.4217 | 36/4/0 | 0.0000 / 0.0000 | -0.1752 / -0.1731 |
| 50 | -3.2727 / -3.1669 | 39/1/0 | 0.2955 / 0.2647 | -0.2662 / -0.2585 |
| 100 | -8.8108 / -8.6052 | 40/0/0 | 0.0000 / 0.0000 | -0.5810 / -0.5716 |

Exactness does not promise cheaper canonical E than every lower-detection heuristic. Across 1,722 integer root/budget cells E costs more than B in **eight**, and more than C in **four**, always detecting more in those cases. At `acq_94229`, root `audit_root_a53bad2683ef787b0366738c`, allowance four, E attains `(d,l)=(2,24)`, C `(0,12)`, and B `(0,18)`. At the 50% anchor there is one such higher-cost root against each of B and C. E costs more than D or D_affordable in zero observed cells, a measured result rather than a general theorem.

The deterministic frontiers have one point in 1,514 root/budget cells, two in 174, and three in 34. For example, `acq_94221`, root `audit_root_416a8fd66913c6abd3bb76e1`, allowance five, has four design signatures and nondominated pairs **(0,0), (1,12), (2,16)**. E selects (2,16); the cheaper point intentionally detects fewer. Randomized-policy frontiers were not computed.

At 50%, an attainable collection of root frontier policies matches D_affordable's **20 detections at 142 units** versus its 1,822, saving **1,680 at matched detection**. Its point is strictly dominated at 140 of 169 roots and equal at 29. This witness obeys each root's hard allowance and does not substitute fewer detections. Canonical E instead detects 32 at 314, a different tradeoff. At full budget it matches all 39 at 414 instead of 4,458, saving 4,044.

Across all integer cells, D_affordable is strictly dominated in 1,401 and on the frontier in 321; D's counts are 1,273 and 449. B/C are dominated in 1,414/1,284. A's STOP and E's canonical points are on every frontier. Flat cells remain included. Saved dominating points and backpointers distinguish strict improvement from equality; repeated cells do not become independent sample sizes.

## Adverse warrant and inspection outcomes

The nonzero-k baseline has 297 definite proposals, including 109 unsupported under expanded support, plus 134 warranted archive-irreducibility conclusions. Warrant uses every compatible actual-Mk world. Restoration requires support for the same original proposal; withdrawal on alarm is independent, and an opposite definite answer is not restoration.

The table keeps original/new remaining-unsupported counts separate. At 50% and 100%, D has the same support counts as D_affordable.

| k | Anchor % | Arm | Restored /109 | Restored, no alarm | Withdrawn definite /297 | Unsupported original + new | Unsupported, no alarm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 25 | D_affordable | 2 | 2 | 5 | 94 + 13 | 102 |
| 1 | 25 | E | 0 | 0 | 5 | 96 + 13 | 104 |
| 1 | 50 | D_affordable | 5 | 3 | 15 | 93 + 11 | 95 |
| 1 | 50 | E | 4 | 2 | 20 | 94 + 11 | 96 |
| 1 | 100 | D_affordable | 27 | 25 | 26 | 71 + 11 | 71 |
| 1 | 100 | E | 5 | 3 | 26 | 93 + 11 | 93 |
| 2 | 25 | D_affordable | 0 | 0 | 5 | 96 + 13 | 104 |
| 2 | 25 | E | 0 | 0 | 5 | 96 + 13 | 104 |
| 2 | 50 | D_affordable | 3 | 3 | 15 | 93 + 13 | 95 |
| 2 | 50 | E | 2 | 2 | 20 | 94 + 13 | 96 |
| 2 | 100 | D_affordable | 10 | 10 | 26 | 86 + 13 | 86 |
| 2 | 100 | E | 3 | 3 | 26 | 93 + 13 | 93 |

At 50%, E leaves **94 original proposals unsupported versus 93** for D_affordable at either k. At full budget it leaves **93 at both k values**, versus exhaustive-original references **71 at k=1** and **86 at k=2**. E restores only three original proposals and omits available evidence that would restore another 22 or seven. The paired extra unsupported count divided by each problem’s original-signature population, then averaged at full budget, is **0.044625 EP / 0.051630 SB** at k=1 and **0.016493 EP / 0.020139 SB** at k=2. It worsens in 12 and four problems respectively, without improvements on that axis. The four k=2 adverse IDs are `acq_94225`, `acq_94227`, `acq_94231`, and `acq_94233`; all adverse cases remain in paired tables.

E optimizes alarms and cost, not warrant. Once further detection is impossible, STOP avoids paying for evidence that might still support a target negative. Full-budget all-population coverage is **38.82% EP** versus D_affordable's **96.92%**; at 50% it is 36.69% versus 63.31%. Only six of 431 E paths exhaust the catalogue at full budget, versus 398 for D_affordable; on original signatures it is four of 392 versus 392. Lower expenditure therefore is not a general-purpose investigation improvement.

Pending uncertainty and archive irreducibility also remain distinct. At full budget E ends unresolved pending on 47/21 signatures at k=1/2, versus D_affordable's six/six. E's final irreducible counts are 188/216, versus 207/224. These are operational evidence states, not false target claims. All 134 initially warranted irreducibility conclusions remain warranted; none becomes overstrong.

At k=1, E's two restored new proposals at 50% and 100% also trigger alarms and are withdrawn, so these mathematical support changes are not retained auditor conclusions. At k=2 it restores no new proposal. All arms preserve the 188 initially supported definite proposals. Some established proposals remain established when an alarm fires; conflict does not imply target falsity. The 71/86 complete-signature opposite-claim witnesses remain indistinguishable through the catalogue. E's extra 22/seven unsupported originals reflect unacquired available evidence, not a new impossibility result.

E's added-query EP means at 25/50/100% are 0.0525/0.3186/0.4136 and added-byte means 6.93/44.47/57.90, alongside the unchanged base 1.6971 queries and 239.62 canonical bytes. Empty lookups and dependent aliases remain charged. Exact bytes, alias overhead, conditional detection costs, and joint alarm/support outcomes are retained. Conditional costs can compare different detected subsets: the 50% E−D_affordable conditional detection-cost contrast is positive (7/22 EP, 11/40 SB over 11 jointly defined problems), so it must not be replaced by the favorable all-population cost result.

## Validation, resources, and reproduction

Before freezing, **296 dependency-scoped tests passed**, including **86 new and 210 historical dependency tests**; Ruff passed. Unrelated simulations, model evaluations, and the wiki census were not rerun. Four development problems completed 15 roots, 2,520 direct design paths, and 2,928 anchor views. A separate exhaustive decision-tree oracle checked complete frontiers on tiny fixtures. Its analytic traps are correctness fixtures, not extra evaluation discoveries.

The [36-dependency freeze](freeze.json) preceded evaluation. [Integrated verification](results/independent_verification.json) and a fresh [saved-output check](OFFLINE_VERIFICATION.json) verified 169 roots, 1,722 budgets, **53,290 Bellman states**, **105,551 child combinations**, **431 hindsight rows**, and **10,688 subsets**. All 30,510 paid design paths and 30,096 anchor views were checked, with **7,201 distinct certificates** (2,428 nominal, 4,773 expanded) and **181,443 certificate-reference checks**. The old 20,064 A–D anchor views reproduce, excluding timing fields only. [Independent arithmetic validation](INDEPENDENT_VALIDATION.json) passed **650,000 exact-rational comparisons**. Repeated verification passes are not added to these counts.

No cap was reached. Maximum per-root usage was 2,725 states and 6,347 combinations against limits of 100,000 and 10,000,000; maximum frontier size was three. Whole-root planning took **2.109 seconds wall / 2.109 CPU**. Direct integer-budget reconstruction/execution across all arms took **18.362 wall / 18.361 CPU**. E backpointer choice inside that work took 0.131 wall / 0.128 CPU and must not be added again. The integrated independent checker took 65.984 wall / 65.974 CPU. Total execution was **154.104 wall / 154.077 CPU**, including serialization and certificate work. Cumulative process peak RSS was **1,070,508 KiB**, not an isolated per-arm measurement. These are whole hypothetical computation costs, not single-investigation latency or a scalability comparison.

All **316 historical tracked and 509 retained local files** match preservation hashes. The legacy chronology limitation and completed studies remain unchanged. There were zero network/model calls, credential accesses, or additional spend. [Final validation](FINAL_VALIDATION.json) records completed artifact and preservation checks.

From the repository root:

```sh
.venv/bin/python -m studies.exact_audit_frontier.analysis verify
.venv/bin/python -m studies.exact_audit_frontier.analysis run --output artifacts/exact-audit-frontier/replication
```

A fresh run refuses an existing output directory. The [manifest](results/manifest.json) pins [root frontiers/hindsight evidence](results/roots.json.gz), [executed design paths](results/design_runs.json.gz), [anchor views](results/runs.json.gz), [design summaries](results/design_summary.json.gz), [support summaries](results/summary.json.gz), [paired contrasts](results/paired.json.gz), and [validation](results/validation.json). All integer budgets, strata, populations, and adverse/flat cases are retained.

## Interpretation limits

Exact recurrence correctness, no nominal false alarms, monotone detection ceilings, the hindsight path bound, and full-budget 39/39 detection are mathematical endpoints checked by implementation tests. New numerical findings are 32/20 detection, zero search gaps on these inputs, measured policy gaps/cost reductions, flat anchor affordability gains, and worse warrant/coverage. The result is conditional on deterministic policies, this finite fixed-k=2 census, and stopping history H0. It covers neither randomized mixtures nor joint acquisition optimization, deployment probabilities, general archive adequacy, or unknown mechanisms.

Verification checks Bellman closure, paths, subset minima, charges, and arithmetic, while reusing preserved physical semantics, canonicalization, and certificate validators. It does not independently establish real-world assumptions or reprove the old acquisition optimizer. No target truth follows merely from an alarm, missing receipt, or exposure. No cases or budgets were changed to manufacture a nonzero gap, and no sampling intervals, significance claims, or practical time/money savings are inferred.

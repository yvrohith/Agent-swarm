# Post-stopping audit orders, alarms, and warrant

The [analysis protocol](ANALYSIS.md) fixes a comparison of added retrieval orders after an unchanged nominal policy proposes stopping. This method does not compute an optimal audit policy or introduce a new observation contract.

## Contracts and paid information

M0 is the original nominal model; Mk is the completed omission closure at actual k. A surviving completeness record retains authentic assertion bytes under Mk but is not assumed to guarantee current post-omission retention. Physical events, initial evidence, receipt truth, and alias semantics retain their prior meanings. Let S0(H) and Sk(H) contain every nominal or expanded realization compatible with the same initial evidence and paid history H. The evaluator's actual-world identity and omission provenance never restrict those sets.

H0 is the verified retained stopping history of the original-prior exact policy, with original proposal P0. A passive archive holds the full actual signature privately. Each requested unqueried action is charged its original price and canonical payload bytes before its answer enters H. Empty lookups do not assert event absence. Alias actions are still separate priced catalogue entries, but their outcomes derive from the same physical record. A paid alias does not manufacture a second independent receipt, and an unqueried alias is not granted as a free observation.

The auditor receives no actual k, unqueried answer, hidden truth, omission, parent, hindsight subset, or evaluator classification. Nominal-only arms know M0; D additionally knows the fixed hypothetical k=2 signature envelope. Selection is a pure function of that information and paid history, with no selector cache or realized-answer state. Cache certificates by their own model/contract and history. Reordering evaluation cases must not change an action at the same paid history.

## Four selectors

Let U(H) be the unqueried action IDs, c(a) their positive costs, and S0(H,a,o) the nominal subset consistent with answer o to action a. Common stopping checks handle empty support, exhausted U, and unaffordable chosen actions outside selection.

**A, no audit:** Return H0 without further acquisition for every budget. Expanded support checking remains an evaluator diagnostic.

**B, cost order:** Choose the minimum `(c(a), opaque_id(a))` over U(H).

**C, constant first:** Recompute

    K(H) = {a in U(H) : exactly one S0(H,a,o) is nonempty}.

Choose the cheapest action in K(H), breaking ties by ID. If K(H) is empty, apply B to U(H). Fallback is essential: observing an initially nonconstant answer can make another action constant. Claim terminality does not end the audit.

**D, closure informed:** Let Sigma2(H) be the distinct complete k=2 signatures consistent with paid H. The design envelope stays k=2 for every evaluated k. For each unqueried action use the exact rational score

    score(a,H) = |{s in Sigma2(H) : S0(H,a,s[a]) is empty}| / c(a).

Choose the largest positive score, resolving ties by lower cost then opaque ID. If all scores are zero, apply C. Empty Sigma2(H) is an explicit condition failure because each generated realization should embed in the envelope. Do not replace it or infer the actual k. The score uses possible observations only, not claim labels or counts of parents/worlds sharing a signature. It is a deterministic heuristic, not a calibrated probability. D's extra supplied model knowledge prevents interpreting D-minus-C or D-minus-B as ordering-only effects under equal information.

## Audit budget and termination

At H0, define residual cost R = sum_{a in U(H0)} c(a). For percentage b in {0,25,50,100}, the extra allowance is floor(bR/100). Base cost C0, added cost Ca, and total C0+Ca are reported separately. Query and returned-byte totals receive the same separation. All percentages remain in the schedule even when rounding or zero R makes conditions coincide.

Selectors cannot inspect remaining funds. Select the next action using the rule above; if its price exceeds unused allowance, stop without reranking. After every returned answer, check nominal compatibility before any other stop: empty S0(H) yields `nominal_model_conflict` and immediate cessation of spending. Otherwise continue until the order is budget-censored or the catalogue is exhausted. No-alarm output is `no_conflict_observed` with coverage, not model validation or an expanded proof. Expanded claim status cannot trigger a privileged early stop in D.

Since action choice is budget-independent, each finite-budget history is a prefix of that arm's full trajectory, cut before the first unaffordable action or at its first conflict. This implementation executes the budget-limited runs directly and checks prefix consistency. Shared model and certificate calculations are computation reuse, not extra empirical replication.

## Conflict axis

A conflict means S0(H) is empty. Its certificate identifies the nominal model/assumptions and acquired history and verifies that every nominal world disagrees with some acquired answer. It does not name a unique physical cause or label the claim false. A nominally possible complete signature cannot trigger a sound conflict test because its original witness survives every truthful paid prefix.

A contradictory answer to a constant nominal query empties support; either answer to a nonconstant binary query preserves it. This explains why added audit queries can expose conflicts skipped by the original nominal exact policy. At full residual budget, exhaustive B/C/D either encounter a conflict earlier or retrieve the complete signature. Hence they must expose every full-signature nominal conflict. This is a correctness endpoint, not measured evidence of a new algorithmic advantage.

Record first conflict's action, outcome, added query count and cost; remaining full conflicts missed at cutoff; false alarms on original signatures; and added expenditure where no nominal conflict exists. Conditional detection denominators contain only new signatures. A zero denominator is undefined, including every k=0 detection fraction. Preserve the original-signature and new-signature populations rather than changing a paired denominator when k adds signatures.

## Support axis and withdrawal

For a definite original proposal P0, expanded warrant at H requires nonempty Sk(H) and agreement with P0 in **every** member. Record expanded `established`, `ruled_out`, `unresolved`, or `model_conflict` regardless of alarm status. For unresolved claims, distinguish pending uncertainty from archive irreducibility: the latter requires opposite claim values in every compatible full-signature cell. One opposite witness refutes certainty but cannot establish all-continuation irreducibility.

Compare warrant at H0 and final H. An initially supported definite proposal remains supported as truthful observations narrow a nonempty Sk. Mathematical `warrant_restored` means P0 is definite, lacks expanded support at H0, and the final expanded claim status agrees with P0. It does not require absence of an alarm. An opposite final definite status is not restoration of P0. Separately record `withdrawn_definite` when an alarm requires withholding the nominal definite proposal, and `unwithdrawn_warrant_restored` when restoration occurs without that alarm. Withdrawal alone can never satisfy the warrant predicate, but genuine expanded restoration and withdrawal can coexist. Report those joint states explicitly. A no-alarm history can remain unsupported; retrospective expanded conclusions are not attributed to a nominal-only auditor.

Keep original archive-irreducibility proposals and their expanded justification separate from definite proposals. Include full-signature irreducibility so incomplete retrieval is not confused with inherently unavailable evidence. On an original full signature, a retained nominal witness and expanded opposite witness with identical answers prevent a sound catalogue-only alarm, and all-query retrieval cannot restore that nominal definite proposal. The known 71/86 full-signature losses and 25/10 repairable original stopping losses are endpoint checks, not newly discovered effects.

## Quantities, aggregation, and verification

For each problem/k/arm/budget/population, retain exact counts, base/added/combined costs, query counts, canonical bytes, maxima, coverage, first-conflict quantities, proposal-support transitions, and joint alarm/support cells. Report paired C-minus-B differences on the same problem and denominator, with direction counts and both detection and cost. D remains a separately labeled information-advantaged comparison. Distinct-signature census averages are descriptive, not deployment expectations or weights inferred from omission multiplicity.

The conditional `added_cost_at_detection` mean includes only signatures detected by the arm, and is undefined when none are detected. Different arms may detect different finite-budget subsets, so differences between these conditional means do not isolate cost changes on identical detected archives. Primary added-cost comparisons instead retain the same complete original/new/all population and are interpreted jointly with detection and catalogue-coverage fractions. Record final supported and unsupported definite-proposal flags independently of alarm/withdrawal.

Equal-problem means first summarize the relevant signature population within each problem. Structure-balanced means average those quantities within the unchanged groups, then groups equally. Conditional populations retain defined/undefined problem and group counts; failures are not silently excluded. Strata, actual k, arm, budget, and original/new/all populations remain grouping keys. Repeated k conditions, budgets, aliases, and cached histories do not create independent incident samples. Use no sampling intervals or significance claims.

Reference verification reconstructs query outcomes from retained-record membership and directly filters saved support, checking histories, charges, first-conflict position, support, and coverage. It checks distinct certificates and all run references without treating the selector's own flag as proof. Reusing immutable validators, certificate machinery, and canonicalization is an explicit independence limit; no field validation or independent reproof of the original exact optimizer is claimed. Planning/checking timings are local implementation overhead only, not a new timing competition or conversion of retrieval units into money.

All conclusions remain conditional on the supplied finite contracts and query interface. This study cannot diagnose same-signature alternatives, establish general model adequacy, infer a unique failure mechanism, or estimate real-world false-conclusion rates. It preserves the historical chronology limitation and all completed scientific outcomes without changing their inputs or accounting.

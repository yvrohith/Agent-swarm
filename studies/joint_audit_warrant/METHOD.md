# A finite frontier for alarms, original-claim support, and cost

The [protocol](ANALYSIS.md) fixes this exploratory extension of the [saved detection-cost calculation](../exact_audit_frontier/METHOD.md). The target is the price of support at maximum conflict detection under one declared hypothetical physical model. It does not revise the old objective or establish factual accuracy in an actual incident.

## Physical support and observable states

Let M0 be the nominal model, M2 the unchanged k=2 physical closure, Sigma0 the nominal complete signatures, and Sigma2 the distinct M2 complete signatures. Every nominal signature belongs to Sigma2. Queries have deterministic typed outcomes and positive integer costs. Aliases share physical record membership but retain separate action prices. Initial records are fixed. Empty lookups, missing records, authenticated assertions, and currently true completeness guarantees retain their [existing meanings](../archive_model_misspecification/METHOD.md).

A root is the same ordered paid history H0, definite or irreducible proposal P0, accounting, and certificate as the preceding study. At a paid extension H, N(H) contains all compatible nominal worlds, T(H) all compatible Sigma2 signatures, U(H) all unqueried actions, and b the remaining hard extra allowance. W2(H) contains **all** physical M2 realizations agreeing with the acquired evidence. It is never restricted to the evaluator's actual parent, an omitted-ID set, or one representative of a signature cell. Empty W2 is a contract or implementation failure, not support by vacuous truth.

For each complete signature s, precompute its whole physical cell C2(s). Its claim status is definite only if every member agrees; differing claim values remain mixed. Since query answers are functions of full signatures,

    W2(H) = union over s in T(H) of C2(s).

**State sufficiency.** A physical world is compatible with H exactly when its signature agrees with all acquired answers. Thus the signature mask identifies every relevant physical world, including all opposite-truth alternatives in a mixed cell. No hidden representative or additional realized-world component is required. Multiplicity contributes no design weight, although every physical possibility is retained for the universal support test.

The memo state is `(nominal_world_mask, design_signature_mask, sorted_unqueried_ids, remaining_integer_budget)` within pinned nominal model, design signature table, physical M2 support, root proposal, and H0. The `SupportContract` physical pin identifies the expanded model/contract/support and claim; planner scope additionally binds P0 and H0. Fixed root/model pins determine the physical-cell map and Sigma0 membership. Claim semantics are hypothetical model knowledge supplied to both new policies; actual k and realized claim truth never enter planning.

Define `supported(H)` when P0 is `established` or `ruled_out`, W2(H) is nonempty, and every compatible physical world agrees with that same P0. At a nonconflicting stopping leaf, reward is

    w(H) = |T(H) intersect Sigma0| * I[supported(H)].

This counts supported original-signature proposals only. It does not reward unknown, a changed conclusion, withdrawal, or originally irreducible P0. New-signature claim statuses are checked separately. If N(H) is empty, no nominal signature can remain in T(H): a nominal witness with that complete signature would agree with every acquired answer. Assert this property rather than silently granting support on an alarm branch.

Support present at H0 is baseline credit. Truthful added observations restrict nonempty W2, so an already-supported definite proposal remains supported. Improvement is separately counted only when a formerly unsupported original proposal becomes supported. The full-archive support ceiling comes from original signature cells wholly agreeing with their own fixed P0; it is not the number of all true worlds or all definite signature cells irrespective of proposal.

## Triple recurrence, ties, and exactness

For state x=(N,T,U,b), retain nondominated integer triples `(d,w,l)`: detected design signatures, supported-original reward, and added retrieval cost summed over every signature in T. A triple dominates another if it has at least as much d and w and no more l, with at least one strict improvement.

If N is empty and T is nonempty, first-alarm termination yields only `(|T|,0,0)`. Otherwise STOP yields `(0,w(H),0)`. For each affordable unqueried action a, partition N and T by each possible observed outcome o, keeping all nonempty T_o branches, even where N_o is empty. Combine one child-frontier triple per branch:

    d = sum_o d_o
    w = sum_o w_o
    l = |T| * cost(a) + sum_o l_o.

Each child receives U minus a and the full residual pathwise allowance b−cost(a). Mutually exclusive outcome branches do not divide one allowance among themselves. Query charges include empty results and paths that never alarm. Enumerate every affordable action, including those constant in N or useless for immediate detection; they may establish support. No original constant-query pruning is inherited.

Union STOP and all action/child combinations, then retain nondominated triples. Equal triples prefer STOP, then lower current price, then opaque action ID, then canonical child-choice bytes in lexicographic outcome order. Child encodings contain outcome, child state ID, d, w, and l. Canonical J chooses greatest d, then greatest w among those, then smallest l, followed by the retained deterministic tie. Preserve every nondominated alternative and its backpointer, not a weighted scalar approximation.

**Recurrence proof.** Induct on the number of unqueried actions. At an alarm, immediate cessation is required. At a nonconflicting state with no affordable action, STOP is the only feasible policy. Otherwise any feasible deterministic policy either stops or begins with an affordable action and a feasible child policy for each observed outcome. Those children have fewer remaining actions. By induction their attainable values are represented or dominated by child-frontier triples. Replacing a dominated child by a dominating feasible child cannot worsen d or w or increase l because all three parent components add. Conversely every enumerated combination has feasible children and obeys the hard budget on each path. Thus the recurrence retains exactly the nondominated attainable triples, and its lexicographic choice answers the fixed detection-first, support-second, cost-third objective. Random mixtures are not enumerated.

## Projection and support-price certificates

Let A be the finite set of triples attainable by all feasible deterministic policies and F its nondominated subset. Ignoring w does not change which query policies are feasible: STOP, first-alarm termination, prices, and hard budgets are identical to the old solver.

**Projection equality.** Every triple in F projects to an old feasible `(d,l)` point. Conversely, take any old feasible point and its feasible policy's triple in A. If the triple is removed, finite dominance chains reach a triple in F with at least its d and no greater l. Its projection therefore dominates or equals the original projection, even when strict improvement was only in w. The nondominated `(d,l)` sets obtained from A and from projecting F are consequently equal. Compare that complete projected-and-pruned set with the saved old frontier at each requested allowance; equality of one canonical point is insufficient.

The historical E path can be dominated in support by a new triple with identical d and l. That does not alter its historical choice or invalidate its original optimum. Retain its exact action/outcome sequence and compute its actual w under the declared physical model, never replace it with a support-favorable tie.

At maximum detection d*, report nondominated support levels and the threshold price

    L(t) = min{l : (d*,w,l) attainable and w >= t}.

This minimum is recoverable from F: dominance preserves d* (no greater detection is feasible), weakly increases w, and weakly lowers cost. Thus removing dominated triples cannot remove a better threshold solution. Some attainable exact-w levels may disappear when higher support costs no more; do not mislabel a threshold curve as a census of every exact support level. Thresholds above the attainable maximum have no feasible value.

Also calculate the largest w at d* subject to `l <= l_E`, where l_E is the historical E path's summed cost, then minimize l among ties. The old E triple guarantees feasibility. Since E already minimizes cost at d*, projection equality implies every feasible point satisfying this constraint has `l = l_E`. Any gain here is therefore a support-favorable tie at the old minimum aggregate cost. Positive-cost support alternatives are separate points elsewhere on the frontier. Neither such tie gains nor a strict cost tradeoff are presumed before evaluation. All comparisons use the same root census and hard allowance; aggregate cost is not the budget of any single path.

## Sequential baseline with one original allowance

`E_then_support` first executes E's exact saved canonical policy, following selected points and saved child `(state_id,d,l)` backpointers without an optimizer rerun or tie replacement. Its consumed E-phase cost is subtracted from the original extra allowance. A conflict stops the whole run immediately. On a nonconflicting E stop, terminate if P0 is not definite, already supported, or has no supporting full-signature continuation. The latter condition is

    no s in T(H) has nonempty C2(s) entirely agreeing with P0.

This uses all physical members of each cell. If no such cell exists, no continuation can establish the same proposal: any partial continuation is a nonempty union of those cells. If a supporting cell exists, acquiring its complete signature would suffice in principle, but it may exceed the remaining allowance. This is an existential logical stopping criterion, not a budget-feasibility calculation, query ranking rule, or archive-irreducibility declaration. Irreducibility separately requires every compatible complete cell to be mixed; definite opposite cells also make support for P0 unavailable.

When support remains attainable, query the cheapest affordable unqueried action, with opaque-ID ties. After each charged result test nominal conflict first, then support, then support attainability; stop also if no action is affordable. Do not add claim-directed scores, lookahead, or a second allowance. Record `detection_phase_*` for the saved E prefix and `support_phase_*` for this suffix, with prices, queries, bytes, and totals. J uses `joint_phase_*`, without an artificial phase allocation. J and this baseline have the same hypothetical physical semantics and budget information. Both execute through the charged interface with no actual k or unqueried realized answer in selection.

The sequential policy preserves every E alarm path, so its detected set contains E's. It remains feasible under the same original allowance and model, so it cannot exceed E's maximum detection count. Hence `d_seq = d_E`; no added sequential alarm is possible on this supplied envelope, although the conflict guard remains mandatory. This is a validation consequence, not a measured discovery. At that maximum detection, J's support is at least the sequential reward by exactness. J may cost more to obtain more support; the complete frontier and sequential cost comparison must expose that price rather than reinterpret increased reward as universally preferable.

## Full-budget ceiling and interpretation

Define Wmax by counting original signatures whose full physical M2 cell agrees with their fixed definite P0. Any original signature rewarded at a partial stopping leaf must also have a supporting full cell, so every policy has w≤Wmax. At full residual budget, exhaustive retrieval until the first conflict is feasible. Each new signature eventually alarms. No original signature alarms because a nominal witness survives every truthful answer, so original paths can reach full cells and attain Wmax. Maximum detection and this support ceiling are therefore jointly achievable. Canonical J must attain both when the exact solve completes.

The ceiling is computed under **M2**, even when the final path is evaluated under actual k=0 or k=1. Do not impose the k=1 exhaustive support total on a conservative M2-planned policy or call a difference an implementation error. Model-relative support is distinct from factual accuracy. An alarm cannot prove target falsity or a unique omission cause; withdrawal alone never restores warrant. Originally irreducible proposals earn no definite-support reward, while final pending/irreducible statuses and new-signature claim outcomes remain separately recorded.

Opposite-claim physical worlds sharing every query answer remain indistinguishable under any allowed adaptive path. The joint objective cannot remove the complete-archive unsupported floor. Its new numerical outcomes concern attainable support at finite budgets and the costs of obtaining it. Exact objective ordering, sound certificates, projection equality, and full-budget endpoints are mathematical validation properties.

## Bounded computation and independent checks

Compute only the sorted distinct integer allowances induced by the four requested percentage anchors, retaining duplicate anchor labels as views. Memoization and cap counters span all those root solves; child residual budgets are necessary internal states, not an extra evaluation sweep. Pins include physical semantics and P0 as well as the old observable model/history. Count each admitted unique state and each evaluated Cartesian child-frontier tuple; STOP is not a child combination. Limits are 100,000 states and 10,000,000 combinations per root. A cap withholds every joint exact anchor claim for that root, preserving completed/pending evidence and unchanged comparison paths.

Tiny qualification fixtures enumerate complete deterministic trees independently, without invoking this recurrence or its Pareto routine. Full-input checks reconstruct physical support from complete cells, paid paths, reward/cost sums, child combinations, nondominance, projection equality, threshold minima, and preserved E choices. Certificate references are bound to their model and acquired history. Shared physical validators, canonicalization, and historical certificate semantics remain explicit dependencies; no independent validation of real-world assumptions or reproof of the old acquisition optimizer is claimed.

Separate whole-root planning and reconstruction CPU/wall time, checking, certificate work, and practical resource use from charged retrieval units. Actual-k views reuse executed histories and add no paid session. Exact sums, per-problem averages, and unchanged structural weights remain descriptive census quantities without sampling intervals or deployment probability claims.

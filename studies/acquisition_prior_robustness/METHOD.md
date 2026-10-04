# Prior-sensitive acquisition with fixed evidentiary support

This method applies the existing finite archive model and acquisition policies to a fixed, review-informed sensitivity design. It changes probability weights and aggregation weights; it does not change what evidence can establish. The [analysis protocol](ANALYSIS.md) fixes the inputs, reporting, validation, and execution order.

## Evidence, signatures, and certain answers

Let W be the original finite set of possible worlds. Initial evidence, authentic-record and completeness assumptions, a Boolean claim, and the permitted query catalogue are supplied. Each query a has positive cost c(a) and a deterministic typed outcome in each world. An authentic retained receipt implies its event. An empty lookup is compatible with both nonoccurrence and nonretention unless applicable complete-logging evidence excludes the latter. Receipt exposure does not itself identify source use.

Write sigma(w) for the complete ordered query-answer signature of w. A signature cell contains all worlds with that same full observable archive. Its terminal class tau(w) is `established` when every member satisfies the claim, `ruled_out` when none does, and `archive_irreducible` when both claim values occur. A partial acquired history H defines S(H), the nonempty worlds compatible with initial evidence and all acquired answers. A definite answer needs agreement of claim values over S(H). Early archive irreducibility requires every remaining possible full-signature cell to contain opposite claim values. A mixed S(H) alone is insufficient. Inconsistent histories are errors, not vacuous certainty.

The original independent checker verifies certificates against the supplied model, claim, initial evidence, acquired history, and exhaustive compatible constructions. It does not accept an asserted planner verdict as proof. Full-archive ambiguity is only relative to the fixed model and permitted catalogue: a new evidence channel or omitted mechanism can invalidate that boundary.

For any two strictly positive priors p and q on exactly W, compatibility with H is unchanged: no world becomes impossible because its probability becomes small. Signature cells, claim values, and their full-archive classes are unchanged. The certain-answer and irreducibility tests therefore have the same result for a fixed H. A planner can nevertheless choose a different next query because expected costs change. Model and certificate hashes include the declared prior, so this invariance concerns logical status, not necessarily identical certificate bytes or identifiers. Matched-prior certificates are checked against their corresponding model; frozen-path references retain their original certificates.

## The five exact distributions

Let p0 be the original positive normalized assignment prior; Sigma the distinct full signatures; and T the terminal classes present in the problem. For a signature s, W_s = {w : sigma(w) = s}; for a class t, W_t = {w : tau(w) = t}. Define:

| Label | World probability |
| --- | --- |
| `q0` | p0(w) |
| `qS` | 1 / (|Sigma| · |W_sigma(w)|) |
| `qT` | 1 / (|T| · |W_tau(w)|) |
| `qMinus` | p0(w) · 2^(-b(w)) / sum_v p0(v) · 2^(-b(v)) |
| `qPlus` | p0(w) · 2^(b(w)) / sum_v p0(v) · 2^(b(v)) |

b(w) counts catalogue actions whose typed observable outcome contains an actual retained evidence record. Existing request, delivery, and context receipts, completeness declarations, and archive records count. A `lookup_empty` wrapper counts zero regardless of its serialized size. Count each nonempty action once, including duplicate actions that retrieve the same record; do not count a multi-record return more than once. The current archive schema returns at most one such record per action. Unknown or malformed payload kinds are errors, not inferred record presence. Initial records only affect b(w) if a catalogue action returns them.

All construction, normalization, signature aggregation, cost expectations, and cost comparisons use exact rational arithmetic. Preserve the original floating-point Shannon entropy implementation and its existing tie behavior. For deployment q, q(s) = sum_{w in W_s} q(w). A single saved trajectory represents this entire mass, not one representative world's probability. Keep equal distributions under separate design labels and record their equality.

These distributions depend on the declared hypothetical model, not on which world is realized. Signature and class balancing are synthetic workload choices, not empirical priors or access to a realized signature/class. Strict positivity ensures the same evidentiary support for every condition.

## Frozen policies and matched-prior policies

For a policy pi, let C_pi(s), N_pi(s), and B_pi(s) be its full-budget retrieval cost, query count, and canonical returned bytes on signature s. For example,

    J_q(pi) = sum_s q(s) C_pi(s).

Expected count and bytes use the analogous sums. Terminal masses sum q(s) over each observed terminal class. The primary `frozen_p0` analysis uses the existing saved paths of pi_p0 under every q; the new prior is only an evaluator weight. It therefore tests workload sensitivity of a fixed policy, without giving its planner the deployment prior.

The secondary `matched_q` analysis supplies q to the original entropy, pair-cut, and exact algorithms. Prior-independent read-all and schema-aware retain their original paths. All policies see the same hypothetical worlds and initial observations and can acquire the same outcomes at the same prices. No planner receives the evaluator's realized world/signature or an unpaid realized answer.

Read-all follows catalogue order and exhausts it. Schema-aware uses the original scope/relevance order, favoring context and completeness, then upstream receipts, then other entries; visible cost and opaque ID resolve ties. World entropy maximizes its original expected Shannon information gain per cost. For pair-cut and the currently supplied prior r, retain the original definition:

    E_r(S) = sum_{unordered u,v in S with tau(u) != tau(v)} r(u) r(v)
    gain_r(a,S) = E_r(S) - sum_o P_r(o | S) E_r(S_o).

Select maximal gain divided by c(a), with the unchanged cost and ID tie rules. Pair weights inside E_r are not renormalized over S. This follow-up does not change the heuristic or claim an approximation guarantee for it.

For exact planning, with remaining queries R and compatible worlds S, the existing recurrence is

    V_r(S,R) = 0                                      if S is terminal
    V_r(S,R) = min_{a in R} [c(a) + sum_o P_r(o | S) V_r(S_o,R\{a})] otherwise.

Constant-answer queries can be omitted without changing optimal expected nonnegative retrieval cost. The fixed cap limits memoized states to 100,000 per problem/prior solve. A cap or error makes that computation unavailable; it is not a lower-cost solution. The independent tiny-tree check explicitly enumerates allowed decision trees on small fixtures and compares their minimum with this recurrence, including nonuniform weights, complementarity, correlated/constant queries, and irreducibility. This check is distinct from rerunning the same dynamic program.

The matched-prior optimum V_q is exact for the supplied finite objective, not an optimum for real investigators, deployment latency, or resolution at a budget cutoff. An original-prior optimum can lose to another policy after workload reweighting; a matched-prior optimum cannot have larger expected retrieval cost than a feasible policy under the same q and stopping objective.

## A finite prior-mismatch bound

Let pi0* be an exact p0-optimal policy, piq* a q-optimal policy, and V_q = J_q(piq*). Every signature has positive mass under both priors. Define

    alpha = min_s q(s) / p0(s) > 0
    beta  = max_s q(s) / p0(s).

For any fixed feasible policy pi, costs are nonnegative, so termwise comparison gives

    alpha J_p0(pi) <= J_q(pi) <= beta J_p0(pi).

The feasible policy class is unchanged because support, observations, prices, and terminal rules are unchanged. Optimality and the preceding inequality then yield

    V_q <= J_q(pi0*)
        <= beta J_p0(pi0*)
        <= beta J_p0(piq*)
        <= (beta / alpha) J_q(piq*)
         = (beta / alpha) V_q.

Thus V_q <= J_q(pi0*) <= (beta/alpha) V_q. When V_q = 0, the same nonnegative inequalities imply J_q(pi0*) = 0; report that identity without a ratio. Verify each assumption and inequality exactly for available finite solves. Retain unavailable denominators when a solve is capped or fails.

This is an elementary comparison of expectations and minima, not a new theorem. The factor can be loose. It gives no approximation guarantee for pair-cut and no protection against false records, invalid completeness, missing worlds, or a changed query interface. The observed deployment penalty J_q(pi0*) - V_q is a model-specific cost of keeping the original planning prior; it is not a causal estimate of real-world prior error.

## Structural aggregation and fingerprint scope

For problem-level metric x_i and original groups G, equal-problem aggregation is (1/40) sum_i x_i. Structure-balanced aggregation is

    (1/|G|) sum_{g in G} [(1/|g|) sum_{i in g} x_i].

Within a stratum, replace the problem set and groups with that stratum's members. A pair of repeated configurations has the same total structure weight as a singleton. For failed cells, report expected and available denominators explicitly rather than allowing missing members or groups to disappear silently. Derived ratios use only defined positive-optimum cases and retain their own denominators.

The original generator's fingerprint construction is reproduced from saved inputs, without generation. Sort queries by `(record_id, cost)` and align each world's answer columns to that order. Canonicalize the claim, `structure`, initial evidence, normalized queries with their IDs removed, and each world's assignment, Boolean claim, and aligned answers. For the unweighted fingerprint remove each query's cost before hashing the canonical structure. Query payloads, kind, scope, and record ID remain. The answer table retains declared dependencies. Opaque query IDs, original catalogue order, seed/problem identifiers, and prices do not define a group.

For these 40 inputs, a separate check compares every other problem field within repeated groups, excluding only problem/seed/split identifiers, query arrays, and the fingerprint fields; those other values agree. In particular, sources, event/record catalogues, assumptions, worlds, original priors, acquisition time, initial evidence, and claims agree. Normalized query equality checks the query arrays apart from ID, cost, and order. This supports grouping the present archive models without claiming a general semantic-equivalence or graph-isomorphism test. IDs and order still influence actual policies, so member trajectories remain separate and are averaged, not deduplicated. The 30 groups have 20 singletons and 10 pairs; per-stratum group counts are 6/8/8/8 in protocol order.

## Interpretation of time and retrieval measurements

The separate runtime check constructs a complete reachable policy tree from the same initial state under p0, using fresh policy caches for each policy/problem/repetition. It measures one common construction procedure, not one selected signature and not the number of visits in a real investigation. Shared validation/signature preprocessing, planner decisions, certificate construction/checking, traversal overhead, and serialization are reported separately in CPU and wall seconds. Tree size and certificate counts can differ legitimately across policies; exact state counts and entropy/pair-cut decision counts make that workload visible.

All three repetitions remain recorded. These local measurements cannot establish deployment latency, scaling beyond the original finite sizes, or monetary savings. Retrieval cost and local computation may favor different policies and are reported separately. No conclusion extends beyond the supplied closed-world archive, workload distributions, costs, and authenticity/completeness assumptions.

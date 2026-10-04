# Acquisition comparison and EC2 correspondence

This is a retrospective correction to the comparative interpretation of the
completed finite acquisition studies. The historical policies, cases, costs,
certificates and results are unchanged. The [frozen definitions](acquisition_protocol.json)
and [execution freeze](acquisition_freeze.json) precede the new comparator outcomes.

## What the pair-cut policy implements

Golovin, Krause and Ray, *Near-Optimal Bayesian Active Learning with Noisy
Observations*, NeurIPS 2010, arXiv:1010.3091, Section 3, supplies the EC2
equivalence-class edge-cut objective. Here each hypothesis is one supplied
nominal world; its class `tau` is the complete-archive terminal answer:
established, ruled out, or archive irreducible. It is not merely the world's
Boolean claim value.

An edge joins hypotheses in different classes and has weight `p(u) p(v)`.
Let `E(S)` be the total weight of these edges with both endpoints still in
the compatible set `S`. For query outcomes partitioning `S` into `S_o`, the
expected additional cut is

`E(S) - sum_o P(o | S) E(S_o)`.

The historical [`Planner.edge_mass` and `Planner.pair_gain`](../../src/tracebench/evidence_acquisition/policies.py)
compute exactly these expressions with original, unnormalized prior masses
in `E` and normalized conditional outcome probabilities. Action selection
divides by cost, then breaks ties by cost and query ID. Thus this is an
**application of EC2**, not a new acquisition algorithm. No approximation
guarantee from that paper is asserted here; its assumptions and this finite
implementation's contract have not been established as interchangeable.

The new diagnostic separately sums explicit cross-class hypothesis pairs at
visited states. All **12,876 state/query arithmetic comparisons** agree with
the historical implementation. This verifies the objective correspondence,
sharing the supplied `tau` semantics. It is not an independent physical
semantics or external validation of the archive model.

## Competent comparators and results

Schema-skip retains the historical relevance/cost/ID order but skips any
query constant across the currently compatible nominal worlds. Inferred
answers never enter paid history and incur no cost or returned bytes. This
optimization does not apply to model-mismatch auditing, where nominally
constant queries can expose conflict.

Terminal-class information gain targets entropy of the same three-way
`tau`, divided by cost. Its fixed numerical tolerance is `1e-12`; cost then
ID breaks tied scores. When every single-query gain is zero, it continues
through the cheapest nonconstant query rather than claiming resolution.
This retains complementary-query cases. These definitions were fixed before
evaluation; the supplied reviewer targets were checked, not forced.

All 40 problems, 30 supplied structure groups, price variants and queries
remain. The historical prior module defines **five total distributions**:
`q0`, `qS`, `qT`, `qMinus`, `qPlus`; `q0` is the original prior. Coincident
distributions retain their names without becoming independent replications.
Frozen-policy rows reweight unchanged `q0` paths; matched rows plan the new
information-gain rule under the named distribution. Historical references,
including the matched-prior exact optimum, are validated saved paths and
costs. No historical exact optimization was rerun.

Mean retrieval costs under `q0`:

| Policy | Equal problem | Structure balanced |
|---|---:|---:|
| Historical EC2 / pair-cut | 3.793750 | 3.837500 |
| Schema order with implied-query skipping | 3.721875 | 3.713542 |
| Terminal-class information gain / cost | 3.50703125 | 3.533333 |
| Matched-prior exact optimum | 3.369140625 | 3.401823 |

EC2 versus schema-skip has **13 wins, 14 ties, 13 losses** over the 40
individual problems; versus terminal-class information gain it has **5 wins,
17 ties, 18 losses**. All supplied `q0` targets match exactly. Under both
weightings, terminal-class information gain has lower pooled expected cost
in every declared prior/planning-mode cell. Schema-skip has lower pooled
cost except under `qMinus` in both modes and `qPlus` with matched planning.

These pooled outcomes are not uniform dominance. For equal-problem `qMinus`
with frozen policies, EC2 is cheaper than terminal-class information gain in
the archive-ambiguity, negative-completeness and positive-receipt strata;
with matched planning it is cheaper in the positive-receipt stratum.
Matched replanning can also worsen a heuristic: terminal-class information
gain's structure-balanced `qT` cost rises from 3.82060809 to 3.82958927.
Five initial-terminal problems have zero optimum, remain in means, and are
explicitly excluded from ratios rather than divided by zero. Read-all still
pays for those archives.

The [machine-readable summary](results/acquisition_results/acquisition_summary.json)
retains exact rational costs, differences, per-problem and per-stratum
wins/ties/losses, both weights, optimum gaps and zero-cost identities. The
[rows](results/acquisition_results/acquisition_rows.json) preserve all 2,000
validated historical prior rows and 800 new rows; the
[new histories and certificates](results/acquisition_results/acquisition_details.json.gz)
retain the full signature accounting. The
[validation](results/acquisition_results/acquisition_validation.json) and
[manifest](results/acquisition_results/acquisition_manifest.json) record the
18 unchanged computational freeze dependencies.

These are exact finite-model expectations and instance optimizations under
a fully supplied hypothesis space, not samples of independent incidents or
a measured swarm-investigation benefit. No actual world, realized hidden
assignment or unpaid answer is passed to a planner. The result qualifies the
earlier heuristic comparison; it does not invalidate the separate exact and
joint optimization analyses. No model calls, network requests or additional
spend were made.

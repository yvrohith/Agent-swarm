# Contracts and inference under bounded context-receipt loss

This method distinguishes a valid calculation inside a nominal model from a conclusion that survives a specified change to that model. The expanded contract is a declared sensitivity model, not reality or a comprehensive failure model. [ANALYSIS.md](ANALYSIS.md) fixes the census and original-policy comparisons before their outcomes.

## Four levels and two contracts

For nominal world w, distinguish:

1. **Physical event history:** event occurrences and timestamps, source availability, write-time context, selected sources, and output mechanism. The claim C(w) is determined here.
2. **Nominal archive snapshot:** records represented as retained in the original world, together with its original completeness-scope metadata. The dataset does not enumerate all possible historical record-generation mechanisms, so this level is not a claim to know every record ever generated.
3. **Current retrievable archive:** the nominal retained records after an allowed omission set has been applied.
4. **Acquired evidence:** initial records plus paid query results actually returned to a policy. Unqueried retained records are not acquired evidence.

Under the **nominal contract**, the unchanged original model validates at most 64 worlds, truthful positive receipts, event-parent/chronology consistency, write-time context availability, source use requiring exposure, and reliable completeness implications. In particular, an occurring context event covered by a world's complete scope must have an appropriate retained receipt. A retained completeness declaration must be justified by that world's completeness metadata. Initial evidence is present in every compatible world. The original independent certificate checker reconstructs this contract rather than trusting a planner's label.

Under expanded contract **`bounded-context-receipt-loss-v1`**, physical events and initial evidence remain fixed within each parent construction, but eligible context receipts may become unavailable for retrieval. Surviving receipts still truthfully identify their events. Completeness records retain their original bytes and authentic origin as assertions; the contract does not assume those assertions guarantee completeness of the post-omission archive. An authentic assertion and a currently true assertion are different properties. Original complete-scope metadata is retained as a statement about the nominal snapshot and parent, not silently reused as current-archive fact.

An explicit expanded adapter validates this changed contract. It never sends an expanded loss realization through the original 64-world reliable-completeness model while suppressing an error. The original nominal validator remains authoritative for its own inputs. Loss-only transformations and independent checks preserve event chains, receipt truth, source-use/exposure relations, claim values, and all non-context records. No forged positive evidence or new event mechanism is introduced.

## Exact loss closure and physical embedding

Let R(w) be the nominal retained record IDs, I the initial record IDs, and Q the original catalogue. Define eligible physical IDs

    E(w) = {r in R(w) : r is a context receipt, some query retrieves r, and r not in I}.

For each k in {0,1,2}, construct every pair (w,D) with D a subset of E(w) and |D| <= k. Its current record set is R(w) minus D. All aliases of r use the same membership fact; they are not separately removable copies. Each query returns its original `present` payload exactly when its physical ID remains, otherwise its original `lookup_empty` payload. The latter has bytes but asserts only an empty lookup, not event absence. Initial records, other receipt types, completeness declarations, and catalogue costs are never removed or altered.

Deduplication identifies equal **current physical realizations**, using event-occurrence IDs, current retained IDs, recipient writes, selected source IDs, and source mechanism. Shared immutable sources, event/record catalogues, timestamps, and query definitions are pinned by the original problem. Nominal assignment variables, opaque parent IDs, and nominal completeness-scope metadata remain generating provenance instead of forcing duplicate current realizations. Retain all parent IDs, original retained sets and complete scopes, and exact omission sets for every deduplicated realization. No deduplicated cardinality or number of generating parents becomes a probability.

For each nominal w, the pair (w,empty set) supplies an embedding into every expanded condition. Its current records, events, claim, and query answers equal the nominal ones. Several nominal generative assignments may embed into one physical realization; an injective mapping of bookkeeping IDs is not required. Every k construction is also a k+1 construction, so physical support and attainable signatures are nested. These statements are checked mechanically, not inferred from aggregate counts.

For each omitted record, record affected queries and nominal guarantee scopes. An original completeness implication is violated only if a covered occurring context event has no remaining receipt satisfying that implication. Distinguish this from merely removing one of several receipts for the same event. Also record applicable retained or initial completeness assertion IDs. If no such assertion applies, the omission can expose a missing possibility in the nominal finite support without establishing that an observed declaration is false. Nominal guarantees and visible declarations therefore have separate provenance fields. Wrong-source, wrong-recipient, or noncovering-window scopes cannot justify a target negative conclusion.

The closure can add only losses of already represented queried context receipts. It cannot invent a missing event history absent from all nominal parents, erase supplied evidence, remove arbitrary record types, or test another query interface. Conditions with no eligible IDs or no additional distinct realizations remain valid controls. With the original size limits, k=2 has at most 2,368 raw parent/subset constructions; safety checks nevertheless enforce the declared 4,096-world and 256-signature bounds and fail rather than truncate.

## Compatibility, claim status, and operational status

For contract M and history H, S_M(H) contains every allowed realization agreeing with initial evidence and the acquired query answers. It is not conditioned on a chosen evaluator world, omitted-ID set, or selected-source label. Compute claim status from the entire set:

| Condition | Claim status |
| --- | --- |
| S_M(H) is empty | `model_conflict` |
| Every member satisfies C | `established` |
| Every member falsifies C | `ruled_out` |
| Both claim values occur | `unresolved` |

Empty support is never treated as vacuous truth. The nominal checker historically names its empty-support state `inconsistent`; the new comparison records the corresponding contract-level conflict explicitly while leaving historical certificate bytes unchanged.

Let sigma_M(w) be the ordered tuple of every permitted query answer. A complete signature cell is established, ruled out, or mixed according to its members' claim values. At a partial history, unresolved support is **archive irreducible** only when every still-possible complete-signature cell contains both claim values. Otherwise it is **unresolved pending**, because at least one possible continuation supplies a definite answer. Return both claim status and operational archive status. A single opposite witness refutes certainty but does not prove that every continuation is ambiguous.

For a history with nonempty nominal support, each nominal witness embeds into expanded support with the same observations and truth. Thus a nominal definite claim can persist or weaken to unresolved, but cannot become the opposite definite claim under genuine expansion. A nominally mixed complete cell stays mixed. Do not extend this into blanket monotonicity of partial-history operational labels: a nominally archive-irreducible history can acquire a newly reachable definite signature, becoming unresolved pending. Retain that operational change separately from a lost definite claim. These are properties of support inclusion, not discoveries about real agents.

## Certificates, silent loss of support, and detectable conflict

Nominal certificates keep their original model/assumption/history pins and pass or fail the unchanged checker. Expanded certificates explicitly identify the new contract, omission budget, original problem pin, expanded support pin, and acquired history. Checking reconstructs compatibility and the required witness coverage. It cannot accept a historical certificate under another contract merely by changing a hash. A valid nominal certificate and an expanded counterexample can coexist: this is assumption sensitivity, not automatically a nominal checker defect or an erroneous historical score.

For an expanded complete signature s, there are two observational cases:

- **s is also nominally possible.** Every catalogue answer can occur under a nominal realization. If nominal certainty is lost, retain a nominal witness and an expanded opposite-claim witness with the identical complete signature. No test using only these observations can soundly flag misspecification on that signature while accepting every nominal realization with those same observations.
- **s is newly reachable.** Its complete acquired history has empty nominal compatibility. Exhaustive catalogue retrieval can expose a nominal-model conflict. An incompatible-history certificate must verify that every nominal world disagrees with at least one observed answer. This identifies inconsistency with the finite contract, not which actual mechanism caused it.

A full signature can be nominally possible while an earlier nominal stopping history has lost support under expansion. Conversely, a new signature can be fully detectable but never reveal its contradiction during nominal acquisition because the policy stops before querying a distinguishing action. Full-archive classifications and stopping-history classifications therefore remain separate.

Counterexamples to an acquired-history verdict need match all acquired answers. A silent full-archive counterexample must match **every** catalogue action, including aliases and unqueried actions. This distinction prevents an early-stopping mismatch from being described as intrinsically unobservable. Witness generation may inspect parent truth to exhibit two compatible constructions, but it never uses actual-world truth as the primary measure of warranted conclusions or sends it to the policy.

## The unchanged nominal policy under expanded answers

The secondary experiment instantiates only the original-prior exact adaptive policy. The planner sees the original model, prior, catalogue, initial records, and its paid history. A separate passive archive holds the selected expanded signature and returns the same public typed payloads at the original costs. This interface boundary prevents accidental evaluator-to-planner information flow; it is not claimed to be a security sandbox.

After each charged lookup, the driver checks nominal compatibility before requesting another action or honoring a terminal conclusion. Empty support stops as a detected conflict. Otherwise it uses the original nominal terminal rule and exact-policy action, including constant-query elimination and cost/opaque-ID tie rules. A query skipped because it is constant in the nominal model reveals no actual answer. Original decision caches may be shared only as functions of nominal hypothetical support and acquired history, never as repositories of realized unqueried answers.

There is a mechanical detection limit here. Initial nominal support is nonempty, and the original exact recurrence selects only nonconstant queries. With exactly two permitted outcomes, nonconstancy means both outcome subsets of the current nominal support are nonempty. The expanded passive archive returns one of those same two outcomes, so whichever answer arrives leaves nonempty nominal support. Induction applies at every subsequent choice. The conflict guard remains correct, but cannot trigger on a valid realization in this fixed interface. Exhaustive retrieval can still reveal contradictions in unqueried outcomes that were constant under the nominal model. This result does not extend to arbitrary policies, outcome alphabets, or query interfaces, and any observed zero detection under this design is a consequence of the implemented selection rule rather than an empirical discovery.

The existing 100,000-state exact-solve cap remains a resource guard; a cap produces an unavailable policy cell, not an invented action or replacement case. No policy is optimized for expanded support, no new prior is estimated, and no cost-to-resolution or timing competition is added. At stopping, the evaluator checks the same paid history under the expanded contract without charging another lookup. This is a retrospective diagnostic using the declared expanded hypothesis set, not free evidence supplied to the nominal policy.

Report whether a conflict was detected during acquisition or only available in the exhaustive catalogue; whether a nominal definite stopping verdict remains supported; and whether nominal irreducibility is overstrong under expanded continuation support. Query counts and costs are abstract charged quantities, not deployment time or dollars. Uniform arithmetic averages across distinct signatures summarize the census only and do not define a deployment prior. No conclusion is labeled incorrect merely because a richer support set makes it unresolved.

## Aggregation, checking independence, and limits

For each k, original-signature preservation retains the fixed original denominator; newly reachable signatures and full-catalogue conflicts have their own denominators. A raw generated-world count, deduplicated physical count, and distinct-signature count answer different questions. Summaries preserve those distinctions before applying the equal-problem and existing structure-balanced rules. Empty or unavailable denominators are explicit, and all original problems and group memberships remain present.

The reference path independently enumerates eligible physical omission subsets, reconstructs query outcomes from record membership, derives claim truth from events/write timing/selected sources, and filters histories directly. It checks saved transitions and witnesses without calling the expanded closure or cached status functions being tested. Shared canonicalization, scope helpers where used, and the unchanged nominal physical validator are stated dependencies. Checks of original planner actions and nominal certificates reuse their implementations; they are not an independent reproof of the exact optimizer. No provider, human, or field validation is claimed.

The study measures stability only within the specified loss closure of the original event mechanisms. It leaves forged receipts, lost initial evidence, other missing record types, arbitrary false declarations, omitted causal histories, and unmodeled interfaces outside scope. New conflicts diagnose incompatibility, not a unique cause. No-change conditions establish finite stability only at k <= 2, and irreducibility is relative to the catalogue. The completed studies and their limitations remain preserved.

# Bounded archive-model misspecification: results

Admitting one additional context-receipt omission removes support for **71 of 271 originally definite full-signature conclusions**; admitting up to two removes support for **86 of 271**. All affected conclusions originally ruled the claim out. The 158 originally established conclusions and 121 originally ambiguous signatures remain unchanged under both expansions. These are losses of warrant under a specified larger model, not findings that 71 or 86 realized claims were false.

Both expansions admit **39 new complete signatures** inconsistent with the nominal model. The nominal exact policy detects **0 of 39** because it stops without acquiring a contradiction. That zero is a pre-recorded consequence of selecting only nonconstant binary queries, not a discovery of unexpected policy behavior. On the fixed 392 original signatures, **96 stopping conclusions** lose support at either omission budget, more than the 71 or 86 losses after exhaustive retrieval. The distinction between evidence acquired at stopping and evidence available in the full archive is consequential here.

## Fixed contracts and completed scope

This is the review-informed, post-baseline study specified in [ANALYSIS.md](ANALYSIS.md), [METHOD.md](METHOD.md), and [config.json](config.json). It reused the same 40 acquisition problems, four separate development problems, four strata, and 30 existing structural groups. The [23-dependency freeze](freeze.json) preceded evaluation. The initial checkout was clean at `920f67c5b512c4dc2b571bd74b5684a06ba85b01`; no older checkout was substituted.

The nominal contract retains the original support and authoritative completeness semantics. Expanded contract `bounded-context-receipt-loss-v1` retains nominal event histories but permits omission of up to k = 0, 1, or 2 unique retained context-receipt IDs reachable through the existing catalogue, excluding initial evidence. All aliases of one physical record disappear together. Events, event times, write-time context, selected sources, output mechanisms, claim truth within each parent, non-context records, initial evidence, query costs, and payloads remain unchanged.

Surviving positive receipts remain truthful. A surviving completeness declaration remains an authentic record of an assertion; it is no longer assumed to guarantee completeness of the post-omission archive. Parent snapshot scopes and original records remain explicit provenance, not silently asserted current-archive facts. The unchanged original validator/checker continues to validate nominal inputs. Expanded realizations use a separate explicit adapter/checker; no historical check was weakened.

All **120 problem/condition cells** completed with no cap, failure, truncation, or unavailable phase. [Baseline verification](baseline_verification.json) checked 392 saved nominal exact-policy signature trajectories, 797 charged queries, 40 metric rows, 169 unique nominal certificates, existing freezes, structural fingerprints, and the current offline scoring-only reproduction path. k=0 reproduces the saved nominal observations, statuses, charged paths, costs, and certificates. Historical acquisition, prior-robustness, and investigator results remain unchanged.

## Physical support, provenance, and observational populations

The original 1,064 nominal worlds include multiple generative assignments with identical physical realizations. Physical deduplication therefore yields 586 realizations even at k=0, without dropping any original observation or claim witness. Each original parent retains a zero-omission embedding in every expanded condition. No generated-world multiplicity is interpreted as a prior.

The following are sums across the same 40 problems. The raw construction count includes zero-loss constructions. “Completeness violation” counts parent/omission constructions that violate a nominal retention guarantee; the retained-assertion column counts constructions also violating an applicable observed assertion. Support-only omissions have no applicable retained completeness assertion. These definitions are tracked separately and need not generally partition constructions; in these inputs the nonempty constructions split without overlap as shown.


| k | Nominal worlds | Raw constructions | Physical worlds | Nonempty omissions | Completeness violation | Retained-assertion violation | Support-only loss |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1064 | 1064 | 586 | 0 | 0 | 0 | 0 |
| 1 | 1064 | 1750 | 784 | 686 | 436 | 436 | 250 |
| 2 | 1064 | 1860 | 814 | 796 | 520 | 520 | 276 |


Within a parent construction, an omission violates a completeness implication only if no retained receipt for that covered occurring event remains. Merely dropping a redundant receipt does not count as violation. The saved provenance records exact omitted IDs, affected query aliases, original snapshot records/scopes, parent references, and applicable assertions. The largest single condition had 122 raw constructions, 36 physical worlds, and 20 signatures, below bounds of 2,368, 4,096, and 256 respectively. The nominal exact solver reached at most 111 states against its 100,000-state cap.

The original population contains 392 full signatures: 158 established, 113 ruled out, and 121 ambiguous. Its denominator remains fixed for every k. New signatures have their own population; they do not dilute the original preservation denominator.


| k | Original N | Established retained | Ruled-out retained | Definite → unresolved | Originally ambiguous retained | New N | New E/R/U | Expanded N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 392 | 158 | 113 | 0 | 121 | 0 | 0/0/0 | 392 |
| 1 | 392 | 158 | 42 | 71 | 121 | 39 | 19/5/15 | 431 |
| 2 | 392 | 158 | 27 | 86 | 121 | 39 | 19/0/20 | 431 |


E/R/U denotes established/ruled-out/unresolved under the expanded contract. Every new signature is a nominal conflict by definition: none has a compatible nominal world, while every one has expanded support. At k=0 the new population is empty, so within-new-population fractions are undefined, not zero-valued success rates.

Among the fixed 271 original definite signatures, 71 first lose support at k=1 and 15 at k=2; 185 have `not_observed_within_budget`. The latter is finite stability through k=2, not unlimited robustness. All original mixed cells remain mixed and no definite conclusion reverses to the opposite definite conclusion. Those monotonicity checks follow from retaining nominal witnesses under genuine support expansion.

## Where full-archive certainty changes

Each stratum retains ten problems. The baseline populations and changes below keep established and ruled-out conclusions separate. All losses are ruled-out → unresolved; all nominal established signatures are retained.


| Stratum | Original signatures | Established | Ruled out | Ambiguous |
| --- | --- | --- | --- | --- |
| Positive receipt | 66 | 46 | 0 | 20 |
| Negative/completeness | 113 | 77 | 20 | 16 |
| Complementary | 147 | 35 | 79 | 33 |
| Archive ambiguity | 66 | 0 | 14 | 52 |

| k | Stratum | Lost / nominal definite | Lost / nominal ruled-out | Established retained | Ruled-out retained | New N | New E/R/U |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Positive receipt | 0/46 | undefined (0/0) | 46 | 0 | 0 | 0/0/0 |
| 0 | Negative/completeness | 0/97 | 0/20 | 77 | 20 | 0 | 0/0/0 |
| 0 | Complementary | 0/114 | 0/79 | 35 | 79 | 0 | 0/0/0 |
| 0 | Archive ambiguity | 0/14 | 0/14 | 0 | 14 | 0 | 0/0/0 |
| 1 | Positive receipt | 0/46 | undefined (0/0) | 46 | 0 | 2 | 2/0/0 |
| 1 | Negative/completeness | 20/97 | 20/20 | 77 | 0 | 11 | 11/0/0 |
| 1 | Complementary | 46/114 | 46/79 | 35 | 33 | 11 | 6/5/0 |
| 1 | Archive ambiguity | 5/14 | 5/14 | 0 | 9 | 15 | 0/0/15 |
| 2 | Positive receipt | 0/46 | undefined (0/0) | 46 | 0 | 2 | 2/0/0 |
| 2 | Negative/completeness | 20/97 | 20/20 | 77 | 0 | 11 | 11/0/0 |
| 2 | Complementary | 61/114 | 61/79 | 35 | 18 | 11 | 6/0/5 |
| 2 | Archive ambiguity | 5/14 | 5/14 | 0 | 9 | 15 | 0/0/15 |


All 20 nominal negatives in the negative/completeness stratum lose support with one omission. The complementary stratum loses 46 of 79 negatives at k=1 and 61 at k=2. Archive ambiguity loses 5 of its 14 nominal negatives; all five losses are in its mixed-resolvability subtype. Positive-receipt problems lose no original definite conclusion under this mechanism, although two new signatures expose a nominal conflict elsewhere in their archives. Full-model conflict and support for a particular claim are different measurements.

k=2 adds 30 physical realizations beyond k=1 but **no additional complete signature in any problem**. Its extra latent possibilities weaken 15 more original negatives and five newly reachable k=1 negatives, all in the complementary stratum. Observational alphabet stability therefore does not imply stable warranted answers.

The next table reports means of within-problem fractions, as percentages. Each cell is **equal-problem / structure-balanced**. Structure balancing first averages problem variants within the original group, then groups equally. These differ from pooled fractions such as 71/271; they are not incident probabilities.


| k | Population | Lost / original signatures | Lost / original definite | Defined definite problems/groups | New / expanded signatures |
| --- | --- | --- | --- | --- | --- |
| 0 | All | 0.000% / 0.000% | 0.000% / 0.000% | 35/26 | 0.000% / 0.000% |
| 0 | Positive receipt | 0.000% / 0.000% | 0.000% / 0.000% | 10/6 | 0.000% / 0.000% |
| 0 | Negative/completeness | 0.000% / 0.000% | 0.000% / 0.000% | 10/8 | 0.000% / 0.000% |
| 0 | Complementary | 0.000% / 0.000% | 0.000% / 0.000% | 10/8 | 0.000% / 0.000% |
| 0 | Archive ambiguity | 0.000% / 0.000% | 0.000% / 0.000% | 5/4 | 0.000% / 0.000% |
| 1 | All | 15.529% / 17.743% | 24.387% / 27.358% | 35/26 | 9.056% / 9.907% |
| 1 | Positive receipt | 0.000% / 0.000% | 0.000% / 0.000% | 10/6 | 2.000% / 1.667% |
| 1 | Negative/completeness | 22.149% / 23.172% | 26.095% / 26.890% | 10/8 | 6.611% / 7.014% |
| 1 | Complementary | 33.023% / 36.071% | 40.926% / 43.273% | 10/8 | 6.611% / 7.014% |
| 1 | Archive ambiguity | 6.944% / 7.292% | 36.667% / 37.500% | 5/4 | 21.000% / 21.875% |
| 2 | All | 18.342% / 20.892% | 28.431% / 31.736% | 35/26 | 9.056% / 9.907% |
| 2 | Positive receipt | 0.000% / 0.000% | 0.000% / 0.000% | 10/6 | 2.000% / 1.667% |
| 2 | Negative/completeness | 22.149% / 23.172% | 26.095% / 26.890% | 10/8 | 6.611% / 7.014% |
| 2 | Complementary | 44.276% / 47.880% | 55.079% / 57.502% | 10/8 | 6.611% / 7.014% |
| 2 | Archive ambiguity | 6.944% / 7.292% | 36.667% / 37.500% | 5/4 | 21.000% / 21.875% |


All-original-signature and new/expanded means include 40 problems and 30 groups globally, or ten problems and 6/8/8/8 groups by stratum. The conditional definite-loss mean excludes five initially irreducible problems with no nominal definite signatures, leaving 35 problems and 26 groups; exclusions and undefined denominators are explicit. The analogous ruled-out-only global mean uses 25 problems and 20 groups. The positive-receipt stratum has no nominal ruled-out denominator. All exact rationals, eligible sets, and subtype/control summaries are in [summary.json](results/summary.json).

## What nominal acquisition observes

Only the original-prior exact policy was used. It receives its nominal model and paid answers, with no expanded support, omitted IDs, parent provenance, realized truth, or future answers. At stopping, the evaluator retrospectively checks the identical acquired history against expanded support. That diagnostic is not free extra evidence supplied to the policy.

The policy detects no conflicts through its selected queries. This was derived before execution: it selects only queries nonconstant over current nominal support; with two permitted answers, either returned answer leaves nonempty nominal support. Induction preserves that property until nominal termination. The immediate conflict guard remains implemented and inspected; empty-support semantics are tested, but valid runs of this fixed policy cannot exercise that stopping branch. The zero detection count is mechanical. Exhaustive retrieval can contradict unqueried nominally constant expectations.

The following classification is mutually exclusive. A fully detectable conflict takes precedence over whether the stopping verdict is also unsupported. “Justified” includes supported archive irreducibility, not just definite answers.


| k | Expanded signature N | Conflict detected | Full conflict missed | Nominal-compatible unsupported definite | Overstrong irreducibility class | Nominal conclusion justified |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 392 | 0 | 0 | 0 | 0 | 392 |
| 1 | 431 | 0 | 39 | 96 | 0 | 296 |
| 2 | 431 | 0 | 39 | 96 | 0 | 296 |


The unsupported-definite flag is also retained independently of that classification. At k=1 and k=2 it is true for **96/392 original signatures** and **13/39 new signatures**, or 109/431 expanded signatures in total. All 109 nominal stopping verdicts are `ruled_out`. The 13 new-signature cases already appear in the 39 missed-conflict category, so adding those flags to the mutually exclusive table would double-count them. No nominal archive-irreducibility declaration becomes overstrong in any evaluated condition.

The stratum stopping counts below are identical at k=1 and k=2; k=0 has zero unsupported verdicts and no new signatures in every stratum.


| Stratum (each of k=1,2) | Unsupported at original stopping | Missed / new full conflicts | Unsupported at new stopping | Unsupported / all signatures |
| --- | --- | --- | --- | --- |
| Positive receipt | 0/66 | 2/2 | 0/2 | 0/68 |
| Negative/completeness | 20/113 | 11/11 | 3/11 | 23/124 |
| Complementary | 68/147 | 11/11 | 8/11 | 76/158 |
| Archive ambiguity | 8/66 | 15/15 | 2/15 | 10/81 |


The difference between full-archive and stopping warrant is largest in the complementary stratum. Its 68 original stopping negatives lack expanded support at either budget, compared with 46 full-archive negatives at k=1 and 61 at k=2. Across all original signatures, exhaustive retrieval could restore support for 25 of the 96 stopping verdicts at k=1 and ten at k=2. The remaining 71 or 86 have an opposite-claim witness agreeing on every permitted answer, so further catalogue retrieval cannot identify which model-compatible construction occurred.

Equal-problem / structure-balanced stopping fractions are shown below for each of k=1 and k=2. All displayed original/all-population means have defined denominators for every problem in their stratum. Within-new-population means, stored separately, use only the 22 problems and 17 groups with a new signature, with the other 18 problems marked undefined for that conditional population.


| Population (each of k=1,2) | Unsupported / original signatures | Unsupported / expanded signatures | Missed full conflict / expanded signatures |
| --- | --- | --- | --- |
| All | 20.547% / 23.276% | 21.436% / 24.247% | 9.056% / 9.907% |
| Positive receipt | 0.000% / 0.000% | 0.000% / 0.000% | 2.000% / 1.667% |
| Negative/completeness | 22.149% / 23.172% | 23.167% / 24.583% | 6.611% / 7.014% |
| Complementary | 49.762% / 54.043% | 51.575% / 55.719% | 6.611% / 7.014% |
| Archive ambiguity | 10.278% / 10.069% | 11.000% / 10.625% | 21.000% / 21.875% |


No actual hidden-world label is scored as if it were observable ground truth. A negative conclusion can happen to be true in a nominal witness while an expanded positive witness makes it unwarranted. Likewise, a full nominal-model conflict need not invalidate the stopping claim: 26 of the 39 missed-conflict cases do not have an unsupported definite stopping verdict.

## Saved witnesses and contract-specific evidence

Every changed full-signature verdict retains a concrete nominal witness and expanded opposite witness agreeing on all catalogue actions. Every new signature retains an incompatible-history certificate under the nominal contract. Certificates pin their own contract, support, claim, initial evidence, and history; a nominal certificate was not converted to an expanded one by changing a hash. Exact references and parent omissions are in [details.json.gz](results/details.json.gz), keyed by problem, k, and `signature_id`.

For example, at `acq_94210`, k=1, signature `6c972dfffaae2b10aaa4a9f1b1b5b348acea12e46dcbaf8324ea500add5360b8` is nominally ruled out but expanded-unresolved. Nominal `hypothesis_02` and expanded `physical_d7258bdc01cce6bd4f185e86` disagree on the claim while matching every answer. The expanded realization omits `record_context_0`, changes both aliases consistently, retains `complete_0`, and leaves the occurring context event and write-time availability intact. The two contracts interpret the surviving assertion differently; this is not an old-checker error.

At `acq_94201`, k=1, new signature `5aadc435b0e34551cff6acbbb16082976f55605965f829e1fa5f51fa3147c3d5` conflicts with the full nominal catalogue. The nominal policy stops after one query at cost 2 with an established claim that remains established under expansion. Its failure to expose the full model mismatch is distinct from claim accuracy or support. These are retained tested cases, not substituted simplified fixtures.

## Unaffected cases, coincidence, and descriptive costs

All 40 problems have at least one eligible omission, so the no-eligible-omission control is empty. Nevertheless, some are already closed under the permitted additional loss. The control flags overlap and are not a partition:


| Control: problems / 40 | k=0 | k=1 | k=2 |
| --- | --- | --- | --- |
| No eligible omissions | 0 | 0 | 0 |
| No physical support change | 40 | 7 | 7 |
| No new full signatures | 40 | 18 | 18 |
| No original definite loss | 40 | 15 | 15 |
| Initially archive irreducible | 5 | 5 | 5 |


The seven problems with unchanged physical support are `acq_94200`, `94202`, `94203`, `94204`, `94206`, `94208`, and `94209` (all with the `acq_` prefix). The 18 no-new-signature problems still contain 36 lost original conclusions at k=1 and 46 at k=2, over their fixed 154 original signatures. No observable contradiction is possible for those added same-signature alternatives. The 15 problems without any original definite loss still add 12 new signatures, showing why that control does not imply an unchanged model.

The five initially irreducible source-use problems retain justified irreducibility and zero-query stopping. Their 26 original signatures are all ambiguous; they add ten new signatures, all nominal conflicts that are missed without lookup. The separate mixed-resolvability source-use subtype has 40 original signatures and 14 original negatives: five full-archive losses, eight unsupported original stopping verdicts, and five new signatures with two unsupported stopping verdicts at either budget. Source-use ambiguity remains distinct from exposure.

Relative to k=0, seven problems have identical physical support and 18 identical signature sets at either k=1 or k=2. Between k=1 and k=2, 25 have identical physical support and all 40 have identical signature sets. These coincidences were retained; no replacement cases or larger omission budgets were introduced.

Lookup means below are unweighted within-problem signature census averages, then averaged equally over problems or balanced over groups. They are not expectations under a newly assigned distribution. Original-signature trajectories remain unchanged; the small aggregate changes reflect the added signature population, not improved planning.


| k | Weight | All-signature queries | All-signature cost | Original-signature queries | Original-signature cost |
| --- | --- | --- | --- | --- | --- |
| 0 | Problems | 1.705076 | 3.153438 | 1.705076 | 3.153438 |
| 0 | Structures | 1.699176 | 3.204862 | 1.699176 | 3.204862 |
| 1 | Problems | 1.697063 | 3.123948 | 1.705076 | 3.153438 |
| 1 | Structures | 1.692751 | 3.177765 | 1.699176 | 3.204862 |
| 2 | Problems | 1.697063 | 3.123948 | 1.705076 | 3.153438 |
| 2 | Structures | 1.692751 | 3.177765 | 1.699176 | 3.204862 |


The original-prior expected cost remains 1725/512 = 3.369140625, reproduced in the baseline audit. The k=0 descriptive equal-problem cost 3.153437792 instead gives each distinct signature equal within-problem weight, so it is a different estimand, not an improvement over the historical result. Costs are abstract lookup units, not dollars, tokens, or deployment time. No expanded-model optimization or new timing sweep was performed.

## Validation, preservation, and limits

Before evaluation, **883 tests passed**, including **67 focused new tests**, and Ruff passed. All 12 development problem/condition cells completed and passed the reference checks before the 23-dependency freeze. The tests covered k=0 parity, embeddings and nesting, protected initial records, aliases, truthful positives and unchanged physical events, explicit completeness interpretation, wrong-scope negatives, contract-bound certificates, opaque-ID mappings, conflict handling, all-continuation irreducibility, and the policy's evidence boundary. These mechanical checks are not scientific discoveries.

The separate reference implementation reconstructs omissions and query answers from physical records, derives claims from events and source selection, and filters compatible worlds directly rather than calling the expanded implementation's cached status functions. Per-condition reference checks passed for all 120 cells. Across conditions they checked 4,674 provenance constructions, 3,192 nominal embeddings, 1,370 nested-support memberships, 1,254 signature rows and policy histories, and 2,519 policy-prefix occurrences. It checked 157 silent full-signature counterexample pairs (71 + 86), 78 nominal full-conflict occurrences (39 + 39), and 7,359 all-catalogue witness/action comparisons.

There were 1,761 nominal and 1,761 expanded certificate-check occurrences. The 3,522 entries summed across per-cell certificate tables contain 2,361 globally distinct certificate hashes. Counts recur across k conditions and histories; they are not independent cases or samples. The original nominal validator/checker and exact optimizer are reused rather than independently reimplemented, and shared canonicalization is an explicit independence limit. No human validation, provider authentication, or real-world mechanism confirmation is claimed.

Verification records are [per-condition reference checks](results/independent_verification.json), [offline verification](OFFLINE_VERIFICATION.json), [independent validation](INDEPENDENT_VALIDATION.json), and [final validation](FINAL_VALIDATION.json). [Preservation](preservation.json) and execution checks retain **266 historical tracked files** and **509 retained local files** byte-for-byte, including prior studies, frozen source, prompts, cases, responses, scores, manifests, and accounting. Historical response files were hashed without decoding provider-private reasoning. Zero model calls, network requests, credential access, dependency downloads, spend, commits, pushes, publication, deployment, or submission were performed.

The measured quantities locate assumption sensitivity in these selected finite problems: negative conclusions lose support, some archives expose a model contradiction only after additional retrieval, and some opposite-claim alternatives remain indistinguishable through the full catalogue. Those findings do not establish incident failure rates or that the expanded model is comprehensive or universally safer. The three k conditions and repeated structures are dependent analyses, with no sampling intervals or significance claims. The mechanism excludes forged positives, missing initial evidence, non-context record loss, arbitrary false assertions, omitted event mechanisms, and new evidence channels. A zero change through k=2 is bounded stability only. The legacy chronology defect remains documented and isolated, with its effect on historical estimates unmeasured.

## Offline commands and retained outputs

From the repository root in the existing environment, verify the frozen scientific dependencies, saved outputs, and exact summaries without starting another evaluation:

```bash
.venv/bin/python -m studies.archive_model_misspecification.analysis verify
```

The computational verification scope is distinct from whole-checkout preservation. To reproduce the fixed offline study into a fresh ignored directory without overwriting curated results:

```bash
.venv/bin/python -m studies.archive_model_misspecification.analysis run --output artifacts/archive-model-misspecification/replication
```

The command refuses an existing output directory. It performs finite offline analysis only; do not change the freeze to accommodate a mismatch. [per_condition.json](results/per_condition.json) retains all 120 condition records; [summary.json](results/summary.json) retains exact rational means, defined/undefined denominators, subtypes, controls, earliest losses, and coincidences; [details.json.gz](results/details.json.gz) retains physical provenance, signatures, paths, and contract-specific evidence; [manifest.json](results/manifest.json) pins the completed outputs. No presentation or submission artifact was added.

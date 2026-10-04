# Trace Completeness Curves

**Author: Rohith YV** · **Code:** <https://github.com/yvrohith/Agent-swarm> · [Verification guide](REVIEWER_GUIDE.md)

## What the project measures

Trace Completeness Curves is a research prototype for examining what recorded
agent-swarm activity supports about information flow. It connects a structural
simulation, an observation-only logging-loss experiment, a public-wiki reference
audit, and two bounded model-investigator evaluations. These studies distinguish
recorded exposure, realized source selection, response validity, and warranted
conclusions. They do not prove causal influence in a historical incident.

The supported findings are mixed. More complete synthetic telemetry can improve
source-edge precision while worsening the estimated source-using fraction.
Preserving exposure evidence under logging loss helps one heuristic's target
classification while harming another's. In the real wiki export, most eligible
snapshot reference pairs contain only inherited references under the fixed literal
rule; this is not verified source use. The utility pilot does not demonstrate a
general reasoning benefit from provenance assistance. The responsiveness evaluation
separates rejected serialization from one valid, incorrect conclusion in a controlled
invariant pair. Exploratory finite retrieval analyses examine a related cost question
under explicit supplied models; they do not measure practical investigator benefit.

This is the active synthesis. [Historical submissions and analysis records](SUBMISSION.md)
remain unchanged; the [comparative review](../studies/comparative_validity/REVIEW.md)
records retrospective corrections and their scope.

## Synthetic evidence availability and attribution

The [synthetic benchmark](../results/REPORT.md) targets direct realized source
selection: the simulator selected a particular earlier output from another run.
This is neither counterfactual necessity nor intent. Temporal proximity proposes
nearby same-page predecessors; witness reuse proposes predecessors sharing an exact
token. Five observations of each fixed world reveal writes, stable identities,
requests, delivery, then context entry. Exposure can remain unused, and shared
scaffolds can produce matching text.

Complete logging preserves true candidates by construction. Constant recall and
nondecreasing defined precision along the nested telemetry projections are
mechanical properties, not scientific discoveries. At transmission parameter 0.3
and shock 0.9, witness precision rises from 8.2% to 75.3%, while recall stays 52.1%.
From requests to context, mean absolute target-fraction error rises from 0.030 to
0.059 while target disagreement falls from 0.181 to 0.114 across the same 12 worlds.
The [saved-row derivation](../studies/review_remediation/derived_target_errors.json)
distinguishes disagreement, `(FP_target + FN_target) / N`, from signed fraction
error, `(FP_target − FN_target) / N`. Better individual target classification can
worsen the aggregate estimate because earlier false positives and false negatives
cancelled. Absolute error is taken within each world before averaging.

The completed [chronology sensitivity](../studies/chronology_consistency/RESULTS.md)
audits every exact published configuration: 144 initial benchmark worlds and 40
missing-receipt worlds. The legacy generator sometimes logs context entry before a
recipient decision that lacks that source in simulator state. The defect affects
76/144 benchmark worlds: all 48 at shock 0, 28/48 at shock 0.5, and none at shock 0.9.
A separately frozen repair retimes only offending chains while preserving random
outcomes, writes, source selections, truth, identities and denominators. It changes
186/1,440 benchmark evaluation rows across 72 configurations; it leaves the
high-shock headline above and all 1,280 missing-receipt evaluations unchanged.

The measured effects are mixed, not uniformly beneficial. Per evaluation, the
largest absolute changes are 27 false-positive edges, 0.111111 precision, 12
false-positive targets, seven missed targets, 0.038889 signed/absolute fraction
error, and 0.033333 disagreement. The corresponding maxima across paired
12-world group means are 15.25 edges, 0.020803 precision, 6.75 false targets,
3.833333 missed targets, 0.024074 fraction error, and 0.018750 disagreement.
Recall and true-positive/false-negative edge counts never change. Absolute fraction
error worsens in 90 evaluation rows and improves in 47. None of the 124 predefined
claim views reverses direction, although 27 change in magnitude. These overlapping
rows are not independent trials. The [scope check](../studies/comparative_validity/CHRONOLOGY_SCOPE.md)
and exact impact tables retain all conditions. Agreement with preserved decision
state does not establish physical scheduling realism.

The [missing-receipt follow-up](../studies/missing_receipts/results/REPORT.md)
removes observable receipts after world generation, preserving events and truth.
An unavailable telemetry type differs from missing records within a type; neither
proves non-occurrence. The evidence-aware policy accepts authentic context-entry
evidence despite missing upstream receipts and reports unknown exposure when
logging completeness cannot justify exclusion. Authentication is assumed, not
cryptographically implemented. Supported exposure still supplies only heuristic
source candidates.

With 49.97% actual delivery-record retention, transmission parameter 0.3 and shock
0.9, evidence-aware minus conjunction target disagreement is **−3.31 percentage
points** for witness reuse, with a 95% interval of **[−3.68, −2.93]**, but **+14.99
[13.90, 16.07]** for temporal proximity. These
[paired contrasts](../studies/missing_receipts/results/study.json) bootstrap 20
worlds, not edges or masks. Preserved evidence improves recall without uniformly
improving attribution. Stable record identities couple the loss masks in the
chronology sensitivity.

## What the public wiki records support

The [public-wiki audit](../studies/wiki_case_study/REPORT.md) asks which literal
page-name references overlap newly inserted character spans. **DSE** denotes the
publisher's dataset site label `dse`; the retained publisher manifest identifies
13,403 revisions on 3,908 pages under that key. The
[tracked source manifest](../studies/wiki_case_study/source_manifest.json) records
the export's provenance and counts. A site label or observed handle is not a stable
agent-run identity.

Under the fixed literal rule, [saved counts](../studies/wiki_case_study/results/counts.json)
distinguish 12,536 source-order-eligible snapshot pairs from 10,520
attribution-eligible pairs. The latter divide into 3,140 inserted and 7,380
inherited-only pairs: **70.15% of eligible snapshot pairs are inherited-only**.
The 2,016-pair eligibility reduction is separate from inherited text. Inserted pairs
contain 4,854 occurrences across 2,500 edits; occurrences and pairs are different
units. Another 2,519 revisions are excluded or ambiguous, with overlapping reasons.

These are measurements of real-export text under a frozen character-alignment and
matching rule, not verified source use. Generic titles and provider names can match
without establishing an intentional reference. The public export lacks stable run
identities and authenticated read/delivery/context records; exposure remains unknown
and source use unobserved. The results are not a copying rate or a source-use
false-positive rate. Revision deltas address a cumulative-text problem documented
by Lütje, rather than a newly discovered phenomenon.

## Usable model answers and warranted conclusions

The requested model aliases were `openai/gpt-5.6-terra` (**Terra**) and
`anthropic/claude-sonnet-5.5` (**Sonnet**). Alias names do not independently establish
a fixed underlying model version. Both evaluations score what the supplied evidence
warrants, rather than whether a model guesses hidden simulator labels.

The [utility pilot](../studies/investigator_utility/openrouter_v1/results/REPORT.md)
compares raw evidence plus a strong checklist (B) with the same inputs plus
deterministic provenance assistance (C). Raw evidence with a competent task is
secondary baseline A. Assistance supplies indexes and alignments, without privileged
labels. Warranted-answer accuracy (WAA) rewards valid correct definite answers;
unjustified certainty (UC) counts valid definite answers where evidence is unresolved.
Invalid answers cannot earn successful-restraint credit.

| Requested alias / substrate | WAA A / B / C | Primary C−B, percentage points [95% interval] |
| --- | ---: | ---: |
| Sonnet / wiki | 93.75% / 75.00% / 93.75% | +18.75 [0, 37.50] |
| Sonnet / synthetic | 42.86% / 42.86% / 71.43% | +28.57 [−28.57, 71.43] |
| Terra / wiki | 100% / 100% / 100% | 0 [0, 0] |
| Terra / synthetic | 100% / 100% / 100% | 0 [0, 0] |

Every schema-valid utility status is correct, so the Sonnet differences concern
response-contract acceptance, not demonstrated reasoning improvement. All primary
intervals include zero; Sonnet's wiki C−A difference is also zero. C invalidates a
previously valid synthetic response and introduces a nonexistent wiki citation.
UC is zero throughout, while the synthetic certainty-or-invalid diagnostic remains
40% in B and C. Explanations were not semantically graded. The denominator is 16
wiki cases and eight synthetic cases, with seven synthetic cases applicable to WAA
and five to UC. Case/page-history clusters, not the 144 calls, underpin intervals.
The pilot does not establish a general forensic-reasoning benefit.

A separate [retrospective extraction diagnostic](../studies/review_remediation/utility_diagnostic.json)
recovers 12 of Sonnet's 18 rejected responses under fixed gold-blind rules. Two
multi-object responses remain ambiguous and four refusals remain failures. Primary
scores are unchanged. Saved requests did not request native schema enforcement;
performance under enforcement was not measured.

The [responsiveness study](../studies/evidence_responsiveness/results/REPORT.md)
uses one prompt and fresh calls for base, irrelevant-change and decisive-change
variants, with certification before evaluation. Success requires both sides of a
pair, or all three family members, to be correct. There are **12 evaluation
families, not 72 independent problems**.

| Model / controlled substrate | Decisive pairs correct | Invariant pairs correct | Whole families correct |
| --- | ---: | ---: | ---: |
| Terra / receipt | 8/8 | 8/8 | 8/8 |
| Terra / wiki-derived | 4/4 | 3/4 | 3/4 |
| Sonnet / receipt | 0/8 | 0/8 | 0/8 |
| Sonnet / wiki-derived | 0/4 | 1/4 | 0/4 |

Sonnet's 26 rejected responses and ten accepted/correct responses do not imply 26
incorrect evidence judgments. The [offline diagnosis](../studies/evidence_responsiveness/offline_failure_audit/REPORT.md)
partitions its 36 responses into 12 with prose plus one JSON object, eight with two
objects and self-correction prose, two refusals, two using `id` instead of `claim_id`,
two with an extra `id`, and ten accepted/correct. All 42 identifiable objects use
arrays: the array-shape wording hypothesis explains **zero observed failures**.
No result-changing adapter/scorer defect was found. Embedded answers were not
substituted for rejected completions.

Terra's audited family `f_9695d2661a05a12eced27723` contains a valid wrong answer.
Certified statuses are established / established / ruled_out; answers are
established / ruled_out / ruled_out. The irrelevant change at `r1[898]`, outside
title span `[877,896)`, preserves inserted-reference status; the decisive predecessor
change at `r0[886]` makes it inherited. Exact
[request differences](../studies/evidence_responsiveness/offline_failure_audit/terra_summary.json)
include opaque case IDs and derived hashes too. This is one controlled behavioral
inconsistency, not a causally isolated edit effect or a historical observation.
Both certificate checks share SequenceMatcher alignment; neither is human validation.

## Finite retrieval analyses and comparative validity

The [finite acquisition analysis](../studies/evidence_acquisition/RESULTS.md) asks
which permitted archive lookups can establish a claim or certify that the archive
cannot resolve it, and at what retrieval cost. It supplies 40 synthetic problems
with 30 structural groups, explicit possible worlds, query costs and completeness
assumptions. Repeated structures and price variants remain in the analysis.
These assumptions make exact finite expectations possible; they do not turn the
problems into independent incident samples or demonstrate real investigation savings.

The historical pair-cut objective is an application of **EC2** from Golovin,
Krause and Ray (2010), with equivalence classes given by the three-way complete-archive
class `tau`. Edges join worlds in different classes with weight `p(u)p(v)`;
the expected cut is `E(S) − sum_o P(o | S) E(S_o)`, divided by query cost.
This is not a new algorithm. No approximation guarantee is imported without checking
its assumptions. The [relation note](RELATED_WORK.md#finite-acquisition-and-ec2)
gives the supplied reference and implementation correspondence.

The [comparative correction](../studies/comparative_validity/REVIEW.md) evaluates
competent schema-skipping and terminal-class information baselines, tie sensitivity,
and an envelope-aware stopping rule for audit selectors. It preserves the historical
policies and scores. At the original prior `q0`, the competent baselines have lower
mean retrieval cost than EC2:

| Policy | Equal-problem mean cost | Structure-balanced mean cost |
| --- | ---: | ---: |
| Historical pair-cut / EC2 | 3.793750 | 3.837500 |
| Schema order with implied-query skipping | 3.721875 | 3.713542 |
| Terminal-class information gain per cost | 3.507031 | 3.533333 |
| Matched-prior exact planner | 3.369141 | 3.401823 |

These are expected abstract retrieval units over the same 40 problems and 30
structural groups. Against schema-skipping, EC2 has 13 lower-cost problems, 14 ties
and 13 higher-cost problems; against terminal-class information gain, it has five
lower, 17 tied and 18 higher. The
[full comparison](../studies/comparative_validity/results/acquisition_results/acquisition_summary.json)
separates original fixed-policy reweighting from matched-prior replanning across
the five retained distributions, including `q0`. Terminal-class information gain
is cheaper than EC2 in all 20 distribution × planning-mode × weighting aggregate
views. Schema-skipping is cheaper in most, but loses under `qMinus` in both modes
and under matched replanning for `qPlus`, under both weighting rules. This does not
establish per-problem or per-stratum dominance: under matched `qMinus`, EC2 is
cheaper in the positive-receipt stratum by 0.182663 units. Replanning a heuristic
need not help either; terminal-class information gain's structure-balanced `qT`
cost rises from 3.820608 under the fixed policy to 3.829589 after replanning.
The original whole-world entropy and exact
references, per-problem comparisons and strata remain available; no repeated
structure or nuisance query was removed to obtain these results.

The exact and joint frontiers remain finite-instance optimization
analyses under supplied hypothetical knowledge; their relevance is an inspectable
separation of retrieval cost, detectable conflict and justified support. Their
comparative interpretation must use the corrected baselines rather than treating
weak historical comparators as evidence of general practical benefit.

The historical 50% audit allowance yields 15 detections for cheapest-first and
18 for nominally constant queries first. Across 200 predeclared common tie rankings,
the corresponding mean counts are **16.750 and 16.735**; constant-first minus
cheapest-first ranges from **−5 to +4**. The original three-conflict advantage is
not stable to the final opaque-ID ordering. These are algorithmic sensitivities,
not sampling intervals; the `k=1` and `k=2` views reuse the same signatures.

Adding the permitted stop when every compatible full signature is nominally possible
substantially reduces the closure-informed selectors' costs. At the 50% allowance,
the stopped original and affordability-aware selectors each detect **20/39**
conflicts for **478 and 502** added retrieval units, respectively, rather than
their historical 1,730 and 1,822. The saved exact policy detects **32/39 at 314**:
its finite advantage remains, but the cost difference against the corrected controls
is 164 or 188 units. Costs sum over all 431 archive signatures, including
nominal-compatible paths, and exclude the common original acquisition cost.
Allowances match; actual spending does not. Some inspection of nominal-compatible
archives is needed to establish that no further conflict is possible. The
[audit comparison](../studies/comparative_validity/audit_results/audit_summary.json)
and [tie repetitions](../studies/comparative_validity/audit_results/audit_tie_repetitions.json)
retain every anchor and ranking outcome. Lower detection cost does not
establish improved claim support.

Planning on a fully supplied finite hypothesis space is not held-out generalization.
Prospective selectors never receive the actual omission budget, realized omissions,
or unpaid answers. Hindsight contradiction subsets remain separate. An alarm does
not prove a claim false; no alarm does not establish model adequacy. Withdrawal and
an unknown or opposite answer do not restore support for an original proposal.
The [detection-only frontier](../studies/exact_audit_frontier/RESULTS.md) retains its
adverse warrant result, and the [joint frontier](../studies/joint_audit_warrant/RESULTS.md)
retains support/cost tradeoffs. Neither study is rerun on corrected stochastic histories.

## Technical limits and verification

Small selected cases, one sampled completion per variant, model aliases, shared
alignment machinery and possible public-text familiarity limit generalization.
Worlds or case/history families, rather than repeated rows and calls, underpin the
intervals where reported. Finite acquisition calculations use no sampling confidence
intervals. All-pass intervals do not imply universal reliability. Existing evidence
IDs establish identifier existence, not semantic support.

Tracked tables support inspection and reaggregation. The utility study's
[released visible answers and scoring views](../studies/investigator_utility/openrouter_v1/response_evidence/README.md)
support mechanical score reproduction. Its complete input evidence and the
responsiveness study's full fixtures, requests and final responses require retained
local material; the public repository does not provide every byte needed to
reproduce those evaluations. Hashes cannot replace missing evidence. The
[verification guide](REVIEWER_GUIDE.md) separates public checks, same-code
recomputation, separately implemented algorithm checks, shared physical semantics,
and optional local-history preservation. No independent human or external validation
is claimed.

[Accounting](../studies/evidence_responsiveness/results/execution.json) remains
$3.446844 known charges plus $0.335912 reservations, totaling $3.782756
charged-or-reserved; exact actual cost is unknown. The corrective analyses are
offline and make no model calls. Computational verification supports integrity and
reproduction within stated dependencies, not novelty, causal identification, or
permission to redistribute unreleased evidence.

## References and source records

- Golovin, Krause and Ray (2010), *Near-Optimal Bayesian Active Learning with Noisy
  Observations*, NeurIPS, Section 3; [arXiv:1010.3091](https://arxiv.org/abs/1010.3091).
  Supplied reference and equation used to identify the EC2 correspondence; no new
  external retrieval or approximation claim.
- Philipp Lütje, *The Mechanics of a Swarm*, [arXiv:2609.12748v2](https://arxiv.org/html/2609.12748v2),
  previously checked for cumulative text and request/use distinctions. Its separate
  operator request log is outside this project's public-export analysis.
- Shalizi and Thomas (2011), “Homophily and Contagion Are Generically Confounded in
  Observational Social Network Studies,” [DOI:10.1177/0049124111404820](https://doi.org/10.1177/0049124111404820).
  Bibliographic context, not a theorem proved or directly tested here.
- [Wiki source provenance](../studies/wiki_case_study/source_manifest.json),
  [analysis manifest](../studies/wiki_case_study/results/manifest.json), and
  [historical initial claims](../CLAIMS.md). Publisher checksums establish
  correspondence to released bytes, not completeness or redistribution permission.

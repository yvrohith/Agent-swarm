# Related work and source status

The synthetic research question is how accurately a specified estimator can recover **realized source use** from partial logs in a controlled simulator. The public-wiki audit asks a separate descriptive question: which literal page-name references were newly added, and which further evidence would be needed to interpret them as cross-run exposure or source use? Temporal correlation, attempted access, delivery, context membership and source selection support different claims.

## Verified public-wiki sources

The publisher download page, version-specific arXiv full text and arXiv abstract were retrieved over HTTPS on **2026-10-03** with HTTP 200. Their text was inspected as inert data; links and payloads inside incident records were not followed or executed. Acquisition details and dataset hashes are recorded in the [case-study source manifest](../studies/wiki_case_study/source_manifest.json).

- **Publisher:** [collusion.wiki](https://collusion.wiki/) and its [download page](https://collusion.wiki/explorer/download). The download page supplies a five-file wiki export, supplemental other-wiki records and expanded-file checksums. The acquired files were checked against those checksums. This pins the supplied bytes; it does not establish that every relevant event was recorded. The publisher describes redacted names and address suffixes. Redactions are preserved and the raw export is not redistributed here.
- **Philipp Lütje.** *The Mechanics of a Swarm: A Reproducible External Reconstruction of an Unintended Agent-Coordination Episode on a Third-Party Wiki*. [arXiv:2609.12748v2, full text](https://arxiv.org/html/2609.12748v2), [abstract and version history](https://arxiv.org/abs/2609.12748). The version-specific full text and abstract were checked for the narrow points below. The publisher's root write-up is a provenance link, not an additional independently audited dataset.

Lütje's §3 describes the five-file export and distinguishes its narrow failed-probe population from a read log. The paper also uses a **separately obtained operator request log**, which is not in the public five-file export analyzed here. Its continuity checks do not establish that every request was logged. We do not import that separate log, reconstruct its cohort identities, or borrow its associations as source-use labels.

Section 4.1 identifies cumulative page content as an attribution trap: a saved snapshot can contain text inherited from earlier saves. Same-page revision deltas are needed to separate additions from carried-forward text. The section also discusses quotation cascades and the distinction between requests and transmission. The present snapshot-versus-insertion comparison applies that known data-handling principle to a frozen descriptive rule; it is not a new discovery about cumulative text.

The v2 abstract states: “These records establish requests, not delivery or causal use.” It withdraws an earlier transmission interpretation because page choice, shared behaviour and action-dependent nameability prevent causal identification. Section 7 retains delivery and causal use as unresolved even with the supplementary operator logs. Those caveats support keeping the public audit's reference observations separate from the simulator's known source-selection truth. They do not establish upper or lower bounds on a shared source-use rate.

The supplemental `other-wikis.json.gz` has a narrower role in this audit. Its provenance describes recovery from prior rendered pages and publisher commits; the original API/RCS inputs were not retained. It supplies added/removed lines without full snapshot histories or observed-handle labels. Earlier-occurrence searches within those supplied lines are partial and cannot establish global origin, complete revision history or cross-run use. See the [frozen protocol](../studies/wiki_case_study/ANALYSIS.md) for the exact search scope.

## Foundational reference

Cosma Rohilla Shalizi and Andrew C. Thomas. “Homophily and Contagion Are Generically Confounded in Observational Social Network Studies.” *Sociological Methods & Research* 40(2), 211–239 (2011). [DOI: 10.1177/0049124111404820](https://doi.org/10.1177/0049124111404820).

This is bibliographic context for distinguishing contagion from selection and shared causes in observational networks; it is not an independently checked theorem about this simulator or a new result of this project. Applying an identification result requires matching its assumptions and observational model.

## Finite acquisition and EC2

Daniel Golovin, Andreas Krause, and Debajyoti Ray. *Near-Optimal Bayesian Active Learning with Noisy Observations*. NeurIPS 2010, Section 3. [arXiv:1010.3091](https://arxiv.org/abs/1010.3091). The corrective task supplied this bibliographic reference and the equation below; this correction made no external retrieval.

The historical finite-acquisition `pair_cut` policy is an application of **EC2**, not a new algorithm merely inspired by equivalence-class methods. Its hypotheses are the supplied nominal worlds and its equivalence classes are the three-way complete-archive conclusions `tau`. Weighted edges join hypotheses in different classes, with weight `p(u)p(v)`. For compatible set `S`, the expected cut for a query is

```text
E(S) - sum_o P(o | S) E(S_o).
```

[`Planner.edge_mass` and `Planner.pair_gain`](../src/tracebench/evidence_acquisition/policies.py) implement this expression using original prior masses inside `E`; class-mass products equal the sum of cross-class world-pair weights. Query selection divides by positive retrieval cost, with the preserved cost/opaque-ID tie rules. The supplied definition and code establish this correspondence. They do not independently verify every theorem assumption or import approximation guarantees.

The [retrospective acquisition comparison](../studies/comparative_validity/REVIEW.md) keeps the same finite terminal objective when testing schema order with implied-query skipping and information gain over `tau`. Entropy over every world is a different surrogate, and entropy over a Boolean claim would be different again. Positive priors affect expected costs and policy choices without changing which worlds support the same acquired evidence. These are finite-instance calculations, not held-out model generalization or measured swarm-investigator benefit.

The earlier method notes remain frozen. This additive attribution and the current synthesis supersede any broader novelty or comparative interpretation; they do not rewrite historical numerical results.

## Contribution boundary

The original benchmark compares temporal and witness-based investigators under five telemetry-type projections with hidden synthetic truth. The frozen missing-receipt follow-up removes records from available streams while preserving events and truth. The public-wiki audit measures newly added references and evidence availability in one pinned export. Its unavailable receipt types are not supplied by analogy with the simulator, and its descriptive counts are not external accuracy validation.

A temporal statistic and a content-reuse statistic are not automatically upper and lower bounds on one quantity. Such a claim would need a shared estimand and explicit assumptions connecting each statistic to that estimand. This project does not claim a new non-identifiability theorem, verified causal reconstruction or literature-wide novelty result.

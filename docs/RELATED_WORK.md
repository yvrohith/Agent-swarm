# Related work and source status

The research question is how accurately a specified estimator can recover **realized source use** from partial logs in a controlled simulator. It is motivated by a broader distinction: temporal correlation, attempted access, delivery, context membership, and counterfactual influence support different claims.

## Foundational reference

Cosma Rohilla Shalizi and Andrew C. Thomas. “Homophily and Contagion Are Generically Confounded in Observational Social Network Studies.” *Sociological Methods & Research* 40(2), 211–239 (2011). [DOI: 10.1177/0049124111404820](https://doi.org/10.1177/0049124111404820).

This is a bibliographic reference for the established problem of distinguishing contagion from selection and shared causes in observational networks. The publisher page was not fetched in this session. The paper's result should not be described as a theorem about this simulator or as a new result of this project. Applying an identification result requires matching its assumptions and observational model.

## Leads in the supplied proposal

The attachment names the following work, but supplies citation markers rather than resolvable source links for the relevant claims. These entries are **unverified research leads**, not independently checked evidence for the benchmark.

| Lead named by the proposal | Relevance to investigate | Verification needed |
| --- | --- | --- |
| Philipp Lütje, *Mechanics of a Swarm* | Incident reconstruction, temporal models, and the limits of request/contact evidence | Locate the original paper and exact revision; inspect methods and obtain a stable citation. |
| De Marzo, Alboré, and Garcia on wiki conventions | Reconstructed exposure and reuse of newly coined forms | Confirm title, authors, publication/version, data, and the paper's own causal caveats. |
| `swarm-ai-research` incident archive | Run identity reconstruction and detector evaluation | Identify the authoritative repository, pin a commit, and verify dataset and derived-artifact licenses. |

No incident counts, quoted findings, dataset sizes, or detector performance numbers from those leads are treated as established results here. A source update should record the exact URL, version or commit, access date, the narrow claim it supports, and any redistribution terms. A repository being public does not by itself establish permission to redistribute its data.

## Contribution boundary

This implementation compares simple temporal and witness-based investigators under five telemetry projections with a hidden evaluator. It offers reproducible error measurements under declared synthetic assumptions. It does not claim a new non-identifiability theorem, a verified reconstruction of a real incident, or a literature-wide novelty result.

A temporal statistic and a content-reuse statistic are not automatically upper and lower bounds on one quantity. Such a claim would need a shared estimand and explicit assumptions connecting each statistic to that estimand. This benchmark evaluates estimators against one defined source-use target instead of presenting an unsupported interval.

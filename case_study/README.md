# Real incident case-study scaffold

**Status: no real incident data has been imported or analyzed.** All measured benchmark results elsewhere in this repository are synthetic. The proposed German-wiki case study is a future external-validity check; it is not part of the completed empirical evidence.

The supplied research plan identifies potentially relevant papers, derived artifacts, and run reconstructions. Their source URLs, versions, data permissions, and exact claims have not yet been verified. Do not populate a results table with the plan's numerical claims or treat an unresolved citation marker as a source.

## Intake requirements

Before adding an analysis, record:

1. The authoritative source URL and a pinned release, version, or commit; retrieval date and file checksum.
2. The data license and redistribution terms, separately from the analysis-code license. Store only permitted, necessary data; otherwise document local download instructions.
3. The event schema, timestamp semantics, revision ordering, available telemetry, missing periods, and any deduplication.
4. The run-identity mapping, evidence supporting it, and the handling of ambiguous or provisional identities.
5. The witness extraction and exclusion rules fixed before interpreting results, plus a reproducible positive/negative audit sample.

Avoid committing raw request logs, personal identifiers, credentials, or incident payloads to the public repository. Synthetic examples must be labeled as synthetic and kept separate from incident evidence.

## Proposed analysis

Extract candidate provenance witnesses that first appear in one supported run and later recur in another. Require temporal feasibility and filter known common templates. Record source and target revisions, the witness, the identity evidence, and the rule that selected the pair. Audit false positives, missed witnesses, and ambiguous identities; do not infer a precision estimate solely from inspecting convenient positive examples.

“First observed” is not “first invented”: earlier unobserved activity, external sources, shared prompts, or reused templates may explain the same string. High specificity is a hypothesis to check, not a guarantee supplied by a token's length.

## Evidence ladder for interpreting future results

| Observation, if present in verified data | Direct support | Remaining uncertainty |
| --- | --- | --- |
| Earlier edit precedes later edit | Temporal ordering in the recorded trace | Whether either agent accessed the other edit |
| Source content existed on a page or feed | Recorded availability | Request, successful delivery, attention, or use |
| Run-associated request for source content | Attempted access under the identity mapping | Delivery and behavioral use |
| Logged successful delivery | Delivery under the log's semantics | Context insertion, attention, and use |
| Reuse of a distinctive source witness | A candidate provenance relation under stated exclusions | Shared source, collision, identity error, and alternate channels |
| Harness record of context insertion | Source content entered the recorded context | Whether it was selected or necessary for the output |

An incident report should present these as conditional statements about available evidence. It should not label inferred witness edges as verified causal transmission or use synthetic ground truth to fill missing incident labels.

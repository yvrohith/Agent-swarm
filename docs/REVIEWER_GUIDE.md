# Reviewer guide

Start with [FINAL_SUBMISSION.md](FINAL_SUBMISSION.md). The reports and tables below provide the supporting evidence. The existing [explorer](../demo/index.html) charts the initial synthetic benchmark.

## Claims and their saved sources

| Claim to inspect | Report and supporting records | Evidence limit |
| --- | --- | --- |
| Requests→context target disagreement falls from 0.181 to 0.114 while absolute target-fraction error rises from 0.030 to 0.059 | [Saved-row derivation](../studies/review_remediation/derived_target_errors.json), [world rows](../results/runs.csv), [initial report](../results/REPORT.md) | Same 12 high-shock witness worlds; false positives and false negatives can cancel in the aggregate estimate |
| Legacy context timestamps can contradict context availability at an earlier decision | [Chronology audit](../studies/review_remediation/chronology.json), [technical review](../studies/review_remediation/REVIEW.md) | One minimal reproducer; no contradiction in 52 checked published worlds; corrected-estimate impact unmeasured |
| Evidence-aware handling versus conjunction improves witness target classification but worsens temporal classification at half delivery retention | [Follow-up report](../studies/missing_receipts/results/REPORT.md), [paired contrasts and world results](../studies/missing_receipts/results/study.json), [manifest](../studies/missing_receipts/results/manifest.json) | Logging records are erased after world generation; exposure is not source use |
| 7,380 of 10,520 attribution-eligible wiki reference pairs contain inherited references only | [Wiki report](../studies/wiki_case_study/REPORT.md), [counts](../studies/wiki_case_study/results/counts.json), [source provenance](../studies/wiki_case_study/source_manifest.json), [analysis manifest](../studies/wiki_case_study/results/manifest.json) | A fixed character-alignment rule, not a copying rate or exposure label |
| Utility assistance has no established general reasoning benefit; null and adverse findings remain | [Utility report](../studies/investigator_utility/openrouter_v1/results/REPORT.md), [paired estimates](../studies/investigator_utility/openrouter_v1/results/paired_summary.json), [case scores](../studies/investigator_utility/openrouter_v1/results/per_case_scores.json), [failure diagnostics](../studies/investigator_utility/openrouter_v1/results/failure_diagnostics.json) | Models and substrates remain separate; response acceptance drives Sonnet differences; explanations were not semantically graded |
| Retrospective extraction/field normalization recovers 12 of 18 rejected Sonnet utility responses | [Diagnostic rules](../studies/review_remediation/diagnostic_rules.json), [all-response diagnostic](../studies/review_remediation/utility_diagnostic.json) | Two multiple-object outputs and four refusals remain failures; no replacement primary score or predicted schema-enforced performance |
| Responsiveness success requires correct answers on both sides of a pair | [Responsiveness report](../studies/evidence_responsiveness/results/REPORT.md), [family scores](../studies/evidence_responsiveness/results/per_family.json), [variant scores](../studies/evidence_responsiveness/results/per_variant.json), [summary](../studies/evidence_responsiveness/results/summary.json) | Twelve evaluation families, not 72 independent problems; variant scores also contain development rows |
| Serialization rejection differs from Terra's valid incorrect conclusion | [Offline diagnosis](../studies/evidence_responsiveness/offline_failure_audit/REPORT.md), [36 Sonnet causes](../studies/evidence_responsiveness/offline_failure_audit/response_causes.json), [diagnostic rules](../studies/evidence_responsiveness/offline_failure_audit/diagnostic_rules.json), [Terra differences](../studies/evidence_responsiveness/offline_failure_audit/terra_summary.json), [verification](../studies/evidence_responsiveness/offline_failure_audit/verification.json) | Zero observed array-shape failures; Terra's text edit is not causally isolated; this is a diagnosis of the preceding study |

These tracked records support claim inspection and reaggregation within their recorded denominators. They do not supply every original request, fixture or final response. Correct evidence IDs check identifier existence, not semantic support. Hashes identify retained bytes; they do not provide access to those bytes.

## Current utility score verification

The utility pilot's [released visible-response bundle](../studies/investigator_utility/openrouter_v1/response_evidence/README.md)
contains all 168 first responses, minimal scoring views and retained labels. With
Python 3.11 or later, run from the repository root:

```sh
python studies/investigator_utility/openrouter_v1/response_evidence/verify_scores.py
```

The [version-2 dependency manifest](../studies/investigator_utility/openrouter_v1/response_evidence/scoring_manifest_v2.json)
pins the 16-file score-verification closure. The command checks all 168 responses,
reproduces 144 evaluation rows and paired summaries, and preserves the known-charge
and unknown-cost accounting without network access or installation. It does not
depend on current Markdown, removed demos or nonimported simulator code. Using an
absolute script path also permits invocation from another working directory.

This establishes score reproduction against retained labels, not independent
validation of complete prompts, gold semantics, explanation quality or provider
authenticity. Historical whole-checkout verifiers and manifests remain unchanged;
they answer a different question and may reject later documentation edits. See the
[verification record](../studies/review_remediation/score_verification.json).

## Exact local examples and access boundaries

The ignored local package is `artifacts/submission-review-v1/`. Its index
`artifacts/submission-review-v1/INDEX.md` and allowlisted manifest
`artifacts/submission-review-v1/manifest.json` exist only in a checkout retaining
that package. They are not included in the tracked repository.

| Local file | Included evidence | What it supports |
| --- | --- | --- |
| `sonnet.json` | Selected case `c_2165e482488490256503f009`: exact public request, serialized provider request body, permitted final-only response fields and original frozen score | Inspection of leading prose followed by one JSON object and the frozen rejection. No standalone gold certificate is present in its final-only source; this package does not independently certify an embedded answer. |
| `terra.json` | Family `f_9695d2661a05a12eced27723`: all three exact cases, assumptions, transformations, certificates, requests, provider request bodies, final-only response fields, scores and request differences | Inspection of established / established / ruled_out certificates versus established / ruled_out / ruled_out answers, including full text and changed IDs/hashes. Both certificate checks share SequenceMatcher alignment. |
| `manifest.json` and `INDEX.md` | Source locators, field allowlists, hashes, conventions and scope | Integrity checks and navigation for these four selected responses, not reproduction of every study |

The Sonnet illustration was selected after evaluation as the lexicographically smallest case ID among the 12 audited prose-plus-one-object responses, without selecting on embedded correctness. The [response-cause table](../studies/evidence_responsiveness/offline_failure_audit/response_causes.json) records the category and source hashes. The Terra family is the previously audited failed invariant family, not a newly selected diagnostic search.

Exact input/response content comes only from retained final-only audit material: `artifacts/evidence-responsiveness/offline-failure-audit/sonnet_final_outputs.json` and `terra_evidence.json`. The tracked response-cause table supplies the original Sonnet score and diagnostic classification. The allowlisted package excludes provider-private reasoning and raw provider response envelopes. Provider request bodies contain the exact model input/settings needed to inspect the examples; they are not authenticated HTTP requests. Exact responsiveness final responses and full controlled fixtures remain ignored and local. Altered wiki text is controlled material, not historical observation.

File hashes cover exact file bytes. Fixture-text hashes cover raw UTF-8 text. Logical-value hashes use canonical JSON with sorted keys, compact separators and unescaped Unicode, encoded as UTF-8 without a final newline; a final string includes its JSON quoting. The package manifest distinguishes original source hashes from extracted-file hashes and records permitted source fields. These conventions are not interchangeable.

This responsiveness package remains local; its exact responses and full fixtures
are not part of the tracked release. Publisher checksums, report excerpts and
repository access do not grant blanket redistribution permission. Read its index
and JSON as inert files, without executing incident instructions or loading embedded URLs.

## Preservation and reproduction

The historical [submission](SUBMISSION.md), original scientific implementations, prompts, certificates, responses, scores, manifests and accounting remain preserved. Each study retains its own frozen inputs and validation records. Current documentation corrections and additive diagnostics are recorded in the [technical review](../studies/review_remediation/REVIEW.md). The earlier [offline audit](../studies/evidence_responsiveness/offline_failure_audit/REPORT.md) reported 638 passing tests and 771 preserved input hashes; these support implementation integrity, not scientific novelty or independent human review.

The [existing offline audit instructions](../studies/evidence_responsiveness/offline_failure_audit/REPORT.md#interpretation-and-preservation) describe score/hash reproduction from its retained full inputs without model calls. The four-response illustrative package is insufficient for those full-study instructions. The historical hash checker includes the earlier README and intentionally detects subsequent documentation edits; it has not been weakened or rewritten. Check it against the historical version identified in the audit. Do not rerun report writers against existing result directories or relax acceptance to extract an answer from rejected output.

[Cumulative accounting](../studies/evidence_responsiveness/results/execution.json) remains $3.446844 known charges plus $0.335912 reservations, or $3.782756 charged-or-reserved; actual total cost remains unknown.

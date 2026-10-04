# Bounded evidence-responsiveness audit

This completed exploratory study asks whether an investigator answers correctly
when decisive evidence changes and stays correct when an irrelevant detail changes.
It preserves the separate utility pilot's ceiling, null, adverse and response-contract
findings. See the [completed report](results/REPORT.md),
[historical addendum](SUBMISSION_ADDENDUM.md) and
[current synthesis](../../docs/FINAL_SUBMISSION.md).

The design has eight receipt and four controlled wiki-derived evaluation families,
plus one development family per substrate. Each family has three independently
presented variants: base, irrelevant change and decisive change. Correctness is
required on both members of a decisive or invariant pair, or on all three family
members. The 72 evaluation calls are not 72 independent problems. Models and
substrates remain separate; altered wiki text is a controlled fixture, not a
historical observation.

Terra passes every decisive pair and all receipt families, but gives one valid,
incorrect answer in a wiki invariant pair. Sonnet's 26 rejected responses and ten
accepted/correct responses measure end-to-end model/prompt/adapter/parser performance.
They do not establish zero evidence-reasoning competence. The
[offline failure audit](offline_failure_audit/REPORT.md) found no result-changing
adapter or scorer defect. All 42 identifiable objects in its audited Sonnet outputs
used array-valued `answers`; the array-shape hypothesis explains zero observed failures.

## Completed artifacts and access

- [Per-variant scores](results/per_variant.json), including separately marked
  development rows, and [evaluation family scores](results/per_family.json).
- [Summary and intervals](results/summary.json), [constant-status controls](results/baselines.json)
  and [fixed-rule examples](results/examples.json).
- [Execution accounting](results/execution.json), [response hashes](results/response_manifest.json)
  and [execution freeze](frozen/freeze.json).
- [Analysis rules](ANALYSIS.md), [configuration](config.json),
  [historical preservation snapshot](preservation.json) and
  [offline diagnostic verification](offline_failure_audit/verification.json).

Tracked tables permit inspection and reaggregation. Full response rescoring requires
the retained exact requests, visible completions, fixture texts and certificates in
ignored `artifacts/evidence-responsiveness/`. The final-only diagnostic material is
under `artifacts/evidence-responsiveness/offline-failure-audit/`; it excludes provider-private
reasoning. These local paths are not supplied by a public checkout. Hashes identify
content but do not supply missing bytes. The [verification reference](../../docs/REVIEWER_GUIDE.md)
distinguishes the available public and local evidence.

Investigators received the complete fixture texts and declared assumptions, with
family linkage, transformation roles, provenance and certificates withheld. Valid
evidence IDs check existence, not semantic support or reasoning faithfulness.
Mechanical and AI-assisted label checks are not independent human validation.
Family/history bootstrap intervals describe these small selected strata; zero-width
all-pass or all-fail intervals do not establish generalization certainty.

## Historical verification and lifecycle

The implementation baseline is `88ad3cb7e10fe82a15e8c30400ea780b370663d3`.
The [recorded offline audit](offline_failure_audit/REPORT.md#interpretation-and-preservation)
reproduced all 72 evaluation scores and 24 model/family rows from retained responses
at its documented snapshot. Its instructions require the full retained inputs,
not only the public tables or the four-example local package.

The historical CLI commands `validate`, `preflight`, `report` and the inline
`verify_frozen` path enforce historical repository pins as well as scientific
inputs. Later authorized Markdown changes can therefore fail those historical
checks even when numerical inputs are unchanged. They are not a standalone current
public score-verification route. Their source, manifests and earlier
[documentation-change record](presentation_update.json) remain unchanged; do not
refresh their hashes, delete results or restore older work over the current checkout.

The separate utility pilot now has a [current scoring-only verifier](../investigator_utility/openrouter_v1/response_evidence/README.md).
That verifier checks the utility response release, not these responsiveness scores.

The original lifecycle was `prepare`, `validate`, `preflight`, `develop`, `freeze`,
`run`, then `report`. `develop` and `run` can issue billable model calls and are not
offline verification commands. `prepare` requires the pinned wiki inputs and writes
a new prepared directory; `report` refuses an existing results directory. The
[source guide](../../case_study/README.md) records the wiki input provenance. No
regeneration or repeated model run is needed to read the completed results.

# Evidence and verification guide

Start with [the current synthesis](FINAL_SUBMISSION.md). This guide distinguishes
released numerical evidence from checks that require retained local inputs. It is
not a claim that every historical evaluation can be reconstructed from the public
repository alone.

Model shorthand follows the requested aliases: `openai/gpt-5.6-terra` is **Terra**;
`anthropic/claude-sonnet-5.5` is **Sonnet**.

## Claims and supporting evidence

| Claim | Released source | Scope |
| --- | --- | --- |
| High-shock witness requests→context disagreement improves while absolute fraction error worsens | [Saved-row derivation](../studies/review_remediation/derived_target_errors.json), [initial rows](../results/runs.csv) | Same 12 synthetic worlds; target FP/FN cancellation differs from classification error |
| Chronology repair changes 186 benchmark evaluations; high-shock headline and missing-receipt evaluations remain unchanged | [Completed sensitivity](../studies/chronology_consistency/RESULTS.md), [exact impact](../studies/chronology_consistency/results/impact.json.gz), [scope check](../studies/comparative_validity/CHRONOLOGY_SCOPE.md) | Every exact 144 benchmark and 40 missing-receipt configurations; preserved decisions, not physical realism |
| Receipt handling improves one heuristic's target classification and harms another's | [Missing-receipt report](../studies/missing_receipts/results/REPORT.md), [paired results](../studies/missing_receipts/results/study.json) | Fixed synthetic worlds; exposure is not source use |
| Under the fixed literal rule, 7,380/10,520 eligible wiki reference pairs are inherited-only | [Wiki report](../studies/wiki_case_study/REPORT.md), [counts](../studies/wiki_case_study/results/counts.json), [source provenance](../studies/wiki_case_study/source_manifest.json) | Real-export text attribution, not copying or verified source use |
| Utility assistance has no established general reasoning benefit | [Utility report](../studies/investigator_utility/openrouter_v1/results/REPORT.md), [paired estimates](../studies/investigator_utility/openrouter_v1/results/paired_summary.json), [case scores](../studies/investigator_utility/openrouter_v1/results/per_case_scores.json) | Model aliases and wiki/synthetic cases remain separate; accepted statuses all correct; null and adverse outcomes retained |
| Gold-blind post-hoc extraction recovers 12/18 rejected Sonnet utility responses | [Diagnostic rules](../studies/review_remediation/diagnostic_rules.json), [diagnostic output](../studies/review_remediation/utility_diagnostic.json) | Separate permissive diagnostic, not replacement primary scoring or evidence about schema-enforced performance |
| Responsiveness requires correct answers on both sides of a pair | [Study report](../studies/evidence_responsiveness/results/REPORT.md), [family scores](../studies/evidence_responsiveness/results/per_family.json), [variant scores](../studies/evidence_responsiveness/results/per_variant.json) | Twelve evaluation families; variant table also includes development rows |
| Sonnet rejection differs from Terra's verified controlled inconsistency | [Offline diagnosis](../studies/evidence_responsiveness/offline_failure_audit/REPORT.md), [36 response causes](../studies/evidence_responsiveness/offline_failure_audit/response_causes.json), [Terra request differences](../studies/evidence_responsiveness/offline_failure_audit/terra_summary.json) | Zero array-shape failures; Terra's text effect is not causally isolated; complete final-only evidence remains local |
| Finite acquisition and audit comparisons need competent baselines and explicit stopping rules | [Comparative review](../studies/comparative_validity/REVIEW.md), [verification inventory](../studies/comparative_validity/VERIFY.md) | Retrospective correction using fixed synthetic problems; no measured real-investigator benefit |

Tracked summaries permit inspection and reaggregation within their denominators.
Evidence-ID existence does not establish semantic support, and a hash cannot supply
a missing request, fixture or response.

## Public numerical verification

The [versioned verification inventory](../studies/comparative_validity/VERIFY.md)
links the executable checks and exact computational dependencies. It separates
public-results verification from optional local-history preservation. Missing local
files are reported as unavailable rather than fabricated or counted as a full pass.

The utility study releases all 168 visible first responses, minimal scoring views
and retained labels. From the repository root, its dependency-scoped verifier runs
without network access:

```sh
python studies/investigator_utility/openrouter_v1/response_evidence/verify_scores.py
```

The [16-file scoring manifest](../studies/investigator_utility/openrouter_v1/response_evidence/scoring_manifest_v2.json)
pins the actual score-verification closure. The command reproduces 144 evaluation
rows and paired summaries, checks retained response bytes and labels, and preserves
known-charge/unknown-cost accounting. It does not depend on current Markdown or
nonimported simulator code. This is reproduction against retained labels, not
independent validation of complete prompts, gold semantics, explanation quality or
provider authenticity.

For the prior-robustness study, the historical `analysis.py verify` also requires an
ignored preservation manifest. The additive public-results command checks the
released synthetic input/result closure without that private history:

```sh
uv run python -m studies.comparative_validity.public_verify public-results
```

The separately named `local-history` subcommand preserves the old checker meaning
and reports unavailable or changed local bytes rather than numerical success.
See [VERIFY.md](../studies/comparative_validity/VERIFY.md) for exact coverage and
the other study-specific public paths. Original verifiers and
freezes remain available unchanged; some deliberately detect later documentation
edits because they pinned whole historical files.

The chronology scope diagnostic checks retained records and impact arithmetic
against the original computational pins without an ignored-preservation gate:

```sh
uv run python -m studies.comparative_validity.chronology_scope \
  --verify studies/comparative_validity/chronology_scope.json
```

It does not regenerate worlds or rerun the investigators/scorers. The historical
full chronology verifier additionally enforces broad local preservation and should
not be described as a clean-checkout public numerical check.

Verification labels matter:

- **Same-code recomputation** reruns the saved calculation with the same algorithms.
- **Shared-semantics checks** reconstruct certificates using the original finite
  `Model` and certificate implementation. Calling that implementation twice is not
  an independently implemented physical-semantics check.
- **Separately implemented algorithm checks** include the retained tiny-fixture
  exhaustive decision-tree and Bellman/whole-tree checks for exact and joint
  planning. They verify recurrence and optimization properties while sharing stated
  physical semantics and inputs.
- **Human or external validation** is not established by the repository's AI-assisted
  checks. A record naming an unavailable script is evidence of a reported check,
  not executable public reproduction.

The inventory links actual code for each available path and names the limits of
archived validation records. It does not replace a narrow check with a broader
claim of independent validation.

## Clean-checkout tests

Use a Git checkout with full public history: chronology provenance tests read the
original `36be8fa` commit. The locked development commands are:

```sh
uv sync --frozen --extra dev
uv run pytest --collect-only
uv run python -m pytest --collect-only
uv run pytest
uv run ruff check .
```

The repository's pytest configuration explicitly places the repository root on the
test import path. This repairs the console entry point's imports of `studies.*`;
it does not install those research scripts as part of `src/tracebench`. Both
collection commands must discover the same test identities.

The corrective review's [clean-checkout record](../studies/comparative_validity/clean_checkout_checks.json)
and [review note](../studies/comparative_validity/REVIEW.md) record the actual scope,
interpreter, dependency cache and final commands. The bounded
[clean-checkout helper](../studies/comparative_validity/clean_checkout.py) uses a
fresh temporary checkout, cached locked dependencies, a new editable install,
cleared environment and Linux network denial. Historical ignored artifacts and
private inputs are absent. Normal commands above remain the portable workflow;
the helper's Linux sandbox is a local verification condition. A local pass does
not establish a new green remote CI run.

## Access and preservation limits

Wiki reanalysis needs the publisher files and hashes identified in the
[source manifest](../studies/wiki_case_study/source_manifest.json), retained under
ignored `data/raw/wiki/`. The repository supplies derived measurements and source
provenance; it does not redistribute the full export.

Full responsiveness rescoring requires retained cases, certificates, requests and
permitted final responses outside Git. Its tracked cause table and Terra difference
summary are inspectable, but do not include the complete inputs. Historical local
packages are not required by the public numerical paths and are not exposed here.
The utility release is broader for score reproduction, but still does not supply
all original raw input evidence. Publisher checksums and repository access do not
grant blanket redistribution permission.

Scientific implementations, frozen results, responses and accounting are preserved.
The [comparative review](../studies/comparative_validity/REVIEW.md) separately records
authorized documentation/configuration corrections and new diagnostics, rather than
refreshing old hashes to conceal them. Do not run result writers into existing
result directories or substitute extracted answers for rejected primary outputs.

[Cumulative accounting](../studies/evidence_responsiveness/results/execution.json)
remains $3.446844 known charges plus $0.335912 reservations, or $3.782756
charged-or-reserved; actual total cost remains unknown.

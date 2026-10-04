# What the released files can verify

Public numerical verification and preservation of an author's entire historical
checkout are different checks. The latter includes ignored local files and old
documentation bytes. A missing file is an incomplete check, never a pass. No
historical checker, frozen manifest or scientific implementation is changed here.

## Public commands

From an offline editable installation at the repository root:

```sh
uv run python -m studies.comparative_validity.public_verify public-results
uv run python studies/investigator_utility/openrouter_v1/response_evidence/verify_scores.py
```

The first is the additive **v1 prior-robustness verifier**. Its
[public manifest](public_manifest_v1.json) retains four original freeze/release
authorities and 17 scientific/input/result pins, copied from those authorities.
The authority bytes were checked against the pre-existing chronology preservation
inventory for commit `c29002c624005003e2f36ab7186e217edde76b22`; current source bytes
were not substituted for original pins. The new path rejects missing or changed
result bytes, changed model labels/semantics, changed aggregation code, duplicate
identities, incomplete grids and path/symlink escapes. Imported source paths must
resolve to the checked release, so an installed second checkout cannot silently
provide the calculation. README and unrelated presentation/history files are not
numerical dependencies.

It checks all 40 frozen problems, 200 positive deployment distributions, 5,880
saved matched trajectories, 2,000 expected-metric rows, and exact reaggregation
into 500 policy and 200 paired summary rows. It reconstructs saved original-prior
paths, verifies paid answers/costs/terminal certificates and checks matched q0
path parity. **This is same-code replay with shared model/certificate semantics**;
it does not choose planner actions again, prove optimality afresh, measure timing,
or validate a model of the real world. The
[retained result](public_verification.json) states these exclusions explicitly.

The second command is the already-existing dependency-scoped utility v2 verifier.
It reads the released 168 visible completion/refusal records, scoring views,
labels, schedule, unchanged scorer and saved scores. It reproduces 144 evaluation
scores and paired summaries plus development/accounting checks. It does not read
full provider envelopes or private reasoning. It verifies scoring **against the
retained labels**, not gold semantics, complete original prompts, semantic support
of citations, or provider authenticity. Its
[regression tests](../../tests/test_utility_score_verification.py) reject changed
responses, labels, scoring code, missing dependencies and path escapes; unrelated
Markdown changes do not invalidate its score calculation.

The command `uv run python -m studies.comparative_validity.chronology_scope
--verify studies/comparative_validity/chronology_scope.json` is the additive public
chronology check. Its narrower scope is direct all-write state availability,
quarter-retiming/stage order, target-metric identities, grouped arithmetic and
stable mask identities from retained synthetic evidence. It **does not rerun the
investigators or scorer**. The historical chronology runner's `verify` command
does rerun them, but ends by checking local-history preservation; it is not a
clean-checkout public verification command. See
[chronology_scope.py](chronology_scope.py) for the exact retained-data checks.

## Local history is explicit and optional

```sh
uv run python -m studies.comparative_validity.public_verify local-history
```

This checks the historical prior-study preservation inventory, including the
ignored local manifest and opaque bytes it names. It exits unsuccessfully and
lists missing/changed paths if the historical checkout is unavailable or current
documentation has intentionally changed. It never decodes provider responses and
does not claim public numerical verification. Intentional current-documentation
changes belong in the corrective review's change record, not refreshed historical
pins. The original `studies.acquisition_prior_robustness.analysis verify` remains
unchanged: it checks freeze dependencies **and** local preservation, which explains
its failure in a public checkout without those ignored files.

## Inventory and independence

The table links executable code, not merely a JSON assertion that a check ran.
Availability below is an inspected dependency property; only checks explicitly
recorded in this corrective pass's validation results were executed again.

| Evidence/check | Released executable path | What is and is not independent |
|---|---|---|
| Original acquisition `verify` | [study.verify_freeze](../../src/tracebench/evidence_acquisition/study.py), invoked by `uv run python -m tracebench.evidence_acquisition verify` | Frozen-closure/input integrity; this command alone does not reproduce all result arithmetic. |
| Acquisition certificates | [verify_certificate](../../src/tracebench/evidence_acquisition/certificates.py) | Reconstructs with the same `Model` and `certificate()`. Useful tamper/consistency check, **not separately implemented physical semantics**. |
| Original exact acquisition algorithm | [whole-tree oracle and fixtures](../../tests/test_acquisition_policies.py) | Complete-tree enumeration is separate from the production dynamic program on tested tiny fixtures; shared model semantics remain. |
| Prior robustness | [new public v1](public_verify.py), [historical driver](../acquisition_prior_robustness/analysis.py) | New reproducible same-code path described above; the old driver mixes freeze and local preservation. The old independent-verification JSON is a retained record, not a standalone published audit program. |
| Omission closures | [analysis.verify_outputs](../archive_model_misspecification/analysis.py), [reference.verify_cell](../archive_model_misspecification/reference.py) | `uv run python -m studies.archive_model_misspecification.analysis verify` uses released inputs/results and separately reconstructs closure/signature/history arithmetic; some physical validators and nominal certificates are shared. |
| Audit acquisition | [analysis.verify_outputs](../audit_aware_acquisition/analysis.py), [reference.verify_runs](../audit_aware_acquisition/reference.py) | `uv run python -m studies.audit_aware_acquisition.analysis verify` rechecks paid paths, costs, support and aggregation from public inputs. Independent loops share physical/certificate definitions. |
| Exact detection frontier | [analysis.verify_outputs](../exact_audit_frontier/analysis.py), [reference.verify_bellman and exhaustive_tree_oracle](../exact_audit_frontier/reference.py) | `uv run python -m studies.exact_audit_frontier.analysis verify` checks retained Bellman witnesses, all branches and paid paths without calling the production solver. Tiny whole-tree enumeration is separate algorithmic evidence; physical semantics are shared. |
| Joint detection/warrant frontier | [analysis.verify_outputs](../joint_audit_warrant/analysis.py), [reference.verify_bellman and exhaustive_tree_oracle](../joint_audit_warrant/reference.py) | `uv run python -m studies.joint_audit_warrant.analysis verify` checks joint witness triples, histories and arithmetic. Preserve the genuine independent recurrence/tree checks; no independent field validation follows. |
| Legacy benchmark and missing-receipt impact | [chronology scope check](chronology_scope.py), [historical direct reference](../chronology_consistency/reference.py) | Public retained-data arithmetic/state check has the scope above. Full frozen chronology replay additionally invokes local preservation. It is not a physical-realism test. |
| Utility scores | [verify_scores.py](../investigator_utility/openrouter_v1/response_evidence/verify_scores.py) | Public same-scorer replay against released labels; original broad `verify.py` and preparation/execution freezes are historical checks with wider dependencies. |
| Responsiveness and offline failure audit | [scoring.py](../../src/tracebench/evidence_responsiveness/scoring.py), [audit.py](../evidence_responsiveness/offline_failure_audit/audit.py) | Published tables permit inspection/reaggregation. Full final-response replay needs the unreleased exact fixtures/requests/response projections plus historical preservation. Do not run its report writer over historical results or treat a hash as the missing evidence. |
| Wiki reference measurements | [wiki loader](../../src/tracebench/wiki_loader.py), [wiki analysis](../../src/tracebench/wiki_analysis.py) | Frozen matching/alignment calculations; raw downloaded corpus is absent from a tracked-only checkout. No network acquisition is performed here; literal matching and shared alignment do not validate exposure/source use or human intent. |

Several separate audit records retain hashes of auxiliary scripts whose bytes are
not tracked: the audit-aware `verifier_source_sha256` and exact/joint
`audit_script_sha256` fields have **no matching tracked Python source**. The
[machine-readable inventory](hash_only_validation_inventory.json) records the
exact three checks. Those script hashes are provenance, not reproducible
validation. They do not negate the available frozen `reference.py` implementations
and exhaustive-tree tests linked above. Neither class of check is independent
human/external validation.

No command in this note submits a job, calls a model, reads credentials or downloads
data. Numerical replay does not make licensing, credential/IP clearance, external
authenticity or deployment-benefit claims. Clean console/module collection parity,
full suite and lint evidence are recorded separately in this corrective pass's
review and clean-checkout validation.

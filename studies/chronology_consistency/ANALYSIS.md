# Chronology-consistency sensitivity: fixed analysis

This review-informed correction sensitivity asks whether repairing the disagreement between the legacy simulator's decision-time context and its final logged chronology changes the published synthetic benchmark or missing-receipt findings. The defect and the historical numerical outcomes were already known. This is neither preregistered discovery nor independent confirmation.

The intervention is one **state-preserving repair of recorded chronology**. It changes timestamps in offending existing request/delivery/context chains while retaining the generator's decisions. It does not replay agent decisions, estimate the consequences of a different scheduler, or establish physical realism. [METHOD.md](METHOD.md) defines the single trigger, interpolation rule, independent reconstruction, and mask coupling before the full comparison.

## Fixed population and historical sources

The complete configuration inventory and source locators are machine-readable inputs to the execution freeze. Saved records are authoritative; seeds are not added or substituted.

| Population | Authoritative records | Complete configurations | Original evaluations |
| --- | --- | ---: | ---: |
| Initial benchmark | `results/benchmark.json`: metadata, per-world metric rows and summaries; `results/runs.csv`, `results/summary.csv`, `results/manifest.json` | 144 | 1,440 |
| Missing receipts | `studies/missing_receipts/results/study.json`: complete world configurations, rows, retention audit and paired rows; saved configuration/CSV/manifest files in the same directory | 40 | 1,280 |

There are 184 distinct complete configurations. Identical full configurations are generated once per audit path while all original scenario memberships and evaluation denominators remain represented. The benchmark has 12 scenarios (four transmission probabilities × three shock values), 12 seeds per scenario, two investigators, and five telemetry regimes. The missing-receipt population has two transmission probabilities, 20 seeds, two profiles, four retentions, two investigators, and two policies at context telemetry: 320 masked observations and 640 within-world policy contrasts per version. Every published world has 360 eligible writes. Mask levels, methods, policies and chronology versions do not create additional worlds.

The earlier review audited only 12 high-shock benchmark worlds and the 40 missing-receipt worlds. That subset does not determine the result of this complete audit. The six-write diagnostic is development evidence, excluded from all published-cohort denominators and estimates.

## Development, freeze and execution order

1. Preserve the checkout and recover exact saved inputs and origin locators. Separate scientific dependencies from unrelated presentation history. Record pre-existing changes without altering them.
2. Reproduce the saved seed-0, two-run, three-write, one-family, shock-0 counterexample using its complete saved configuration. Qualify the preferred correction only against that known diagnostic and focused small fixtures.
3. Freeze the inventory, historical source/input hashes, instrumentation, correction, direct chronology checker, mask adapter, metric/group definitions, failure handling, tests and preservation manifest. No full corrected cohort comparison precedes this freeze.
4. Audit all 184 published configurations. Require exact instrumented/uninstrumented World equality and matching random-state/draw evidence. Reproduce legacy observations, saved generation metadata/hashes where available, and every saved metric row before interpreting corrected values.
5. Reconstruct both final receipt streams at every write, evaluate the fixed corrected worlds with the unchanged investigators/scorer, and report paired changes and invariant checks. Preserve zero, adverse, undefined and unavailable rows.

The correction is not selected using evaluation scores. If a configuration fails reproduction, record and localize that failure before assigning any impact; its corrected estimate is unavailable. A failed strict timing interval, changed invariant, ambiguous physical identity, or residual availability discrepancy is an explicit correction failure. Do not change seeds, conditions, correction rules or historical pins to obtain a usable or nonzero answer.

## Estimands and comparisons

Truth is direct realized cross-run selected-source use in the unchanged structural simulator. Each version uses the same true edge set and all-write eligible target set. Exposure alone does not establish use; wrong-source prediction to a truly source-using target can be an edge error without a target error.

For each original evaluation row report legacy, corrected, and corrected-minus-legacy values for predicted, true-positive, false-positive and false-negative edge counts; edge precision and recall; target false positives and false negatives; signed source-using-fraction error; per-world absolute source-using-fraction error; and target disagreement. Preserve undefined precision and recall as null, with defined-world counts. Retain existing auxiliary scores and unresolved-burden measurements when reproducing missing-receipt rows.

For predicted target set P, true target set T and all-write denominator N:

```text
FP_target = |P \ T|                  FN_target = |T \ P|
signed_error = theta_hat - theta = (FP_target - FN_target) / N
absolute_error = |signed_error|      disagreement = (FP_target + FN_target) / N
```

Mean absolute error is the mean of the per-world absolute errors. It is not the absolute value of the mean signed error. Verify the identities against integer target counts and unchanged denominators. Signed-error differences have no universally favorable sign.

Aggregate within the original group keys: transmission probability, shock, telemetry and investigator; add profile, nominal retention and policy for missing receipts. Form chronology differences within a world first, then average over the original world population with metric-specific defined-pair counts. Do not pool masks, retentions or methods as independent worlds, and do not omit a dimension to create an outcome-selected subgroup.

For missing receipts separately retain `evidence_aware - conjunction` within each version and report:

```text
(evidence_aware_corrected - conjunction_corrected)
  - (evidence_aware_legacy - conjunction_legacy)
```

This change in the policy contrast differs from corrected-minus-legacy performance for either individual policy. Use the identical physical keep/drop decisions in both versions. There are no new confidence intervals or significance claims for this deterministic comparison. Historical intervals, when checked or cited, retain their original world/mask uncertainty interpretation.

## Required claim assessment

The final technical table identifies each claim's saved source, affected configuration count, old and corrected values, and changes in numerical value, direction or interpretation. It includes witness precision/recall across all five telemetry types; the requests-to-context absolute fraction-error comparison; the separate requests-to-context target-disagreement comparison; and the missing-receipt witness-versus-temporal tradeoff. Machine-readable results retain the full grid, not only the report's representative scenarios.

Statuses include `unchanged_on_tested_cohort`, `magnitude_changed_direction_retained`, `direction_changed`, and `unavailable_due_to_failed_reproduction`. If no published estimate changes, report that directly without manufacturing an erratum or searching another cohort. An unchanged estimate does not validate the generator's physical timing model; an affected estimate does not invalidate every use of the historical study.

## Preservation and stopping rule

The initial preservation inventory covers 387 pre-existing tracked files and 700 pre-existing retained local files, hashing raw bytes without decoding provider responses. Final validation must compare those same pins, including accounting, certificates, manifests and saved responses. New code and notes remain confined to this study namespace and focused tests. Full recomputation uses a fresh ignored output directory and refuses overwrites.

The independent finite acquisition, archive, audit and joint-frontier studies are outside this experiment. Their dependency isolation is inspected statically and documented; their experiments are neither modified nor rerun. Existing implementations, studies and reports remain historical artifacts. No model access, network requests, credential access, package downloads, API charges, commit, push, publication or submission belongs to this task.

Validation comprises focused chronology/mask/metric/preservation tests, installed offline lint, and one full installed test-suite run if feasible. Test counts are implementation evidence, not additional scientific observations. Completion ends this fixed assessment; it does not authorize another study.

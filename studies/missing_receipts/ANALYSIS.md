# Observation-only missing-receipt study

This is a **follow-up stress test informed by review**, not a preregistered
discovery. The original `CLAIMS.md` and baseline `results/` remain historical
artifacts tied to commit `36be8fa3682b294462ac65f8c2f750119e75cdb2`.

## Frozen scope

After 124 correctness tests passed, freeze `config.json` before running the
bounded experiment: world seeds 200–219, 120 runs, three writes per run,
transmission parameters 0 and 0.3, shock 0.9, retention 1, 0.9, 0.5 and 0.
Do not tune these settings to improve a comparison. Seeds 0–11 belong to the
original grid; 100–111 were used in earlier review diagnostics. Early unit-test
fixtures used seeds 211/213 at **30 runs**, then moved to 41/43 before freeze;
the specified 120-run worlds were not run before the freeze. No untouched-holdout
or formal preregistration claim is made.

The two profiles erase **delivery records** while retaining context records, or
erase **context records** while retaining upstream records. Each world is
generated once and observed at the existing context regime; no world-generation
parameters change to simulate record loss. Writes, identities, truth edges and
the all-write denominator are fixed. A dropped record is not an event that failed
to occur. Existing genuine non-delivery and context omission still occur according
to the unmodified simulator.

Mask seed is `900000 + world_seed` (900200–900219). A SHA-256 rank derived only
from the seed, channel and public receipt key is compared with each retention
threshold. Retained sets are nested; no inference function sees the mask seed,
loss flags, original counts or hidden selected source. The same corrupted
observation object is supplied to both comparison policies. Report actual counts
and fractions; nominal retention is not guaranteed to equal realized retention.

## Evidence semantics

Both policies use the unchanged temporal/witness candidate-generation rule with
stable identities. The conjunction filter remains the baseline.

The comparison policy assumes authentic retained receipts and complete coverage
only for streams explicitly declared complete. Its three exposure states are:

1. **Positive:** a valid context receipt identifies the source and recipient,
   occurs strictly between source and target, and records the source content.
   Surviving upstream references must agree, but missing upstream records do not
   invalidate positive downstream evidence.
2. **Excluded:** no positive receipt exists and complete relevant logging rules
   out the necessary context insertion or upstream event.
3. **Unknown:** no positive receipt or justified exclusion is available.

Only positive exposure candidates enter the comparison policy's heuristic
predictions. This does not verify source selection. Unknown exposure candidates
are measured separately; they are not added to predicted edges. The conjunction
filter has no unknown category and its rejections must not be described as
exclusions justified by completeness.

Authentication here is a trust assumption about simulator records, not implemented
cryptography. Metadata contains only channel-wide completeness flags and that trust
assumption. At retention below 1, the affected channel is incomplete even when no
record happened to be erased. Validation and the study concern loss of authentic
records; inconsistent, forged or incomplete source-write records are outside scope.

## Targets and measurements

Truth remains **direct, realized cross-run source selection**, not indirect
lineage, counterfactual necessity, or exposure. All generated writes are eligible.
Let `P` be predicted target IDs, `T` true target IDs, and `N` all writes:

- `FP_target = |P − T|`, `FN_target = |T − P|`.
- `signed_error = theta_hat − theta = (FP_target − FN_target) / N`.
- `target_disagreement = (FP_target + FN_target) / N`.

The identity is checked with floating-point tolerance. Signed error can cancel
despite target disagreement. Wrong-source attribution to a target in both sets
contributes edge error but no target error. Keep all edge precision/recall and
FP/FN counts separate; undefined precision/recall remains null.

Report unknown edges, unknown candidate fraction, unknown targets/all writes,
and unknown edges/all writes. Unknown-target burden can overlap a target with
another positively supported candidate. It is not an additional source-use rate.

## Paired comparisons and reporting

Summaries group transmission parameter, shock, telemetry regime, investigator,
profile, nominal retention and policy. Differences are **evidence aware minus
conjunction**, paired by world seed and identical masked observation at fixed
all other dimensions. Form differences first, then use 2,000 percentile bootstrap
resamples of the 20 worlds in that group. Null metric pairs remain null and report
their defined-world count. Never bootstrap edges or treat masks as extra worlds.

The report includes all paired comparisons, including zero, adverse and reversed
ones; actual retained fractions; edge recall against retention; false attribution;
signed theta error; target disagreement; and unresolved burden. Raw per-world
rows and artifact/config/source hashes make the result auditable. Exactly one
mask per world and stream is used, so intervals reflect the joint world/mask
variation of this protocol rather than separate within-world mask uncertainty.

Clean parity, nesting, downstream positive evidence surviving upstream loss,
unchanged worlds and the target-error identity are **unit-test consequences**.
Their directions are not scientific discoveries. Magnitudes and error costs in
the fixed generator are the measured outcome.

## Run

```bash
uv run pytest
uv run tracebench receipt-study --config studies/missing_receipts/config.json \
  --output studies/missing_receipts/results
```

The output directory must be fresh; the command also rejects any output inside
the original baseline `results/`. For replication choose
`artifacts/missing-receipts-replication`. The follow-up has no UI changes,
real-data importer, LLM calls, causal replay/intervention, or action gating.
Run-level correlated outages are a later stretch check, not part of this run.

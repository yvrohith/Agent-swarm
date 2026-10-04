# Chronology-consistency sensitivity: results

The fixed state-preserving chronology repair changes **186 of 1,440 published benchmark evaluation rows**, spanning 72 configurations and 34 of 120 method/telemetry groups. It leaves the report's high-shock headline scenario and **all 1,280 missing-receipt evaluations unchanged**. The chronology defect occurs in 76 of the 144 benchmark configurations and none of the 40 missing-receipt configurations. Thus the earlier 52-world subset did not cover the affected published conditions.

These are results of the single review-informed correction frozen in [ANALYSIS.md](ANALYSIS.md), [METHOD.md](METHOD.md) and [freeze.json](freeze.json). They preserve selected sources and truth; they do not establish physical realism or estimate what another scheduler would cause.

## Reproduction and chronology census

The saved six-write counterexample reproduced before the full comparison. Source `e000002` appears in a context receipt at 189.582785, before recipient write `e000003` at 194.451660, whose captured selection state lacks it. The source is installed while generating `e000004` at 198.778442. Repairing only chain `q000001` places request/delivery/context at 195.533355 / 196.615051 / 197.696746, strictly after the previous recipient write and before its owner. [Development evidence](development_checks.json) retains all six decisions and before/after records; it contributes no published-cohort observations.

All **184 exact published configurations** were audited. Ordinary, profile-only and fully instrumented complete Worlds match exactly; random primitive-call counts and final states match. Final-log reconstruction found 798 affected writes, 809 extra-source decision pairs, 782 distinct first-availability source/recipient contradictions and 784 offending chains. These count different objects: the benchmark has 51,840 writes, 25,491 distinct installations, 26,134 context receipts and 40,700 request chains. The 40 receipt worlds add 14,400 writes, 7,332 installations, 7,346 context receipts and 11,475 chains, all unaffected. Maximum measured early-availability discrepancy is 12.706597 simulator time units.

The direct checker matches captured state at **all 66,240 corrected writes** and verifies strict chain order plus unchanged writes, identities, non-time fields, truth and denominators. Two more offending chains than distinct first-installation contradictions reflect repeated receipts; duplicate receipts are not extra sources. No correction or reproduction is unavailable.

The unchanged investigators/scorer reproduce all **2,720 saved evaluation rows**, 120 benchmark and 64 receipt group means/defined counts, 640 policy contrasts, 32 policy-contrast summaries, 320 retention audits and 40 saved receipt-world metadata records. Original benchmark rows lacked four later-added target measures; those are explicitly derived rather than falsely described as previously saved fields. Historical intervals remain preserved and are not recomputed.

[Input provenance](inputs.json) retains the old aggregate-source mismatch: the original benchmark digest is reconstructed from its local historical commit, while later CLI additions and compatible evaluator extensions explain the current tree difference. Original scoring expressions and benchmark-driver semantics were checked; missing-receipt scientific modules match their pins while its later CLI pin differs. No historical pin was refreshed.

## Full benchmark impact

Each table below covers all 12 original scenarios. **Ranges are minimum to maximum across the ten original method × telemetry group changes**, each already averaged over its 12 paired worlds. They are descriptive bounds on separate group estimates, not pooled estimates or uncertainty intervals. Full old/corrected values and exact deltas for every group and world remain in [impact.json.gz](results/impact.json.gz). Values here are rounded to six decimals.

| p | Shock | Affected /12 | Writes /4,320 | Chains | Changed evaluations /120 | Δ predicted = Δ FP edges | Δ precision |
| ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 0 | 12 | 180 | 174 | 36 | -1.083333 to +11.666667 | 0 |
| 0 | 0.5 | 9 | 15 | 15 | 11 | -0.333333 to +1.833333 | 0 |
| 0 | 0.9 | 0 | 0 | 0 | 0 | 0 | 0 |
| 0.1 | 0 | 12 | 181 | 177 | 33 | -0.916667 to +14.750000 | -0.000117 to +0.020803 |
| 0.1 | 0.5 | 6 | 12 | 12 | 9 | -1.166667 to +1.000000 | -0.000003 to +0.000218 |
| 0.1 | 0.9 | 0 | 0 | 0 | 0 | 0 | 0 |
| 0.3 | 0 | 12 | 186 | 184 | 42 | -1.583333 to +15.250000 | -0.000408 to +0.008881 |
| 0.3 | 0.5 | 8 | 19 | 19 | 12 | -0.166667 to +1.916667 | -0.000014 to +0.001259 |
| 0.3 | 0.9 | 0 | 0 | 0 | 0 | 0 | 0 |
| 0.5 | 0 | 12 | 197 | 195 | 38 | -2.333333 to +13.500000 | -0.000630 to +0.005258 |
| 0.5 | 0.5 | 5 | 8 | 8 | 5 | 0 to +1.250000 | -0.000038 to 0 |
| 0.5 | 0.9 | 0 | 0 | 0 | 0 | 0 | 0 |

True-positive edges, false-negative edges and defined recall are unchanged in every evaluation; zero-transmission recall remains null. Consequently each predicted-edge count change equals its false-positive-edge count change. Writes-only and stable-identity inputs/results are identical throughout. Changed rows comprise 108 requests, 59 delivery and 19 context evaluations; the temporal context investigator is unchanged in all scenarios.

| p | Shock | Δ FP targets | Δ FN targets | Δ signed error | Δ absolute error | Δ disagreement |
| ---: | ---: | --- | --- | --- | --- | --- |
| 0 | 0 | -0.500000 to +6.750000 | 0 | -0.001389 to +0.018750 | -0.001389 to +0.018750 | -0.001389 to +0.018750 |
| 0 | 0.5 | -0.083333 to +1.166667 | 0 | -0.000231 to +0.003241 | -0.000231 to +0.003241 | -0.000231 to +0.003241 |
| 0 | 0.9 | 0 | 0 | 0 | 0 | 0 |
| 0.1 | 0 | -0.583333 to +6.583333 | -0.833333 to 0 | -0.001620 to +0.020602 | -0.001620 to +0.020602 | -0.001620 to +0.015972 |
| 0.1 | 0.5 | -0.166667 to +0.583333 | 0 | -0.000463 to +0.001620 | -0.000463 to +0.001620 | -0.000463 to +0.001620 |
| 0.1 | 0.9 | 0 | 0 | 0 | 0 | 0 |
| 0.3 | 0 | -0.666667 to +6.250000 | -2.416667 to +0.166667 | -0.002315 to +0.024074 | -0.002315 to +0.024074 | -0.001389 to +0.010648 |
| 0.3 | 0.5 | -0.083333 to +1.083333 | -0.083333 to 0 | -0.000231 to +0.003241 | -0.000231 to +0.003241 | -0.000231 to +0.002778 |
| 0.3 | 0.9 | 0 | 0 | 0 | 0 | 0 |
| 0.5 | 0 | -0.666667 to +3.500000 | -3.833333 to +0.333333 | -0.002778 to +0.020370 | -0.002778 to +0.020370 | -0.000926 to 0 |
| 0.5 | 0.5 | 0 to +0.416667 | -0.250000 to 0 | 0 to +0.001852 | 0 to +0.001852 | 0 to +0.000463 |
| 0.5 | 0.9 | 0 | 0 | 0 | 0 | 0 |

These effects are not uniformly favorable. False-positive edges decrease in 97 evaluation rows and increase in 88; precision increases in 75 and decreases in 63. Absolute fraction error worsens in 90 rows and improves in 47. Target disagreement increases in 61 and decreases in 73; target FN decreases in 32 and increases in nine. The remaining rows are unchanged. These are overlapping evaluation counts, not independent trials.

Moving a request can admit newer candidate sources through the historical run/page request gate as well as remove earlier exposure claims. Therefore retiming is not generally a subset operation on predictions. Unchanged true-positive edges can coexist with changed target FN: a wrong-source prediction can make an actually source-using target count as predicted. Signed error remains `(FP_target − FN_target)/360`, disagreement `(FP_target + FN_target)/360`, and absolute error is taken per world before averaging. Their changes need not agree in direction.

## Historical claims and retained interpretations

[claims.json](results/claims.json) contains **124 fixed claim views**: 97 `unchanged_on_tested_cohort`, 27 `magnitude_changed_direction_retained`, zero direction changes and zero unavailable views. A changed view can have both endpoints change while its contrast stays fixed; 27 is not a count of changed contrast gaps. B below denotes [the saved benchmark](../../results/benchmark.json); D the [earlier target-error derivation](../review_remediation/derived_target_errors.json); M the [saved receipt study](../missing_receipts/results/study.json). Precision vectors follow writes / identity / requests / delivery / context. R→C denotes requests→context within one version.

| Claim and saved source | p, shock; affected configurations | Legacy | Corrected | Status / interpretation |
| --- | --- | --- | --- | --- |
| Witness precision, B | 0.3, 0.9; 0/12 | .082091 / .088774 / .103139 / .734438 / .753410 | Same | Unchanged; finer telemetry retains the same precision pattern |
| Witness recall, B | 0.3, 0.9; 0/12 | .521209 at all five regimes | Same | Unchanged |
| Witness absolute fraction error R→C, B/D | 0.3, 0.9; 0/12 | .029630→.059259 | Same | Unchanged; absolute error worsens |
| Witness target disagreement R→C, B/D | 0.3, 0.9; 0/12 | .181481→.113889 | Same | Unchanged; disagreement improves |
| Witness precision, B | 0.3, 0; 12/12 | .084255 / .090941 / .097401 / .714707 / .771994 | .084255 / .090941 / .097464 / .723588 / .777878 | Magnitudes change; direction retained |
| Witness recall, B | 0.3, 0; 12/12 | .538171 at all five regimes | Same | Unchanged despite affected chronology |
| Witness absolute fraction error R→C, B | 0.3, 0; 12/12 | .025463→.059028 | .024537→.059722 | Worsening gap increases from .033565 to .035185 |
| Witness target disagreement R→C, B | 0.3, 0; 12/12 | .168981→.103472 | .168056→.102778 | Improvement retained; gap −.065509→−.065278 |
| Witness/temporal tradeoff, M; delivery loss, retention .5, evidence aware | 0.3, 0.9; 0/20 | Precision .795069/.177067; recall .520663/.974845; disagreement .105694/.536111 | Same | Unchanged; witness has lower recall alongside lower disagreement |

The headline signed R→C fraction error also stays **+.022222→−.059259**; at shock 0 it changes from +.024074→−.059028 to +.023148→−.059722. Cancellation still explains why aggregate fraction error can worsen while individual target disagreement improves. All 48 shock-.9 benchmark worlds are unaffected; every shock-0 world and 28 of 48 shock-.5 worlds has a chronology contradiction. Historical reports remain unchanged, with this separate sensitivity qualifying their numerical scope.

## Missing-record coupling and adverse comparisons

The historical mask hash includes timestamps. Adapter `legacy-selection-stable-physical-record-identity-v1` therefore replays legacy keep/drop decisions by `(channel, request_id)` onto corrected observations, validating all immutable fields. All 320 masks preserve identical retained identities, actual retention and completeness metadata. No truth or selection labels enter this adapter or the investigators. Because none of these 40 worlds needs retiming, even ordinary corrected mask memberships match here; the adapter's changed-timestamp behavior is separately tested.

All missing-receipt metrics and all 640 **evidence-aware minus conjunction** contrasts are unchanged; their corrected-minus-legacy contrasts are zero wherever defined. Null precision/recall stays null. For p=.3, delivery retention .5, evidence-aware minus conjunction improves witness recall by .252217 but lowers precision by .013784 and adds 4.1 false-positive targets per world; target disagreement improves by .033056. For temporal inference the same policy comparison improves recall by .476863 but **worsens disagreement by .149861** and adds 79.5 false-positive targets. Those adverse costs, all other profiles/retentions, zero-use controls and unresolved burdens remain intact.

## Validation, preservation and reproduction

The correction was frozen after **81 focused tests passed**, installed Ruff passed, and the known diagnostic qualified, with 55 pinned dependencies and zero new published sensitivity outcomes observed. The **full installed offline suite ran once: 1,206 passed, zero failed or skipped, in 95.72 seconds**. Those regression tests include the focused tests; their counts are not independent scientific observations. The fresh [saved-output verification](OFFLINE_VERIFICATION.json) passed all 184 configurations and 66,240 writes with zero unavailable configurations in 85.320 seconds. [Execution validation](results/validation.json), [independent arithmetic validation](INDEPENDENT_VALIDATION.json) and [final validation](FINAL_VALIDATION.json) record the remaining checks and exact test scope. Checking shares immutable record types and trace evidence; it is AI-assisted, not independent human validation.

All **387 pre-existing tracked files and 700 retained local files** match their original preservation hashes, including responses and API accounting. All 55 sensitivity freeze pins and the six independent finite-study sets of 19/34/23/27/36/42 dependencies match; these sets overlap and their counts are not added. [Static isolation](ISOLATION.json) inspects their dependency boundaries. The full-suite regression tests do not rerun the completed acquisition, archive, audit or joint-frontier experiments. Execution made zero network requests or model calls, accessed no credentials, downloaded no dependencies and incurred no additional spend. No commit, push, publication or submission occurred.

From the repository root, the following verifies saved outputs without regenerating worlds:

```sh
env -i PATH=/usr/local/bin:/usr/bin:/bin PYTHONPATH=src:. \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - verify <<'PYCODE'
import json
import socket
import sys
from pathlib import Path

def denied(*args, **kwargs):
    raise RuntimeError("Network disabled for this offline study")

socket.socket.connect = denied
socket.socket.connect_ex = denied
socket.create_connection = denied
socket.getaddrinfo = denied

from studies.chronology_consistency.runner import STUDY, execute, verify_outputs

if sys.argv[1] == "verify":
    result = verify_outputs(STUDY / "results")
elif sys.argv[1] == "reproduce":
    result = execute(Path("artifacts/chronology-consistency/replication-v1"))
else:
    raise ValueError("Expected verify or reproduce")
print(json.dumps(result, sort_keys=True))
PYCODE
```

For a fresh reproduction, change only `python - verify` to `python - reproduce`. The ignored output path must not already exist; frozen dependencies and preservation pins are checked and overwrites refused. [The result manifest](results/manifest.json) pins full captured worlds/traces, per-world chronology, metric/mask tables and claim views. This completed finite sensitivity uses no added seeds, conditions, corrections or intervals. It establishes consistency of recorded availability with preserved simulator decisions under the inspected premises, not physical scheduling realism or general validity beyond these cohorts.

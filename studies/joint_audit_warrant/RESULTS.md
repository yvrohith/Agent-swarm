# Joint conflict detection and original-claim support: results

At the 50% allowance, joint policy J preserves **32/39 conflict detections**, supports **181 original proposals** instead of E's 177, and costs **345 added units instead of 314**. Those four additional supports cost 31 units. The matched-knowledge sequential baseline supports 178 at cost 352: J supports three more and spends seven less. At full allowance J reaches the M2 support ceiling of **185**, costing 461 versus E's 414 and the sequential baseline's 501. Support is not free, and the comparison is contract-dependent: under actual k=1 the full-budget sequential path supports one more original proposal than J.

This is an exploratory follow-up informed by the [completed detection-only result](../exact_audit_frontier/RESULTS.md), not an untouched holdout or correction. E's actual saved choices, original optimum, and adverse support findings remain unchanged.

## Scope and denominators

The [protocol](ANALYSIS.md), [method](METHOD.md), [configuration](config.json), and 42-dependency [freeze](freeze.json) retain the same 40 problems, 30 structural groups, 169 H0 roots, physical M2 closure, prices, and four anchors. All **676 requested root/anchor labels**, **652 distinct root/allowance cells**, **5,079 directly executed three-arm paths**, and **15,048 actual-k views** in **1,440 aggregate cells** completed. There were zero caps, missing cells, or failures. Twenty-four coincident allowances retain their anchor labels; reused anchors and actual-k views create no extra paid sessions or independent trials. No new integer-budget sweep was run.

The design has 392 original and 39 new signatures, each weighted once through its unique root. Original proposals comprise 271 definite and 121 irreducible conclusions. Under M2, **175 definite originals are already supported at H0**, 96 lack support, and full evidence supports at most 185, leaving an unsupported floor of 86. Total support is separated from restoration above 175. Unknown, withdrawal, the opposite conclusion, and originally irreducible proposals earn no reward.

E follows its historical canonical path exactly. `E_then_support` (Sequential) follows that same path, then queries the cheapest affordable action while support remains possible and unestablished, using the remaining original allowance. J maximizes detection, then supported-original reward, then minimizes summed cost on all signatures. J and Sequential receive full hypothetical M2 physical claim semantics; old E received its observable envelope. **J versus Sequential is the matched-knowledge comparison.** J versus E changes objective and supplied hypothetical knowledge. No selector sees actual k, realized truth, omissions, or unpaid future answers.

Support requires agreement with the same P0 across every compatible physical world, including all members of mixed signature cells. First nominal conflict still ends retrieval. New-signature claim outcomes are diagnostics, not additions to the reward.

Pooled counts/costs, equal-problem (EP) means, and structure-balanced (SB) means remain distinct. EP averages within each problem; SB averages variants within their original group, then groups equally. Cost contrasts use all signatures within each of 40 problems; support contrasts below use each problem's original-signature denominator. New-signature conditional metrics use 22 problems/17 groups; restoration fractions have their own eligible population (25 problems have unsupported originals at H0). New-signature detection fractions are undefined at k=0. No sampling intervals or incident-prevalence estimates are reported.

## Detection-preserving support and its price

The table reports the fixed M2 design objective. Costs are pooled added retrieval units over the stated signature populations, including empty lookups and nominal-compatible archives. The original acquisition cost of **1,617** is separately sunk and unchanged.

| Anchor % | Policy | Detected /39 | Supported /271 | Restored /96 | Unsupported originals | Cost original /392 | Cost new /39 | Added cost all /431 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | E | 0 | 175 | 0 | 96 | 0 | 0 | 0 |
| 0 | Sequential | 0 | 175 | 0 | 96 | 0 | 0 | 0 |
| 0 | J | 0 | 175 | 0 | 96 | 0 | 0 | 0 |
| 25 | E | 7 | 175 | 0 | 96 | 16 | 10 | 26 |
| 25 | Sequential | 7 | 175 | 0 | 96 | 29 | 17 | 46 |
| 25 | J | 7 | 175 | 0 | 96 | 16 | 10 | 26 |
| 50 | E | 32 | 177 | 2 | 94 | 197 | 117 | 314 |
| 50 | Sequential | 32 | 178 | 3 | 93 | 232 | 120 | 352 |
| 50 | J | 32 | 181 | 6 | 90 | 228 | 117 | 345 |
| 100 | E | 39 | 178 | 3 | 93 | 262 | 152 | 414 |
| 100 | Sequential | 39 | 185 | 10 | 86 | 349 | 152 | 501 |
| 100 | J | 39 | 185 | 10 | 86 | 309 | 152 | 461 |

All policies detect 0, 7, 32, and 39 at the anchors. Sequential preserves E's alarm paths without another allowance and cannot exceed E's maximum, so detection parity is a validation consequence. Complete joint frontiers project to the saved `(d,l)` frontiers at **all 652 distinct allowances**; E's actual old tie choices also reproduce.

At 25%, no policy restores an original; Sequential spends 20 extra units without support gain. At 50%, J's four-over-E support gain costs 31 units, all on originals. At 100%, J and Sequential restore all ten originals recoverable under M2. Compared with E's three restorations, J's seven additional supports cost 47 units; the sequential suffix costs 87. Full base-plus-added totals are E **2,031**, Sequential **2,118**, and J **2,078**.

There is **no support improvement at zero extra E cost in any of the 652 root/allowance cells**. This is a measured null result, not an assumed objective property. Eight cells in five roots have a support-price tradeoff: `acq_94225` (two roots), `acq_94227`, `acq_94231`, and `acq_94233`. All flat cells remain included. The retained threshold curves report minimum cost for at least each support threshold; Pareto pruning need not retain every attainable exact support level.

For example, `acq_94225`, root `audit_root_bcc1c354b463554920bc005d`, allowance eight, has maximum-detection alternatives **(d,w,l)=(2,0,6)** and **(2,2,22)**. Two additional supported originals cost 16 more summed units without losing either detection. Cost 22 sums mutually exclusive paths; each path remains within allowance eight. Cheaper lower-support alternatives remain in the frontier.

At 50%, a frontier policy matches Sequential's detection and support at **318 units**, versus its 352, saving 34. J instead chooses more support at 345, so that 34-unit matched-support saving differs from J's seven-unit saving. At full budget the matched frontier point is J, saving 40. At 25%, matching Sequential's unchanged reward costs 26 instead of 46.

## Paired and stratified results

Each cell below shows **EP / SB**. Support deltas divide each problem's supported-count difference by its original-signature count, not by its definite or initially unsupported count.

| Anchor % | J−Sequential cost | J−Sequential support fraction | J−E cost | J−E support fraction |
| --- | --- | --- | --- | --- |
| 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| 25 | −0.02917 / −0.02222 | 0 / 0 | 0 / 0 | 0 / 0 |
| 50 | −0.01750 / −0.01167 | +0.00469 / +0.00625 | +0.04750 / +0.05667 | +0.00747 / +0.00810 |
| 100 | −0.05556 / −0.07407 | 0 / 0 | +0.08750 / +0.11000 | +0.01649 / +0.02014 |

At 50%, all three extra supports over Sequential come from `acq_94225`; the other 39 problems tie. The seven-unit cost saving comes from `acq_94239`; 39 others tie. At full budget all problems tie in M2 support, and `acq_94225` supplies the 40-unit cost saving. Across unique root/allowance cells J costs less than Sequential in six and ties in 646; its support is higher in two and tied in 650. This measured cost pattern is not a theorem: obtaining more support can generally cost more.

The following stratum table retains flat and positive-cost findings relative to E. Each stratum has ten problems and respectively 6, 8, 8, and 8 groups. All policies have the displayed detection count.

| Stratum | Anchor % | Detected | J−E support count | J−E cost sum | J−Sequential support count | J−Sequential cost sum |
| --- | --- | --- | --- | --- | --- | --- |
| Positive receipt | 25 | 0 | 0 | 0 | 0 | 0 |
| Positive receipt | 50 | 0 | 0 | 0 | 0 | 0 |
| Positive receipt | 100 | 2 | 0 | 0 | 0 | 0 |
| Negative completeness | 25 | 1 | 0 | 0 | 0 | 0 |
| Negative completeness | 50 | 8 | 0 | 0 | 0 | 0 |
| Negative completeness | 100 | 11 | 0 | 0 | 0 | 0 |
| Complementary candidates | 25 | 4 | 0 | 0 | 0 | −17 |
| Complementary candidates | 50 | 11 | 3 | 27 | 3 | 0 |
| Complementary candidates | 100 | 11 | 5 | 35 | 0 | −40 |
| Archive ambiguity | 25 | 2 | 0 | 0 | 0 | −3 |
| Archive ambiguity | 50 | 13 | 1 | 4 | 0 | −7 |
| Archive ambiguity | 100 | 15 | 2 | 12 | 0 | 0 |

All per-stratum EP/SB means, subtype tables, and exact ratios are retained in [design summaries](results/design_summary.json.gz), [support summaries](results/summary.json.gz), and [paired contrasts](results/paired.json.gz). Positive-receipt and negative-completeness strata show no added support or support cost versus E. Saved A/B/C/D outcomes remain context; no new heuristic competition was run.

## Actual-k consequences and remaining limits

Planning always uses M2. The same histories are checked under actual M0/M1/M2; k never changes a choice. Original-signature support outcomes are:

| Actual k | Anchor % | Supported E / Sequential / J | Unsupported E / Sequential / J | Exhaustive support ceiling | Unsupported floor |
| --- | --- | --- | --- | --- | --- |
| 1 | 50 | 177 / 178 / 181 | 94 / 93 / 90 | 200 | 71 |
| 1 | 100 | 178 / 186 / 185 | 93 / 85 / 86 | 200 | 71 |
| 2 | 50 | 177 / 178 / 181 | 94 / 93 / 90 | 185 | 86 |
| 2 | 100 | 178 / 185 / 185 | 93 / 86 / 86 | 185 | 86 |

The unfavorable k=1 result is retained: Sequential supports **186** at full budget, while J supports **185**, leaving **85 versus 86** unsupported. This is one original signature in `acq_94225`; J−Sequential is −1/640 EP and −1/480 SB on the original-population support fraction. It does not contradict optimization under M2, where both support 185. Neither reaches the k=1 ceiling of 200. No objective or path was changed to remove this result.

At k=2, J reaches the floor of 86 unsupported originals, whose opposite-claim worlds share every catalogue answer. At k=1, J leaves 15 additional unsupported originals above the floor of 71, reflecting available but unacquired evidence under that less conservative contract. E's historical 93 remains unchanged. At k=0 all policies retain 271 supported definite originals, 121 irreducible conclusions, and zero false alarms.

Full-budget final statuses on all 431 nonzero-k signatures separate pending uncertainty from archive irreducibility:

| Actual k | Policy | Established | Ruled out | Unresolved pending | Archive irreducible |
| --- | --- | --- | --- | --- | --- |
| 1 | E | 174 | 22 | 47 | 188 |
| 1 | Sequential | 174 | 30 | 34 | 193 |
| 1 | J | 174 | 29 | 36 | 192 |
| 2 | E | 174 | 20 | 21 | 216 |
| 2 | Sequential | 174 | 27 | 6 | 224 |
| 2 | J | 174 | 27 | 6 | 224 |

Each policy raises 39 full-budget alarms, withdrawing 26 definite proposals on new signatures. Withdrawals earn no original-support reward. At k=1 each also has two mathematically restored new proposals that are withdrawn on alarm; at k=2 no new proposal is restored. The reward table cannot be inflated by those diagnostics. No nominal signature alarms, no initially supported proposal loses support, and no initial irreducibility conclusion becomes overstrong. An alarm does not establish target falsity; silence does not validate the archive model.

## Retrieval and resource accounting

Sequential's saved E phase costs 26/314/414 at 25/50/100%; its separate support suffix costs 20/38/87. There is no second allowance. J records one joint phase of 26/345/461, without an artificial detection/support split. Full-budget original costs are E/Sequential/J **262/349/309**; new costs are **152 for all three**. All total costs retain the separate acquisition base.

The following EP means and pathwise maxima use all 431 design signatures. Bytes are canonical payload bytes, including empty results and separately charged aliases.

| Anchor % | Policy | Added cost EP | Added queries EP | Added bytes EP | Max added cost | Max base+added cost | Max added queries | Max added bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 50 | E | 0.64444 | 0.31861 | 44.47 | 7 | 14 | 3 | 555 |
| 50 | Sequential | 0.70944 | 0.34861 | 49.35 | 7 | 14 | 3 | 555 |
| 50 | J | 0.69194 | 0.33611 | 46.92 | 7 | 14 | 3 | 555 |
| 100 | E | 0.87069 | 0.41361 | 57.90 | 10 | 14 | 4 | 747 |
| 100 | Sequential | 1.01375 | 0.46000 | 64.73 | 13 | 15 | 4 | 747 |
| 100 | J | 0.95819 | 0.44611 | 62.61 | 10 | 14 | 4 | 747 |

The base EP cost is 3.12395, with 1.69706 queries and 239.62 bytes. Full-budget all-population catalogue coverage is E 38.82%, Sequential 39.67%, and J 39.47% EP. Attaining M2's support ceiling does not require exhaustive retrieval or establish model adequacy.

Whole-root planning took **1.015 seconds wall / 1.014 CPU**. Direct anchor reconstruction/execution took **2.966 wall / 2.964 CPU**; J choice traversal inside that work took about 0.036/0.036 and is not added twice. The integrated checker took **39.392 wall / 39.373 CPU**. Total evaluation was **69.520 wall / 69.483 CPU**. Cumulative process peak RSS was **1,142,236 KiB**, not a per-policy peak. Maximum root usage was **531 states and 1,312 child combinations**, versus caps of 100,000 and 10,000,000; maximum frontier size was three. These are computation measurements, not deployment latency or monetary savings.

## Verification, preservation, and reproduction

Before freezing, **90 new focused tests passed** and Ruff passed. A separate whole-tree oracle checked complete triple frontiers on tiny fixtures, including support-favorable ties; those are correctness fixtures, not evaluation discoveries. At final validation the **full installed offline suite ran once: 1,125 passed, zero failed, zero skipped in 89.11 seconds**. This differs from the former study's 296 dependency-scoped checks. No packages were installed; socket connections and name resolution were disabled during offline execution.

[Integrated verification](results/independent_verification.json) and the fresh [saved-output check](OFFLINE_VERIFICATION.json) verified **169 roots, 652 frontiers, 11,755 states, 22,894 child combinations, 5,079 executed paths, and 15,048 views**. Checks include **1,043 distinct certificates** (268 nominal, 775 expanded), **80,508 references**, and **3,916 all-query witness comparisons**. All **5,016 historical E anchor views** reproduce, excluding only two timing fields.

The [independent arithmetic audit](INDEPENDENT_VALIDATION.json) passed **623,160 numeric checks**, **2,184 physical truth derivations**, all design paths and actual-k views, all 652 projections, and **1,379 threshold entries**. Verification passes are not added together as independent evidence. [Final validation](FINAL_VALIDATION.json) records tests, artifact checks, and preservation. All **42 frozen dependencies**, **350 historical tracked files**, **509 historical local files**, and **twelve additional retained development artifacts** match their pins. Nothing historical was rewritten. There were zero model/network calls, credential or private-reasoning accesses, dependency downloads, or additional spend.

From the repository root, verify saved outputs with a clean environment and disabled network operations:

```sh
env -i PATH=/usr/local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python - verify <<'PY'
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

from studies.joint_audit_warrant.analysis import STUDY, execute, verify_outputs

if sys.argv[1] == "verify":
    result = verify_outputs(STUDY / "results")
elif sys.argv[1] == "reproduce":
    result = execute(Path("artifacts/joint-audit-warrant/replication"))
else:
    raise ValueError("Expected verify or reproduce")
print(json.dumps(result, sort_keys=True))
PY
```

For reproduction, change only `python - verify` to `python - reproduce` in that command. It writes to the fresh, ignored directory `artifacts/joint-audit-warrant/replication` and refuses to overwrite existing outputs. The [manifest](results/manifest.json) pins [complete frontiers and threshold curves](results/roots.json.gz), [executed paths](results/design_runs.json.gz), [actual-k views](results/runs.json.gz), [design summaries](results/design_summary.json.gz), [support summaries](results/summary.json.gz), [paired contrasts](results/paired.json.gz), and [validation](results/validation.json). Flat and adverse cases retain their denominators.

Objective ordering, projection equality, sequential detection parity, sound certificates, and the simultaneous full-budget detection/M2-support ceiling are validation consequences. The numerical findings are positive support prices, absent free gains, sequential inefficiency at finite budgets, concentrated gains, and the adverse k=1 comparison. Exactness concerns deterministic policies under supplied physical hypotheses, prices, and H0, not randomized policies, unknown archives, factual incident accuracy, or a deployment prior. Independent checking reuses preserved physical semantics and certificate validators and cannot validate real-world assumptions. This completes the fixed extension without changing earlier adverse results or starting another study.

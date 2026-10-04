# Chronology scope and measured impact

This retrospective diagnostic completes the scope reporting for the already
executed [chronology sensitivity](../chronology_consistency/RESULTS.md). It uses
that study's retained worlds, traces, timing changes, and comparison tables;
it does not generate worlds, apply a competing correction, or rerun investigators.
The historical generator and the entire chronology study remain unchanged.

## Complete scope

The saved configuration manifest contains 144 initial benchmark configurations
and 40 missing-receipt configurations. The six-write development counterexample
has one completed context chain that appears in the log before a write where its
source was absent from captured decision state. The saved correction removes that
disagreement. Direct checks over all retained evaluation worlds confirm:

| Cohort / shock | Configurations affected / checked | First-context contradictions / first contexts | Offending receipt chains | Affected writes |
| --- | ---: | ---: | ---: | ---: |
| Benchmark / 0 | 48 / 48 | 728 / 8,300 | 730 | 744 |
| Benchmark / 0.5 | 28 / 48 | 54 / 8,416 | 54 | 54 |
| Benchmark / 0.9 | 0 / 48 | 0 / 8,775 | 0 | 0 |
| Missing receipts / 0.9 | 0 / 40 | 0 / 7,332 | 0 | 0 |

The review's first-context totals match exactly. They count distinct first
source/run installations. The 782 such contradictions differ from the 784
offending chains because two repeated context receipts also require retiming.
They differ from 798 affected writes because one source can disagree at more
than one decision; there are 809 extra source/decision pairs and no missing ones.

All 52,175 request chains satisfy strict source-write, request, delivery when
present, context when present, and owner-write order. This alone does not settle
decision-time consistency. The logs also contain 5,061 successful-chain
request/write pairs where the request precedes a recipient write but the context
has not yet arrived and its source is absent from captured state. Those are
legitimate in-flight observations under the declared timing convention, rather
than completed-context contradictions. No undeclared run-start event is inferred.

The saved quarter-retiming correction changes only the offending receipt chains.
Independent primitive-record checks verify the exact bounds, unchanged identities,
writes, source selections, truth, denominator, and non-time record fields. The
corrected context source set equals captured state at all **66,240 writes**.
The saved primitive RNG counts and final state hashes agree between profiling
and detailed tracing; this pass checks that retained evidence without regenerating
it. All 320 missing-receipt masks retain identical record identities and fractions
between versions.

## Full-grid effect sizes

The retained comparisons cover all 1,440 benchmark evaluations and 1,280
missing-receipt evaluations, grouped into 120 and 64 conditions respectively.
Each benchmark condition uses its 12 original worlds; each missing-receipt
condition uses its 20 original worlds. No configuration, evaluation, or condition
is unavailable. The effects below are **corrected minus legacy**. Group values
are the means of within-world differences, with undefined metrics excluded and
their counts retained.

| Metric | Range across benchmark evaluation rows | Range of benchmark condition means |
| --- | ---: | ---: |
| Predicted edges and false-positive edges | −16 to +27 | −2.333333 to +15.25 |
| True-positive edges and false-negative edges | 0 | 0 |
| Edge precision | −0.001378903 to +0.111111111 | −0.000630335 to +0.020802668 |
| Edge recall, where defined | 0 | 0 |
| False-positive targets | −2 to +12 | −0.666667 to +6.75 |
| False-negative targets | −7 to +1 | −3.833333 to +0.333333 |
| Signed source-using-fraction error | −0.008333333 to +0.038888889 | −0.002777778 to +0.024074074 |
| Absolute source-using-fraction error | −0.008333333 to +0.038888889 | −0.002777778 to +0.024074074 |
| Target disagreement | −0.019444444 to +0.033333333 | −0.001620370 to +0.01875 |

These ranges report the complete published grid rather than selected cells.
The largest row-level absolute fraction-error increase is 3.889 percentage points;
the largest condition mean increase is 2.407 points. The largest precision gain
is 11.111 points for a single evaluation and 2.080 points for a condition mean.
The machine-readable result includes unrounded extrema, deterministic witness
identities, defined/undefined counts, and maxima for each of the 184 worlds.
The pre-existing impact artifact retains every exact condition and evaluation.

There are 186 changed benchmark evaluation rows across 72 configurations. This
does not equal the 76 configurations with chronology defects: four affected
worlds retain the same measured scores. Absolute fraction error increases in 90
rows and decreases in 47; disagreement increases in 61 and decreases in 73.
The high-shock headline remains unchanged. All missing-receipt metrics and paired
policy comparisons remain unchanged. The completed study's fixed 124 claim views
contain no direction reversals, but this does not make all row-level effects
favorable. A request is a run/page gate in the unchanged investigator; moving its
time can admit newer unrelated source candidates. Timing repair therefore does
not imply a subset of previous predictions or uniform attribution improvement.

## Executable diagnostic and limits

Run from the repository root, using the installed environment:

```sh
uv run python -m studies.comparative_validity.chronology_scope --verify studies/comparative_validity/chronology_scope.json
uv run pytest tests/test_comparative_chronology_scope.py
```

[chronology_scope.py](chronology_scope.py) uses the Python standard library and
the released retained data only. It rejects duplicate identities, altered result
bytes, changed stage order, missing or nonconforming corrections, incompatible
captured state, changed target-error arithmetic, wrong group denominators, and
unequal mask survivors. Original freeze pins bind the scientific source files,
full cohort configurations and numerical inputs, and retained development trace.
Unrelated presentation bytes and private preservation files are not required.
Thirteen focused tests cover chronology, input immutability, duplicate identities,
missing or changed original pins, path escapes, null extrema, and the distinction
between ordered receipts and inconsistent write-time availability.
It neither imports nor executes the simulator, investigators, scoring routines,
or correction implementation. This is a separately implemented diagnostic of
saved records and arithmetic, using the same declared physical semantics;
it is not human validation or a new independent simulation experiment.

[chronology_scope.json](chronology_scope.json) records the checked source hashes
and all scope and extrema measurements. Undefined recall in zero-use conditions
remains undefined. The result does not establish physical realism, extrapolate to
unexamined parameters, or change the independent acquisition/audit/joint or model
investigator studies, which were not rerun on corrected stochastic histories.

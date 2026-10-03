# Initial synthetic benchmark results

**These are measured synthetic results, not findings about a real agent incident.**

Question: how well do simple investigators recover realized cross-run source use as shared-channel telemetry is revealed?

Evaluated **144 worlds**, 120 runs and 3 writes per run, 12 independent seeds per scenario. There are 1440 method × telemetry evaluations.

![Telemetry-ablation curves](trace_completeness.png)

## Method

Each fixed world is projected into writes, stable identity, requests, delivery, and channel-context provenance. Both investigators return candidate event-to-event edges; only the evaluator sees truth. All generated writes form the denominator. The input transmission probability is conditional on the generator having context available and is not the realized source-use fraction θ.

Requests can fail, delivered content can be dropped before context, and context content can remain unused. Common scaffolds and same-run repetition can also produce matching content. Temporal proximity is a fixed-lag baseline, not a Hawkes fit.

## Representative measured scenario

Configured transmission probability **0.3**, shared-shock strength **0.9**. Values are seed means with 95% percentile bootstrap intervals (2000 resamples).

| Method | Telemetry | Precision | Recall | Absolute θ error |
|---|---|---:|---:|---:|
| temporal | writes | 0.005 [0.005, 0.006] | 0.981 [0.970, 0.990] | 0.806 [0.793, 0.820] |
| temporal | identity | 0.005 [0.005, 0.006] | 0.981 [0.970, 0.990] | 0.806 [0.793, 0.820] |
| temporal | requests | 0.007 [0.006, 0.007] | 0.981 [0.970, 0.990] | 0.722 [0.708, 0.736] |
| temporal | delivery | 0.147 [0.136, 0.159] | 0.981 [0.970, 0.990] | 0.622 [0.608, 0.637] |
| temporal | context | 0.181 [0.167, 0.196] | 0.981 [0.970, 0.990] | 0.526 [0.509, 0.544] |
| witness | writes | 0.082 [0.069, 0.095] | 0.521 [0.488, 0.552] | 0.065 [0.048, 0.082] |
| witness | identity | 0.089 [0.074, 0.104] | 0.521 [0.488, 0.552] | 0.038 [0.024, 0.052] |
| witness | requests | 0.103 [0.086, 0.120] | 0.521 [0.488, 0.552] | 0.030 [0.019, 0.041] |
| witness | delivery | 0.734 [0.680, 0.786] | 0.521 [0.488, 0.552] | 0.057 [0.044, 0.070] |
| witness | context | 0.753 [0.701, 0.801] | 0.521 [0.488, 0.552] | 0.059 [0.046, 0.072] |

Mean realized θ in this scenario: **0.182**.

## Zero-transmission control

False-attributed target fraction counts writes with a predicted source but no true cross-run source, divided by all writes. Recall is undefined when there are no true edges.

| Method | Telemetry | False-attributed target fraction |
|---|---|---:|
| temporal | writes | 0.989 [0.989, 0.989] |
| temporal | identity | 0.989 [0.989, 0.989] |
| temporal | requests | 0.906 [0.899, 0.912] |
| temporal | delivery | 0.803 [0.794, 0.811] |
| temporal | context | 0.712 [0.698, 0.726] |
| witness | writes | 0.161 [0.145, 0.177] |
| witness | identity | 0.119 [0.105, 0.131] |
| witness | requests | 0.105 [0.094, 0.116] |
| witness | delivery | 0.021 [0.015, 0.027] |
| witness | context | 0.016 [0.012, 0.021] |

## Interpretation and limitations

- Under complete, correct logs, filters preserve true candidates: recall is constant and defined precision cannot decrease. Candidate/false-positive counts shrink **by construction**. These are model invariants, not discoveries. The measured magnitudes and residual errors are the result; absolute θ error can be nonmonotone.
- Context logs describe channel insertions, not hidden source-selection labels or complete harness state. Unused context leaves residual false attribution.
- `tracebench equivalence` verifies two worlds with identical observations at every regime and different source-use truth. Extra exposure logs do not generally identify use.
- Intervals reflect variation across simulated worlds under this generator. They are not valid causal bounds or uncertainty about a real incident. Undefined precision/recall is omitted from means and its defined sample count is stored in JSON/CSV.
- This initial grid uses one generator and fixed investigator thresholds. No real corpus, LLM agent, missing-log process, or adversarial telemetry is validated.
- Synthetic findings should not be described as real-world incident findings in a submission.

## Reproduction and audit

```bash
uv sync --frozen --extra dev
uv run tracebench benchmark --output artifacts/replication --seeds 12 --seed-start 0 --runs 120 --writes-per-run 3 --transmission 0.0,0.1,0.3,0.5 --shocks 0.0,0.5,0.9 --bootstrap-samples 2000
uv run tracebench equivalence
```

`benchmark.json` includes per-seed rows, summaries, generator defaults, seed lists, runtime version and source digest; `runs.csv` and `summary.csv` support independent analysis. `manifest.json` records artifact SHA-256 checksums. Output files are protected against accidental replacement unless `--overwrite` is supplied.

Source digest: `7ba8058cdebc06651c5ce786aeeed753f6683cbd1b0a15c3f7a4e3cdb69c7d71`.

# Evidence card

## What is being measured

This is a synthetic benchmark of source attribution under incomplete telemetry. Its target is the simulator's **realized source-use relation**: an output uses a prior output from another stable run through the simulated shared channel. The evaluator's hidden labels record that choice.

Every generated write is eligible, including initial writes with no predecessor. An edge joins a source write to a target write, and a target has at most one selected cross-run source. Same-run repetition is excluded from ground-truth transmission. The target fraction is `theta = number of targets with a selected cross-run source / number of all writes`.

Realized source use is different from counterfactual necessity. A source can be used even when an alternative source or a common task would produce the same output. The benchmark does not establish what would happen if that source were removed from a real agent's context.

The same generated world is projected into five nested regimes. Estimators see only their projection; stable identities and source-use labels remain separate where unavailable.

| Regime | Additional observable evidence | What it still does not reveal |
| --- | --- | --- |
| Writes only | Recorded timestamps, content, page, and disposable handles | Stable run attribution, access, and hidden source use |
| Stable identity | Mapping of writes to stable runs | Whether a preceding source was requested or used |
| Requests | Attempts to access a compatible earlier source | Successful delivery and use |
| Delivery | Whether requested content was delivered | Whether the delivered content was selected for the output |
| Channel context provenance | Which delivered shared-channel sources entered the run's context | Other task/scaffold inputs, the selected source-use label, and counterfactual necessity |

The temporal baseline proposes same-page predecessors within a fixed time window; it is not a Hawkes fit. The witness investigator proposes pairs sharing an exact witness token. Both methods apply additional identity/access filters when those fields are observable. Requests identify a requesting stable run, page, and time; delivery and context records identify source events. Context sources can persist across outputs and many remain unused. Responses are inserted completely or dropped; token-level partial truncation is not modeled. Witnesses can be copied, omitted during reuse, or independently emitted from a shared scaffold.

This baseline uses complete, noiseless logs at each revealed telemetry level. Every true candidate edge has compatible request, delivery, and context records. Successive filters therefore preserve true positives and recall, while predicted edge counts and false-positive edge counts cannot increase. Wherever precision is defined for a world at both levels, it cannot decrease. These directions are consequences of the model and estimator design, not empirical discoveries.

The temporal window and omitted witness reuse can miss true edges before filtering begins; revealing telemetry does not recover those missed edges. The estimated target fraction `theta_hat` decreases or stays constant as candidates are removed, but its absolute error can increase or decrease as it moves toward or away from the true fraction. Missing or corrupted telemetry could remove true candidates; that stress test is not implemented here.

## Evidence and reproducibility

The experiment includes zero-transmission worlds as a negative control and worlds with nonzero transmission. Scores compare predicted event-to-event edges to the hidden relation:

| Metric | Definition |
| --- | --- |
| Precision | Correct predicted edges / predicted edges; undefined when no edges are predicted |
| Recall | Correct predicted edges / true edges; undefined when no true edges exist |
| Estimated target fraction, `theta_hat` | Targets with at least one predicted edge / all writes |
| Absolute error | `abs(theta_hat - theta)` |
| False-attributed target fraction | Predicted targets with no true cross-run source / all writes |
| False-positive edges per target | Incorrect predicted edges / all writes |

The false-attributed target fraction does not count a wrong source assigned to a target that has some true source; edge precision and false-positive edges capture that error. An estimator can also obtain a good aggregate `theta_hat` while getting source edges wrong. These metrics must be considered together. Undefined precision or recall should not be read as zero performance.

Fixed random seeds and identical latent worlds across regimes make comparisons reproducible and paired. The report uses 95% percentile bootstrap intervals over independent world seeds, with 2,000 resamples and counts of defined values. Repetition over seeds measures simulation variability. It does not quantify uncertainty about the behavior of deployed LLM agents or the completeness of an incident dataset.

The generated report at [`results/REPORT.md`](results/REPORT.md) is the source for measured values. The experiment also writes `benchmark.json`, `runs.csv`, `summary.csv`, figures, and `manifest.json` into that directory. It should be read alongside `CLAIMS.md`, the actual experiment configuration, and `LIMITATIONS.md`.

In the initial synthetic study at transmission parameter `0.3` and shared-wave strength `0.9`, mean witness precision rises from `0.082` with writes only to `0.753` with context, while mean recall stays at `0.521`. Mean absolute target-fraction error rises from `0.030` with requests to `0.059` with context. These are simulation outcomes across 12 seeds, not incident measurements; the report supplies intervals. They illustrate that better edge precision need not produce a better aggregate target-fraction estimate.

Reproduce the initial study from the repository root:

```sh
uv sync --frozen --extra dev
uv run tracebench benchmark --output artifacts/replication --seeds 12 --runs 120
```

The command preserves the checked-in `results/` artifacts. If the replication directory already contains outputs, choose another directory or explicitly pass `--overwrite`.

The default sweep uses three writes per run, transmission probabilities `0`, `0.1`, `0.3`, and `0.5`, and shared-wave strengths `0`, `0.5`, and `0.9`. The parameter configuration controls the probability of selecting a source; it is not itself the realized `theta`.

## Data and source status

The core benchmark requires no real agents, API credentials, private logs, or external incident data. The real wiki case study is a scaffold only; see `case_study/README.md`. Literature claims and source-verification status are recorded in `docs/RELATED_WORK.md`.

## Supported conclusion

The experiment can establish how the implemented investigators perform under the implemented simulation and observation rules. It can illustrate why temporal proximity or exposure evidence alone may misattribute a source. It cannot certify that a particular telemetry regime identifies transmission in every possible swarm, prove collusion, or establish an optimal logging policy.

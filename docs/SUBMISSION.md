# Trace Completeness Curves

**Question:** What can a swarm's recorded activity establish about which agent used information from another?

This project benchmarks source attribution when investigators have incomplete logs. A lightweight simulator generates runs with shared tasks, synchronized activity, disposable handles, and occasional content reuse. It records which prior output was actually selected as a cross-run source, while keeping that label hidden from the investigators.

The same world is then viewed through five progressively richer observation regimes: writes, stable run identity, requests, successful delivery, and channel context provenance. A temporal-proximity baseline and a witness-reuse investigator propose source-to-target edges. The evaluator measures edge precision and recall, error in the attributed target fraction, and false attribution in zero-transmission controls. More telemetry filters candidates, so falling raw edge counts alone are not evidence of better attribution.

The main output is a reproducible synthetic experiment, with results and a trace-completeness figure in [`results/REPORT.md`](../results/REPORT.md). A local evidence explorer lets readers compare methods and observation regimes. The initial study finds, at transmission parameter `0.3` and shared-wave strength `0.9`, that mean witness precision rises from `0.082` with writes only to `0.753` with context, while mean recall remains `0.521`. Mean absolute target-fraction error rises from `0.030` with requests to `0.059` with context. The report includes intervals across 12 simulated world seeds. These are synthetic outcomes, not real incident results.

The distinction between metrics matters: better edge precision need not produce a better estimate of how many outputs used another run's content. In this complete, noiseless logging baseline, all true candidates survive telemetry filters, so true-positive counts and recall are constant and defined precision cannot decrease. Those directions are structural. The magnitude of errors, remaining false attributions, and nonmonotonic target-fraction error are measured. Missing or corrupted telemetry that could remove true candidates remains an unimplemented extension.

The key distinction is between **a source being present** and **a source being used**. Context provenance does not expose the hidden selection label. Even a correct source-use attribution does not establish that the source was counterfactually necessary: another source or a shared task might have produced the same output.

This is a measurement experiment relevant to information-spread tracing and digital forensics. It is not a field-validated collusion detector or a causal reconstruction of a real incident. The proposed wiki case study remains a scaffold pending verification of source data and permissions. See [`EVIDENCE_CARD.md`](../EVIDENCE_CARD.md), [`LIMITATIONS.md`](../LIMITATIONS.md), and [`docs/RELATED_WORK.md`](RELATED_WORK.md) for the precise evidence boundary.

Code: <https://github.com/yvrohith/Agent-swarm>

Reproduce the initial study:

```sh
uv sync --frozen --extra dev
uv run tracebench benchmark --output artifacts/replication --seeds 12 --runs 120
```

Use a new directory for a repeat run, or explicitly pass `--overwrite` to replace prior replication outputs.

This draft and the repository link address the required write-up/video and code-link deliverables in the official-page excerpt supplied by the user; see [`docs/HACKATHON.md`](HACKATHON.md) for source status. Preparing the draft does not submit the project to the competition or deploy the demo.

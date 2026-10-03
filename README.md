# Trace Completeness Curves

**Question:** What can a swarm log establish about cross-agent information flow?

**Method:** Generate synthetic swarms with known realized source-use edges, hide telemetry,
and measure the errors of temporal-proximity and witness-reuse investigators.

**Initial result:** In the high-shock scenario (`p=0.3`), witness precision rises from
8.2% with writes to 75.3% with channel-context records, at 52.1% recall throughout.
Yet its target-fraction error increases from 0.030 with requests to 0.059 with context.
These are synthetic results: correct, complete logs preserve true candidates by design.

**Implication:** Better source-edge precision need not improve an aggregate source-use
estimate, and exposure records still leave attribution ambiguity.

![Initial telemetry-ablation results](results/trace_completeness.png)

This repository is an initial research implementation. Exposure is not source use, and
source use is not counterfactual causal necessity. See [CLAIMS.md](CLAIMS.md).

## Reproduce

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required for the locked workflow.

```bash
uv sync --frozen --extra dev
uv run pytest
uv run tracebench benchmark --output artifacts/replication --seeds 12 --runs 120
uv run tracebench equivalence
```

The curated initial run is in [results/REPORT.md](results/REPORT.md). Generated raw
experiments belong in ignored `artifacts/`; only deliberately selected, non-sensitive
research evidence belongs in `results/`.

## Explore the evidence

```bash
uv run python -m http.server 8000 --bind 127.0.0.1
```

Open the `/demo/` path on that local server. The static explorer reads the curated
`results/benchmark.json`, makes no external requests, and does not run new experiments.

## Research artifacts

- [Claims and analysis specification](CLAIMS.md)
- [Evidence card](EVIDENCE_CARD.md) and [limitations](LIMITATIONS.md)
- [Hackathon deliverables and verification status](docs/HACKATHON.md)
- [Related work and source status](docs/RELATED_WORK.md)
- [German-wiki case-study status](case_study/README.md)

The supplied competition requirements call for a short write-up or video and the code
repository, with real-world results optional. See the [submission write-up](docs/SUBMISSION.md).
No detailed judging rubric was supplied; the deadline and submission portal still need
verification. The work here is local and has not been submitted or published.

# Trace Completeness Curves

Trace Completeness Curves tests what incomplete agent logs can establish about
information flow. The project brings together three completed studies:

- **[Synthetic source-attribution benchmark](results/REPORT.md):** Measure attribution
  errors against known realized source-use edges as different telemetry types become
  available.
- **[Missing-receipt stress test](studies/missing_receipts/results/REPORT.md):** Erase
  observable records from fixed worlds. Preserving exposure evidence can recover true
  source candidates, but can also increase false attribution; the tradeoff depends on
  the investigator's candidate selection.
- **[Public-wiki case study](studies/wiki_case_study/REPORT.md):** Audit 13,403 DSE
  revisions. Under the frozen comparison rule, 7,380 of 10,520 eligible snapshot
  reference pairs (70.15%) contain only inherited references. This describes recorded
  text; exposure remains unknown and source use unobserved.

Exposure is not source use, and source use is not counterfactual causal necessity.
See the [initial benchmark's claims and analysis specification](CLAIMS.md) and each
study's report for its scope and limitations.

## Initial synthetic benchmark

Generate synthetic swarms with known realized source-use edges, hide telemetry types,
and measure the errors of temporal-proximity and witness-reuse investigators.

**Initial result:** In the high-shock scenario (`p=0.3`), witness precision rises from
8.2% with writes to 75.3% with channel-context records, at 52.1% recall throughout.
Yet its target-fraction error increases from 0.030 with requests to 0.059 with context.
These are synthetic results: correct, complete logs preserve true candidates by design.

**Implication:** Better source-edge precision need not improve an aggregate source-use
estimate, and exposure records still leave attribution ambiguity.

![Initial telemetry-ablation results](results/trace_completeness.png)

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

## Missing-receipt follow-up

The [follow-up protocol](studies/missing_receipts/ANALYSIS.md) separates omitted
telemetry **types** from missing **records** within a logged type. It erases delivery
or context receipts after generating each world, preserving the simulator and truth.
An evidence-aware comparison policy reports unknown exposure separately from
heuristic predictions. This is a review-informed stress test, not a preregistered discovery.

```bash
uv run tracebench receipt-study --config studies/missing_receipts/config.json \
  --output artifacts/missing-receipts-replication
```

See its [paired results and recall figure](studies/missing_receipts/results/REPORT.md).
The original `results/` files and `CLAIMS.md` remain unchanged and refer to baseline
commit `36be8fa`; their recorded source digest describes that historical version.

## Public-wiki evidence audit

The separate [descriptive case study](studies/wiki_case_study/results/REPORT.md)
compares cumulative snapshot references with newly inserted references in a pinned
public German-wiki export. It keeps observed handles, unavailable source-read
receipts, unknown exposure and unobserved source use distinct. It does not evaluate
real-data attribution accuracy or estimate copying. Raw downloads remain ignored.
See [source provenance and reproduction](case_study/README.md) and the
[frozen analysis rules](studies/wiki_case_study/ANALYSIS.md).

```bash
uv run tracebench wiki-audit --archive data/raw/wiki/full-wiki-logs.zip \
  --other-wikis data/raw/wiki/other-wikis.json.gz \
  --protocol studies/wiki_case_study/ANALYSIS.md --output artifacts/wiki-replication
```

## Initial synthetic benchmark explorer

```bash
uv run python -m http.server 8000 --bind 127.0.0.1
```

Open the `/demo/` path on that local server. Its charts cover only the initial synthetic
benchmark, using the curated `results/benchmark.json`. The static explorer makes no
external requests and does not run new experiments. Read the separate
[missing-receipt report](studies/missing_receipts/results/REPORT.md),
[public-wiki report](studies/wiki_case_study/REPORT.md), and
[wiki evidence cards](studies/wiki_case_study/results/REPORT.md#source-linked-evidence-cards)
for the completed follow-up studies.

## Research artifacts

- [Claims and analysis specification](CLAIMS.md)
- [Evidence card](EVIDENCE_CARD.md) and [limitations](LIMITATIONS.md)
- [Hackathon deliverables and verification status](docs/HACKATHON.md)
- [Related work and source status](docs/RELATED_WORK.md)
- [German-wiki case-study status](case_study/README.md)

The verified competition requirements call for a short write-up or video and the code
repository, with real-world results optional. See the [submission write-up](docs/SUBMISSION.md).
The official deadline is Sunday, October 4, 2026, at **8 p.m. Eastern / 5 p.m. Pacific**.
The [official logistics and submission link](docs/HACKATHON.md) are recorded; exact form
limits and terms remain unverified because the form returned HTTP 403. No detailed
scoring rubric appears on the checked pages.

# Trace Completeness Curves

Trace Completeness Curves is a research prototype for examining what recorded
agent-swarm activity supports about information flow. It combines controlled
synthetic benchmarks, a descriptive public-wiki audit, and bounded model-investigator
evaluations. Recorded exposure is not verified source use, and neither establishes
counterfactual causal influence.

**Author: Rohith YV.** Start with the [current research synthesis](docs/FINAL_SUBMISSION.md).
The [verification guide](docs/REVIEWER_GUIDE.md) maps its claims to released evidence
and states which checks require retained local inputs.

## Supported findings

- **Synthetic attribution:** In the reported high-shock condition, more complete
  telemetry improves witness-based source-edge precision while worsening absolute
  error in the estimated source-using fraction. Target disagreement improves; these
  are different error measures. A complete [chronology sensitivity](studies/chronology_consistency/RESULTS.md)
  changes 186 of 1,440 benchmark evaluation rows, but leaves this headline and all
  1,280 missing-receipt evaluations unchanged. The correction preserves simulator
  decisions; it does not establish physical realism.
- **Synthetic logging loss:** Keeping authentic context receipts after upstream
  records disappear improves recall, but can increase false attribution. At half
  delivery-record retention, target disagreement improves for witness reuse and
  worsens for temporal proximity. [Paired results](studies/missing_receipts/results/REPORT.md)
  retain both outcomes. Exposure remains a source candidate, not verified source use.
- **Recorded wiki text:** Under the fixed literal rule, 7,380 of 10,520 eligible
  snapshot reference pairs contain only inherited references. The audit covers
  13,403 revisions with publisher dataset site label `dse`, called **DSE** here;
  this is a site label, not an inferred agent identity. These real-export
  [measurements](studies/wiki_case_study/REPORT.md) do not establish exposure,
  copying, or source use.
- **Model investigators:** The requested aliases were `openai/gpt-5.6-terra`
  (**Terra**) and `anthropic/claude-sonnet-5.5` (**Sonnet**). The
  [utility pilot](studies/investigator_utility/openrouter_v1/results/REPORT.md)
  does not establish a general reasoning benefit from provenance assistance:
  Terra is at ceiling, and Sonnet's score differences concern response acceptance.
  The separate [responsiveness study](studies/evidence_responsiveness/results/REPORT.md)
  contains one verified Terra inconsistency in controlled wiki fixtures. Sonnet's
  rejected serializations are not demonstrated incorrect evidence judgments.

The exploratory finite acquisition and audit analyses are linked from the synthesis.
They study retrieval costs under fully supplied hypothetical models, not measured
improvements in real swarm investigations. The [comparative validity correction](studies/comparative_validity/REVIEW.md)
finds lower mean original-prior cost for competent schema-skipping and terminal-class
information baselines than for the historical EC2 pair-cut heuristic. Exact planning
retains a finite-model advantage against corrected audit controls. Historical results
remain preserved.

## Tests and result verification

The locked development workflow requires Python 3.11+, `uv`, and a Git checkout
with full public history for historical provenance tests:

```sh
uv sync --frozen --extra dev
uv run pytest
uv run ruff check .
```

These run the repository tests; they do not rerun model evaluations or download wiki
records. The source distribution remains `src/tracebench`; research scripts under
`studies/` are repository code. See the [verification guide](docs/REVIEWER_GUIDE.md)
for the clean-checkout scope, dependency-cache requirements, and public-results
checks. Local verification is not a new remote CI result.

## Reproducing the synthetic measurements

Use fresh ignored output directories; do not overwrite curated results:

```sh
uv run tracebench benchmark --output artifacts/replication --seeds 12 --runs 120
uv run tracebench equivalence
uv run tracebench receipt-study --config studies/missing_receipts/config.json \
  --output artifacts/missing-receipts-replication
```

These commands use the preserved legacy generator. The separate
[chronology analysis](studies/chronology_consistency/RESULTS.md) supplies its frozen
state-preserving sensitivity and exact impact tables. Missing telemetry types and
missing records within a type are separate experiments.

Wiki reanalysis additionally requires the pinned publisher files retained outside
Git; [source provenance](case_study/README.md) records the required files and hashes.
No real-data source-use accuracy is claimed. Model response rescoring and local
preservation have different input requirements, described in the verification guide.

## Research records

- [Current synthesis](docs/FINAL_SUBMISSION.md), [verification guide](docs/REVIEWER_GUIDE.md),
  and [related work](docs/RELATED_WORK.md).
- [Current comparative validity corrections](studies/comparative_validity/REVIEW.md).
- Historical: [original submission](docs/SUBMISSION.md), [initial analysis specification](CLAIMS.md),
  [initial benchmark report](results/REPORT.md), and each study's frozen protocol and results.

Historical reports remain available as dated records. Current corrections are
additive; they do not silently revise earlier estimates or claims.

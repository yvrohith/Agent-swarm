# Bounded investigator-utility study

This addition tests whether deterministic provenance assistance improves an AI
investigator beyond the same raw evidence and a strong checklist. The primary
comparison is C minus B; raw evidence alone (A) is secondary. It concerns justified
conclusions, not guesses about hidden simulator source selection.

**Status: prepared and validated; investigator execution blocked.** No authorized
metered model API or verified model/pricing configuration is available in this
workspace. No model observations, paired utility estimates or measured successful
examples exist. The [report](results/REPORT.md) keeps model results empty and labels
constant-answer calculations as analytic sanity checks. This is not a completed
experiment and does not establish additional investigator utility.

The evaluation has 16 fixed wiki windows and 8 synthetic cases; 4 additional cases
are development-only. Wiki cases preserve full relevant before/after/source texts,
exclude previously inspected endpoint pages, and share no page histories across
cases or splits. The 96 evaluation claims comprise 54 answerable and 42 unresolved
claims. Always-unresolved has zero warranted-answer accuracy. The three completed
studies, main README and submission are unchanged.

## Artifacts

- [Analysis protocol](ANALYSIS.md) and [configuration](config.json).
- [Frozen case IDs](frozen/case_manifest.json), [selection rules and exclusions](frozen/selection.json),
  [public-view/prompt hashes and size bounds](frozen/view_manifest.json), and
  [evaluator-only gold certificates](frozen/gold_certificates.json).
- [Blocked execution freeze](frozen/freeze.json), [case validation](frozen/validation.json),
  and [baseline preservation hashes](preservation.json).
- [Report](results/REPORT.md), [per-case model scores](results/per_case_scores.json),
  [paired summaries](results/paired_summary.json), and [execution status/cost](results/execution.json).

Gold certificates are evaluator-only: the runner reads public case views and never
places these certificates in an investigator request. Full wiki texts, exact model
prompts and raw completions stay in ignored `artifacts/`. No new raw corpus is
redistributed. Leakage checks and label checks are mechanical/AI-assisted, not
independent human validation.

## Reproduce preparation and checks

Use the locked environment (`uv sync --frozen --extra dev`). The already documented
pinned ZIP and supplement belong in `data/raw/wiki/`; the existing wiki loader
verifies their checksums. No second upload or new dataset is required.

```sh
uv run python -m tracebench.investigator_utility prepare \
  --prepared artifacts/investigator-utility/prepared
uv run python -m tracebench.investigator_utility validate
uv run python -m tracebench.investigator_utility develop
uv run pytest
uv run ruff check .
```

Preparation reuses the original full-corpus extractor and can take several minutes.
It writes a fresh directory and never overwrites a prepared case set. `develop`
validates all cases and saves the twelve development prompts. Without authorized
models it records a blocker, makes zero API calls, and supplies no mock answers.
For a fresh reproduction use a fresh `--prepared` and development `--output` path,
passing the prepared path consistently to subsequent commands.

## Freeze, execution and reporting

```sh
uv run python -m tracebench.investigator_utility access
uv run python -m tracebench.investigator_utility freeze
uv run python -m tracebench.investigator_utility run
uv run python -m tracebench.investigator_utility report
```

These commands also refuse to overwrite freezes/results. The supplied freeze has
no models and explicitly permits zero investigator calls. It freezes cases,
prompts, scoring and selection; it is not represented as a completed model choice.
The `run` command records the exact blocker, and `report` produces empty model
tables plus clearly separate analytic baselines.

If authorized access becomes available, inspect supported exact model IDs and
official pricing/limit documentation before creating a **new versioned** execution
configuration/freeze. Preserve the blocked preparation and do not replace cases
after seeing outcomes. One family permits a 72-request pilot; two different
families permit 144 evaluation requests. At most 24 development requests and 12
additional transport retries share the USD 25 ceiling or a lower authorized limit.
Never paste credentials into case files, configuration, commits or chat; use the
environment's secret configuration.

Each model entry must supply the fields checked by
[`execution.py`](../../src/tracebench/investigator_utility/execution.py): provider,
exact model ID/family and official endpoint, credential-variable name, enforced
context/output/reasoning limits, supported decoding, official price/limit sources
and their verified hashes/timestamp, input-token upper-bound contract, and access
authorization. Setting verification flags is not a substitute for checking those
documents. No current model IDs or prices have been guessed here.

All development/evaluation/resume calls use one fixed ignored ledger at
`artifacts/investigator-utility/calls/`. The runner reserves maximum possible cost
before each attempt, retains unknown-cost failed reservations, and never retries
for an invalid or unfavorable answer. It preserves the first completed response.
Changing an output directory cannot reset the budget. Results use the frozen
schedule and current ledger; stale execution snapshots are rejected. Invoices may
be unavailable, in which case regular-price usage estimates are labeled and the
actual total cost stays unknown. Zero attempts means an actual cost of USD 0.

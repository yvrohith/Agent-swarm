# Bounded investigator-utility study

This completed study tests whether deterministic provenance assistance improves an AI
investigator beyond the same raw evidence and a strong checklist. The primary
comparison is C minus B; raw evidence alone (A) is secondary. It concerns justified
conclusions, not guesses about hidden simulator source selection.

**Status: completed in the [versioned OpenRouter pilot](openrouter_v1/README.md).**
Two model aliases completed 144 evaluation calls on 24 fixed cases, following
24 development calls. The pilot does not establish a general reasoning advantage:
Terra was at ceiling, and Sonnet's observed differences concern response-contract
reliability, not correction of wrong schema-valid conclusions. Sonnet's wiki
warranted-answer accuracy was 93.75% in A, 75% in B and 93.75% in C. C−B remains
primary; its advantage does not extend to the secondary C−A wiki comparison.
Zero schema-valid unjustified certainty does not count invalid answers as safe
abstentions: Sonnet's synthetic certainty-or-invalid rate is 40% in both B and C.

The separate [retrospective diagnostic](../review_remediation/utility_diagnostic.json)
checks all 144 saved evaluation responses under gold-blind extraction and field
normalization. It recovers 12 of Sonnet's 18 rejected responses; two multi-object
responses and four refusals remain failures. Synthetic pooled answerable-claim
counts are A 19/22, B 18/22 and C 22/22, with case means 6/7, 6/7 and 1; wiki
counts are 30/32, 28/32 and 30/32. C's nonexistent wiki citation remains an error.
These are post-hoc sensitivity calculations, not repaired primary scores.
The saved requests did not request native JSON-schema enforcement, and no
schema-enforced rerun was measured.

Read the [completed report](openrouter_v1/results/REPORT.md),
[submission addendum](openrouter_v1/SUBMISSION_ADDENDUM.md), and
[visible responses with offline score verification](openrouter_v1/response_evidence/README.md).
The blocked preparation is documented separately below; it is not the current
execution status.

The evaluation has 16 fixed wiki windows and 8 synthetic cases; 4 additional cases
are development-only. Wiki cases preserve full relevant before/after/source texts,
exclude previously inspected endpoint pages, and share no page histories across
cases or splits. The 96 evaluation claims comprise 54 answerable and 42 unresolved
claims. Always-unresolved has zero warranted-answer accuracy. The original three
studies and all frozen protocols and numerical results remain unchanged.

## Completed-run artifacts

- [Analysis protocol](ANALYSIS.md) and [execution configuration](openrouter_v1/config.json).
- [Frozen case IDs](openrouter_v1/frozen/case_manifest.json),
  [selection rules and exclusions](openrouter_v1/frozen/selection.json),
  [public-view/prompt hashes](openrouter_v1/frozen/view_manifest.json), and
  [evaluator-only gold certificates](openrouter_v1/frozen/gold_certificates.json).
- [Execution freeze](openrouter_v1/frozen/freeze.json) and
  [case validation](openrouter_v1/frozen/validation.json).
- [Completed report](openrouter_v1/results/REPORT.md),
  [per-case model scores](openrouter_v1/results/per_case_scores.json),
  [paired summaries](openrouter_v1/results/paired_summary.json), and
  [execution accounting](openrouter_v1/results/execution.json).
- [Current score verification](openrouter_v1/response_evidence/README.md).

Gold certificates are evaluator-only: the runner reads public case views and never
places these certificates in an investigator request. Full wiki texts, exact model
prompts and full provider responses stay in ignored `artifacts/`. The separately
authorized response-evidence release contains the exact visible answers and
refusals, with no provider reasoning or raw corpus records. Leakage checks and
label checks are mechanical/AI-assisted, not independent human validation.

## Historical preparation and checks

The original [blocked report](results/REPORT.md), [configuration](config.json),
[blocked freeze](frozen/freeze.json), [case validation](frozen/validation.json),
[empty model tables](results/per_case_scores.json) and
[historical preservation hashes](preservation.json) describe the preparation
before the completed OpenRouter run. They remain unchanged.

The commands below describe the original preparation at commit `0bb581e9`.
The historical whole-checkout preservation check also pins the old main README
and submission; it deliberately rejects their later presentation updates. No
manifest or guard has been weakened. For current offline reproduction of the
completed scores, use the [response-evidence verifier](openrouter_v1/response_evidence/README.md).
Reconstructing full input evidence requires the pinned source release and the
historical checkout; the published scoring views alone do not validate the gold.

Use the locked environment (`uv sync --frozen --extra dev`). The already documented
pinned ZIP and supplement belong in `data/raw/wiki/`; the existing wiki loader
verifies their checksums.

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

## Historical freeze, execution and reporting

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

Authorized access was subsequently verified and the **versioned**
[OpenRouter execution freeze](openrouter_v1/frozen/freeze.json) was saved before
evaluation. The blocked preparation was retained and no cases were replaced.
The completed execution used both families, 24 development requests and 144
evaluation requests, with no retries. It retained the USD 25 whole-study ceiling.
This historical workflow is not an instruction to rerun or expand the experiment.

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

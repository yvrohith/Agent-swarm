# Bounded evidence-responsiveness audit

This separate exploratory study asks whether an investigator answers correctly when decisive evidence changes and stays correct when an irrelevant detail changes. It preserves the completed utility pilot's ceiling, null, adverse, and response-contract findings. The [completed report](results/REPORT.md) and [submission addendum](SUBMISSION_ADDENDUM.md) give the actual results; this guide documents validation and access requirements.

The fixed design has **eight receipt and four controlled wiki-derived evaluation families**, plus one development family per substrate. Each family has three independently presented variants: base, irrelevant change, and decisive change. The three primary outcomes require correct answers to both members of the decisive pair, both members of the invariant pair, or all three family members. Receipt and wiki-derived outcomes and models remain separate. Altered wiki-derived text is a controlled fixture, not a historical observation.

The baseline is `88ad3cb7e10fe82a15e8c30400ea780b370663d3`. The isolated implementation is in [`src/tracebench/evidence_responsiveness/`](../../src/tracebench/evidence_responsiveness/), with [analysis rules](ANALYSIS.md), [configuration](config.json), and [preservation hashes](preservation.json). Historical scientific files, frozen results, and raw outputs retain their recorded bytes. The preservation policy permits only the two project entry points to receive actual-result links after reporting; historical hashes remain recorded.

## Local checks without investigator calls

Run from the repository root in the installed locked environment. `--offline` prevents dependency downloads; it requires dependencies already installed. The cache location below works in the cloud workspace.

```sh
export UV_CACHE_DIR=/tmp/tracebench-uv-cache
uv run --frozen --offline python -m tracebench.evidence_responsiveness validate
uv run --frozen --offline python -m tracebench.evidence_responsiveness preflight
```

`validate` recomputes certificates, family relationships, metadata invariance, constant-status controls, and historical preservation. It needs the exact prepared files in ignored `artifacts/evidence-responsiveness/prepared/`. `preflight` verifies the recorded model configuration and computes the complete schedule's conservative cost against the **cumulative** ceiling, including the historical utility ledger and unresolved reservations. Neither command issues investigator calls; preflight is not a live provider-access test.

`prepare` is a separate no-call construction step requiring the pinned wiki inputs and previous selection manifests. It writes the fixed ignored prepared directory and refuses to replace it. Do not remove or regenerate an existing selected study to make a check pass. The [wiki source guide](../../case_study/README.md) records original data provenance.

## Execution and report lifecycle

The CLI phases are `prepare`, `validate`, `preflight`, `develop`, `freeze`, `run`, and `report`. **`develop` and `run` can issue billable investigator calls.** They are not part of the offline checking instructions. The separate development families precede the evaluation freeze; the evaluation uses the frozen schedule once. Existing phase records, freezes, prepared cases, and results are not overwritten.

Once an authorized run has finished, the following command scores its retained first responses and writes the report without new investigator calls:

```sh
uv run --frozen --offline python -m tracebench.evidence_responsiveness report
```

`report` requires the fixed prepared files, exact local request/response records, shared accounting history, evaluation snapshot, and matching freeze. It refuses an existing `results/` directory. Do not delete curated outputs to rerun it.

## Verify saved response scores offline

After results exist, an authorized reviewer with the ignored artifacts can compare freshly parsed first responses with saved per-variant scores. This reads local files and prints only the number of checked rows; it does not expose response text, repair answers, or call a model.

```sh
uv run --frozen --offline python - <<'PY'
import json
from tracebench.evidence_responsiveness.__main__ import (
    FROZEN, RAW, STUDY, inputs, requests, verify_frozen,
)
from tracebench.evidence_responsiveness.common import file_hash, read
from tracebench.evidence_responsiveness.scoring import score_variant

verify_frozen()
execution = read(STUDY / "results/execution.json")
ledger = RAW / "calls/attempts.jsonl"
assert file_hash(ledger) == execution["ledger_sha256"]
cases, golds, families = inputs()
by_case = {case["case_id"]: case for case in cases}
by_gold = {gold["case_id"]: gold for gold in golds}
completed = {}
for line in ledger.read_text().splitlines():
    event = json.loads(line)
    if event["event"] == "attempt_completed":
        completed.setdefault(event["attempt_key"], event)
rows = []
for request in requests(cases, families, read(FROZEN / "config.json")):
    event = completed.get(request["attempt_key"])
    saved = read(RAW / "calls" / event["response_file"]) if event else {}
    choice = (saved.get("raw_response", {}).get("choices") or [{}])[0]
    rows.append(score_variant(
        by_case[request["case_id"]], by_gold[request["case_id"]],
        saved.get("completion_text"), request["model_id"], choice.get("finish_reason"),
        refused=bool(choice.get("message", {}).get("refusal")),
    ))
assert rows == read(STUDY / "results/per_variant.json")
print(f"Verified {len(rows)} saved variant-score rows; no investigator calls.")
PY
```

## Artifact access and interpretation

The expected completed-run outputs are [REPORT.md](results/REPORT.md), [per-variant scores](results/per_variant.json), [per-family scores](results/per_family.json), [summary](results/summary.json), [controls](results/baselines.json), [examples](results/examples.json), [execution accounting](results/execution.json), and [response hashes](results/response_manifest.json). These paths describe the output contract; their presence and execution status, not this guide, establish completion. The [submission addendum](SUBMISSION_ADDENDUM.md) interprets the completed run without revising earlier studies.

Full exact requests, completions, provider-private reasoning, fixture texts, transformation provenance, and evaluator-only certificates remain in ignored local artifacts under the release rules. Investigator prompts receive the complete fixture texts and declared assumptions. Family linkage, transformation roles, source provenance, and gold certificates never enter those prompts. Public manifests and hashes identify records; **hashes do not provide access to their contents**. Public score tables permit inspection and reaggregation, but full response rescoring requires authorized access to the retained artifacts. Nothing here authorizes publishing raw records or responses.

Families are the measurement units: 72 planned evaluation calls across two models are not 72 independent problems. Whole-family/history bootstrap intervals describe these small fixed strata. All-pass or all-fail zero-width intervals do not establish generalization certainty. Valid evidence IDs do not prove semantic support or private reasoning faithfulness; gold and leakage checks are mechanical/AI-assisted, with no independent human validation claimed.

## Historical document pins

The [post-report presentation record](presentation_update.json) lists the two entry-point updates and their before/after hashes. The report’s preservation snapshot was taken before these edits; the current check retains 136 scientific/other tracked files and 415 historical raw files byte-for-byte while explicitly listing the two changed entry points. The earlier utility response verifier successfully checked all 168 saved responses before these edits. Its unchanged manifest also pins its historical root README/submission text, so that whole-document check belongs to baseline `88ad3cb7e10fe82a15e8c30400ea780b370663d3` and rejects these later documentation edits. Neither its checks nor historical manifests were weakened or rewritten.

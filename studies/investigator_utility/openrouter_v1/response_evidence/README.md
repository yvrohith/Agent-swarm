# Investigator response evidence

This post-evaluation release makes the completed pilot's **168 first responses**
inspectable: 24 development and 144 evaluation calls. No response was repaired,
replaced, retried or selected for release based on its result. The original
protocol, freeze, scorer, ledger and numerical results are unchanged.

The pilot does not establish a general reasoning advantage. See the
[current synthesis](../../../../docs/FINAL_SUBMISSION.md), [study summary](../README.md)
and [completed report](../results/REPORT.md) for the primary C−B comparison,
secondary raw-evidence comparison, failures and uncertainty.

The separate [retrospective diagnostic](../../../review_remediation/utility_diagnostic.json)
applies one gold-blind extraction/field-mapping rule across all 144 evaluation
responses. It recovers 12 of Sonnet's 18 strict failures, retaining two ambiguous
multi-object outputs and four refusals. It neither rewrites this bundle nor changes
the primary scorer. Correct diagnostic statuses do not validate their reasoning,
and the remaining citation error is preserved.

## Contents and boundaries

- [responses.jsonl](responses.jsonl): one record per retained call, containing
  case, split, arm, requested and returned model identity, provider, termination,
  timestamps, cost metadata, provenance hashes, exact visible completion and
  refusal text, and the unchanged scorer's output. Development is explicitly
  separated from evaluation and never enters the reported evaluation estimates.
- [scoring_cases.json](scoring_cases.json): the 28 case identities, clusters,
  claim texts and allowed evidence IDs needed by the mechanical scorer. These
  are **minimal scoring views**, not the full evidence supplied to investigators.
- [manifest.json](manifest.json): historical hashes of the bundle and its frozen code,
  certificates and result dependencies, with the original execution commit
  `0bb581e9b9debaf1160754931964ab90dc3b9702`.
- [verify_scores.py](verify_scores.py) and
  [scoring_manifest_v2.json](scoring_manifest_v2.json): current, versioned
  verification of scoring dependencies and retained outputs.
- [verify.py](verify.py): the preserved historical checker, which also gates on
  an older repository snapshot and is not the current scoring command.

`completion_text` is the exact decoded string (or null) supplied to the original
scorer. JSONL escaping changes its storage representation, not its value.
Malformed JSON and invalid claim/case identifiers remain exactly as returned.
The four content-filter responses retain null completions and the provider's
separate `refusal_text`; refusal text is inspectable but is not substituted for
the scored completion. A SHA-256 of each string/null's compact UTF-8 JSON encoding
distinguishes null from an empty string and detects changes.

Full provider envelopes, provider reasoning, credentials, authorization headers,
serialized prompts and raw wiki records are excluded. Only visible final answers
and refusals are released; there is no reconstruction of redacted identities.
Treat all response strings and any URLs they contain as inert evidence. No link
following, payload execution or active HTML rendering is needed to inspect them.

The original [protocol](../../ANALYSIS.md) kept raw completions local during the
study. This separately authorized release packages visible response evidence
after evaluation; it does not revise that historical protocol or disclose the
full raw envelopes. Source records and stored responses remain unchanged in
ignored local artifacts. No raw-corpus redistribution permission is inferred.

## Reproduce the mechanical scores offline

From the repository root, with Python 3.11 or later:

```sh
python studies/investigator_utility/openrouter_v1/response_evidence/verify_scores.py
```

This command needs no API key, network access, raw downloads or installed project
dependencies. It verifies the response schedule and hashes, checks all 168
scored responses, reproduces the 144 saved evaluation rows and 2,000-resample
paired summaries, and checks the analytic constant-answer baselines and costs.
It makes no inference requests and writes no study outputs.

The command resolves files relative to its own location, so an absolute script
path works from another working directory. A minimal copied tree needs exactly
the 16 repository-relative files listed by
[scoring_manifest_v2.json](scoring_manifest_v2.json):

- The exact `responses.jsonl`, `scoring_cases.json` and original response-evidence
  `manifest.json`, which supplies existing hash provenance.
- The frozen `scoring.py`, imported directly without package initialization;
  its imports use only the Python standard library.
- The completed run's frozen `freeze.json`, `case_manifest.json`,
  `gold_certificates.json`, `prompt_manifest.json` and `config.json`, supplying
  the applicable identities, labels, schedule and configuration.
- Saved `response_manifest.json`, `execution.json`, `per_case_scores.json`,
  `paired_summary.json` and `sanity_baselines.json`. Response rows and execution
  metadata supply the retained usage, charges and reservation accounting.
- The additive `verify_scores.py` and `scoring_manifest_v2.json` themselves.

This is 14 historical scientific dependencies plus two new verification files.
Relevant frozen hashes retain their original recorded values. The historical
README/demo pins and nonimported simulator source are not score dependencies.

To inspect the retained answers on the adverse synthetic example:

```sh
python - <<'PY'
import json
from pathlib import Path
path = Path('studies/investigator_utility/openrouter_v1/response_evidence/responses.jsonl')
for line in path.read_text().splitlines():
    row = json.loads(line)
    if row['case_id'] == 's004' and row['model_id'] == 'anthropic/claude-sonnet-5.5':
        print(json.dumps({key: row[key] for key in
              ('arm', 'finish_reason', 'completion_text', 'refusal_text', 'score')},
              ensure_ascii=False, indent=2))
PY
```

## What verification does and does not establish

Readers can inspect exact visible answers and reproduce their schema, status,
citation-ID and aggregate scores. The minimal views and certificates do not
independently validate the full supplied evidence, gold derivations, explanation
quality, or semantic citation support. They cannot reproduce inference from
mutable model aliases. Original response-envelope hashes establish local
integrity references; they are not provider signatures or proof of authenticity.

Full input reconstruction still requires the pinned publisher release and the
historical preparation code described in the [study guide](../../README.md).
This is a reproducible mechanical scoring release, not a claim of independently
reproducing all evidence, labels or model behavior from the bundle alone.

Score reproduction and historical checkout preservation are different checks.
The current scoring-only verifier pins the exact responses, scoring views,
gold metadata, frozen scorer, schedule/configuration, numerical summaries and
accounting it uses. Its versioned manifest describes that dependency scope;
unrelated Markdown, demos and simulator files do not gate the calculation.
It reproduces the retained scores against the retained labels, without claiming
that the entire older repository tree is unchanged.

The historical `verify.py` and its manifests remain unchanged. At the review
baseline that command failed at `demo/index.html`, an unrelated historical file
pin; later authorized edits to this README are also outside its pinned snapshot.
Those are checkout-preservation mismatches, not demonstrated score discrepancies.
Do not suppress its hashes or replace its historical baseline to make it accept
a newer tree. The [technical verification record](../../../review_remediation/score_verification.json)
reports the current scoring check and focused dependency/tamper tests.

Known provider-reported charges remain **$2.861514** across 167 calls. One refusal
omitted usage and retains **$0.137392**, giving **$2.998906 charged or reserved**.
**Actual total cost remains unknown.** Packaging and rescoring require no new
model calls or charges.

# Offline failure audit

**The frozen results reproduce. Sonnet’s rejected outputs principally violate serialization requirements; object-versus-array mismatch explains none of the observed failures. Terra’s invariant-pair error survives direct verification.** No adapter/scorer defect was found, and no corrected score calculation or erratum is warranted.

This is an offline, review-informed diagnostic of the completed study at `f9028f581170cf4b5d43ea7ac6aebb4813ea4219`, not a new investigator experiment. The initial working tree was clean. All 72 evaluation variant rows, 24 model/family rows, paired summaries, selected examples, and equality of primary/strict-ID family outcomes reproduce from the exact retained first responses. Development responses are excluded from the 36-response Sonnet audit. No answers were repaired, selected from alternatives, or rescored under a relaxed policy.

## Sonnet: one primary cause per evaluation response

The [diagnostic precedence](diagnostic_rules.json) was recorded before annotating the complete set. Categories identify observable rejection causes, not the internal causes of model behavior. Secondary flags and all original cascading parser flags remain in the [36-row response-cause table](response_causes.json).

| Mutually exclusive primary cause | Receipt | Controlled wiki | Total |
| --- | ---: | ---: | ---: |
| Provider-declared refusal/filter | 0 | 2 | 2 |
| Serialization / whole-response JSON violation | 17 | 3 | 20 |
| `id` instead of required `claim_id` | 1 | 1 | 2 |
| Extra `id` alongside `claim_id` | 1 | 1 | 2 |
| Accepted under frozen contract | 5 | 5 | 10 |
| **Total** | **24** | **12** | **36** |

There are zero demonstrated extraction defects, empty nonrefusals, root/answers-container primary failures, or unresolved diagnoses. All ten accepted outputs are correct under the frozen labels. The 26 rejected outputs remain failures; a recognizable status inside rejected text is not a newly correct primary answer.

The **20 serialization violations** comprise:

- **12** final outputs with leading explanatory prose and one identifiable JSON response object. Eleven also fence that object; one does not. None is merely a sole Markdown fence around an otherwise isolated JSON response.
- **8** final outputs with two JSON response objects separated by self-correction prose. Both objects remain diagnostic content; neither is chosen as the answer.

Across those outputs and the other nonrefusals, all **42 identifiable response objects** decode as JSON and have array-valued `answers`. All 42 response-object case IDs match their supplied cases; 40 include `claim_id=q0`, while two use `id` instead. No duplicate JSON keys or genuinely malformed embedded response object was observed. This does **not** make the complete final outputs valid JSON: the prompt explicitly requests only one JSON object. The 12 bracketed numeric time-window intervals in explanatory prose are not additional response candidates; the diagnostic scanner identifies disjoint objects bearing `case_id` or `answers`, without using gold to choose among them. This is diagnostic inspection, not a replacement acceptance policy.

The two refusals have `finish_reason=content_filter`, nonempty refusal metadata, and null final content. The other 34 final contents are nonempty strings with `finish_reason=stop`. In all 36, the provider’s final `choices[0].message.content`, the adapter’s extracted value, and saved `completion_text` agree exactly; requested/returned model IDs match `anthropic/claude-sonnet-5.5`. There is no dropped visible answer or content-joining discrepancy.

The old parser catches whole-string JSON decoding failure, substitutes an empty object internally, and then adds `missing_response`, `wrong_case_id`, `answers_not_list`, and missing-claim flags. Thus **22** responses carry `missing_response`, but only **two** actually lack final content. The other **20** are nonempty serialization failures. These flags are stages of one rejection path, not independent incidents or proof of missing provider output.

## Prompt wording: ambiguous, but not the observed explanation

Every actual serialized Sonnet request contains “`answers must contain one object`.” It does not explicitly say that `answers` is an array. The saved provider bodies contain only `model`, `messages`, `max_tokens`, `stream`, and `provider`; no response schema resolves that ambiguity. Their system/user contents match the frozen requests.

Nevertheless, **zero** inspected response objects use object-valued `answers`. The proposed object-versus-array mechanism therefore does not explain any observed rejection. The observed prose, multiple-object, and field-name violations concern explicit instructions. This dataset cannot establish whether different wording would have changed other behavior.

A minimal prospective clarification is: “`answers must be a JSON array containing exactly one object`.” This audit does not change the prompt or execute that alternative. Prompt underspecification is not an observed adapter or scorer implementation defect.

## Terra: the failed invariant family

Family `f_9695d2661a05a12eced27723` is the frozen `inserted_versus_inherited` family. All three exact public/provider requests, full texts, transformations, certificates, and final visible responses are retained in the [ignored local evidence package](../../../artifacts/evidence-responsiveness/offline-failure-audit/terra_evidence.json). The [Terra summary](terra_summary.json) records the complete pairwise field differences, IDs, hashes, spans, classifications, and reproduced scores without publishing full fixture bodies or final explanations.

| Variant | Case ID | Certified status | Final status | Primary / strict-ID correct |
| --- | --- | --- | --- | --- |
| Base | `c_5d0eca8fa432a0bd5f37a404` | established | established | yes / yes |
| Irrelevant | `c_bf88b0680f8898862c1cf548` | established | ruled_out | no / no |
| Decisive | `c_796c25ca0ea2a0b5a0d6efcd` | ruled_out | ruled_out | yes / yes |

All offsets below are zero-based Unicode code points and spans are half-open. The following title strings are **explanatory excerpts**, not reduced substitutes for the full tested requests.

The target’s exact bounded title `Jan14PovertyWatcher` spans **[877,896)**. In the base predecessor `r0`, the corresponding excerpt is `Jan14PoveQtyWatcher`: offset **886** is `Q`, while the target `r1` has `r`. The frozen alignment includes `replace` from predecessor **[886,887)** to target **[886,887)**. That replacement overlaps a title character, so the target occurrence is inserted under the explicit rule. The predecessor has no bounded match of the exact title.

The irrelevant variant changes only fixture text **`r1[898]: M → Q`**, outside the title. Offset 898 is two code points beyond the half-open end 896, or three positions after the last title character 895; two newlines separate it from the title. Alignment still contains the decisive **[886,887)** replacement and adds a separate **[898,899)** replacement. The exact target match stays at **[877,896)** and remains inserted; the gold answer is still `established`.

The decisive variant instead restores **`r0[886]: Q → r`**, nine positions from the title’s start and inside its span. Both predecessor and target now contain the same bounded title at **[877,896)**, within the alignment’s `equal` span **[0,2557)**. The later target insertion **[2557,2765)** contains no additional matching title. The relevant occurrence is inherited, not inserted, so the claim is `ruled_out`.

All three certificates reproduce from the actual full supplied texts under the unchanged rule. The separate literal-membership check corroborates the matches; both classification checks share `SequenceMatcher(autojunk=False)`. This is neither an independent alignment implementation nor human gold validation.

The exact final answers cite `r0`, `r1`, and `a1` (the irrelevant answer orders them `a1`, `r0`, `r1`); all IDs are valid and all three responses satisfy the schema. The irrelevant answer’s short explanation claims the title is inherited through an equal span. That visible explanation conflicts with the predecessor’s `Q` and the overlapping replace opcode. Its exact wording is retained locally as response content, not used as proof of an internal reasoning process.

### Every request difference

Relative to base, the irrelevant public evidence changes exactly `/case_id`, `/records/1/text`, and `/records/1/text_sha256`. The decisive evidence changes exactly `/case_id`, `/records/0/text`, and `/records/0/text_sha256`.

| Fixture record | Base UTF-8 text SHA-256 | Changed variant UTF-8 text SHA-256 |
| --- | --- | --- |
| `r1`, irrelevant edit | `966a811ffcba2c82aea9ab1fb15a746e65f2fca93b6a806748d86df88d62c661` | `2863c760655065ffaf4f0a7b3e74be6883aa044f6df84d8b645dc49b9cedafaf` |
| `r0`, decisive edit | `597291a19564655e9326cf577c5ce9c47047fb6b102d62be5c1d0c5cb08f9ed2` | `d0e5147167668d92854a221564eb4e0ba02684520ea0bb311c168a6ff619add2` |

Local public-request wrappers also change the derived `attempt_key`; their `case_id` and serialized `user` change. The provider body changes only `/messages/1/content`, containing those evidence differences. Wrapper attempt keys are not sent to the provider. System prompt, task wrapper, assumptions, claim, record order, text lengths, output-token limit, model, routing, and all other provider fields match. There is no truncation or unexpected setting difference. The summary includes all three pairwise comparisons and complete request/public-case/payload/file hashes.

This is **not literally a one-byte-identical request pair**: opaque case IDs and derived text hashes change too. With one sample per variant, the audit verifies an incorrect answer within a certified invariant pair; it does not isolate the text edit as its cause, establish reproducibility, or explain an internal mechanism. These altered wiki texts remain controlled fixtures, not historical observations.

## Interpretation and preservation

No original estimate needs correction. The scientific interpretation should be more specific: Sonnet’s observed failures are mostly whole-output serialization violations, with a small number of explicit field violations and two refusals. They do not demonstrate 26 separate incorrect evidence interpretations or 22 empty provider responses. The proposed array-shape explanation is unsupported here. Terra’s narrow behavioral inconsistency stands, subject to the complete-request differences above. No `ERRATUM.md` or corrected acceptance policy has been created because no result-changing implementation defect was identified.

The audit added one focused [script](audit.py), 18 focused tests, this report, diagnostic tables, and manifests. **638 tests passed**, including the prior 620, in the installed environment with credentials absent and socket network operations blocked; Ruff and whitespace checks passed. No dependencies were installed or upgraded. The audit script likewise blocks socket operations and never invokes a provider adapter’s network path.

All **771 historical input hashes** match after the audit, including every previously tracked file, the preserved historical raw chain, and the prepared/request/response/ledger inputs used here. Existing presentation exceptions from the prior study were respected; no new exceptions or historical-document edits were introduced. The unchanged ledger still accounts for USD 3.7827560 cumulatively (USD 3.4468440 known charges and USD 0.335912 unresolved reservations); actual total cost remains unknown. **Zero network requests, zero model calls, zero additional spend, and no credential or provider-private reasoning inspection.**

See [verification counts](verification.json), [baseline input hashes](baseline.json), and the [manifest](manifest.json). File hashes cover exact file bytes; fixture text hashes cover raw UTF-8 text. Logical-value hashes, including `final_content_sha256`, cover canonical JSON (sorted keys, compact separators, unescaped Unicode encoded as UTF-8, no final newline); a final string includes its JSON quoting and null is encoded as `null`. Canonical provider-body hashes use the adapter’s same JSON encoding. Independent annotation `completion_sha256` instead covers raw UTF-8 final text; these deliberately different conventions are not interchangeable. Exact final-only Sonnet material and full Terra evidence stay in ignored `artifacts/evidence-responsiveness/offline-failure-audit/`; no raw provider envelope or private reasoning is exported. Public hashes identify retained content but do not give independent readers access to it. Checks combine deterministic computation and AI-assisted inspection, not independent human review.

To reproduce the score/hash checks without writing outputs or making model calls, use the already installed environment:

```sh
.venv/bin/python - <<'PY'
import runpy
m = runpy.run_path('studies/evidence_responsiveness/offline_failure_audit/audit.py')
_, _, _, _, variants, families = m['load_verified']()
print(len(variants), 'evaluation variants;', len(families), 'model/family rows verified')
print(m['historical_hashes'](), 'unchanged historical inputs')
PY
```

The script’s main path refuses to overwrite its diagnostic outputs. The locally retained exact evidence, not hashes alone, is necessary to reproduce response-level diagnoses.

# Targeted review remediation

Baseline: `38d456a5235c3b03e5bef50c4755f5f3279d316c`, clean checkout. No acquisition extension existed locally. [baseline.json](baseline.json) separates 177 relevant immutable files from eight authorized Markdown exceptions. [local_preservation.json](local_preservation.json) checks 509 retained call/accounting files against previously recorded hashes without decoding provider envelopes. The original studies, refusals, strict scores, protocols, manifests, scientific implementations and ledgers are preserved.

## Findings and dispositions

| Review observation | Status | Checked outcome |
| --- | --- | --- |
| Public score verification is blocked by unrelated historical documentation | verified | Original `verify.py` first fails at `demo/index.html`; after current README corrections it fails at the bundled README. These are snapshot differences, not score changes. A separate dependency-scoped verifier succeeds. |
| Utility accepted statuses are at ceiling and invalid outputs drive Sonnet's score differences | verified | All 144 original evaluation rows reproduce. Sonnet has 54 schema-valid responses, 216 correct statuses; Terra has 72 and 288. Explanations are not semantically graded and a citation error is separate. |
| Eighteen Sonnet utility failures are eight field-ID, six prose/JSON and four refusals | verified | Counts agree with the released final visible outputs. They are utility-pilot counts, not the later responsiveness counts. |
| Retrospective extraction yields 22/22 answerable synthetic claims in every arm | not_supported | Under one gold-blind rule applied to both models/all arms, A=19/22, B=18/22, C=22/22. Two multi-object responses remain ambiguous. |
| Nonrefused malformed responses can be recovered by deterministic normalization | partly_supported | Twelve of 18 invalid responses recover, adding 48 correct schema-valid statuses. Four refusals and two ambiguous outputs remain failures; the wiki C citation error remains. This is diagnostic sensitivity, not a replacement primary result. |
| Native JSON-schema output enforcement was requested | not_supported | All 144 saved evaluation request bodies contain model/messages/max_tokens/stream/provider, without response_format, schema enforcement or tool-schema fields. A schema-enforced rerun and its performance are not tested or authorized. |
| The two original target-error figures conflict | not_supported | They are different estimands. Mean absolute fraction error worsens while individual target disagreement improves in the exact same 12-world cohort. |
| Receipt timestamps contradict context available at an earlier decision | verified | A supported six-write example has a first context receipt before an earlier same-run write whose actual selection state lacks that source. Ordinary source/request/delivery/context/target order still holds. |
| The chronology defect changes published point estimates | not_tested | No corrected generator or corrected historical grid was run. None of the 52 checked published worlds had the specific first-context contradiction; this is not a proof for all published scenarios. |
| Utility README was wholly unfixed | partly_supported | It already identified the completed run, but generic report/score links still pointed to blocked preparation. Current links now identify completed OpenRouter results; blocked files remain historical. |

## Scoring verification is not checkout preservation

Current command, Python 3.11+ with no project installation, credentials or network:

```sh
python studies/investigator_utility/openrouter_v1/response_evidence/verify_scores.py
```

The [version-2 manifest](../investigator_utility/openrouter_v1/response_evidence/scoring_manifest_v2.json) declares the complete 16-file set: fourteen historical dependencies plus the new entry point and manifest. Historical pins come from existing freeze/release records, not refreshed source hashes. The unchanged scorer is imported by filename and has only standard-library imports. The verifier checks exact response bytes, minimal scoring cases, gold, case/schedule/configuration metadata, saved scores/summaries/controls, and accounting. It checks missing/duplicate identities and claims, text/null hashes, refusals, 2,000 paired resamples and reservations. JSON duplicate keys and path traversal fail closed.

Result: **168 responses, 24 development, 144 evaluation, 28 cases**, original scores and paired summaries reproduced. Known charges remain $2.861514 plus a $0.137392 reservation, $2.998906 accounted for this utility run; exact actual cost remains unknown. The historical verifier/manifests are unmodified. Neither checker authenticates the provider or independently establishes retained gold semantics/full unseen prompts. See [score_verification.json](score_verification.json) for actual commands and 32 focused tamper/copied-tree checks. The current check passes after the authorized documentation edits.

## Retrospective utility diagnostic

[diagnostic_rules.json](diagnostic_rules.json) fixes the gold-blind, post-evaluation rules; [utility_diagnostic.py](utility_diagnostic.py) applies them uniformly to all 144 evaluation responses. Development rows are excluded. Extraction requires exactly one nonoverlapping response-shaped object. Nested answer objects and numeric arrays are not extra response candidates. ID mapping requires unambiguous expected claim membership; unrelated fields and incorrect citations are not discarded. Gold is consulted only after deterministic transformation, never to choose an object.

The two ambiguous Sonnet cases are `s003/A` and `s006/B`, each with two complete response objects. No preferred self-correction is selected. Twelve response transformations add 48 decodable correct statuses; 132 response values remain unchanged. Sonnet changes from 216/288 to 264/288 correct schema-valid statuses, with 24 invalid claims and one citation error still present. Terra remains 288/288. Pooled answerable synthetic counts A/B/C are 19/22, 18/22, 22/22; corresponding case-mean warranted-answer accuracy is 6/7, 6/7, 1 over seven applicable cases. Wiki counts are 30/32, 28/32, 30/32 over 16 cases. These distinct denominators are retained in [utility_diagnostic.json](utility_diagnostic.json).

This does not repair primary scores, prove faithful reasoning, establish a general assistance benefit, or predict a future schema-enforced run. The primary C−B comparison, its intervals, secondary A comparison and adverse cases remain intact. The separate responsiveness study retains Sonnet's end-to-end failures, zero observed array-shape explanation, and Terra's valid incorrect answer; the offline audit found no adapter/scorer defect.

## Two different target-error measures

[derived_target_errors.csv](derived_target_errors.csv) and [JSON derivation](derived_target_errors.json) use the original witness investigator, transmission 0.3, shock 0.9, seeds 0–11, N=360 writes per world. They use saved rows rather than new simulation results. Derive signed error s=theta_hat−theta, FN/N=FP/N−s, and disagreement=FP/N+FN/N. Verify integer counts, ranges, matching denominators and (FP−FN)/N=s for every row. Mean absolute error is the mean of per-world |s|, never |mean(s)|.

| Mean metric | Requests | Context |
| --- | ---: | ---: |
| Signed target-fraction error | +0.02222222 | −0.05925926 |
| Absolute target-fraction error | 0.02962963 | 0.05925926 |
| Target disagreement | 0.18148148 | 0.11388889 |
| FP targets / N | 0.10185185 | 0.02731481 |
| FN targets / N | 0.07962963 | 0.08657407 |

Finer filtering reduces individual target disagreement while worsening aggregate fraction error because earlier false positives and false negatives partly cancelled. Neither measure supersedes the other. The target remains direct realized structural source selection, not a measured wiki copying rate. The pure `derive` function in `target_errors.py` supports read-only recomputation; its command-line writer refuses to overwrite the saved derived outputs.

## Chronology issue and scope

[chronology_audit.py](chronology_audit.py) uses read-only `sys.settrace` snapshots at the original generator's source-selection entry. It does not edit source, patch event generation, or inject RNG calls. All 53 traced complete World objects exactly equal uninstrumented calls with identical configurations. [chronology.json](chronology.json) records first source/run availability, not later duplicate receipts, across twelve original high-shock worlds, forty missing-receipt worlds and one six-write diagnostic.

The minimal supported example uses seed 0, two runs, three writes/run, one family and shock 0, otherwise defaults. Source `e000002` occurs at 161.995815; request at 171.191471, delivery at 180.387128 and first context at 189.582785. Recipient `r00001` writes `e000003` at 194.451660 with an empty available-source state. The source is first installed while generating `e000004` at 198.778442. Thus the log places first availability before a decision at which the generator did not have it. A receipt before its intended target is normal; this earlier-decision contradiction is the defect. The model defines no explicit run-start event from which to infer a separate startup violation.

Original simulator and missing-receipt results remain results of the legacy generator; chronological replay fidelity is not warranted. The point-estimate impact of a separately corrected simulator is unmeasured. The wiki export, finite utility/responsiveness fixtures and saved model scoring are not invalidated by repository proximity.

**Verified dependency isolation for Phase B:** the existing finite receipt-contract enumerator is independent of `simulate.py`; its explicit event slots and shared-input alternatives are useful conceptual precedents, not stochastic histories. The new acquisition package imports no legacy simulator/observer/estimator/scorer/API adapter and consumes no simulator history. Its independent validator enforces event chains, first context availability at every write, retrospective completeness scope and retention. This boundary permits Phase B without treating the legacy defect as fixed.

## Documentation, validation and owner decisions

Only the eight Markdown exceptions recorded in the baseline receive corrections. Current narrative removes drafting handoffs and stale HTTP/form-access notes, uses `FINAL_SUBMISSION.md` as the synthesis, distinguishes completed versus blocked historical results, removes root-directory server launch advice, and uses plain local paths instead of misleading links into ignored evidence. Frozen submissions/addenda/results are retained. Documentation before/after hashes and final tests/preservation checks are recorded in [validation.json](validation.json).

No approved author/team/contact attribution was supplied, so none was invented. No LICENSE/LICENCE file was found; choosing a license remains an owner action. Remote description, account-email association and future git identity were not inspected or changed. These are not technical blockers or legal/IP clearance. An optional description for an owner to consider is “Benchmarks and evidence audits for source attribution, investigator response reliability, and passive evidence acquisition under incomplete agent logging.” No form verification, public-access guarantee or universal credential-safety claim is made.

Phase B completed 40 fixed problems, five policies and five budgets: 9,800 signature runs, 19,300 charged lookups and 1,922 independently checked certificates, with zero certificate failures. Pair-cut mean cost was 3.793750 versus schema-aware 4.228125, entropy 4.103125 and exact adaptive 3.369141. It lost to schema-aware ordering on seven problems and in the positive-receipt stratum; all policies reached the same eventual archive conclusions. The separate four-example wiki check found no target literal matches and establishes no acquisition advantage.

Phase B protocol and measured outcomes: [ANALYSIS.md](../evidence_acquisition/ANALYSIS.md), [METHOD.md](../evidence_acquisition/METHOD.md), and [RESULTS.md](../evidence_acquisition/RESULTS.md). No presentation, demo, screenshots, UI, reviewer package, model call, network request, additional spend, commit or push is part of this task.

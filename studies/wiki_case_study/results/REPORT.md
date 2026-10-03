# Public-wiki reference audit

Exploratory, review-informed census of one pinned public export. True source use is unobserved.

The descriptive target is newly inserted literal page-name references. It is separate from the simulator's direct, realized cross-run source selection. A reference may address a page without showing that its writer read it.

## Counts and exclusions

Pairs identify a target revision and referenced page title; repeated mentions count separately only as occurrences. Handles are observed labels, not runs.

| Measurement | Count |
| --- | ---: |
| total input records | 14,681 |
| total input revisions | 14,591 |
| auxiliary added line records | 90 |
| target revisions | 13,403 |
| eligible target revisions | 10,884 |
| excluded or ambiguous revisions | 2,519 |
| raw snapshot pairs before source check | 17,948 |
| excluded source order pairs | 5,412 |
| naive snapshot pairs | 12,536 |
| naive snapshot occurrences | 24,757 |
| eligible snapshot pairs | 10,520 |
| eligible snapshot occurrences | 16,585 |
| inserted reference pairs | 3,140 |
| inserted reference occurrences | 4,854 |
| target revisions with snapshot match | 6,048 |
| target revisions with inserted reference | 2,500 |
| distinct observed handles | 2,997 |
| distinct snapshot target handles | 1,788 |
| distinct inserted target handles | 1,128 |
| inherited only pairs | 7,380 |
| inherited reference occurrences | 11,731 |
| excluded or ambiguous pairs | 7,428 |
| ambiguous reference occurrences | 4 |

The naive snapshot count already requires earlier source-page evidence but ignores target attribution eligibility. The eligible snapshot count isolates the comparison after those checks. Inherited-only content and excluded history are different reasons for a smaller inserted count; this is not a false-positive source-use rate.

Eligible snapshot pairs comprise **3,140 inserted** and **7,380 inherited-only** pairs. There are **7,428 excluded/ambiguous** raw pairs. Reason counts below overlap.

Frozen generic/navigation exclusions: <code>HomePage</code>, <code>RecentChanges</code>, <code>SandBox</code>, <code>WikiSandBox</code>, <code>Help</code>, <code>Index</code>, <code>FrontPage</code>. Present in the target site's supplied title set: <code>RecentChanges</code>, <code>SandBox</code>.

Inserted-pair cross-handle statuses: different=1,910, mixed=363, same=616, unknown=251. All have unresolved stable run identity, unknown exposure and unobserved use.

### Revision exclusion reasons

| Reason | Count |
| --- | ---: |
| ambiguous_predecessor_order | 2,228 |
| missing_predecessor | 11 |
| publisher_recreation_or_revert_not_new_authorship | 63 |
| restoration_not_new_authorship | 1,272 |

### Revision flags

| Reason | Count |
| --- | ---: |
| ambiguous_latest_predecessor_interval | 395 |
| duplicate_snapshot | 41 |
| missing_or_redacted_author | 91 |
| missing_predecessor | 11 |
| nonpreceding_or_undated_predecessor | 1,658 |
| overlapping_same_page_timestamp_intervals | 2,082 |
| publisher_recreation | 63 |
| redacted_author | 91 |
| restoration_of_earlier_snapshot | 1,272 |
| tied_predecessor_timestamp | 26 |
| tied_same_page_timestamp | 194 |

### Pair exclusion reasons

| Reason | Count |
| --- | ---: |
| ambiguous_predecessor_order | 4,031 |
| boundary_only_or_unmapped_reference | 4 |
| missing_predecessor | 4 |
| no_strictly_earlier_same_site_source_page | 5,412 |
| publisher_recreation_or_revert_not_new_authorship | 48 |
| restoration_not_new_authorship | 2,257 |

## Evidence capabilities

| Evidence type | Availability | Meaning and limits |
| --- | --- | --- |
| revision_snapshots | available_with_history_gaps | Stored revision contents with explicit same-page diff bases Published write-date cut only; earlier unpublished rows flagged |
| observed_handles | available_or_missing_by_record | Observed posted handles only No stable identity assurance |
| server_requests | limited_save_and_probe_metadata | Limited server evidence about saves and probes, not source-page reading No complete general read-request stream; raw request logs not included |
| publisher_events | available_selected_event_populations | Overlapping publisher populations, not independent incident counts Population-specific release coverage only |
| stable_run_identity | unavailable | Observed labels do not identify stable runs or owners none; absence of a type is not an empty complete stream |
| authenticated_delivery | unavailable | Save/probe success is not delivery of a source page to a target none; absence of a type is not an empty complete stream |
| authenticated_context | unavailable | No authenticated source-page context-entry receipts supplied none; absence of a type is not an empty complete stream |
| source_selection | unavailable | Direct realized source selection is unobserved none; absence of a type is not an empty complete stream |

Absent telemetry types are not empty complete streams. An absent record in an available stream also cannot establish that an event did not occur. Save or probe records do not establish a candidate source-page read; a posted assertion of reading is unverified. Exposure remains unknown, while source use remains unobserved even if exposure were later established.

## Frozen extraction review

The sheet contains 10 inserted and 10 inherited-only pairs selected by the frozen hash rule. All candidate locators, excerpts, offsets and eligible time conditions were checked mechanically before output. Human-review fields are blank; these checks are not independent human validation. See `review_sheet.json` for the selected cases and any separately labeled AI review.

## Source-linked evidence cards

### inserted: <code>AgentSecDirectJQP999</code>

Target <code>dse~AgentPureNext778@2</code>, page <code>AgentPureNext778</code>, time <code>2026-06-18T19:35:44Z</code>, observed handle <code>OpenAIMass2026</code>.

Pinned record: <code>revisions.jsonl</code>, line 2970; SHA-256 <code>501019009a089138449e22c169533ec47372423280cb9f5ad1e1666b0e80dd4c</code>. Title span [100, 120); excerpt span [60, 180).

<pre>se/wiki.cgi?action=browse%26diff=4%26id=AgentSecDirectJQP999%26x=1777%26uniq=InvJsDiff1777 GoDiffEnc]
* [https://wikiser</pre>

All 3 strictly earlier source-page revisions are retained in `evidence_cards.json`; none is designated a direct source.

First chronological source-page locator: <code>dse~AgentSecDirectJQP999@1</code>, <code>2026-06-18T18:59:19Z</code>, <code>revisions.jsonl</code> line 3238.

Cross-handle status: **different**; stable identity unresolved; source-read request, authenticated delivery and context evidence unavailable; exposure unknown; source use unobserved.

### inserted: <code>AgentTempOpenAIx</code>

Target <code>dse~ForumSeite@7</code>, page <code>ForumSeite</code>, time <code>2026-06-18T20:10:08Z</code>, observed handle <code>AgentMapCite8x</code>.

Pinned record: <code>revisions.jsonl</code>, line 6269; SHA-256 <code>342846dfdb1f891203371497b4f7f2900480651dba78a0ab9013c72c19f9c489</code>. Title span [2300, 2316); excerpt span [2260, 2380).

<pre>ervice.at/dse/wiki.cgi?action=browse&amp;id=AgentTempOpenAIx&amp;lang=1&amp;uniq=FreshTemp1781823 GoTempForum]

RandGET 0.6377641776</pre>

All 2 strictly earlier source-page revisions are retained in `evidence_cards.json`; none is designated a direct source.

First chronological source-page locator: <code>dse~AgentTempOpenAIx@1</code>, <code>2026-06-18T19:32:48Z</code>, <code>revisions.jsonl</code> line 3408.

Cross-handle status: **mixed**; stable identity unresolved; source-read request, authenticated delivery and context evidence unavailable; exposure unknown; source use unobserved.

### inherited_only: <code>OpenAIHealthdataCVDMar27</code>

Target <code>dse~HealthdataCVDSequenceCollab@28</code>, page <code>HealthdataCVDSequenceCollab</code>, time <code>2026-06-19T03:19:16Z</code>, observed handle <code>OpenAIHealthdataCVDNov01</code>.

Pinned record: <code>revisions.jsonl</code>, line 6401; SHA-256 <code>95cb218992cfa6315dc416d36302be46754d9d42313793dd8e68f035c9bbbd6a</code>. Title span [3413, 3437); excerpt span [3373, 3493).

<pre>will use Poland/8016 and relay. Contact OpenAIHealthdataCVDMar27 . Does anyone have direct evidence why 8016 is expected</pre>

All 2 strictly earlier source-page revisions are retained in `evidence_cards.json`; none is designated a direct source.

First chronological source-page locator: <code>dse~OpenAIHealthdataCVDMar27@1</code>, <code>2026-06-19T00:29:09Z</code>, <code>revisions.jsonl</code> line 8355.

Cross-handle status: **different**; stable identity unresolved; source-read request, authenticated delivery and context evidence unavailable; exposure unknown; source use unobserved.

## Interpretation and limits

The snapshot-to-insertion comparison measures sensitivity to attribution of cumulative text. It does not measure copying, collusion, exposure or causal use. Diff and evidence invariants are unit-test consequences, not discoveries. Character alignment is deterministic but not unique; partial history, conservative timestamp intervals, excluded recreations/restorations, quoted text, title collisions and alternative sources limit interpretation. First observed in this export is not global origin. Redacted handles do not support run reconstruction.

This census has no sampling interval and no real-data precision, recall or theta. Raw files remain ignored. Source URLs, publisher checksums and retrieval provenance are in `../source_manifest.json`; frozen rules are in `../ANALYSIS.md`. `manifest.json` pins the rules, code and local outputs. Original synthetic and missing-receipt artifacts are preserved separately.

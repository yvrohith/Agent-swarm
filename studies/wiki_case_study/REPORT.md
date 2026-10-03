# German-wiki descriptive evidence audit

The publisher's pinned export was acquired successfully through its published
HTTPS links. The five main data-file checksums and supplemental-file checksum
match the download page; all 14,591 revision body hashes verify. The
[source manifest](source_manifest.json) records exact URLs, retrieval times,
sizes, schemas and reconciliation checks. Raw downloads remain ignored.

The [frozen exploratory protocol](ANALYSIS.md) analyzes all 13,403 supplied DSE
revisions. This is a descriptive reference audit, with a different target from
the simulator's direct, realized cross-run source selection.

| Counting unit | Snapshot | After attribution checks | Newly inserted |
| --- | ---: | ---: | ---: |
| Revision–referenced-title pairs | 12,536 | 10,520 | 3,140 |
| Literal occurrences | 24,757 | 16,585 | 4,854 |

The snapshot column already requires strictly earlier source-page evidence.
Its matches span 6,048 target revisions; inserted matches span 2,500.
Before that check there are 17,948 raw pairs, of which 5,412 lack such evidence.
Attribution checks remove another 2,016 snapshot pairs. Of the remaining 10,520,
**7,380 (70.15%) contain only inherited references**. The reduction therefore
reflects both excluded records and cumulative text. It is not a source-use
false-positive rate.

Of 13,403 DSE revisions, 10,884 are eligible for attribution and 2,519 are excluded
or ambiguous. Reasons overlap: 2,228 have ambiguous predecessor ordering, 1,272
restore an earlier snapshot, 63 carry publisher recreation relations, and 11 lack
the required predecessor. Inserted matches span 2,500 target revisions and 1,128
nonmissing, nonredacted observed handles. Those handles are not stable runs.

The [full tables and three fixed evidence cards](results/REPORT.md),
[machine-readable counts](results/counts.json), and
[frozen 20-pair review sheet](results/review_sheet.json) retain the exact units,
exclusions, source locators, offsets and all possible earlier source revisions.
The cards remain the first two inserted pairs and first inherited-only pair under
the frozen hash order; no favorable examples replaced them.

The [AI-assisted review](AI_REVIEW.json) checked all 20 selected pairs, 28 reference
spans and 333 earlier-source links against pinned records and character diffs.
All 20 conform to the frozen extraction rule; this is not independent human
validation, semantic-reference accuracy, or ground truth about use. Human-review
fields remain blank. Review found concrete limits to interpreting literal matches:

- `DataUSA` appears as a provider/topic name. Equality with an existing wiki title
  does not establish an intentional reference to that page.
- `WillkommenImWiki` is a generic welcome/navigation name that was not in the
  frozen exclusion list. It remains included; exclusions were not changed after
  results.
- Some inherited matches move by +201 or −778 character positions when surrounding
  text changes. Changed offsets alone do not make them newly inserted. One
  inserted pair contains both an inherited and a new occurrence of its title.

The event export contains saves, deletions, reverts and narrow failed probes;
it is not a complete read log. All 3,140 inserted candidate pairs retain unknown
exposure and unobserved source use. Cross-handle status is different for 1,910,
same for 616, mixed across possible prior authors for 363, and unknown for 251.
None resolves stable run identity. Posted read assertions, URL parameters and
redirect directives remain inert text, not authenticated receipts.

The main timestamps' declared one-second uncertainty is conservatively interpreted
as ±1 second for ordering. Supplemental earlier-occurrence searches cover 90
recovered added-line records on eight pages; these are not full snapshots and
their unspecified timestamp uncertainty permits only labeled nominal ordering.
No complete-history, global-origin, original-authorship or copying claim follows.
There are no real-data precision, recall, theta or sampling confidence intervals.

Validation: **214 tests passed, 0 failed, 0 skipped**, including 90 new wiki tests;
Ruff and `git diff --check` passed. Every extracted candidate's links, offsets,
excerpts and applicable time conditions were mechanically checked. All 21
[preserved file hashes](preserved_hashes.json) match the initial simulator,
original plan/results and frozen missing-receipt artifacts. The latter remain
40 worlds, 1,280 evaluations and 640 paired contrasts; no synthetic study was
refit or extended. Mechanical properties are test consequences, not discoveries.
See [validation details](VALIDATION.json) and the
[local reproduction command](../../case_study/README.md#reproduce-locally).

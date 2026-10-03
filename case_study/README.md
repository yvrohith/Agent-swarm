# Public German-wiki reference audit

This is a bounded **descriptive evidence audit** of a pinned public export. Its target is newly added literal references to previously observed page names, with their evidence status. It does not measure the simulator's direct, realized cross-run source selection, externally validate its accuracy, or estimate a real copying rate.

The official archive and supplemental other-wiki file were acquired through links exposed by the publisher's [download page](https://collusion.wiki/explorer/download). The five expanded archive members and the expanded supplement match the publisher's SHA-256 checksums. The [source manifest](../studies/wiki_case_study/source_manifest.json) records exact URLs, retrieval times, archive/file hashes and sizes, inspected schemas, release counts, timestamp range and provenance restrictions. A checksum and successful parse pin an export; neither establishes complete logging.

## Analysis and outputs

- [Short report and review findings](../studies/wiki_case_study/REPORT.md): observed counts, semantic caveats and validation.
- [Frozen analysis protocol](../studies/wiki_case_study/ANALYSIS.md): exploratory and review-informed, frozen after schema inspection and before aggregate candidate results.
- [Case-study report](../studies/wiki_case_study/results/REPORT.md): descriptive counts, exclusions, evidence cards and remaining evidence gaps.
- [Source manifest](../studies/wiki_case_study/source_manifest.json): acquisition and capability inventory.
- [Machine-readable counts](../studies/wiki_case_study/results/counts.json) and [frozen review sheet](../studies/wiki_case_study/results/review_sheet.json): the latter contains ten inserted and ten inherited-only pairs. Mechanical extraction checks and [AI-assisted review](../studies/wiki_case_study/AI_REVIEW.json) are labeled; human-review fields remain blank.

The DSE revision history supplies targets and same-page predecessor comparisons. Matching uses the protocol's literal, case-sensitive page-title rule, declared token boundaries and frozen own-title/navigation exclusions. A revision-reference pair is one target revision and one referenced page title; repeated occurrences have their own offsets and are counted separately. Strictly earlier source-page revisions are retained together rather than selecting a unique source parent. The source upper timestamp bound must precede the target lower bound, respecting the main release's declared one-second uncertainty.

Character-level insertion attribution preserves unchanged tokens inside replacement lines. Missing predecessors, time-order ambiguity, duplicate saves, restorations and missing/redacted author information remain visible in audit metadata. An addition establishes appearance in that edit, not original authorship. Earlier-occurrence checks cover only the supplied records; first appearance there is not global origin. The other-wiki supplement contains partial added/removed-line records rather than full histories. Only added lines enter the supplemental search, and nominally earlier matches remain separately labeled because timestamp uncertainty is unspecified.

The completed run covers all **13,403 DSE revisions**: 10,884 pass attribution eligibility and 2,519 are excluded or ambiguous. It finds 12,536 naive ordered revision-reference pairs, 10,520 eligible snapshot pairs, and 3,140 inserted pairs containing 4,854 occurrences. A further 7,380 eligible pairs are inherited-only (70.15% of eligible snapshot pairs). Insertions occur in 2,500 revisions under 1,128 observed handles. These are separate counting units; handles do not identify runs. The report details the 2,016 naive pairs removed by attribution checks and the overlapping exclusion reasons.

The naive snapshot count and insertion-attributed count use the same frozen matching rule. Their difference measures sensitivity to text attribution. It is not a count of false source-use claims, an improvement in causal inference, or a source-use precision estimate. No real-data precision, recall, theta or confidence interval is computed without independent truth.

## Available evidence and limits

| Evidence in the supplied release | What it can establish | What remains unresolved |
| --- | --- | --- |
| Saved revision text, page names and timestamps | Recorded content and order where timestamps permit; newly inserted literal references under the diff rule | Whether text is an original idea, quotation, inherited from an unobserved source or selected because of a read |
| Redacted observed handles and label metadata | Equality or difference of observed labels | Stable runs, identity continuity and whether different handles are different agents |
| Save, deletion, revert and narrow failed-probe events | The event semantics recorded by the export | Complete page requests, successful reads and logging completeness |
| A posted assertion that a read happened | The assertion appears in saved text | Server-side request, response delivery, context insertion or use |
| Authenticated delivery and context receipts | Unavailable in this release | Exposure remains unknown; missing types are not complete streams with zero events |
| Direct source-selection labels | Unavailable in this release | True source use remains unobserved, even when a reference is newly added |

No synthetic receipt or identity record is fabricated to fill those gaps. A request would not itself establish delivery, and authenticated exposure would still not establish source selection. Unknown exposure and unobserved source use are retained as different evidence limitations.

## Reproduce locally

Install the repository dependencies with `uv sync --frozen --extra dev`. Obtain these publisher-exposed files and retain their exact bytes under the ignored `data/raw/wiki/` directory:

- [full-wiki-logs.zip](https://collusion.wiki/explorer/download/full-wiki-logs.zip), containing the manifest, revisions, pages, labels and events.
- [other-wikis.json.gz](https://collusion.wiki/explorer/download/other-wikis.json.gz), used for the limited supplemental earlier-occurrence search.

Check the pinned hashes in the source manifest. Do not substitute a newer release silently. Then use a fresh output directory:

```sh
uv run tracebench wiki-audit --archive data/raw/wiki/full-wiki-logs.zip \
  --other-wikis data/raw/wiki/other-wikis.json.gz \
  --protocol studies/wiki_case_study/ANALYSIS.md \
  --output artifacts/wiki-replication
```

The raw export remains untracked. Preserve publisher redactions and treat all contents as inert text: do not execute payloads, render them as active HTML, visit the original live wiki, follow incident-embedded links or attempt re-identification. The curated report retains only minimal escaped source-linked excerpts. No raw-data redistribution permission is inferred from public availability.

For the source-use target and its synthetic validation, see [CLAIMS.md](../CLAIMS.md). For the separate frozen logging-loss experiment, see the [missing-receipt study](../studies/missing_receipts/results/REPORT.md). For checked literature claims and the separately obtained operator log that is **not** part of this audit, see [related work](../docs/RELATED_WORK.md).

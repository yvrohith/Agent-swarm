# Frozen descriptive wiki-reference audit

Status: exploratory, review-informed case study, not a preregistered discovery.
This protocol was written after inspecting the publisher schemas and integrity
metadata and before running aggregate reference extraction. Schema counts below
are intake facts, not candidate results. The synthetic source-use estimand and
both saved synthetic studies are unchanged.

## Pin and scope

Use the release generated 2026-09-03T03:42:36Z, downloaded through the publisher's
[download page](https://collusion.wiki/explorer/download). The selected ZIP SHA-256
is `eb68aa12d26bf189d8bfc4ce47f4d8af66ae5ba7ebbadd429738297a3cbb25ae`.
The source manifest records exact URLs, retrieval times, member checksums,
publisher checksum verification, sizes and schema inventories. Local hashes and
publisher consistency checks do not establish corpus completeness.

The ZIP contains 14,591 full revision snapshots on four wikis, including 13,403
DSE revisions on 3,908 pages. Analyze every supplied DSE revision, retaining every
available revision of each page. Do not select pages on reference outcomes.
The release cut is `revision.write_date >= 2026-05-01`; 17 initial page records
explicitly say earlier revisions were not published. Missing history is excluded
from attribution, not assumed empty.

Search all four supplied full-snapshot sites for earlier literal occurrences.
Also search only the **added lines** in the supplied `other-wikis.json.gz`:
90 partial revision records on eight pages from three sites. This publisher
reconstruction lacks original full bodies and anonymous labels. Join added lines
with newline for a documented searchable view; never reconstruct a full snapshot
from them or use them as DSE targets or source-page evidence. Their timestamps
lack declared uncertainty; label nominally earlier matches separately, without
claiming assured precedence. Removed lines are outside this auxiliary search.
No other sites, original live wiki, incident URLs or identity reconstructions
are queried. Raw files remain ignored and are not redistributed.

## Decoding, ordering and attribution

The publisher's `body` JSON strings preserve source bytes through Latin-1.
Recover bytes with `body.encode('latin-1')`, verify `body_sha256`, then decode
using the declared `body_encoding` (ASCII, UTF-8 or Latin-1). Retain source strings
and locators. Do not case-fold, Unicode-normalize, trim titles, interpret markup,
execute content or fetch links. Offsets are half-open Unicode code-point spans
in this decoded text, not byte offsets in the JSON container.

Use explicit `diff_base` and page/sequence metadata for the preceding revision
on the same page. Only explicit `page_created` with no contradictory supplied
earlier history permits comparison against empty text. An unpublished/missing
parent is not a page creation. Parent must be the latest unambiguously preceding
supplied revision on that page. Undated same-page history, conflicting ordering
and tied/overlapping timestamp intervals make attribution ineligible. The main
release declares one-second uncertainty: require source upper time bound to be
strictly less than target lower bound, applying the same conservative condition
to eligible parents. Unknown uncertainty cannot establish strict source order.

Reconstruct character diffs with Python `difflib.SequenceMatcher`,
`autojunk=False`. The publisher's line hunks are not sufficient: replacing a line
does not newly add every unchanged token in it. An occurrence counts as inserted
only if its title-character span overlaps an insert/replace span. A bounded
reference mapped entirely through an equal span is inherited only if it was
already a bounded reference in the parent. A new boundary caused solely by
deletion is ambiguous. This deterministic edit alignment is not unique authorship
reconstruction, and insertion is not original intellectual authorship.

Flag duplicate saves (identical immediate-parent body), missing/redacted handles,
missing text, missing/ambiguous predecessors, and timestamp ambiguity. Exact
restoration of an earlier non-immediate snapshot is excluded from new attribution.
Publisher recreation/revert relations are also conservatively excluded, including
any other changed text in those records. Duplicate saves may supply inherited-only
matches but no inserted matches. Missing handles remain records; cross-handle
status is unknown. These rules are frozen before seeing candidate counts.

## Fixed witness and counting rules

Match literal, case-sensitive existing **DSE page titles**, using Unicode token
boundaries `(?<!\w)` and `(?!\w)`. Exclude the target page's own title and the
fixed generic/navigation list: `HomePage`, `RecentChanges`, `SandBox`,
`WikiSandBox`, `Help`, `Index`, `FrontPage`. Report this list and its intersection
with supplied page names; do not add exclusions after results. Titles are ordinary
reference candidates, not high-entropy nonces or proven wiki-born information.

Require at least one strictly earlier revision of the referenced DSE page.
Retain **all** strictly earlier revisions as possible source-page evidence, never
select one direct parent. Ties/overlaps cannot supply that evidence; independently
earlier revisions can. Earlier title occurrences elsewhere are a separate index
and cannot establish global origin, exposure, copying, collusion or independence.

A pair is `(target site, target revision ID, referenced page title)`; repeated
matches collapse for pair counts only. Keep occurrence spans separately.
Report raw snapshot pairs before time checks; naive snapshot pairs after strict
source ordering but before target-attribution checks; eligible snapshot pairs;
inserted pairs and occurrences; inherited-only pairs; ambiguous/excluded records
and pairs; target revisions with any match/inserted match; and distinct observed
handles with explicit denominators. Exclusion reasons overlap and are not summed
as disjoint record totals. Separate attribution exclusions from inherited content
when explaining the naive-to-inserted reduction.

Every reference has separate evidence states: literal reference observed,
cross-handle same/different/mixed/unknown, stable run identity unresolved,
source-read request evidence unavailable, authenticated delivery/context
unavailable, exposure unknown, and source use unobserved. Save/probe event records
and posted claims of reading are not authenticated source-read receipts. Missing
telemetry types are not empty complete streams; missing records within an
available stream are a different limitation. No synthetic receipts are supplied
to this analysis.

## Audit, output and claim limits

Mechanically verify record locators, source-record hashes, span offsets, excerpts,
parent conditions and strict source precedence. Auxiliary nominal-time matches
are verified under their weaker explicitly labeled condition. Select ten inserted
pairs and ten inherited-only pairs, or all if fewer, by ascending SHA-256 of
compact JSON `pair_key` (UTF-8, `ensure_ascii=False`, separators `(',', ':')`),
breaking ties by that JSON string. Do not replace inconvenient examples.
The frozen review sheet has blank human-review fields. Label any AI-assisted
review and automated checking distinctly; neither is independent human validation.
Cards are the first two inserted entries and first inherited-only entry in that
same hash order (omit empty categories). Escape minimal excerpts as inert text.

Save descriptive counts, capability inventory, selection/audit sheet, cards,
report, and analysis/source hashes separately from the synthetic results. Do not
save full corpus text or a full matched-text index in tracked artifacts. Report
null, exclusion-dominated or unresolved outcomes without loosening rules. No
real-data precision, recall, theta, causal bounds, sampling confidence intervals
or copying-rate estimates are defined here. The comparison checks a known
cumulative-text handling issue on this pinned dataset; unit-test properties are
not scientific discoveries or validation of synthetic accuracy.

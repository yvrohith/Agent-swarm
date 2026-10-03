# Final implementation review handoff

This is the local implementation corresponding to the latest review in
**Brainstorm Swarm Research Projects**, read on October 3, 2026. That review could
see only the old remote commit. This package supplies the current code, tests,
reports and minimal derived evidence without publishing the repository or
redistributing the raw wiki export. The available chat connector supports reading
that conversation, not posting this package or starting another researcher turn.

Start with [the submission write-up](../docs/SUBMISSION.md), then the three
reports: [original benchmark](../results/REPORT.md),
[missing receipts](../studies/missing_receipts/results/REPORT.md), and
[wiki audit](../studies/wiki_case_study/REPORT.md).

## Resolution of the four research-review points

### 1. Inherited matches and excluded records are separate

The saved counts and implementation establish the following disjoint accounting
for this pinned export. Pair counts and occurrence counts are different units.

| Stage | Revision–title pairs | Literal occurrences |
| --- | ---: | ---: |
| Snapshot matches with strictly earlier page evidence | 12,536 | 24,757 |
| Excluded/ambiguous under attribution rules | 2,016 | 8,172 |
| Eligible after attribution checks | 10,520 | 16,585 |
| Classified as newly inserted | 3,140 | 4,854 |
| Inherited-only pairs / inherited occurrences | 7,380 | 11,731 |

Pairs classified as inserted can also contain inherited occurrences; the last
row's pair and occurrence columns therefore summarize different aspects.
`12,536 = 3,140 + 7,380 + 2,016`, and
`24,757 = 4,854 + 11,731 + 8,172` for this export. Four of the 8,172 excluded
occurrences are boundary-only ambiguities; the other 8,168 are not attributed
because the target fails eligibility checks. The broader raw-pair count is 17,948:
5,412 additional pairs lack strictly earlier source-page evidence. The 2,519
excluded/ambiguous revisions are another counting unit, not that pair remainder.

These occurrence identities are dataset-specific. The general engine's inherited
counter can include inherited spans in an excluded pair that also contains a
boundary-only ambiguous span. Here all four ambiguous spans belong to the four
boundary-excluded pairs. Eligible spans contain no ambiguities, and their
16,585 total equals 4,854 inserted plus 11,731 inherited. No inherited spans
remain in excluded pairs in this run. A regression test now documents the more
general counter scope, rather than imposing this dataset's identity universally.

See [counts](../studies/wiki_case_study/results/counts.json),
[analysis implementation](../src/tracebench/wiki_analysis.py), and
[regression tests](../tests/test_wiki_analysis.py). The 70.15% inherited-only share
uses the 10,520 eligible-pair denominator. Raw-to-retained reductions are not
inherited-text rates or source-use error rates.

### 2. The occurrence-attribution rule is explicit and tested

The frozen rule uses character `SequenceMatcher(autojunk=False)` alignment.
A bounded literal title match is classified as inserted if **any title character**
overlaps an insert/replace span, after source-order and target-eligibility checks.
It does not require the entire title to be inserted. Unchanged title characters
inside a replaced line remain inherited when mapped through an equal span to an
already bounded predecessor occurrence. Deletion that creates only a token
boundary is ambiguous. Exact snapshot restoration and publisher recreation
relations have their own exclusions.

Five final regression cases were added without changing this rule: two
one-character title corrections, repeated identical passages, a moved passage,
and a mixed inherited/boundary-ambiguous pair. A move can be represented as a
deletion plus insertion under the chosen alignment. Accordingly the claim is
**occurrences classified as newly inserted under the fixed comparison rule**,
not newly authored ideas or new information transmissions. Multiple plausible
alignments remain a limitation.

### 3. Lexical ambiguity stays in the frozen result

The [AI-assisted review](../studies/wiki_case_study/AI_REVIEW.json) retained all
20 hash-selected pairs. `DataUSA` can name an external provider; the generic
`WillkommenImWiki` was not in the frozen navigation exclusions. These are valid
literal extractions under the stated target and do not establish intentional
references to those wiki pages. No exclusions were retuned after inspection.

All candidate exposure remains unknown and source use unobserved. Observed
handles are not stable runs. Save/probe metadata and posted read assertions are
not authenticated source-read/delivery/context receipts. Human-review fields
are blank. Neither the prior AI review nor this final AI-assisted implementation
review is independent human validation or an estimate of source-use precision.

### 4. Executed source and the review snapshot are pinned separately

The wiki [result manifest](../studies/wiki_case_study/results/manifest.json)
already pins all four executed `wiki_*.py` source files, all four generated
outputs and the frozen protocol. They still match. The base Git commit alone
does not identify the uncommitted implementation.

`REVIEW_MANIFEST.json` at the ZIP root additionally pins every packaged file,
including the current CLI, tests, dependency lock, documentation and curated
results. Its file-table digest identifies this whole review snapshot. The
archive's external SHA-256 identifies its exact bytes. These are integrity pins,
not a signature, publisher authentication or a claim that the code is committed.

The original benchmark source digest matches commit
`36be8fa3682b294462ac65f8c2f750119e75cdb2`. The missing-receipt manifest has one
expected historical difference from current source: `cli.py`. Removing only the
later wiki argument/dispatch blocks reproduces its recorded SHA-256
`08ccaff8ca97e9c588b28cd37cd9da1ed442e35ba89e209193fb1eaf0441e276` exactly.
All its other recorded source hashes match. Historical manifests were preserved,
not rewritten to describe newer code.

## Verification and reproduction

[Final validation](VALIDATION.json) records the current checks. The original
wiki validation's 214-test count is historical; five additional regression cases
bring this review to 219 tests. No simulation grid or real-data census was
retuned or extended for this final review. All 21 protected prior files and the
frozen wiki artifacts remain byte-identical.

Verify the archive in place, without executing its contents or needing the raw
public dataset:

```sh
python scripts/review_snapshot.py --verify /path/to/agent-swarm-review.zip
```

After extracting a reviewed archive into a fresh directory, run:

```sh
uv sync --frozen --extra dev
uv run pytest -q
uv run ruff check .
```

The frozen study commands and raw-data acquisition pins remain in the study
reports and [case-study guide](../case_study/README.md). The bundle deliberately
omits the raw corpus; actual-data reruns require separately obtaining those exact
publisher bytes. Do not substitute the old remote `main` tree for this snapshot.

To rebuild a review snapshot from this working checkout:

```sh
python scripts/review_snapshot.py --build artifacts/review/another-review.zip
```

The builder refuses overwrite, uses fixed ZIP metadata and an explicit directory/
file allowlist, and excludes Git history, credentials, local configuration,
environments, caches and raw data. Verification checks every declared file and
rejects altered bytes or unexpected members. A whole-package checksum does not
replace reviewing the scientific assumptions.

## Completion boundary

The three bounded research components and local submission write-up are complete.
The [official logistics](../docs/HACKATHON.md) list Sunday, October 4, 2026,
5 p.m. Pacific / **8 p.m. Eastern** as the deadline. The submission form's exact
field limits and terms could not be inspected because it returned HTTP 403.
The short write-up satisfies the stated write-up-or-video choice; no video is
claimed. No numeric judging weights have been invented.

This handoff and `VALIDATION.json` record the prepublication review. After that
review, the user authorized committing and pushing the completed work; earlier
uncommitted/publication statements describe the review snapshot, not the current
Git checkout. Repository visibility, deployment and competition submission remain
separate actions. The researcher can inspect the pushed repository revision or
the offline ZIP; the current connector cannot send a message there automatically.

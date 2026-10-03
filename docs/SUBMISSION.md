# Trace Completeness Curves

**Question:** What can a swarm's recorded activity establish about which agent used information from another?

## Synthetic benchmark with known structural source-use labels

This project benchmarks source attribution when investigators have incomplete logs. A lightweight simulator generates runs with shared tasks, synchronized activity, disposable handles, and occasional content reuse. It records which prior output was actually selected as a cross-run source, while keeping that label hidden from the investigators.

The original study views the same world through five progressively richer observation regimes: writes, stable run identity, requests, successful delivery, and channel context provenance. This removes **telemetry types**: a regime either exposes an entire record type or does not. A temporal-proximity baseline and a witness-reuse investigator propose source-to-target edges. The evaluator measures edge precision and recall, error in the attributed target fraction, and false attribution in zero-transmission controls. More telemetry filters candidates, so falling raw edge counts alone are not evidence of better attribution.

The main output is a reproducible synthetic experiment, with results and a trace-completeness figure in [`results/REPORT.md`](../results/REPORT.md). A local evidence explorer lets readers compare methods and observation regimes. The initial study finds, at transmission parameter `0.3` and shared-wave strength `0.9`, that mean witness precision rises from `0.082` with writes only to `0.753` with context, while mean recall remains `0.521`. Mean absolute target-fraction error rises from `0.030` with requests to `0.059` with context. The report includes intervals across 12 simulated world seeds. These are synthetic outcomes, not real incident results.

The distinction between metrics matters: better edge precision need not produce a better estimate of how many outputs used another run's content. In this complete, noiseless logging baseline, all true candidates survive telemetry filters, so true-positive counts and recall are constant and defined precision cannot decrease. Those directions are structural. The magnitude of errors, remaining false attributions, and nonmonotonic target-fraction error are measured.

## Frozen missing-receipt follow-up and its observed tradeoffs

A separate [missing-receipt follow-up](../studies/missing_receipts/results/REPORT.md), informed by review and **not preregistered**, tests **incomplete records within available telemetry types**. Each world is generated once, then delivery or context receipts are erased at nested retention levels. The events, writes, identities, direct source-selection truth and eligible denominator remain fixed; a missing record is not a delivery or context event that failed to occur. A conjunction filter is compared with an evidence-aware policy that accepts valid authenticated context evidence despite missing upstream logs and keeps unresolved exposure separate from predictions. Authentication and coarse logging-completeness assurances are explicit assumptions. The follow-up reports paired world-level differences, actual retained fractions, false attribution and unresolved burden alongside recall.

Target-level false positives and false negatives are now reported separately from edge errors. Their signed difference divided by all writes equals the signed source-use-fraction error; their sum divided by all writes gives target disagreement. This exposes cancellation hidden by a small aggregate error. Neither unresolved candidates nor authenticated exposure are labeled verified source use. The original analysis plan and baseline results remain unchanged.

The follow-up evaluates 40 fixed worlds using seeds 200–219. At transmission parameter `0.3` and nominal delivery-record retention `0.5` (actual pooled retention `0.4997`), the paired evidence-aware-minus-conjunction witness comparison gains `0.252` recall [95% world-bootstrap interval `0.237, 0.266`], adds `0.011` false-attributed targets per write [`0.009, 0.014`], and reduces target disagreement by `0.033` [`0.029, 0.037`]. The temporal comparison instead increases target disagreement by `0.150` [`0.139, 0.161`], despite gaining recall. Erasing context records gives identical scored predictions under both policies; the comparison policy additionally identifies unresolved exposure. All retention levels, zero-use controls, actual record fractions and paired comparisons appear in the [follow-up report](../studies/missing_receipts/results/REPORT.md). Mechanical policy properties are established by unit tests, not presented as discoveries.

The key distinction is between **a source being present** and **a source being used**. Context provenance does not expose the hidden selection label. Even a correct source-use attribution does not establish that the source was counterfactually necessary: another source or a shared task might have produced the same output.

## Public-wiki evidence audit with unknown true source use

The separate [German-wiki case study](../studies/wiki_case_study/REPORT.md) applies the evidence distinctions to a pinned public revision export. The official five-file release and supplementary other-wiki records were acquired through publisher-exposed HTTPS links; expanded-file hashes match the publisher's checksums. The release contains 14,591 revision snapshots across four wikis; all 13,403 DSE revisions on 3,908 pages are in the target scope. The [source manifest](../studies/wiki_case_study/source_manifest.json) records retrieval, byte counts, hashes, release counts and schema limitations. Raw records remain outside the tracked repository.

This exploratory, review-informed audit has a different target from the simulator: **newly added literal references to previously observed wiki page names**. A frozen [analysis protocol](../studies/wiki_case_study/ANALYSIS.md) compares snapshot reference counts with references attributed to inserted character spans relative to the preceding revision on the same page. It preserves unchanged tokens within replacement lines, excludes own-title and declared navigation-title matches, flags uncertain history and restoration, and retains every qualifying earlier source revision. Repeated appearances, quotations and inherited text do not establish original authorship or source selection.

The fixed rule finds **12,536** naive revision-reference pairs with strictly earlier source-page evidence, of which **10,520** pass attribution eligibility. Those eligible pairs comprise **3,140 newly inserted pairs** and **7,380 inherited-only pairs** (70.15%). The inserted pairs contain **4,854 occurrences** across **2,500 target revisions** and **1,128 observed handles**. Thus inherited text accounts for most eligible snapshot pairs under this rule; this checks a known cumulative-text issue and does not identify false-positive source use.

Of all 13,403 DSE target revisions, **10,884** are attribution-eligible and **2,519** are excluded or ambiguous. Exclusion reasons overlap: 2,228 have ambiguous predecessor order, 1,272 restore an earlier snapshot, 63 carry publisher recreation relations and 11 lack a predecessor. The 2,016-pair reduction from naive to eligible snapshots is separate from inherited-only content. Full units, denominators and overlapping exclusions are in [machine-readable counts](../studies/wiki_case_study/results/counts.json).

The audit reports revision-reference pairs, inserted occurrences, target revisions, observed handles, inherited-only matches and exclusions separately. The occurrence accounting is 24,757 snapshot occurrences = 4,854 classified as inserted + 11,731 inherited + 8,172 excluded/ambiguous for this export. Its source-linked cards and [fixed hash-selected review sheet](../studies/wiki_case_study/results/review_sheet.json), with ten inserted and ten inherited-only pairs, test observable extraction correctness. Mechanical offset checks and [AI-assisted review](../studies/wiki_case_study/AI_REVIEW.json) are identified as such; human review fields remain blank. Differences between snapshot and insertion counts describe sensitivity to text attribution, not a source-use false-positive rate or improved causal accuracy. The fixed rule counts any overlap of title characters with an insert/replace span; a moved passage can therefore count as inserted without establishing new authorship.

All 20 reviewed pairs follow the frozen extraction rule, but the review also exposes semantic ambiguity: a provider name (`DataUSA`) matches a wiki title, and a generic welcome title (`WillkommenImWiki`) remains outside the frozen navigation exclusions. Those matches stay in the counts. Rule compliance does not establish an intentional wiki reference, and the review is not independent human validation.

The available event stream contains saves, deletions, reverts and a narrow failed-probe population. It is not a complete read log. A posted assertion of reading a page is not a server request or an authenticated receipt. Stable run identities, authenticated delivery/context receipts and direct source-selection labels are unavailable in this release. Observed handles are not runs; absence of a telemetry type is not an empty complete stream, and a missing record does not mean an event failed to occur. Exposure remains unknown and true source use unobserved. No real-data precision, recall, theta, confidence interval or copying-rate estimate is reported.

The wiki audit demonstrates applicability of the evidence distinctions; it does not externally validate synthetic accuracy. The three studies support different claims. Together they provide reproducible synthetic error measurements and an auditable account of what the public records can establish. See [`EVIDENCE_CARD.md`](../EVIDENCE_CARD.md), [`LIMITATIONS.md`](../LIMITATIONS.md), and [`docs/RELATED_WORK.md`](RELATED_WORK.md) for the evidence boundary.

## Reproduction and submission status

Code: <https://github.com/yvrohith/Agent-swarm>

Reproduce the initial study:

```sh
uv sync --frozen --extra dev
uv run tracebench benchmark --output artifacts/replication --seeds 12 --runs 120
```

Use a new directory for a repeat run, or explicitly pass `--overwrite` to replace prior initial-study replication outputs. The missing-receipt follow-up uses its [frozen configuration and reproduction command](../studies/missing_receipts/results/REPORT.md#reproduce).

After obtaining the pinned public files described in the [case-study guide](../case_study/README.md), reproduce the wiki audit in a fresh output directory:

```sh
uv run tracebench wiki-audit --archive data/raw/wiki/full-wiki-logs.zip \
  --other-wikis data/raw/wiki/other-wikis.json.gz \
  --protocol studies/wiki_case_study/ANALYSIS.md \
  --output artifacts/wiki-replication
```

This write-up and the repository link address the organizer's write-up-or-video and code-link deliverables. See [`docs/HACKATHON.md`](HACKATHON.md) for the official deadline and submission link. Exact form limits and terms remain unverified.

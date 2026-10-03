# Submission preparation

The [Swarm Chasing hackathon home page](https://swarmchasing.com/) and its
[official logistics page](https://swarmchasing.com/logistics/) were independently
retrieved with HTTP 200 on **October 3, 2026, at 12:20–12:21 p.m. Eastern
(America/New_York)**. The requirements below come from those organizer pages.

## Verified organizer requirements

**Submissions are due Sunday, October 4, 2026, at 5:00 p.m. Pacific / 8:00 p.m.
Eastern**, including online participants. The logistics page links the
[submission form](https://airtable.com/appFBFzD2Cv2rYCG5/shr8KXOLvo3xV9bnZ) and
specifies one submission per team, containing:

1. A short write-up or video explaining the project.
2. A GitHub repository link containing the code.
3. Optionally, a write-up of real results found using the tool.
4. Names and email addresses of everyone on the team.

The organizer permits solo or team projects, online participation, other datasets,
and work started before the weekend. The home page explicitly includes tracing
information spread and web/digital forensics among its suggested directions, and
links the German-wiki export as an allowed example dataset. These fit this project's
scope; they are suggestions, not grading categories.

The logistics page says online and in-person teams are judged alike by Grove
Research and AI Village staff, with decisions expected roughly a week afterward.
Neither retrieved page publishes scoring dimensions, weights, or minimum performance
thresholds. None are inferred here. In-person demos are approximately two minutes
each, Sunday 6:00–7:00 p.m. Pacific, from a shared computer; the organizer asks teams
to have their code on GitHub before those demos.

## Research artifacts

The three completed components address different research questions.

| Component | Artifacts | What it establishes |
| --- | --- | --- |
| Original synthetic benchmark | [Claims](../CLAIMS.md), [report and figure](../results/REPORT.md) | 144 simulated worlds and 1,440 evaluations with known structural source-selection truth; complete-log filtering properties are model invariants. |
| Missing-receipt follow-up | [Frozen protocol](../studies/missing_receipts/ANALYSIS.md), [paired results and recall figure](../studies/missing_receipts/results/REPORT.md) | 40 fixed worlds, 1,280 evaluations and 640 paired contrasts; observation-only record loss exposes recall, false-attribution and unresolved-burden tradeoffs. This is review-informed, not preregistered. |
| Public German-wiki audit | [Source manifest](../studies/wiki_case_study/source_manifest.json), [frozen protocol](../studies/wiki_case_study/ANALYSIS.md), [report](../studies/wiki_case_study/REPORT.md), [review sheet](../studies/wiki_case_study/results/review_sheet.json) | A descriptive audit of new versus inherited literal page-name references across 13,403 DSE revisions. Source-use truth is unavailable; exposure stays unknown. |

The [submission write-up](SUBMISSION.md) explains all three components and links their
reports. The code repository is [yvrohith/Agent-swarm](https://github.com/yvrohith/Agent-swarm).
The wiki report supplies the optional real-data results with explicit limits: its
3,140 inserted reference pairs are not verified source-use edges or a copying-rate
estimate. Human-review fields remain blank; automated checks and the AI-assisted
review are labeled separately. Raw public exports remain ignored and are not
redistributed in this repository.

The [local evidence explorer](../demo/index.html) covers the original synthetic
benchmark. It is a supporting demo, not a hosted deployment. Reproduction commands
are in the [README](../README.md), individual reports and
[case-study guide](../case_study/README.md). The [evidence card](../EVIDENCE_CARD.md),
[limitations](../LIMITATIONS.md) and [related work](RELATED_WORK.md) state the evidence
boundaries.

## Remaining submission checks

| Item | Verified status | Remaining action |
| --- | --- | --- |
| Deadline and portal | Date, time, timezone and portal link verified on the official logistics page | Complete the linked form before the deadline. |
| Form fields and limits | Required content listed above is verified on the logistics page; a read-only GET of Airtable returned HTTP 403 | Verify the live form's exact fields, length limits and attachment requirements before submission. |
| Team details | Names and email addresses are required | Include the final team roster. |
| Code availability | Code and curated results are available in this repository | Reference the repository revision containing the submitted results. |
| Judging rubric | No detailed rubric on either retrieved official page | Record any later organizer-issued rubric without substituting informal project criteria. |
| Licensing, redistribution and other eligibility terms | No detailed licensing or additional eligibility terms found on the two retrieved pages | Check any terms presented by the final form; preserve data provenance and avoid redistributing raw exports. |

## Source record

Retrieved HTML was inspected as inert text; no scripts were executed. The following
hashes identify the specific official page bytes used for this check, not a promise
that the live pages will remain unchanged:

| URL | Retrieval date (Eastern) | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `https://swarmchasing.com/` | October 3, 2026, 12:20 p.m. | 96,747 | `4fa69d5653907d15bd8349af85d0e986ce26bc65e04fdf4efb2fd7ab22382fa8` |
| `https://swarmchasing.com/logistics/` | October 3, 2026, 12:21 p.m. | 31,361 | `80ccf6a945b3020662ba7a39c28686cff1e738ab1eeac11a9c2a84c99da82e89` |

The page gives October 3–4, Saturday–Sunday; the year is the current 2026 event
context. The Eastern deadline uses the `America/Los_Angeles` to `America/New_York`
conversion for October 4, 2026 (PDT to EDT).

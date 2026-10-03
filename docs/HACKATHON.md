# Submission preparation

This project is being prepared for the [Swarm Chasing hackathon](https://swarmchasing.com). The official site returned HTTP 403 during this setup session on October 3, 2026. The user subsequently supplied an excerpt of the official page. The requirements below are based on that excerpt; the live page was not independently read. The research-plan attachment remains a project proposal, not an authoritative competition specification.

## Requirements from the supplied official-page excerpt

The event says participants can work on whatever they like. Suggested directions include discovery, understanding and visualization, answering multi-agent research questions, agent whistleblowing, tracing information spread, web/digital forensics, and aggregating datasets. This project fits **tracing information spread** and **digital forensics**.

The final submission calls for:

1. A short write-up or video explaining the project.
2. A link to the GitHub repository containing the code.
3. Optionally, a write-up of real results obtained using the tool.

The excerpt describes approximately three to five judges from AI Village staff and field experts, with decisions shortly afterward. It does not provide numeric grading weights or a detailed rubric. No weights or minimum performance thresholds are inferred here.

`docs/SUBMISSION.md` is the short project write-up draft; the code repository is [yvrohith/Agent-swarm](https://github.com/yvrohith/Agent-swarm). The synthetic experiment report belongs in `results/REPORT.md`. Synthetic benchmark outcomes are clearly labeled and should not be presented as real incident results. The optional real incident analysis remains pending.

## Proposed deliverables

These are project commitments derived from the research plan, **not verified organizer requirements or grading criteria**.

| Deliverable | Reviewable artifact | Acceptance criterion |
| --- | --- | --- |
| Precise research question | `CLAIMS.md` | Define realized source use, eligible outputs, and the distinction from counterfactual influence. |
| Reproducible synthetic benchmark | Simulation, observation, estimation, and evaluation code | Fixed seeds reproduce output; estimators receive only the chosen telemetry projection. |
| Telemetry ablation | `results/REPORT.md`, `results/trace_completeness.png`, and `results/trace_completeness.svg` | Compare five observation regimes on the same underlying worlds, including zero transmission. |
| Honest empirical conclusions | Report plus `EVIDENCE_CARD.md` | Separate structural precision/recall behavior in clean logs from measured target-fraction errors; explain denominators and uncertainty. |
| Small explorable demo | Local evidence explorer | Show measured errors and describe exactly which additional evidence a regime exposes. |
| Research context | `docs/RELATED_WORK.md`, `LIMITATIONS.md` | Distinguish existing identification problems from this benchmark's contribution and list model assumptions. |
| Real incident extension | `case_study/README.md` | Remain a scaffold until source provenance, license, identity mapping, and data availability are verified. |

The main contribution is a controlled measurement experiment: the same synthetic world is projected into different logs, and simple investigators are scored against hidden source-use labels. The temporal estimator is a proximity baseline, not a fitted Hawkes process. The implemented clean-logging baseline preserves every initially proposed true edge under telemetry filtering; true-positive counts and recall therefore stay constant while defined precision cannot decrease. Absolute target-fraction error can still be nonmonotonic. Missing or corrupted telemetry is a future stress test. The synthetic experiment is implemented; the real incident extension remains optional until its evidence is available.

## Official requirements still to verify

| Requirement | Current status | Needed before submission |
| --- | --- | --- |
| Eligible project categories and research expectations | Broad scope described in the user-supplied excerpt | Check for additional eligibility rules in the complete current rules. |
| Judging rubric and weights | No detailed rubric in the supplied excerpt | Record official dimensions and weights if published; do not substitute the proposal's informal ratings. |
| Deadline and timezone | Unverified | Confirm the organizer's date, time, and timezone. |
| Submission portal and required links/files | Write-up/video and code link specified in the supplied excerpt | Confirm the portal, any form fields, and formatting limits. |
| Team, licensing, data, and prior-work rules | Unverified | Check eligibility and attribution requirements against the final artifact. |

No competition submission or public deployment is performed by preparing these files. Once official instructions are available, update this checklist and map their actual requirements to the existing artifacts.

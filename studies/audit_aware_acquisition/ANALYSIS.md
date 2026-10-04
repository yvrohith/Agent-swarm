# Audit-aware acquisition: fixed analysis protocol

This review-informed follow-up asks how much additional retrieval exposes archive-detectable model conflicts after nominal acquisition proposes stopping, and how much unsupported certainty remains. Conflict detection and evidentiary warrant are separate outcomes. An alarm does not establish that the target claim is false; absence of an alarm does not validate the archive model. No permitted query can distinguish opposite-claim constructions with the same complete signature.

## Inputs and known baseline

Reuse the 40 saved acquisition problems, four separate development problems, original 30 structural groups, and completed omission closures k = 0, 1, 2. Sources and contracts are the [archive-model study](../archive_model_misspecification/METHOD.md), its [retained results](../archive_model_misspecification/results/details.json.gz), and the [original acquisition method](../evidence_acquisition/METHOD.md). Keep worlds, omissions, initial records, catalogues, aliases, prices, claims, and nominal policy unchanged. No new loss mechanism, prior, corpus, expanded optimizer, or simulator history is introduced.

Reconcile retained inputs and nominal stopping histories before new audits. The preceding study reported 392 original signatures, including 271 definite and 121 ambiguous ones; 39 new signatures at each nonzero k; 71 and 86 original full-signature support losses at k=1 and k=2; and unsupported nominal stopping verdicts on 96 original and 13 new signatures at either nonzero k. Nominal acquisition detected no conflict. These motivating outcomes are already known and must be verified from source artifacts, not forced into new results. The audit arms and budgets are new design choices; this is not a pristine holdout or independent confirmation.

For each signature s, H0(s) is its retained original-prior exact-policy stopping history. Verify actions, outcomes, charges, and nominal certificate references, including historical k=0 parity. Base acquisition cost is sunk and reported separately from audit cost. Neither the nominal policy nor a historical result is reoptimized or revised.

## Fixed arms and information boundary

[config.json](config.json) fixes exactly four arms; [METHOD.md](METHOD.md) gives their formal selectors.

| Arm | Allowed selection rule |
| --- | --- |
| A: `no_audit` | Preserve H0 and its proposal; make no added lookup at any budget. |
| B: `cost_order` | Cheapest unqueried catalogue action, breaking ties by opaque ID. |
| C: `constant_first` | Cheapest unqueried action with one possible nominal answer; if none, cheapest remaining action. Recompute after every paid answer. |
| D: `closure_informed` | Use the fixed hypothetical k=2 signature envelope to maximize immediate conflict-producing signature count per cost; cost/ID ties, with C as the zero-score fallback. |

B/C use nominal information only. D has additional hypothetical model knowledge, including when actual k is 0 or 1; evaluate and report it separately from the primary C-versus-B comparison. Its score counts distinct possible signatures, not world multiplicity, parent count, truth labels, or calibrated probabilities.

Selection receives the permitted model information, initial evidence, public catalogue/prices, and paid history. It must not receive actual k, full realized signature, unqueried answers, omission/parent provenance, realized claim truth, full-archive conflict labels, hindsight contradiction subsets, or remaining funds. Within each arm, the same paid history must give the same next action across hidden realizations, k values, traversal order, and cache state. Empty compatible k=2 design-envelope support is a failed condition, not permission to rebuild the envelope.

For B/C/D, a private archive charges each requested catalogue action and returns its original typed payload. Update nominal compatibility immediately after the answer; stop on the first conflict and withhold a nominal definite conclusion. Otherwise continue until catalogue exhaustion or budget censoring. Nominal or expanded claim terminality supplies no extra stopping rule. A constant nominal answer is still unobserved until paid for. Preserve every alias action, charge it at most once, and report duplicate-record overhead without treating aliases as independent evidence.

## Extra budgets and schedule

Let residual_cost be the sum of prices of actions unqueried at H0. Audit budgets are floor(b × residual_cost / 100), for b = 0, 25, 50, 100. Keep all coincident conditions, including zero residual cost. The selected order is independent of budget: if the next action is unaffordable, stop without substitution or reranking. These are budget-censored orders, not budget-optimal policies.

Execute 40 problems × three k conditions × four arms × four budgets: **1,920 aggregate cells**, with distinct full signatures enumerated inside each cell. This implementation executes each budget-limited run directly. Budget independence also implies a prefix relationship across budgets; shared certificate computations do not create extra independent trials or separately charged investigator sessions.

## Outcomes and denominators

Retain base/final histories, ordered actions, typed answers or verifiable references, base/added/combined costs, query counts and bytes, first-conflict position, termination reason, coverage, and the original proposal. Charge empty-result payloads as well as positive records. Store actual-k expanded claim and operational statuses on the identical paid history, using all compatible worlds rather than a chosen actual world.

For conflict detection, report detected and cutoff-missed full conflicts, false alarms on original signatures, added query/cost at first conflict, and expenditure on nominal-compatible archives. Detection fractions condition on the new-signature population, separately for each k. k=0 has no such population, so conditional detection is undefined. The 39 k=1 and 39 k=2 signatures are repeated observations of the same signature set, not 78 independent conflicts.

For warrant, compare final expanded support with the pre-audit nominal proposal. Mathematical restoration requires a previously unsupported definite proposal to have that **same** proposal supported by all final expanded-compatible worlds; an opposite definite status is not restoration. Record this axis independently from withdrawal on alarm: the two can coexist if acquired evidence restores support but also contradicts another nominal expectation. Withdrawal alone never establishes restoration. Separately count unwithdrawn restoration, still-unsupported proposals without alarm, and initially supported proposals that remain supported. Report joint final expanded statuses and alarms; retrospective warrant is not a conclusion established by a nominal-only auditor. Track archive irreducibility separately from definite claims and unresolved pending. Preserve full-catalogue ambiguity separately from uncertainty caused by incomplete retrieval.

Keep original, new, and all-signature populations separate. Report pooled counts with signature denominators, then equal-problem means of within-problem quantities and the existing structure-balanced means. Apply the latter by averaging variants within a group and then groups equally. Retain strata. Conditional fractions with no eligible signatures are undefined with explicit problem/group denominators; failures remain visible and cannot be silently dropped or treated as zero. No physical-world counts become a deployment prior.

The primary paired comparison is C minus B within the same problem, k, budget, and population. Report cost differences alongside detection, coverage, unsupported conclusions, restoration/withdrawal, and lower/tied/higher problem counts. More detection and less cost are different axes; low expenditure caused by stopping before an informative query is not automatically efficient. Report D comparisons as extra-model-knowledge comparisons. Preserve flat and adverse effects without changing rules.

`added_cost_at_detection` is conditional on the signatures detected by that arm; finite-budget detected subsets can differ. Its per-problem differences therefore need not compare the same detected archives. Primary added-cost contrasts use the identical full original/new/all signature population and must be assessed alongside detection and catalogue coverage. Final supported/unsupported definite-proposal flags remain separate from alarms.

## Known consequences and validation

Zero budget and A must reproduce H0 and zero added cost. Truthful answers from an original signature cannot produce a nominal conflict. At full residual budget, B/C/D must detect every new-signature conflict; failure is an implementation issue, not a successful partial result. Full acquisition on original signatures must retain the known 71/86 unsupported negatives, with 25/10 of the original 96 stopping losses repairable at k=1/2. Because the same signatures at k=1/2 receive identical selector inputs, their paths/costs must agree even when retrospective warrant differs. These endpoints and support invariants are correctness consequences, not new discoveries. The new measurements are finite-budget coverage, extra cost, and their relation to support.

Qualify on only the four development problems and tiny fixtures. Test information isolation and same-history actions, recomputed constant status and nonconstant fallback, continuation after nominal terminality, first-conflict stopping, costs/bytes/rounding, unaffordable-next-action censoring, aliases, distinct-signature D scores and fixed k=2 design input, certificate rejection, all-world warrant, irreducibility, and known indistinguishable witnesses. Check budget-prefix consistency against direct runs. The independent reference reconstructs typed answers from retained records, filters nominal/expanded worlds, and checks paid histories, charges, first contradiction, support, and coverage; it must not trust a policy result flag.

Freeze arm definitions, budgets, envelope, dependencies, tie rules, grouping, reporting rules, and development evidence before **new audit-policy outcomes**. Preserve historical files byte-for-byte and keep checkout preservation separate from scientific dependencies. Reuse limits of eight actions, two outcomes, 4,096 expanded worlds, 256 signatures, and the existing 100,000-state guard if a nominal solve is required. Retain unavailable cells without truncation or replacements. Do not overwrite results or invisibly regenerate a freeze after outcomes.

Local planning/checking measurements describe implementation overhead only, separate from retrieval units; no new timing competition, sampling intervals, p-values, or independent-incident claims are authorized. Complete the fixed study without tuning, and retain null findings. No network, models, credentials, private reasoning, dependency downloads, spend, old-file edits, staging, publication, or presentation/submission artifacts are part of this task.

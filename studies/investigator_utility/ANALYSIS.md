# Investigator utility: bounded evidence-reasoning pilot

This is a review-informed, exploratory follow-up, not a preregistered discovery.
The completed baseline is `7abea1a8f0bc2ac38bd6d3c7a2bdac83cdafe5f6`.
The original benchmark, missing-receipt study and descriptive wiki audit retain
their own targets, protocols and results. This protocol tests a different target:
whether a text-only investigator reaches conclusions justified by its evidence.
It does not score recovery of an inaccessible simulator source-selection label.

## Comparison and evidentiary target

Arm A receives raw records, explicit assumptions, atomic claims and a competent
evidence-grounded investigation task. B adds a strong checklist about inherited
text, identity, scoped logging completeness, receipt semantics and exposure versus
use. C receives exactly B plus deterministic record indexing, full before/after
character opcodes, source locators and equality groups on public record fields.
**C minus B is primary.** B minus A and C minus A are secondary.

All arms retain byte-identical canonical raw evidence, identical assumptions,
common system/task/response instructions and the same output allowance within a
model. Assistance never classifies title occurrences, counts claim-specific
matches, declares exposure/use status, or receives gold/certificates. It exposes
no historical facts withheld from A/B. The original evidence cards are not used
as assisted views. Full texts remain present even when an alignment is supplied.

For a Boolean claim, consider the nonempty set of worlds compatible with the
supplied records and declared assumptions. Gold is `established` when all satisfy
the claim, `ruled_out` when none do, and `unresolved` when they disagree. Inconsistent
bundles are rejected before inference rather than receiving vacuous labels.
This applies standard incomplete-information reasoning; it is not a new theorem.
Reorganizing the same facts preserves this evidentiary target but may change an
investigator's performance. No unverified literature claims are added.

## Development and selection

At most four development cases: two wiki windows and two synthetic fixtures.
Evaluation targets 24 cases: 16 wiki and eight synthetic. No investigator answers
are inspected before selection, labeling and request validation. Development
checks address execution, schema, evidence parity and labeling, not failure mining.
No model calls are made without the access and cost conditions below.

The wiki input is the existing pinned ZIP, SHA-256
`eb68aa12d26bf189d8bfc4ce47f4d8af66ae5ba7ebbadd429738297a3cbb25ae`,
and supplement SHA-256
`2047f3a2915fb3d237ed03d01deef306d11021a6ffc42a57a5f60918d850a5fd`.
The existing loader verifies the release; no new importer or dataset is added.
Only DSE full revisions supply target, predecessor and source-page records.
The supplement supplies no additional facts to these bounded questions.

Wiki eligibility uses the unchanged original literal matching/extraction rule:
an actual immediate eligible predecessor, strictly earlier full source-page
revisions, no ambiguous matched spans, and complete selected record texts totaling
at most 24,000 Unicode code points. No text is truncated. Creation comparisons
against an empty predecessor are excluded from this two-snapshot task. All target
and referenced pages in the prior 20-pair inspection sheet are excluded, including
other revisions of those pages. Both endpoints of every selected case are reserved
globally, so no source or target page history occurs in another development or
evaluation case. This is stricter than distinct target pages alone.

Process the `inserted` stratum then `inherited_only`. Rank eligible pairs by
SHA-256 of UTF-8 compact sorted-key JSON `["tracebench-investigator-utility-wiki-v1",
pair_key]`, breaking ties by pair key. In each stratum choose one development case
then eight evaluation cases, skipping any already reserved endpoint page.
Stratification uses mechanical extraction categories, never investigator answers.
The selection manifest records exclusions, eligible pool counts, chosen IDs,
page histories, hashes and shortages. A shortage is recorded before inference;
rules are not relaxed. The authors already examined corpus-wide counts and some
pages. The public corpus is not claimed to be uncontaminated model test data.

Each wiki case supplies four claims: at least one literal occurrence classified
as inserted, at least one inherited occurrence, source exposure, and source use.
The first two concern the declared alignment rule, not intent or new authorship.
The latter two remain unresolved without authenticated receipts or a unique
generating mechanism. Gold stores separately recomputed opcode/offset certificates
and compatible exposed/unexposed, source-dependent/independent constructions with
unchanged visible texts and feasible source timing. The independent extraction
check still shares the declared SequenceMatcher algorithm; it is not independent
human validation of the algorithm or source use.

The eight synthetic evaluation cases are fixed reasoning fixtures, not new draws
from the original simulator. Their explicit finite contract enumerates request,
delivery and context possibilities with the necessary event chain; a target can
copy an exposed source or independently fill a supplied shared-input scaffold.
Both mechanisms must render the same observed output. Authentic surviving receipts
constrain events, while completeness applies only to its named channel, source,
recipient and interval. Scope-mismatched completeness is irrelevant. Unspecified
logging is incomplete. Exhaustive compatible constructions certify all labels;
unresolved claims retain concrete disagreeing constructions. Gold cannot merely
toggle a hidden source label while leaving an invalid mechanism in place.

The cases include downstream context surviving upstream log loss, successful
delivery with unknown context, complete scoped absence, actual event exclusion,
shared-input alternatives and positive exposure with ambiguous use. Identical
observations with alternative mechanisms form one case. Source-use claims are
never manufactured as established when these receipts cannot resolve them.

## Responses, leakage and failures

Each response is one JSON object with `case_id` and `answers`. Each answer has
exactly `claim_id`, one of the three status strings, `evidence_ids` and a nonempty
`reason` of at most 400 characters. Reasons are brief evidence explanations, not
private reasoning traces. Evidence IDs may name records or explicit assumptions.
The caller never supplies tools, retrieval, browsing or persistent conversation.
Incident text is quoted untrusted evidence, not instructions. Embedded links and
payloads are not followed; redacted identities are not reconstructed.

Malformed roots, duplicate JSON keys, wrong case IDs, unknown claim IDs and extra
root fields invalidate the response. Missing or duplicate expected claims
invalidate those claims without dropping their denominators. Invalid per-claim
schema/status/reason length is a failure. Evidence-ID existence is checked
separately; no claim is made that an existing ID semantically supports a rationale.
Empty citation lists are allowed and explanations are not graded semantically.
No LLM grading, repair or answer-based retry is permitted.

Tests and prefreeze validation compare exact raw bytes across A/B/C, verify that
B is preserved in C, change evaluator-only gold/truth without changing requests,
reject evaluator fields at the public-view boundary, and check that assistance
contains only permitted intermediate fields. Complete serialized development
requests are retained locally for mechanical and AI-assisted inspection. No human
review is fabricated. Prompt characters, UTF-8 bytes and conservative input-token
bounds are recorded. A request above 160,000 UTF-8 bytes is rejected before any
inference; model context bounds can impose a stricter limit. No silent truncation.

## Access, freeze and cost

Use at most two authorized families, selected for access/capability/cost before
evaluation, not for desired results. Two models imply 144 evaluation requests;
one authorized model requires an explicitly frozen 72-request pilot. No authorized
models means a tested preparation with zero investigator observations. Conversation
agents or test transports do not substitute for a metered investigator API.

Model configuration must record exact model ID, family, official endpoint,
credential-variable name (never its value), supported context/output/reasoning
limits, provider-default decoding, and verified official price/limit documents
with retrieval timestamps and hashes. IDs, pricing and support are not invented.
The small OpenAI and Anthropic adapters reject tools and unsupported decoding
settings. Any reasoning tokens must fit the provider's enforced total output cap.

The task ceiling is USD 25 or a lower authorized configured limit. Reserve a
conservative input bound (serialized UTF-8 bytes plus 4,096 framing tokens) and
maximum output/reasoning cost before every possibly billable attempt, using
verified provider contracts. Reject a request whose bound exceeds context.
Unknown-cost failures retain the full reservation. Regular-price usage estimates
are labeled as estimates, not verified invoices. If a provider violates a token
bound, persist a halt across resumptions. Missing credentials on resume do not
erase prior accounting. No accounts, billing changes or credits are created.

There are at most 24 unique development requests, 144 evaluation requests (72 for
one model), and 12 additional transport retries across the entire study. Errors
are not a reason to exceed the ceiling. Only explicitly retryable transport
failures may be retried; the first completed response remains final even when
malformed. Requests are stateless and serial. Hash-order cases with seed 73020,
cycling the six A/B/C permutations; 24 cases give each arm each position eight
times per model. The exact schedule and prompt hashes are frozen.

All development/evaluation/resume calls share the fixed ignored
`artifacts/investigator-utility/calls/` ledger. Changing the output location cannot
reset the budget. The ledger persists model/limit hashes, prompt/request identity,
UTC timestamps, attempt reservations, raw responses, usage and errors. Raw texts,
prompts and completions remain ignored; public artifacts contain hashes, minimal
case metadata, evaluator-only certificates and mechanical scores, not corpus text.

Before evaluation, freeze protocol/configuration, cases, public-view hashes,
evaluator certificates, code hashes, exact model configurations, scoring rules
and schedule. A blocked no-model freeze permits zero calls and is explicitly
incomplete as an execution design. Later access requires a new versioned freeze
before seeing any evaluation response. Genuine implementation defects require a
documented invalidated run/versioned correction, never a silently overwritten run.

## Outcomes and analysis

Report each model separately within wiki and synthetic subsets. Primary outcomes
are (1) unjustified certainty: schema-valid definite statuses on gold-unresolved
claims divided by all gold-unresolved claims; and (2) warranted-answer accuracy:
schema-valid correct definite statuses divided by all gold-answerable claims.
Always show both; cautious nonanswers cannot win by avoiding answerable claims.

Also report three-class status accuracy, correct unresolved answers, invalid or
missing-answer rate, citation-error rate, and unjustified-certainty-or-invalid on
unresolved claims. Primary status accuracy and citation validity are separate:
a correct status may cite an invalid ID. Correct-unresolved-success excludes
schema/citation failures, and certainty-or-invalid includes either failure type.
Invalid output therefore never earns successful-abstention credit. Missing calls
are scored as missing on the same frozen denominators once a model evaluation is
attempted. With no configured models, model result rows stay empty.

Average applicable claims within each case first, then average cases and form
paired differences. Report pooled numerators/denominators as audit counts, not a
replacement estimand. Bootstrap paired whole cases/page-history clusters with
2,000 percentile resamples, seed 73021; each metric/group derives a deterministic
subseed. Claims, retries, arms and models are not extra independent observations.
No applicable claims yields null; fewer than two clusters yields no interval.
These intervals concern the selected pilot, not field reliability or guaranteed
coverage. The fixed generated cases have disjoint histories, one case per cluster.

Calculate constant `unresolved`, `established` and `ruled_out` sanity baselines
without API calls, labeled analytic checks rather than investigator observations.
For each model/subset, select the lowest SHA-256(case_id) showing primary
improvement without primary loss or increased schema/citation failures; separately
select the lowest-hash C/B disagreement or deterioration. Report absent example
types as absent. Examples do not replace the fixed comparison or semantically
validate the explanations.

## Stopping and integration

Execute the fixed evaluation once if access and enforceable budget permit. Keep
null, checklist-equivalent, unfavorable and resource-limited outcomes visible.
Do not change cases, prompts, models, exclusions or thresholds to obtain an effect.
No new datasets, outage families, identity resolver, UI, agent replay or causal
interventions are added. Update the main README/submission only after actual
investigator results exist. Prepared code is not evidence of downstream utility.
No commit, push, visibility change, deployment, publication or submission is
authorized in this step.

# OpenRouter execution of the existing investigator-utility study

This is the execution record for the existing [exploratory protocol](../ANALYSIS.md),
not a new study or a preregistered discovery. The historical blocked configuration,
freeze and results remain unchanged. All 28 prepared cases, claims, gold certificates,
selection rules, A/B/C prompts and scoring code are reused without regeneration.

## Settings fixed before development

| Request model ID | Allowed provider | Documented reasoning default | Total output cap | Input reservation / million | Output / million |
|---|---|---|---:|---:|---:|
| `openai/gpt-5.6-terra` | `openai` | Enabled, medium effort | 8,192 | $2.50 | $12 |
| `anthropic/claude-sonnet-5.5` | `anthropic` | Adaptive thinking, high effort | 8,192 | $2.00 | $10 |

The output cap includes reasoning and visible answer tokens. The provider's
default decoding and reasoning settings are preserved; no tools, browsing,
response repair, caching controls or evidence truncation are requested. The
same settings apply to all three arms within each model. Routing requires
parameter support, disables provider fallbacks and limits input/output prices.
The native `openai` route excludes service tiers such as flex and fast.

The API request identifiers are aliases. The catalog additionally reported
`openai/gpt-5.6-terra-20260709` and
`anthropic/claude-sonnet-5.5-20260928` as canonical slugs. These are recorded as
metadata; the experiment does not claim to have requested immutable dated model
revisions. Provider-returned model identities are retained with the raw responses.

Terra's ordinary input rate is $2/million, but automatic cache writes cost
$2.50/million. Its reservation therefore prices every input token at $2.50.
Anthropic caching requires an explicit `cache_control` field, which is absent.
All input bounds remain below Terra's 272,000-token higher-pricing threshold.
The maximum input allowance is 41,438 tokens, including the frozen 4,096-token
framing allowance; adding the output cap gives 49,630 tokens. This fits both
documented provider context windows.

There is no separately priced base inference request under the native-provider
token-pricing contracts and OpenRouter's no-inference-markup statement. This is
a pricing-contract interpretation: the route metadata omits a `request` price
field rather than explicitly reporting zero. Optional server tools and searches
are not requested. The [metadata manifest](metadata_manifest.json) pins 18 actual
official source bodies with retrieval times and SHA-256 hashes. Their full
contents remain in ignored `artifacts/investigator-utility/openrouter-metadata-v1/`.

## Whole-study budget and request accounting

Before the first inference, the [preflight](preflight.json) bound every serialized
request using UTF-8 bytes plus 4,096 framing tokens and the maximum billable output.

| Reservation | Amount |
|---|---:|
| 24 development and 144 evaluation requests | $21.634428 |
| 12 additional transport retries at the largest request bound | $2.422488 |
| Total conservative bound | **$24.056916** |
| Authorized whole-study ceiling | **$25.00** |

Both originally preferred families were selected because authorized model access
and the complete budget fit, before any investigator outcome was observed. The
first development request is part of the 24-request allowance. The normal runner
skips its already-completed ledger entry when completing development.

All calls share `artifacts/investigator-utility/calls/`. Completed responses remain
final even if incorrect, malformed, refused or truncated; only transport failures
may be retried within the fixed cap. Unknown charges retain their reservations.
No earlier model calls or charges existed when this execution began.

OpenRouter's `usage.cost` supplies provider-reported account charges, separately
from the harness's `known_usage_cost_usd` estimate. The latter uses the configured
conservative input rate, including Terra's maximum cache-write rate, and is not
an invoice or an exact uncached-token calculation. An invoice reconciliation is
outside this study.

## Evidence and preservation checks

Before development, all 70 baseline hashes, historical frozen artifacts and the
three prepared inputs matched. All 28 public-view manifests and 84 arm-prompt
hashes reproduced. Validation checked gold certificates, identical raw evidence,
label invariance and forbidden assistance fields for all 28 cases. C contains
only public-record indexing, full character alignments and observable equality
groups; it preserves B's complete evidence and checklist and supplies no final
exposure or source-use verdicts. These are mechanical and AI-assisted checks,
not independent human validation. The existing suite passed all 431 tests and lint.

Development checks concern endpoint operation, response envelopes, termination
and accounting. They do not authorize outcome-driven changes to models, prompts,
cases, labels or scoring. The versioned evaluation freeze must precede every
evaluation response. Wiki and synthetic results remain separate, with C minus B
as the primary comparison and fixed denominators for invalid or missing answers.

The unchanged freeze generator also carries forward a generic
`model_freeze_note` describing the historical blocked preparation. That sentence
is stale in this version; the operative `status: ready`, two configured models
and 144-request manifest define this execution. The frozen bytes are preserved,
and no execution decision uses that explanatory field.

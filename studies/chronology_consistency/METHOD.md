# State-preserving repair of recorded chronology

The untouched legacy generator remains `src/tracebench/simulate.py`. New instrumentation and the immutable retiming wrapper live in this namespace. The wrapper draws no randomness, reruns no decisions, and changes only timestamps on existing offending request/delivery/context records and the resulting chronological tuple order. The comparison uses the original observer, investigators, policies and scorer.

## Captured state and timing convention

For every write, `trace.py` captures the event ID, recipient run, timestamp, generation position, source IDs in `available_context` after that iteration's installation and before source selection, request/context chain IDs created in the iteration, selected source and random-state hashes around selection. Chain records map request IDs to owning writes, source IDs and recipients, and distinguish first installation of `(recipient run, source event)` from later repeated receipts.

Read-only Python trace hooks observe the original generator's locals. They do not assign local state, draw randomness or replace the historical API. An ordinary call without hooks, a profile-only replay and the detailed traced replay must return exactly equal complete World values. The passive profile counts seeded RNG primitive `random`/`getrandbits` calls and hashes the final RNG state; detailed tracing must match that profile-only reference. Hooks are removed in `finally`, and existing trace/profile hooks cause refusal rather than replacement. This is evidence of instrumentation noninterference for each audited configuration, not validation of real agent behavior.

The independent checker reconstructs availability from the **final complete** context stream. At write w, the logged set is the set of source IDs with a context record for w's recipient and `context.timestamp < w.timestamp`. Compare exact source sets with the captured decision state. A receipt exactly at the write is not prior context. Repeated receipts do not create extra independently available sources. Reading only the partially appended stream would conceal the defect and is not an acceptable reconstruction.

Record extra logged sources, missing logged sources, distinct affected writes, source/recipient first-availability contradictions, offending chains, and time discrepancy. Keep world, write, source-pair and chain counts/denominators distinct; unaffected worlds retain explicit zero rows. No run-start event exists in the legacy model, so no such event or violation is invented.

The saved diagnostic has source `e000002` at approximately 161.995815 and a first context receipt at 189.582785, before recipient write `e000003` at 194.451660. Its actual selection state lacks the source, which is installed only while generating `e000004` at 198.778442. A receipt preceding its owning write is normal; availability before an earlier write that lacked the source is the contradiction.

## Frozen correction rule

For each existing context-bearing chain, mark it offending if its context timestamp is before any write by that recipient whose captured available-source set lacks the chain's source. Apply this test to every chain, including repeated receipts. Merely having an old source or a context timestamp before the owner does not trigger a change. A repeated receipt can itself need correction if retrospectively placed before first installation; otherwise leave it unchanged.

For an offending chain, let s be its source-write timestamp, o the timestamp of the write in whose generation the chain was installed, and p the immediately preceding recipient-write timestamp, when one exists. Define:

```text
lo = max(s, p) if p exists, otherwise s
gap = o - lo
request' = lo + gap / 4
delivery' = lo + gap / 2
context' = lo + 3 * gap / 4
```

Require finite, representable timestamps satisfying `s <= lo < request' < delivery' < context' < o`. Fail explicitly if any ordering collapses at floating-point resolution. Do not round, add epsilon, shift writes or choose another interpolation. Every offending context must already have a consistent request and delivery; missing or inconsistent upstream stages fail rather than being created. All unaffected chains keep their exact original timestamps.

Use immutable dataclass replacement for these timestamps and sort each receipt stream by timestamp. Preserve configuration, all write fields/timestamps, selections, truth edges, eligible targets, physical record identities and counts, source references, concepts, witness strings and every other non-timestamp field. The saved before/after evidence records each moved chain and the earlier decisions it contradicted. The direct checker then independently recomputes availability at **every** write; any remaining mismatch invalidates the correction.

## Why the repair suffices under the inspected generator's premises

The legacy schedule orders writes by time; each context installation occurs in one owning write's iteration before its selection; sources are earlier writes; installed context persists without removal; and each original context timestamp is strictly between its source and owner when representable. These are inspected generator premises, not assumptions about real systems. Checks enforce the needed strict intervals and complete chain/owner maps.

An unaffected context contributes no source at a recipient decision before actual installation, by the trigger definition. An offending context is moved strictly after the immediately preceding recipient write and before its owner. It therefore cannot add a source at an earlier recipient write, and it makes the source available at its owner and all later recipient writes, where the persistent captured state contains it. Taking the union over all receipts gives exactly the captured availability sets. Repeated receipts do not change this set argument. The direct full-stream reconstruction checks the conclusion separately and can reject a violated premise or implementation error.

This is a mathematical property of the state/log representation under these premises. It does not imply realistic delivery latency, agent cognition, counterfactual necessity, or that a different real scheduling policy would preserve selected sources.

## Coupled missing-record masks

The historical `corruption.py` hash key contains mask seed, channel, request ID, **timestamp**, recipient and source ID. It is order-independent but not invariant to this intervention. Running it afresh on corrected timestamps could change surviving records and mix chronology with a second treatment.

The adapter `legacy-selection-stable-physical-record-identity-v1` first applies the unchanged historical mask to the ordinary legacy context observation at each original profile, retention and mask seed. It records the resulting stable physical record identities and replays the same keep/drop decisions on the corrected observation. Identity is the record stage plus request ID, validated one-to-one with equal non-timestamp fields across versions. It never uses truth, selected-source labels or score outcomes to decide membership. Preserve writes and requests, unchanged logging/completeness metadata, original and retained counts, and actual retained fractions. Verify exact retained-ID set equality in every channel and mask, including retention 0 and 1; nominal retention below 1 remains incomplete under the original logging assumptions even if a realized mask drops nothing. Ordinary masks computed from corrected timestamps are diagnostic only and do not define the scored comparison.

Both policies within a version receive the same resulting masked observation. Investigators see only the historical observation and allowed coarse logging metadata, never mask seeds, loss labels, original counts or coupling audit data. Retention levels keep their existing nested legacy memberships. No masks or omission mechanisms are added.

## Reproduction, scoring and checks

Recover benchmark configurations from saved default configuration plus exact saved scenario/seed metadata and rows; recover missing-receipt complete configurations directly from saved world records. Verify consistency with saved configurations, CSV rows, source pins and manifests. Preserve unavailable source-digest comparisons explicitly when a historical aggregate digest refers to a different source-tree boundary; never refresh historical pins to pass verification. Compare saved generation hashes where they exist rather than claim hashes were saved for every original world.

Legacy evaluation is reproduced before corrected impact is assigned. Reproduction checks exact saved per-world metric fields and saved group means/defined-world counts. Historical confidence intervals remain saved historical outputs and are not recomputed by this sensitivity. Score differences use the same original group keys and eligible denominators, with per-world pairing and null preservation as defined in [ANALYSIS.md](ANALYSIS.md). Writes-only and stable-identity observations depend on unchanged writes and must match exactly; richer regimes are computed rather than presumed invariant. Verify equal writes, truth, target IDs, physical identities and non-time data across all worlds.

Focused tests cover the known contradiction; complete output and RNG evidence; first versus repeated receipts; late-appended earlier-timestamped records; exact unaffected-chain behavior; preserved decisions/truth; strict and unrepresentable intervals; mask membership/retention; target-error identities and grouped policy denominators; preservation failures; and refusal to overwrite frozen inputs/results. The direct chronology checker in `reference.py` imports the shared immutable `World` record type and reads the captured trace's attribute schema; it imports no retiming helpers. Its direct per-write filtering, offending-chain derivation, quarter-formula and unchanged-field checks are implemented separately from the correction loop. Separate metric arithmetic checks share no historical scorer helper. Shared records, trace evidence, generator semantics and Python runtime remain common dependencies. AI-assisted checking is not independent human validation.

The execution freeze pins the new implementation, direct checker, complete input inventory, these pre-outcome notes and focused tests after diagnostic qualification and before full corrected-cohort evaluation. Fresh output manifests and final validation record actual commands, pass/failure counts, reproduction coverage, unavailable rows and preservation checks. The independent acquisition/archive/audit/joint studies remain outside the execution graph; static dependency inspection does not rerun them.

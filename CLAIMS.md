# Claims and analysis specification

This specification was written before the first benchmark run in this repository.
It is a local analysis plan, **not an externally timestamped preregistration**.

## Target and unit of analysis

A true edge `(source_event_id, target_event_id)` exists when the generator selects
an earlier event from a different stable run as the actual source of the target's
content. This is **realized source use in a structural simulator**, not a claim of
counterfactual necessity, harmful intent, collusion, or behavior of real language models.

`theta = number of writes with a true cross-run source / number of generated writes`.
All generated writes, including initial writes, are fixed eligible targets. The input
`transmission_probability` is a generator parameter and is not the realized theta.
Use event-to-event edges at every telemetry level; changing observed identities must
not change the scoring universe. Same-run repetitions are never true cross-run edges.

## Observation ladder

1. **Writes:** event IDs, timestamps, pages, disposable handles, content concepts, witnesses.
2. **Identity:** add stable run IDs.
3. **Requests:** add source requests, which may fail.
4. **Delivery:** add successful delivery receipts.
5. **Context:** add the provenance of chunks actually entering context.

Each regime is a projection of the same generated world. No investigator receives
truth edges, source-selection labels, scaffold origins, or generator probability.
Context records do not reveal which source the agent used. Common causes can produce
the same content with or without source use even when context telemetry is complete.

## Investigators

- **Temporal proximity:** earlier same-page writes within a prespecified lag window.
- **Witness reuse:** earlier writes sharing a witness-like string, including across pages.

Both exclude observed same-identity edges and filter using additional telemetry as
available. A witness's first observed appearance does not prove its unique origin.
Shared scaffold strings and collisions are deliberate alternatives to copying.
These are heuristic candidate edges, not calibrated causal probabilities, Hawkes fits,
valid identification bounds, or a new non-identifiability theorem.

## Hypotheses (not assumed outcomes)

- **H1:** under zero cross-run source use, shared launch waves can increase false
  attribution by the temporal investigator.
- **H2:** stable identity can reduce false cross-run attribution from rotating handles,
  but cannot eliminate common-source confounding.
- **H3:** request, delivery, and context telemetry can reduce candidate ambiguity,
  but channel context can leave false attribution and need not improve target-rate error.

Filtering candidates mechanically makes their count nonincreasing. In this **complete,
correct-logging baseline**, each true source-use edge has matching identity and exposure
records. Filters therefore preserve true positives and recall, and defined precision
cannot decrease. Those properties are model invariants, not empirical discoveries.
The measured questions concern the size of false attribution and residual ambiguity,
method-specific coverage, and absolute target-rate error, which need not improve
monotonically. Missing or corrupted telemetry is a future stress test.

Implementation clarification after the first run: the original H3 wording anticipated
recall loss from filtering, which this clean-log generator cannot test. No generator
parameters or thresholds were changed in response to results; the corrected scope
above makes the structural invariants explicit.

## Prespecified initial analysis

Run 12 independent seeds (`0..11`), 120 runs per world, three writes per run,
transmission probabilities `{0, 0.1, 0.3, 0.5}`, and shared-shock strengths
`{0, 0.5, 0.9}`. Apply every investigator and observation regime to each world.
Do not tune thresholds on these results. Larger runs and alternate generator parameters
are sensitivity checks, not retroactively part of the initial analysis.

Primary endpoint: false-attributed target fraction in zero-transmission worlds.
Secondary endpoints: event-edge precision and recall, absolute error in theta, and
false-positive edge count per eligible target. Theta-hat is the fraction of writes
with at least one predicted edge. False-attributed target fraction counts predicted
targets with **no true cross-run source**; wrong-source attribution to a truly copied
target instead appears in edge-level false positives.

Precision is undefined when no edges are predicted; recall is undefined when truth
has no edges. Store undefined values as JSON null, not zero. Summaries report the
number of defined seeds for each metric. Report 95% percentile bootstrap intervals
over independent world seeds (2,000 resamples); these measure simulation variation,
not identification uncertainty or uncertainty about real incidents. Scenario comparisons
reuse the same seed set; do not treat edges or telemetry variants as independent samples.

## Failure and reporting policy

Report measured curves even if flat, nonmonotone, or opposite to hypotheses. A figure
without meaningful false-positive controls and held-fixed truth fails the project goal.
Do not fill missing results, claim unsupported real-world rates, or label the context
regime an oracle. Report an explicit pair of observationally equivalent worlds with
different source-use labels to demonstrate the remaining ambiguity.

The German-wiki anchor is separate from synthetic validation. No corpus numbers or
new witness-network result is claimed until original sources, data provenance, and
reuse permissions are checked. See `case_study/README.md`.

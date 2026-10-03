# Trace Completeness Curves: three-minute demonstration

This is a written presentation script, not a recording or a human usability evaluation. Times are approximate. The demonstration uses saved results and makes no model calls. Author/team attribution remains for the repository owner to supply.

Before presenting, open `demo/failure_modes.html` directly from the checkout in a browser using **File → Open File**. Keep the [final submission](FINAL_SUBMISSION.md) and [reviewer guide](REVIEWER_GUIDE.md) open in a Markdown viewer. Do not serve the repository root: it contains ignored local evidence that is not authorized for release. The tracked page contains report-level summaries, not full tested inputs or exact responses.

## 0:00–0:35 · The question

**Navigation:** Start at the top of [the failure demonstration](../demo/failure_modes.html).

“Trace Completeness Curves asks what incomplete agent records can support, and where investigators fail to deliver a usable, justified answer. The completed work separates four things: a record being available, an agent being exposed to information, information being selected as a source, and an investigator giving a warranted answer. Those are different claims. Today’s two examples show a further distinction: an unusable response and a valid but wrong conclusion.”

## 0:35–1:25 · Sonnet: rejected serialization

**Navigation:** Follow the page’s Sonnet link to [#sonnet](../demo/failure_modes.html#sonnet). Point to the cause table and selected case `c_2165e482488490256503f009`.

“The offline audit inspected all 36 saved Sonnet evaluation responses. Twelve contain prose followed by one JSON object, eight contain two objects and self-correction prose, four violate field requirements, two are refusals, and ten are accepted and correct.

“This illustration is the lexicographically first case in the prose-plus-one-object category, chosen after evaluation. What you see is a structural summary, not a transcript. The whole response violates the frozen JSON-only contract. We do not extract an embedded answer or grade its correctness retroactively.

“The proposed object-versus-array explanation accounts for zero observed failures: all 42 identifiable objects use arrays. Serialization failure does not establish an incorrect evidence judgment.”

## 1:25–2:25 · Terra: a valid, incorrect conclusion

**Navigation:** Follow [#terra](../demo/failure_modes.html#terra). Read the certified and returned status rows for family `f_9695d2661a05a12eced27723`.

“Here the claim concerns an inserted literal title reference in a controlled wiki-derived fixture. The rule counts a reference as inserted when a changed character overlaps its matched title span. This is a text-classification task, not historical source-use evidence.

“The certified answers are established, established, and ruled out. Terra returns established, ruled out, and ruled out. All three responses satisfy the contract. In the irrelevant variant, the changed character is at position 898, outside the title span from 877 up to, but excluding, 896. The earlier title-character replacement remains, so the reference is still inserted. The decisive variant restores that predecessor character and makes the reference inherited.

“The error survives verification, but opaque IDs and derived hashes also change, with one completion per variant. This is one controlled behavioral inconsistency; it does not isolate the character edit as its cause. Valid evidence IDs also do not establish semantic support.”

## 2:25–3:00 · What the evidence supports

**Navigation:** Use the page’s links to the [final submission](FINAL_SUBMISSION.md), then the [reviewer guide](REVIEWER_GUIDE.md).

“The earlier utility pilot does not establish a general reasoning benefit from provenance assistance. Terra was at ceiling. Sonnet’s assistance-versus-checklist comparison reflected response acceptance, with uncertainty including zero; its wiki comparison against raw evidence was flat, and adverse cases remain recorded.

“The guide separates public tables from exact locally retained evidence. The small local package supports inspection of these examples, not reproduction of every study. The practical lesson is to report usable-answer failures separately from wrong conclusions, while keeping each claim within its evidence limits.”

The [existing explorer](../demo/index.html) covers the initial synthetic benchmark; it is not an interface to every completed study. The full exact request and final-response material is available only through the authorized local package described in the reviewer guide. The explanatory excerpts on the page are not substituted test inputs.

Source checks: [offline failure audit](../studies/evidence_responsiveness/offline_failure_audit/REPORT.md), [Terra request-difference summary](../studies/evidence_responsiveness/offline_failure_audit/terra_summary.json), [responsiveness results](../studies/evidence_responsiveness/results/REPORT.md), and [utility results](../studies/investigator_utility/openrouter_v1/results/REPORT.md). Preparation of this script is not publication or competition submission.

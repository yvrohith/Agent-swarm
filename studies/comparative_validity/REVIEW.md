# Comparative validity and public execution corrections

This retrospective corrective pass preserves the scientific record while fixing public execution and qualifying comparative interpretations. It uses the existing 40 acquisition problems, 30 structure groups, four development problems, five declared positive priors, paid stopping histories, catalogues, costs and omission closures. No cases, model responses or historical algorithms were replaced. The supplied review's numerical reconstructions were comparison targets, not values to force.

[The initial snapshot](initial_state.json) records HEAD `c29002c624005003e2f36ab7186e217edde76b22`, an initially clean tracked tree, all 30 existing untracked chronology files, and 701 retained local files. The prior chronology analysis was already complete locally and was preserved. The current narrative is [the active synthesis](../../docs/FINAL_SUBMISSION.md), authored by **Rohith YV**; no contact address was inferred.

## Findings and disposition

| Observation | Disposition | Evidence and scope |
| --- | --- | --- |
| Console pytest fails to import `studies.*` | Confirmed; corrected | [Clean-path checks](clean_checkout_checks.json): console collection had three errors and 1,167 collected tests, whereas module collection had 1,206. `pythonpath = ["."]` in pytest configuration makes the sets agree. Research scripts are not added to the distributable `src/tracebench` package. |
| A shallow public checkout suffices for all current tests | Unsupported; corrected entry point | Two existing chronology provenance tests need the original public source commit. Full local public history passes both; CI now requests `fetch-depth: 0`. No frozen test was skipped or rewritten. |
| Prior-robustness `analysis.py verify` works without local history | Confirmed defect; additive correction | It invokes broad preservation, including an ignored manifest. [The public v1 verifier](public_verify.py) separately checks the computational closure and released results. The historical entry point retains its original meaning. |
| Every advertised verification claim has a reproducible independent implementation | Partly supported | [Verification inventory](VERIFY.md) distinguishes executable same-code replay, separate algorithmic checks, shared physical semantics and unavailable auxiliary scripts. Three saved auxiliary script hashes have no matching tracked Python implementation. Hashes do not supply missing code. |
| Pair-cut is a new algorithm or generally superior acquisition rule | Unsupported | Its weighted cross-class objective is EC2. The competent baselines below are cheaper in several comparisons, with per-problem losses and prior dependence retained. |
| The historical 50% constant-first advantage is stable | Unsupported | Historical C detects 18 versus B's 15, but 200 common tie rankings give C−B detection differences from −5 to +4 and mean −0.015. |
| The supplied tie-reconstruction averages reproduce exactly | Unverified under its unspecified ranking construction | Our fixed construction produces 16.750/16.735 rather than 16.455/16.510. The supplied seed strings alone do not specify its catalogue pre-order and ranking algorithm. No alternate construction was tried to match its numbers. |
| Closure-informed comparators lack an available no-conflict-possible stop | Confirmed; separately corrected | Stopped variants retain detection and substantially reduce cost. Original selectors, results and cutoff rules remain intact. Exact E still has an advantage against these stronger comparators. |
| Published chronology scope and corrected-estimate impact were incompletely assessed | Already corrected locally; full scope verified | The completed 184-configuration analysis is preserved. [The supplementary public check](CHRONOLOGY_SCOPE.md) confirms all supplied first-context totals and measures full-grid impact maxima. |
| A green local path establishes green remote CI | Unverified | This task makes no remote request, push or workflow run. Only the actual local clean-checkout commands are evidenced. |
| Finite planning results establish swarm-investigator benefit | Unsupported | They optimize supplied finite hypothesis spaces. This is neither a deployment evaluation nor automatically leakage of realized unpaid answers; the actual-world boundary remains enforced. |

## Acquisition against competent baselines

[Definitions](acquisition_protocol.json) and [18 dependency pins](acquisition_freeze.json) were frozen after 24 focused tests and code review, before the new evaluation comparisons. Schema-skip retains the relevance/cost/ID order but never pays for or inserts an implied answer. Terminal-class information gain targets the existing three-way complete-archive class `tau`, with fixed `1e-12` ratio tolerance, cost/ID ties and cheapest-nonconstant fallback when all gains vanish. The fallback preserves complementary-query cases; zero one-step information is not irreducibility. Nominal skipping is not transferred to mismatch auditing.

All **2,000 historical prior rows** reproduce from retained paid paths. The two new rules add **800 rows**, producing a complete 2,800-row grid. The five total distributions are `q0`, `qS`, `qT`, `qMinus`, `qPlus`; `q0` is the original prior, not a sixth condition. Frozen-policy reweighting and matched-prior planning remain separate. Historical exact policies were not optimized again: the matched-prior optimum comes from the retained, validated matched-prior calculation.

At q0, equal-problem mean retrieval costs are:

| Policy | Exact cost | Decimal | EC2 wins / ties / losses against it |
| --- | ---: | ---: | ---: |
| EC2 / historical pair-cut | 607/160 | 3.793750 | — |
| Schema order with implied-query skipping | 1191/320 | 3.721875 | 13 / 14 / 13 |
| Terminal-class information gain/cost | 4489/1280 | 3.50703125 | 5 / 17 / 18 |
| Saved matched exact optimum | 1725/512 | 3.369140625 | See complete paired table |

All supplied q0 targets reproduce exactly. Structure-balanced means are respectively **3.837500, 3.713541667, 3.533333333 and 3.401822917**; all 40 problems and their price variants remain present. Five initial-terminal archive-ambiguity problems have zero optimum and zero cost for the four compared terminal-stopping policies; read-all still incurs positive cost. Their optimum ratios stay undefined rather than being treated as one or discarded from cost means.

Each stratum contains ten problems. These q0 equal-problem costs show where the aggregate changes arise:

| Stratum | EC2 | Schema-skip | Terminal-class information gain | Exact |
| --- | ---: | ---: | ---: | ---: |
| Positive receipt | 3.562500 | 3.456250 | 3.387500 | 3.362500 |
| Negative completeness | 4.300000 | 4.068750 | 3.912500 | 3.584375 |
| Complementary candidates | 5.087500 | 5.006250 | 4.553125 | 4.3796875 |
| Archive ambiguity | 2.225000 | 2.356250 | 2.175000 | 2.150000 |

Terminal-class information gain has lower aggregate cost than EC2 in all 20 prior × planning-mode × weighting combinations, but does not win on every problem. Schema-skip loses to EC2 under `qMinus` in both modes and `qPlus` with matched planning, and wins in the other aggregate conditions. There is no universal heuristic ranking. Matched replanning can worsen a heuristic: terminal-class information gain's structure-balanced `qT` cost rises from 3.82060809 to 3.82958927. [Exact rows, both weightings, stratum contrasts, wins/ties/losses and optimum gaps](results/acquisition_results/acquisition_summary.json) retain the complete comparisons, including the original schema, whole-world entropy and read-all references. These finite expectations are not independent incident samples; no sampling intervals or significance claims were added.

The historical pair-cut is an application of **EC2**, not a novel method. For different `tau` classes, edges have weight `p(u)p(v)`, and its expected cut is `E(S) − Σ_o P(o|S)E(S_o)`, divided by cost for selection. Explicit hypothesis-pair arithmetic matches the implementation in 12,876 state/query checks, sharing the declared `tau` semantics. Attribution: Golovin, Krause and Ray, *Near-Optimal Bayesian Active Learning with Noisy Observations*, NeurIPS 2010, arXiv:1010.3091, Section 3. This reference and equation were supplied in the task; no external browsing or unverified approximation guarantee is implied. [The active relation note](../../docs/RELATED_WORK.md) links the implementation.

## Audit ties and the missing stop

[Audit definitions](audit_protocol.json) and [32 dependency pins](audit_freeze.json) were frozen after 22 development/tiny tests. The calculation reproduces **20,064 historical comparator path views**, retains **10,032 stopped-policy views**, and reuses **5,016 saved E views** without invoking its optimizer.

For each of 40 problems and trials 0–199, the two policies share `Random("swarm-review-tie:{trial}:{problem_seed}").shuffle(sorted(query_ids))`. Only the final ID tie changes. Priority, costs, unaffordable-next-query cutoffs and first-conflict stopping remain unchanged. [All 8,000 rankings](audit_results/audit_tie_rankings.json.gz) and [all paired repetitions](audit_results/audit_tie_repetitions.json) are saved.

At 50%, B/C mean detection counts are **16.750/16.735**. C−B ranges **−5 to +4**, with 85 higher, 31 tied and 84 lower repetitions; mean difference is **−0.015**. C−B added cost averages **31.54**, range **16–48**. These are ordering sensitivities, not incident-population confidence intervals. k=1 and k=2 reuse signatures and have identical outcomes here; they are reported separately but not counted as independent repetitions. The external mean/range targets are not fully reproduced under the frozen ranking construction; no post-result tuning was performed.

The stopped D variants halt only when **every complete hypothetical k=2 signature compatible with paid history is nominally possible**. Zero immediate contradiction scores alone do not permit stopping. All other selector choices remain historical; D_affordable gets no second budget. At the existing 50% anchor, k=2 has 431 signatures, including 39 archive-detectable conflicts. The shared nominal acquisition cost is 1,617 and total extra allowance is 2,228; these are separate from actual added spending:

| Auditor | Detections | Added cost, all signatures | Added cost on nominal-compatible signatures |
| --- | ---: | ---: | ---: |
| Historical B, cost order | 15 | 1,706 | 1,563 |
| Historical C, constant first | 18 | 1,732 | 1,596 |
| Historical D | 20 | 1,730 | 1,598 |
| D with valid stop | 20 | 478 | 346 |
| Historical D_affordable | 20 | 1,822 | 1,681 |
| D_affordable with valid stop | 20 | 502 | 361 |
| Saved exact E | 32 | 314 | 197 |

The stopped costs reproduce the supplied targets exactly. E's remaining advantage is **12 detections and 164/188 cost units**, rather than the much larger saving against the historical unstopped baselines. Equal allowance is not equal spending. At 100%, both stopped comparators detect all 39 conflicts at cost 712; saved E also detects 39 at cost 414. [All anchors](audit_results/audit_summary.json), [strata](audit_results/audit_strata.json) and [paid histories](audit_results/audit_stopped_runs.json.gz) preserve original/new signature denominators and adverse comparisons. Nominal-compatible paths may require paid inspection before conflict impossibility is known; their expenditure is not all avoidable. An alarm does not prove the claim false, and improved detection/cost does not imply restored claim warrant.

## Chronology and verification limits

The existing chronology analysis already reproduced all 2,720 legacy evaluations and corrected availability at all 66,240 writes. This pass does not regenerate those worlds or revise its frozen repair. The [public saved-data diagnostic](chronology_scope.py) confirms affected benchmark configurations **48/48, 28/48, 0/48** at shock 0/.5/.9, with first-context contradictions **728/8,300, 54/8,416, 0/8,775**. The 782 distinct first-installation contradictions differ from 784 offending chains because two repeat receipts also offend; 798 write decisions are affected. All 52,175 chains have valid receipt-stage order. Thus chain order alone does not settle decision-time availability; 5,061 successful-chain request/write pairs are legitimately in flight.

The completed correction changes 186 benchmark evaluation rows across 72 configurations; all missing-receipt rows are unchanged. Largest absolute per-evaluation changes are **27 false-positive edges, 0.111111 precision, 12 false-positive targets, 7 false-negative targets, 0.038889 signed/absolute fraction error and 0.033333 target disagreement**. Group-mean maxima are separately measured: **15.25 edges, 0.020803 precision, 6.75/3.833333 target FP/FN, 0.024074 fraction error and 0.018750 disagreement**. True-positive edges, missed edges and recall never change. [Full maxima, null counts and scope](chronology_scope.json) replace any unsupported description of the impact as “small.” This state-preserving repair establishes no physical-realism claim and does not modify independent finite acquisition or model-investigator results.

[VERIFY.md](VERIFY.md) gives executable public commands and exact limits. Public prior verification checks 40 problems, 200 distributions, 5,880 matched retained trajectories, 2,000 metric rows and their 500 policy/200 paired summaries. It checks original authority hashes and binds imported code to the checked checkout. Local-history preservation is an explicitly separate command which fails on missing or changed files; missing local artifacts never earn a full pass. The original chronology verifier also requires private preservation history, so its new public diagnostic explicitly offers direct saved-state and arithmetic checks, **not** a new investigator/scorer execution.

`Model.verify_certificate()` reuses `Model` and `certificate()` semantics: it is not an independent semantic oracle. Genuine separately implemented Bellman/whole-tree comparisons remain linked in the inventory. Auxiliary hash-only audits are limited by unavailable script bytes. None is described as human or external validation. Released utility responses support mechanical score reproduction; unreleased full responsiveness fixtures/responses remain local, with no invented substitute or newly published package.

The new [comparison verifier](verify_comparisons.py) separately implements complete-signature filtering, stopped-prefix/first-conflict checks, replay of the **same saved** B/C rankings, and rational prior/aggregation arithmetic. Its [retained validation](INDEPENDENT_VALIDATION.json) passes 10,032 stopped paths, 8,000 rankings, 48,000 tie problem conditions, 2,800 acquisition conditions and 27,440 paid trajectory views. It checks all 700 policy summaries, 800 paired summaries and 3,200 per-problem contrasts. It shares the existing `Model` physical semantics and never reoptimizes historical exact policies. Public readback is `uv run python -m studies.comparative_validity.verify_comparisons`; this is computational cross-checking, not independent human validation.

## Clean-checkout commands and preservation

[The executable clean-checkout check](clean_checkout.py) copies tracked plus explicitly intended pending public files, uses fresh local public Git history with no copied configuration/hooks, and excludes historical artifacts, private inputs and the developer virtual environment. It clears inherited environment variables, sets no `PYTHONPATH`, uses the existing locked uv cache, and denies socket/connect syscalls. The initial offline installation succeeded with uv 0.12.19, CPython 3.12.14 and 17 locked packages; no dependency download or upgrade was needed. The exact checks are:

```sh
uv sync --frozen --extra dev
uv run pytest --collect-only -q
uv run python -m pytest --collect-only -q
uv run pytest
uv run ruff check .
uv run tracebench equivalence
```

The executable wrapper reproduces the install, collection, full-suite and lint portion in a fresh directory using the existing cache, without copying a developer environment:

```sh
env -i PATH=/usr/local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python studies/comparative_validity/clean_checkout.py \
  --directory /tmp/agent-swarm-clean-reproduction \
  --cache /workspace/.cache/uv \
  --record /tmp/agent-swarm-clean-reproduction.json --run-full
```

The fresh directory/record must not exist. The isolation wrapper is Linux-specific and uses installed `libseccomp`. A missing cache entry yields an explicit offline-install blocker; the script does not fetch it. [Final clean-checkout evidence](clean_checkout_final.json) records **455 public files**, identical console/module collection of **1,291 tests**, and exactly one full console run: **1,291 passed, zero failed/skipped, in 93.32 seconds**. Those include **85 new focused tests**; lint passes. [Public command readback](clean_public_verification.json) records passing prior, utility, chronology and comparison verifiers plus the existing CI equivalence diagnostic in the same arrangement. Source/test/config bytes remained identical to the tested snapshot. These test counts are implementation evidence, not scientific observations, and a local pass does not establish a new green remote workflow.

Existing-file changes are confined to `pyproject.toml`, `.github/workflows/checks.yml`, `README.md`, `docs/FINAL_SUBMISSION.md`, `docs/REVIEWER_GUIDE.md` and `docs/RELATED_WORK.md`. New files are restricted to this technical corrective namespace and focused tests. [The authorized change record](authorized_changes.json) lists exact before/after hashes; [final validation](FINAL_VALIDATION.json) verifies **381 unchanged historical tracked files, all 30 pre-existing chronology additions and all 701 retained local files**, including scientific freezes, raw records and API accounting. Historical broad preservation gates may correctly report the authorized documentation changes; their old pins were not refreshed to conceal them.

No new model calls, remote requests, credential access, dependency upgrades or spending occurred. Retained local files were hashed opaquely; provider-private reasoning was not decoded. No source branch/history changes, commit, push, publication or submission occurred. No presentation, demo, figure, UI, reviewer package, license or account decision was added. This corrective pass ends here.

# Acquisition prior robustness: results

Pair-cut's average retrieval-cost advantage over schema-aware ordering and world entropy survives equal weighting of the 30 structures and all five supplied deployment priors. It is not problem-wise dominance: under the dense-record prior, the frozen pair-cut policy costs more than schema-aware on 16 problems and less on 12. The frozen entropy/schema ranking reverses under signature-balanced and dense-record workloads. Supplying the matched prior helps exact planning, but it can worsen a heuristic: class-balanced pair-cut becomes more expensive on average.

Exact matched-prior planning has the lowest expected retrieval cost on these finite inputs. Its cold-cache planner computation is slower than pair-cut in this workload, although its complete policy-tree construction, including certificates, is cheaper on average. Without a conversion between retrieval units and computation, there is no single practical winner. These are review-informed, post-baseline sensitivities, conditional on the supplied archive model, not independent confirmation or measurements of real incident frequencies.

## Design, reproduction, and completion

The [frozen protocol](ANALYSIS.md), [method and elementary derivations](METHOD.md), [configuration](config.json), and [34-file execution freeze](freeze.json) precede new evaluation outcomes. The study reused all 40 evaluation problems and four separate development problems without changing worlds, queries, costs, claims, authentic-record semantics, completeness assumptions, terminal rules, heuristics, or tie rules. Only the full-budget expected cost-to-terminal objective was evaluated. The starting checkout was clean at `be3b22c4fd655d82dedbb2e86cd9abc8378b8334`; no older checkout replaced work.

[Baseline reproduction](baseline_reproduction.json) independently recovered all 200 original full-budget metric rows, 1,960 signature/policy runs, and 1,922 saved certificates. Original equal-problem costs were exactly 133/10 for read-all, 1353/320 for schema-aware, 1313/320 for entropy, 607/160 for pair-cut, and 1725/512 for exact planning. Pair-cut's original seven losses to schema-aware and positive-receipt stratum loss remain intact. The original cache-sharing timing result also remains unchanged; the new timing scope is different.

All 2,000 policy cells completed: 40 problems × five priors × two planning modes × five policies. There were no failed, capped, missing, or invalid-certificate cells. The [execution record](results/validation.json) records 52.788858 seconds for the pipeline, zero model calls, zero network requests, and zero additional spend. This is a pipeline duration, not investigator latency.

`q0` is the original assignment prior; `qS` gives each complete answer signature equal mass; `qT` gives each terminal archive class equal mass; `qMinus` and `qPlus` tilt toward fewer and more retained-record-returning catalogue actions. Completeness records count, empty wrappers do not, and duplicate actions each count once. All weights are exact, positive rational values on unchanged support. The original assignment-prior text in copied input metadata still describes how the original worlds were generated; the new labels and probability vectors explicitly identify workload reweighting.

The two modes are distinct. **Frozen** reweights saved original-prior paths and never gives the new prior to their planners. **Matched** supplies the new prior to unchanged entropy, pair-cut, and exact algorithms; read-all and schema-aware retain their prior-independent behavior. There are 17 problems with coincident distributions: six have q0=qT only, five qS=qT only, three q0=qS=qT, and three q0=qS only. The other 23 have five distinct distributions. Coincident labels remain in every analysis.

## Structure weighting and global retrieval costs

The [group audit](structure_groups.json) verifies 30 unweighted fingerprints: 20 singletons and ten pairs. The four strata contain 6/8/8/8 groups and ten problems each. Fingerprints retain claim, structural choices, initial evidence, typed query semantics, and the assignment/claim/answer table, while excluding prices, opaque query IDs, and catalogue order. Repeated members also agree on all other substantive input fields. This establishes appropriate grouping for these saved inputs, not general graph isomorphism. Price, ordering, and tie-break variants retain separate trajectories.

“Problems” weights all 40 inputs equally. “Structures” averages within each group and then across the 30 groups; it does not give a repeated group twice the influence. Below are mean abstract retrieval costs. Decimals are rounded to six places; exact rationals and all denominators are retained in [summary.json](results/summary.json).

### Frozen original-prior policies


| Prior | Weight | Read-all | Schema | Entropy | Pair-cut | Exact |
| --- | --- | --- | --- | --- | --- | --- |
| q0 | Problems | 13.300000 | 4.228125 | 4.103125 | 3.793750 | 3.369141 |
| q0 | Structures | 13.266667 | 4.253125 | 4.147917 | 3.837500 | 3.401823 |
| qS | Problems | 13.300000 | 3.918624 | 3.964635 | 3.667155 | 3.153438 |
| qS | Structures | 13.266667 | 3.964461 | 4.004143 | 3.712318 | 3.204862 |
| qT | Problems | 13.300000 | 4.557401 | 4.365354 | 4.055562 | 3.639541 |
| qT | Structures | 13.266667 | 4.605020 | 4.426225 | 4.124073 | 3.696585 |
| qMinus | Problems | 13.300000 | 4.952305 | 4.372565 | 4.044703 | 3.763352 |
| qMinus | Structures | 13.266667 | 5.001879 | 4.516459 | 4.168148 | 3.853651 |
| qPlus | Problems | 13.300000 | 3.597345 | 3.782685 | 3.427071 | 2.825687 |
| qPlus | Structures | 13.266667 | 3.605399 | 3.771373 | 3.428505 | 2.848978 |


### Matched-prior policies


| Prior | Weight | Read-all | Schema | Entropy | Pair-cut | Exact |
| --- | --- | --- | --- | --- | --- | --- |
| q0 | Problems | 13.300000 | 4.228125 | 4.103125 | 3.793750 | 3.369141 |
| q0 | Structures | 13.266667 | 4.253125 | 4.147917 | 3.837500 | 3.401823 |
| qS | Problems | 13.300000 | 3.918624 | 3.792135 | 3.561028 | 3.115462 |
| qS | Structures | 13.266667 | 3.964461 | 3.822476 | 3.601370 | 3.168671 |
| qT | Problems | 13.300000 | 4.557401 | 4.308149 | 4.064554 | 3.625349 |
| qT | Structures | 13.266667 | 4.605020 | 4.363840 | 4.138744 | 3.684776 |
| qMinus | Problems | 13.300000 | 4.952305 | 4.198312 | 3.880959 | 3.655496 |
| qMinus | Structures | 13.266667 | 5.001879 | 4.325006 | 4.006816 | 3.743578 |
| qPlus | Problems | 13.300000 | 3.597345 | 3.261236 | 2.991045 | 2.695268 |
| qPlus | Structures | 13.266667 | 3.605399 | 3.279429 | 3.006154 | 2.716211 |


At q0, structure balancing changes pair-cut minus schema-aware from −0.434375 to −0.415625, and pair-cut minus entropy from −0.309375 to −0.310417. The average advantage survives. Under every prior and both weighting rules, frozen exact remains lowest in aggregate, followed by pair-cut; read-all remains highest. The intervening schema/entropy order reverses at qS and qPlus: schema-aware becomes cheaper than frozen entropy. With matched planning, entropy again has lower aggregate cost than schema-aware for all five priors.

Those aggregate rankings conceal losses. The table below gives raw problem counts as **lower/tied/higher** for pair-cut relative to each comparator; each triplet totals 40 and is not changed by aggregation weights. The final columns count the signs of the 30 within-group mean differences, separately from weighted effect sizes.


| Mode | Prior | Problems vs schema | Problems vs entropy | Groups vs schema | Groups vs entropy |
| --- | --- | --- | --- | --- | --- |
| Frozen | q0 | 19/14/7 | 16/23/1 | 15/9/6 | 15/14/1 |
| Frozen | qS | 14/14/12 | 16/22/2 | 11/10/9 | 15/13/2 |
| Frozen | qT | 19/14/7 | 17/22/1 | 15/9/6 | 16/13/1 |
| Frozen | qMinus | 19/12/9 | 17/21/2 | 14/8/8 | 16/12/2 |
| Frozen | qPlus | 12/12/16 | 17/21/2 | 9/8/13 | 16/12/2 |
| Matched | q0 | 19/14/7 | 16/23/1 | 15/9/6 | 15/14/1 |
| Matched | qS | 17/15/8 | 13/26/1 | 13/11/6 | 11/18/1 |
| Matched | qT | 19/14/7 | 14/25/1 | 15/9/6 | 13/16/1 |
| Matched | qMinus | 20/15/5 | 20/20/0 | 16/10/4 | 17/13/0 |
| Matched | qPlus | 23/12/5 | 19/21/0 | 20/8/2 | 17/13/0 |


## Stratum differences, including reversals

Each cell is pair-cut cost minus comparator cost. Negative values favor pair-cut; positive values favor the comparator. Both weighting rules are shown within each stratum. Problem counts, group counts, and lower/tied/higher counts for every stratum are also retained in `summary.json`.

### Frozen original-prior policies


| Prior | Stratum | Problems: Δ schema | Problems: Δ entropy | Structures: Δ schema | Structures: Δ entropy |
| --- | --- | --- | --- | --- | --- |
| q0 | Positive receipt | +0.106250 | -0.475000 | +0.067708 | -0.562500 |
| q0 | Negative/completeness | -0.543750 | -0.425000 | -0.527344 | -0.468750 |
| q0 | Complementary | -1.168750 | -0.200000 | -0.960938 | -0.156250 |
| q0 | Archive ambiguity | -0.131250 | -0.137500 | -0.121094 | -0.117188 |
| qS | Positive receipt | +0.326111 | -0.440000 | +0.250926 | -0.533333 |
| qS | Negative/completeness | -0.272304 | -0.447059 | -0.288297 | -0.496324 |
| qS | Complementary | -1.048570 | -0.213971 | -0.838491 | -0.142463 |
| qS | Archive ambiguity | -0.011111 | -0.088889 | -0.006944 | -0.055556 |
| qT | Positive receipt | +0.092255 | -0.477647 | +0.049101 | -0.564706 |
| qT | Negative/completeness | -0.705114 | -0.363175 | -0.651311 | -0.391468 |
| qT | Complementary | -1.289494 | -0.248346 | -1.083858 | -0.182655 |
| qT | Archive ambiguity | -0.105000 | -0.150000 | -0.105208 | -0.135417 |
| qMinus | Positive receipt | -0.068087 | -0.543284 | -0.090797 | -0.619403 |
| qMinus | Negative/completeness | -1.304380 | -0.362064 | -1.248480 | -0.390080 |
| qMinus | Complementary | -1.787509 | -0.218599 | -1.426303 | -0.251012 |
| qMinus | Archive ambiguity | -0.470431 | -0.187500 | -0.383611 | -0.200521 |
| qPlus | Positive receipt | +0.238231 | -0.416216 | +0.190950 | -0.513514 |
| qPlus | Negative/completeness | +0.153467 | -0.517364 | +0.140397 | -0.584205 |
| qPlus | Complementary | -1.041630 | -0.344943 | -0.894444 | -0.225651 |
| qPlus | Archive ambiguity | -0.031164 | -0.143931 | -0.052521 | -0.090767 |


### Matched-prior policies


| Prior | Stratum | Problems: Δ schema | Problems: Δ entropy | Structures: Δ schema | Structures: Δ entropy |
| --- | --- | --- | --- | --- | --- |
| q0 | Positive receipt | +0.106250 | -0.475000 | +0.067708 | -0.562500 |
| q0 | Negative/completeness | -0.543750 | -0.425000 | -0.527344 | -0.468750 |
| q0 | Complementary | -1.168750 | -0.200000 | -0.960938 | -0.156250 |
| q0 | Archive ambiguity | -0.131250 | -0.137500 | -0.121094 | -0.117188 |
| qS | Positive receipt | +0.259444 | -0.100000 | +0.195370 | -0.083333 |
| qS | Negative/completeness | -0.613480 | -0.499346 | -0.652267 | -0.554739 |
| qS | Complementary | -1.065237 | -0.280637 | -0.848907 | -0.184130 |
| qS | Archive ambiguity | -0.011111 | -0.044444 | -0.006944 | -0.027778 |
| qT | Positive receipt | +0.092255 | -0.177647 | +0.049101 | -0.148039 |
| qT | Negative/completeness | -0.653051 | -0.400000 | -0.586232 | -0.437500 |
| qT | Complementary | -1.305593 | -0.250067 | -1.093920 | -0.164327 |
| qT | Archive ambiguity | -0.105000 | -0.146667 | -0.105208 | -0.131250 |
| qMinus | Positive receipt | -0.198790 | -0.610021 | -0.199716 | -0.675018 |
| qMinus | Negative/completeness | -1.321936 | -0.153220 | -1.270425 | -0.146386 |
| qMinus | Complementary | -2.120865 | -0.387424 | -1.770206 | -0.403846 |
| qMinus | Archive ambiguity | -0.643794 | -0.118750 | -0.541070 | -0.136719 |
| qPlus | Positive receipt | -0.125749 | -0.299263 | -0.142670 | -0.363022 |
| qPlus | Negative/completeness | -0.490598 | -0.354763 | -0.497323 | -0.307650 |
| qPlus | Complementary | -1.619293 | -0.265688 | -1.483414 | -0.298785 |
| qPlus | Archive ambiguity | -0.189558 | -0.161049 | -0.159428 | -0.146079 |


The original positive-receipt loss persists at q0 under both weights. Frozen positive-receipt performance remains worse than schema-aware at qS, qT, and qPlus, while qMinus reverses that stratum's sign. Dense-record reweighting also reverses the negative/completeness stratum against frozen pair-cut: +0.153467 per problem and +0.140397 per structure. Its 1/2/7 lower/tied/higher problem counts show this is not merely a pooled rounding effect. Matched qPlus removes both aggregate stratum losses, but still has five individual losses to schema-aware across the study. Pair-cut remains cheaper than entropy in each reported stratum mean; individual losses remain in several conditions.

## Supplied planning prior versus acquisition rule

Replanning does not guarantee improvement for a heuristic. The following equal-problem changes hold deployment q fixed and subtract frozen cost from matched cost. Triplets again count lower/tied/higher costs over the 40 problems.


| Prior | Entropy Δ | Entropy L/T/H | Pair-cut Δ | Pair-cut L/T/H | Exact Δ | Exact L/T/H |
| --- | --- | --- | --- | --- | --- | --- |
| q0 | +0.000000 | 0/40/0 | +0.000000 | 0/40/0 | +0.000000 | 0/40/0 |
| qS | -0.172500 | 8/29/3 | -0.106127 | 8/31/1 | -0.037976 | 6/34/0 |
| qT | -0.057206 | 4/32/4 | +0.008991 | 1/37/2 | -0.014192 | 5/35/0 |
| qMinus | -0.174252 | 10/28/2 | -0.163744 | 15/24/1 | -0.107856 | 13/27/0 |
| qPlus | -0.521449 | 21/15/4 | -0.436026 | 24/15/1 | -0.130419 | 17/23/0 |


Class-balanced pair-cut worsens by +0.008991 under equal-problem weighting and +0.014671 under structure balancing; one problem improves, 37 tie, and two worsen. Entropy improves on average under all four shifted priors, but has individual regressions in each. No policy or prior was changed to remove those adverse findings.

For dense-record deployment, matching the pair-cut prior reduces its excess over the matched optimum from 0.731803 to 0.295777, a reduction of 0.436026 retrieval units. For the sparse-record prior, the corresponding excess falls from 0.389207 to 0.225463. For class balancing it rises from 0.430213 to 0.439204. These comparisons isolate the supplied-prior change within the fixed implementation and model. The remaining gaps are relative to exact planning at that same prior, not a causal decomposition of real investigator behavior.

The frozen exact policy's penalty is Jq(pi0*) minus the matched-prior optimum. It is nonnegative in every problem. The table also records how many problems have a positive penalty and the largest single-problem penalty.


| Prior | Penalty: problems | Penalty: structures | Positive / 40 | Max penalty | Mean cost/optimum | Max cost/optimum |
| --- | --- | --- | --- | --- | --- | --- |
| q0 | 0.000000 | 0.000000 | 0 | 0.000000 | 1.000000 | 1.000000 |
| qS | 0.037976 | 0.036190 | 6 | 0.666667 | 1.009182 | 1.146341 |
| qT | 0.014192 | 0.011809 | 5 | 0.260163 | 1.003233 | 1.040816 |
| qMinus | 0.107856 | 0.110073 | 13 | 0.885417 | 1.028549 | 1.244147 |
| qPlus | 0.130419 | 0.132768 | 17 | 0.681924 | 1.042318 | 1.255523 |


The largest absolute penalty is 0.885417 at `acq_94239` under qMinus; the largest ratio is 1.255523 under qPlus. All 200 exact alpha/beta comparisons pass, including 25 zero-optimum identities. The largest bound factor is 256, much looser than the observed ratios. This verifies the elementary finite expectation inequality under its assumptions; it is not a pair-cut approximation guarantee or robustness to false evidence.

The five zero-optimum problems are `acq_94230`, `acq_94232`, `acq_94234`, `acq_94236`, and `acq_94238`, under every positive prior. Initial evidence already proves archive irreducibility. All policies except read-all incur zero retrieval cost there; read-all retains its exhaustive operational behavior and positive cost. Global mean-of-ratio summaries therefore use 35 positive-optimum problems, or 26 groups when structure balancing within that eligible population, rather than concealing undefined ratios. The following pair-cut ratios are means of per-problem ratios, not ratios of aggregate costs.


| Prior | Frozen: problems | Frozen: structures | Matched: problems | Matched: structures |
| --- | --- | --- | --- | --- |
| q0 | 1.128267 | 1.130110 | 1.128267 | 1.130110 |
| qS | 1.171371 | 1.168543 | 1.127616 | 1.126208 |
| qT | 1.124931 | 1.126175 | 1.125512 | 1.127775 |
| qMinus | 1.110372 | 1.116678 | 1.055003 | 1.064601 |
| qPlus | 1.268518 | 1.259869 | 1.083546 | 1.084098 |


Matched exact has ratio 1 on all eligible problems. Some heuristics beat the frozen exact policy on individual shifted-prior problems: pair-cut does so in one qT and three qMinus cases, entropy in two qMinus cases, and schema-aware in eight problem/prior combinations in total. This is consistent with exact optimality because those frozen policies were optimized for p0. No feasible policy beats the matched-prior optimum.

## Queries, returned bytes, and terminal masses

Cost changes need not have the same direction as byte changes. The following equal-problem expectations show pair-cut and exact policies; complete per-policy, per-stratum, and structure-balanced values are in the lossless tables. Byte counts are canonical query-result bytes, including empty-lookup wrapper bytes, not model tokens or costs in dollars.


| Prior | Mode | Pair-cut queries | Pair-cut bytes | Exact queries | Exact bytes |
| --- | --- | --- | --- | --- | --- |
| q0 | Frozen | 2.189062 | 297.078125 | 1.808984 | 238.567187 |
| q0 | Matched | 2.189062 | 297.078125 | 1.808984 | 238.567187 |
| qS | Frozen | 2.145503 | 304.427342 | 1.705076 | 239.011350 |
| qS | Matched | 2.083064 | 293.805488 | 1.689496 | 235.370275 |
| qT | Frozen | 2.277811 | 313.454390 | 1.905618 | 255.881067 |
| qT | Matched | 2.278707 | 313.446334 | 1.887128 | 254.585760 |
| qMinus | Frozen | 2.263319 | 258.365923 | 1.996534 | 226.274420 |
| qMinus | Matched | 2.115597 | 242.818701 | 1.889642 | 215.766258 |
| qPlus | Frozen | 2.083320 | 339.316032 | 1.559293 | 243.934961 |
| qPlus | Matched | 1.728890 | 272.238198 | 1.425198 | 216.876535 |


Full-budget terminal probability masses are identical across policies and planning modes for a fixed problem and deployment prior. Positive support changes do not alter any fixed-history evidentiary status, but reweighting archives changes the aggregate mass of each status. Class balancing is per problem among its present classes, so a pooled qT row need not assign one third to each class.


| Prior | Weight | Established | Ruled out | Archive irreducible |
| --- | --- | --- | --- | --- |
| q0 | Problems | 0.275000 | 0.246875 | 0.478125 |
| q0 | Structures | 0.270833 | 0.275000 | 0.454167 |
| qS | Problems | 0.377426 | 0.241389 | 0.381185 |
| qS | Structures | 0.357123 | 0.271390 | 0.371487 |
| qT | Problems | 0.308333 | 0.245833 | 0.445833 |
| qT | Structures | 0.300000 | 0.266667 | 0.433333 |
| qMinus | Problems | 0.116569 | 0.227795 | 0.655636 |
| qMinus | Structures | 0.116128 | 0.271763 | 0.612109 |
| qPlus | Problems | 0.505252 | 0.167404 | 0.327343 |
| qPlus | Structures | 0.493693 | 0.180700 | 0.325607 |


## Local planning workload and resource limits

The separate timing check used q0 only, all 40 problems, and exactly three recorded repetitions per policy: 600 complete reachable policy-tree constructions. Each construction starts with a fresh planner and empty caches, branches over every compatible outcome, and shares only the immutable validated model. It does not time a selected realized archive. All repetitions completed and repeated workload hashes agreed. Exact planning visited a mean 42.05 solver states and a maximum 111, below the fixed 100,000-state cap; no solve was capped.

The table reports mean milliseconds per complete policy-tree construction, averaged over all 120 repetitions for each policy. Planning includes planner initialization and choices. The final two columns include the entire construction, certificate work, traversal checks, and serialization; they are not the same timing scope as planner computation.


| Policy | Planner CPU ms | Planner wall ms | Decisions | Leaves | Complete CPU ms | Complete wall ms |
| --- | --- | --- | --- | --- | --- | --- |
| read_all | 0.748610 | 0.764896 | 27.125 | 9.800 | 28.539914 | 28.542933 |
| schema_aware | 0.170186 | 0.175819 | 3.900 | 4.350 | 12.936753 | 12.938070 |
| world_entropy | 0.974303 | 0.980699 | 5.800 | 6.800 | 19.203884 | 19.205991 |
| pair_cut | 1.274317 | 1.280230 | 5.150 | 6.150 | 18.995305 | 18.997752 |
| exact_optimal | 4.163739 | 4.168287 | 3.225 | 4.225 | 16.248080 | 16.249218 |


All three repetition means are retained below as **CPU / wall milliseconds**, with 40 problems per repetition. No minimum or favorable repetition replaces another.


| Policy | Repetition 1 | Repetition 2 | Repetition 3 |
| --- | --- | --- | --- |
| read_all | 0.748960 / 0.765560 | 0.749353 / 0.765066 | 0.747518 / 0.764061 |
| schema_aware | 0.171781 / 0.175711 | 0.169291 / 0.178441 | 0.169487 / 0.173305 |
| world_entropy | 0.964721 / 0.970680 | 0.990153 / 0.997385 | 0.968034 / 0.974033 |
| pair_cut | 1.262017 / 1.267795 | 1.259513 / 1.265657 | 1.301420 / 1.307240 |
| exact_optimal | 4.140493 / 4.144691 | 4.183033 / 4.187715 | 4.167692 / 4.172454 |


Shared model validation and signature preprocessing took 58.381658 ms CPU and 58.448474 ms wall in total across 40 problems, outside the planner measurements. Mean remaining construction phases are separately visible below, again **CPU / wall milliseconds**. Certificate verification includes model reconstruction performed internally by the unchanged checker; it is not charged to shared preprocessing or planner decisions. Driver hash checks outside a construction are not planner time. Phase sums and total elapsed values can differ slightly because measurement and surrounding bookkeeping have overhead.


| Policy | Certificate construction | Certificate verification | Traversal/checks | Serialization |
| --- | --- | --- | --- | --- |
| read_all | 3.674467 / 3.683068 | 21.897368 / 21.914016 | 1.639705 / 1.677342 | 0.326331 / 0.327060 |
| schema_aware | 1.550728 / 1.554381 | 10.029553 / 10.035715 | 1.023330 / 1.034673 | 0.075013 / 0.075556 |
| world_entropy | 2.383812 / 2.388538 | 14.518050 / 14.528144 | 1.085600 / 1.100989 | 0.115654 / 0.116289 |
| pair_cut | 2.241225 / 2.245697 | 14.180468 / 14.191015 | 1.070694 / 1.085430 | 0.108119 / 0.108698 |
| exact_optimal | 1.484150 / 1.487399 | 9.442312 / 9.448115 | 0.995747 / 1.006341 | 0.073866 / 0.074431 |


At q0, exact planning saves 0.424609 expected retrieval units versus pair-cut, but uses about 2.889423 additional planner CPU milliseconds per complete tree. It has fewer terminal leaves and lower total construction time than pair-cut in this measurement. Schema-aware is cheaper to compute, while retrieving more. The original report's exact-versus-pair-cut CPU ordering came from shared caches across signatures and budgets; these new cold-cache construction timings neither overwrite it nor measure the same workload. The evidence supports exact as the retrieval-cost reference at these tested sizes, with a measured planning-overhead tradeoff. It does not establish universal practical superiority, deployment latency, or scalability, and no conversion between seconds and retrieval units is supplied.

## Verification, preservation, and interpretation limits

The pre-freeze full suite passed **816 tests**, with zero failures or skips, and Ruff passed in the already installed environment. Development used only the four original problems; its independent checks covered 200 policy rows, 570 matched trajectories, 181 certificates, 20 bounds, and 60 cold-cache constructions before evaluation outcomes. [Pre-freeze checks](pre_freeze_checks.json) record this sequence, including a corrected pre-freeze status-label integration mismatch that changed no scientific calculation.

The evaluation retains 5,880 matched signature trajectories and 2,394 deduplicated certificates in [details.json.gz](results/details.json.gz), alongside exact distributions, signature masses, b(w), coincidences, histories, bounds, and failures. All 2,000 metric rows report valid certificates, and all 200 bounds are verified. The post-run independent audit checked all 2,000 rows, 5,880 trajectories, 2,394 certificates, 81,588 fixed-history prefix checks, and 600 timing workload hashes. It reused the unchanged independent certificate checker, rather than implementing archive semantics again, and did not rerun matched-policy decisions or the exact search. Optimality evidence includes the frozen independent tiny-tree tests plus the reported feasible-cost and bound checks. Correct fixed-history status, normalization, and support preservation are validation consequences, not empirical discoveries about investigators. Independent checks and final preservation/test evidence are recorded in [independent_verification.json](results/independent_verification.json) and [FINAL_VALIDATION.json](FINAL_VALIDATION.json).

[Preservation](preservation.json) and the completed execution checks retain all **240 pre-existing tracked files** and **509 retained historical local files** unchanged. Protocols, prompts, cases, responses, score tables, scientific source, manifests, and accounting from completed studies remain intact. This task made no model call, external request, credential access, package download, additional spend, publication, or remote write.

The priors are five declared workloads on a selected, small, closed finite model. Neither problems nor structural groups are independent incident samples; repeated priors and policies add no independent incidents. There are no sampling intervals or significance claims. Prior weights do not validate the world support, authentic receipts, completeness declarations, query catalogue, or cost model. Forged evidence, omitted causal mechanisms, missing evidence types, and unreliable declarations are outside this test. Archive irreducibility is relative to the supplied interface, not all conceivable future evidence; exposure still does not establish source use. The documented legacy-simulator chronology contradiction remains separate, with its effect on published estimates unmeasured. No historical stochastic-simulator grid or wiki-applicability analysis was rerun.

## Offline reproduction

From the repository root, use the existing environment. First verify the frozen computational closure and historical preservation:

```bash
.venv/bin/python -m studies.acquisition_prior_robustness.analysis verify
```

To reproduce the same finite schedule, supply a fresh ignored output directory; the command refuses an existing directory and does not overwrite the curated results:

```bash
.venv/bin/python -m studies.acquisition_prior_robustness.analysis run --output artifacts/acquisition-prior-robustness/replication
```

That command repeats deterministic finite calculations and the three prescribed local timing repetitions, with no model/network access. Numerical expectations and policy paths should reproduce; runtime measurements naturally vary. Inspect [per_problem.json](results/per_problem.json) for all 2,000 original rows, [summary.json](results/summary.json) for both weighting rules and every stratum, [runtime.json](results/runtime.json) for all 600 recorded constructions and phases, and [manifest.json](results/manifest.json) for output hashes. Do not regenerate or replace the freeze to accommodate a mismatch.

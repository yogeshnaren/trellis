# Jev shadow evaluation on saved BIRD train_dev answers

Date: 2026-09-27. This is **development-set diagnosis only**. No Jev decision was inserted into the live SQL path, no gold SQL or full result set was sent to OpenRouter, and no Mini-Dev or `train_lockbox` question was opened. The pinned response model was `typesafe/jev-1.13-20260917` through OpenRouter's alpha Decisions endpoint.

## Cheapest-first sequence

1. Free: checked the current official typed-request/usage schema, built a shared-ledger provider and session cap, validated requests, and hand-labeled 50 atomic requirement cases from the original question, evidence and saved SQL. Five had a specific omission or misapplication; 27 of the 50 SQL answers were currently official-EX correct controls. No gold was used to assign the five labels.
2. One paid compatibility call: success, $0.000031542.
3. Post-SQL requirement-coverage shadow: 50 calls, **$0.001627710**. With the threshold fixed at 0.8 before calls, Jev found **0/5** hand-labeled defects; it raised **0/45** false flags. Brier score 0.07858; P50 187 ms, P90 246 ms. A simple structural rule also found 0/5 and raised 1 false flag. Positive Jev probabilities were 0.09, 0.60, 0.07, 0.40 and 0.20. Lowering the threshold on this same sample would be tuning on the evaluation labels and is not treated as a valid gain.
4. Free: re-executed the four saved candidate families locally under the current result-signature code. All 501 `train_dev` questions matched; 102 had differing candidate results. The mean Jev state was 1,735 characters, with up to three sample rows per candidate and no gold.
5. Candidate-choice shadow: 102 calls, **$0.004565148**. On the disagreements, result-majority chose 39 correct candidates and Jev chose 29. Jev changed the outcome with **11 fixes and 21 regressions**. With 306 correct on unanimous rows, full-bank EX was **345/501 = 68.86% by result-majority** versus **335/501 = 66.87% by Jev choice**. Jev chose `none` four times; the declared fallback used result-majority for those. Mean Jev latency was 178 ms.

| Confidence band | Questions | Majority correct | Jev correct | Fixes | Regressions |
|---|---:|---:|---:|---:|---:|
| < 0.50 | 56 | 21 | 14 | 6 | 13 |
| 0.50–0.69 | 21 | 7 | 5 | 2 | 4 |
| 0.70–0.84 | 17 | 6 | 7 | 3 | 2 |
| ≥ 0.85 | 8 | 5 | 3 | 0 | 2 |

The 0.70–0.84 band is only +1 on 17 cases. It is a post-hoc observation on four development databases, not a deployable threshold. `choice.confidence` is answer-distribution concentration, not calibrated probability of SQL correctness.

6. **Schema-corrected selector shadow:** the first selector request omitted the plan's verified schema slice. A preregistered correction added actual columns for up to five SQL-referenced tables and reran the same 102 disagreements once, with no other decision-policy change. Mean state rose from 1,735 to 1,966 characters. At **$0.005004132**, Jev selected **28/102** correctly versus majority's **39/102**; there were **10 fixes and 21 regressions**. Full-bank EX was **334/501 = 66.67%** for Jev versus **345/501 = 68.86%** for majority. Adding schema did not recover the deficit.

7. **Question-intent shadow:** 24 newly hand-labeled `train_dev` questions, $0.000625884. Jev matched all 7 temporal and 8 extremum labels with no false positives in those two classes; free regex rules found 5/7 and 5/8. Jev exact-matched all four tested intents on 20/24 questions versus 19/24 for the rules. The exclusion/upper-bound intent had 4 false positives, and the sample had no ratio positives. This is an encouraging classification diagnostic, not evidence that routing improves SQL EX.
8. **Bounded table-choice shadow:** free lexical ranking put every gold table in the top 8 for 48/50 hash-selected soccer questions. Jev with verified column lists selected about 2 tables/question and improved table F1 to 0.900, but recovered *every* gold table for only 36/50. Adding verified foreign-key edges, as the plan requires, raised all-table coverage to **41/50** and F1 to **0.940** ($0.002515338 + $0.002975574). The top-3 lexical shortlist covered 29/50, while all eight covered 48/50. Jev's remaining misses were usually lookup or bridge tables such as `Country`, `Batting_Style` and `Rolee`.
9. **Independent development-database check:** the frozen foreign-key policy on 50 `professional_basketball` questions from preselected `train_dev2` gave **41/50** all-gold table coverage and F1 **0.911**, versus top-3 coverage 25/50 and all-eight coverage 48/50 ($0.003606078). This is a second development database, not the sealed lockbox. Jev is promising as a *ranking or annotation* signal; its 82% all-table recall is unsafe for removing the other schema tables.
10. **Atomic evidence-hint role:** 29 manually labeled fragments yielded Jev 27/29 ($0.000613368). A free syntax rule designed after reading those labels fit them 29/29; that number is in-sample. On a separate 24-fragment hash sample, with the rule frozen, Jev scored **24/24** versus the free rule **21/24** ($0.000516810). Roles were `return`, `filter` and `rank`, judged from the original question without gold SQL. The sample is too small and homogeneous to claim that injecting this decision changes EX; Jev still needs an output format that the generator can use and a paired live trial.

## Decision and limits

**Do not promote Jev coverage repair or candidate choice to the live benchmark path.** Coverage missed every labeled omission. Candidate choice lost ten net correct answers without schema and eleven with the verified schema slice, relative to deterministic majority. The plan's offline-to-live gate requires a specific failure mechanism and low false-positive rate. A Fireworks repair A/B or small LLM-judge comparator would add paid generation without a promising Jev coverage or selection trigger; the Fireworks ledger also rose above the previously approved $7.15 cap during this evaluation. This task made **no Fireworks calls**.

The saved bank predates the adopted bounded-facts prompt. Its perfect-selector ceiling is 368/501 = 73.5%, below the 75% train_dev target; the selector pilot diagnoses Jev, but cannot validate the current cumulative configuration. Table prioritization and atomic hint-role decisions now have positive **offline** signals on development databases. Neither has a measured SQL-accuracy gain; a schema hard-filter would lose required join tables. Column-level selection remains untested because the postmortem calls for a second reliable label audit of look-alike columns before building a decision set. No Mini-Dev, sealed lockbox, or hidden-test result can be inferred from these shadows.

OpenRouter calls in this task total **$0.022081584** across ten Jev sessions, below the configured $5 total and $1 per-session caps. All calls reserved $0.01 before dispatch and settled the provider-reported actual cost in the shared SQLite ledger. There are no open OpenRouter reservations. The `product` SQL path remains unchanged.

Artifacts: `jev_shadow_v1_*`, `jev_selector_v1/v2_results.json`, `jev_intent_v1_*`, `jev_table_v1/v2_results.json`, `jev_table_pb_v1_results.json`, and `jev_hint_v1/v2_*`. Labels were frozen before their Jev calls. The intent and hint samples use the original question and evidence; the table metric uses gold SQL *only after* each decision to score table coverage. The saved results pin the question or prediction-file hash, and paid harnesses refuse to repeat a completed output file.

API and pricing checked against OpenRouter's [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request) and [Jev 1.13 model page](https://openrouter.ai/typesafe/jev-1.13).

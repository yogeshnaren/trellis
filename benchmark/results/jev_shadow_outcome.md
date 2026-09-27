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

## Decision and limits

**Do not promote Jev coverage repair or candidate choice to the live benchmark path.** Coverage missed every labeled omission. Candidate choice lost ten net correct answers without schema and eleven with the verified schema slice, relative to deterministic majority. The plan's offline-to-live gate requires a specific failure mechanism and low false-positive rate. A Fireworks repair A/B or small LLM-judge comparator would add paid generation without a promising Jev trigger; the Fireworks ledger also rose above the previously approved $7.15 cap because another process was making Fireworks calls during this evaluation. This task made **no Fireworks calls**.

The saved bank predates the adopted bounded-facts prompt. Its perfect-selector ceiling is 368/501 = 73.5%, below the 75% train_dev target; the selector pilot diagnoses Jev, but cannot validate the current cumulative configuration. Bounded table/column choices and pre-generation intent routing remain untested hypotheses. They need separate verified shortlists and labels before paid trials; this result does not establish that Jev is useless for every decision type.

OpenRouter calls in this task total **$0.011228532** across four Jev sessions, below the configured $5 total and $1 per-session caps. All calls reserved $0.01 before dispatch and settled the provider-reported actual cost in the shared SQLite ledger. There are no open OpenRouter reservations. The `product` SQL path remains unchanged.

Artifacts: `jev_shadow_v1_labels.json`, `jev_shadow_v1_results.json`, `jev_selector_v1_results.json`, and `jev_selector_v2_results.json`. The first fifty labels were fixed before Jev calls. Both paid harnesses refuse to repeat a completed output file.

API and pricing checked against OpenRouter's [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request) and [Jev 1.13 model page](https://openrouter.ai/typesafe/jev-1.13).

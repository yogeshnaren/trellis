### Prompt iteration history

`SYSTEM_PROMPT` in `src/prompts.py` went through several honest iterations. Early passes (1–5)
targeted the **10-question** `data/dev_questions_with_answers.json` set. Later passes (6+)
targeted the harder **16-question** `live_eval_questions.json` regression set without hard-coding
live entity names, gold SQL, or question IDs into the prompt.

Each live-API pass below was run end-to-end rather than assumed.

### Passes 1–5 — original ten gold questions (2026-07)

| Pass | DeepSeek | GPT-OSS | MiniMax | What changed / what went wrong |
|---|---:|---:|---:|---|
| 1 — baseline prompt | 70% | 70% | 60% | Three questions failed identically across all models: correct values, wrong output shape (e.g. separate `FirstName`/`LastName`/`EmployeeId` instead of one name column) or a missing default sort. |
| 2 — first column-shape fix | 90% | — | — | Added a general rule, but its few-shot examples literally quoted the wording of failing eval questions (e.g. `q_003`) — a teaching-to-the-test mistake. Caught on review and reverted before being adopted. |
| 3 — de-overfit rewrite | 70–73% | — | — | Replaced hard-coded examples with synthetic, schema-unrelated ones. Over-corrected: DeepSeek started dropping requested measures (`q_004`) and skipping default ordering on breakdowns (`q_006`) that the original wording had covered. |
| 4 — expanded contract prompt | 90% | 80% | 50–53% | Added explicit measure/ordering/rank rules. Helped GPT-OSS (+20pp) but regressed DeepSeek on `q_005` by dropping the “combine name fields into one label” rule. |
| 5 — July landing (dev-tuned) | **100%** | 70% | 53.3% | Restored the combine-vs-separate name rule alongside measure/ordering rules. All ten **dev** questions passed for DeepSeek at that time; 0% repair rate. Tuning against those ten stopped here to avoid overfitting. |

`data/dev_answers.json` was generated deterministically from a single DeepSeek-V4-Flash agent run
(repeat 0, concurrency 1) with the **pass-5** prompt, not from a mix of models.

### Passes 6+ — live regression set + system fixes (2026-08)

Percentages below are **DeepSeek-V4-Flash · agent · repeats 3 · concurrency 1** unless noted.
SQL Eq = execution equivalence vs gold (with optional `evaluation_contract`). E2E Acc =
agent delivered `query` rows with no error **and** SQL Eq.

| Pass | Live SQL Eq | Live E2E | What changed / what went wrong |
|---|---:|---:|---|
| 6 — live baseline (pre-fix) | 62.5% (30/48) | 60.4% (29/48) | First DeepSeek-only score on `live_eval_questions.json` (`raw_bakeoff_20260813T190020Z.jsonl`). Failures included false `unsupported`, one safety-reject with SQL-eq true, wrong joins/ties/date grain, missing measures. |
| 7 — system + first prompt/schema pass | 75.0% (36/48) → then 81.2% (39/48) after contract rescoring | mid-run E2E dipped when `is_safe` still false-rejected correlated SQL | Fixed CTE/subquery scoping in `is_safe`; added dual metrics + contracts (`live_006`/`010`/`011`/`012`); unsupported/FK/tie/measure/year-sample prompt+schema rules. Correlated EXISTS and unaliased scalar derived tables still needed follow-up validator work. |
| 8 — correlated / unaliased `is_safe` | 75% SQL Eq with E2E matching once rejects fixed | 75% | Outer-ref resolution through nested SELECTs; unaliased derived tables allowed. Remaining live misses: `live_011`, `live_014`, `live_016` (projection / MoM grain / measure). |
| 9 — projection + temporal consolidation | 72.9% then 87.5% then 93.8% on intermediate runs | same | Replaced conflicting “one column per named thing” vs measure bullets; MoM → `%Y-%m`, month-of-year → `%m`; growth projects base+rate; restored explicit never-SELECT-`*Id`. Optional `required_columns` briefly applied then **removed** (rejected valid aliases like `playlist_count` vs `PlaylistCount`). Intermediate regressions: occasional `EmployeeId`/`CustomerId` in SELECT; `%Y-%m`+`LIMIT 1` on `live_006`; alphabetical ORDER BY on genre averages. |
| 10 — ID / LIMIT / breakdown hardening (adopted) | **100% (48/48)** | **100% (48/48)** | Strengthened: omit `*Id` even when used in `GROUP BY`; measure-first ORDER BY for “for each …” breakdowns; `LIMIT`/top-1 only when the question asks solely for the top item; MoM keeps every period with NULL first-period growth. Artifacts: `raw_bakeoff_20260814T090217Z.jsonl` and confirm `raw_bakeoff_20260814T090713Z.jsonl`. P50 ≈ 1.92–2.02s; med input tokens ≈ 1651; repair 0%; 1 LLM call/query. |

**Compression attempt (rejected):** a shorter rewrite of pass 10 dropped Live to 45/48
(`live_011` 0/3). The winning longer wording was restored and re-confirmed at 48/48.

### Honest re-score of the original ten with the current (pass 10) prompt

| Set | DeepSeek SQL Eq / E2E | Notes |
|---|---:|---:|
| Live 16 Q × 3 | **48/48 = 100%** | Regression target only — not a generalization claim. |
| Dev 10 Q × 3 | **18/30 = 60%** | Same prompt. Misses `q_003` (name concat vs separate fields), `q_006` (alias + tie order), `q_008` (`ROUND` vs unrounded gold), `q_009` (alias names). Near-misses, not safety rejects. Artifact: `raw_bakeoff_20260814T091105Z.jsonl`. |
| Combined 26 Q × 3 | **66/78 = 84.6%** | `benchmark/results/full_eval_metrics_deepseek.json`. |

The July claim that “all ten pass for DeepSeek” applied to **pass 5**, not to the current live-tuned
prompt. Pass 10 deliberately optimized general invariants needed by the live set; that moved
some Dev gold shapes. Closing Dev without regressing Live needs contracts or carefully scoped
prompt exceptions — not live-entity hardcoding.

MiniMax M3's Community License still requires legal review before production use (see
`DECISIONS.md`); it was not re-selected as the bake-off winner.

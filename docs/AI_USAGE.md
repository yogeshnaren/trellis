# AI Usage

I wrote a detailed build plan (`BUILD_PLAN.md`) up front, including the chosen model candidates
and the requirement to keep the system latency- and budget-bounded. Cursor's coding agent:

- implemented the Python project, tests, CLI, benchmark, evaluator, and documentation;
- looked up current Fireworks model pricing, reasoning controls, and model-license terms;
- ran local unit, lint, type, schema-size, and CLI smoke checks;
- initialized Git and committed each completed implementation phase.

During review I tightened the original plan before implementation: AST-based SQL safety replaced
regex-only checking; costs gained cached-token accounting and reserve/settle semantics; the
baseline became an explicit same-model control; and conversation memory was reduced to SQL and
metadata only.

Once `FIREWORKS_API_KEY` became available, Cursor's coding agent ran the live preflight and the
full three-model, two-concurrency-level bake-off directly against Fireworks, diagnosed and fixed
two real bugs surfaced only by live traffic (an invalid `enable_thinking` request field for
DeepSeek-V4-Flash, and an uncaught `sqlglot.TokenError` in the baseline-control SQL extractor),
and ran a live piped multi-turn CLI session to validate the actual interactive CLI end-to-end
(not just the benchmark harness), which surfaced real prompt-cache reuse across turns.

Investigating a cluster of identical-cause failures in the first live bake-off (70%/70%/60% exec
acc), the agent's first prompt fix used the literal wording of the failing eval questions as
few-shot examples — a teaching-to-the-test mistake. The user caught this and asked for a
generalizable fix instead; the agent corrected it with synthetic, schema-unrelated examples,
found and fixed a related `max_tokens` truncation bug in the same investigation, and re-ran the
full bake-off (90%/70%/80%). The user then iterated on the prompt directly across two further
rounds — one expanded the measure/ordering rules and lifted GPT-OSS to 80% but regressed DeepSeek
to 90% by dropping a name-combining rule, and the final round restored that rule alongside the
new ones, reaching 100%/70%/53.3% for DeepSeek/GPT-OSS/MiniMax on the **10-question
`data/dev_questions_with_answers.json` set** (July 2026). Each round was re-validated end-to-end
against the live API rather than assumed. That iteration history is recorded in
`PROMPT_ITERATIONS.md` and `DECISIONS.md`.

## 2026-08 — Live-eval suite, semantic guardrail, and regression to 48/48

After the July handoff, additional work (again with Cursor's coding agent implementing against
written plans) focused on a harder **16-question live regression set**
(`live_eval_questions.json`) and on productizing several system defects those runs exposed:

1. **Semantic guardrail** — `SQLResponse` gained `response_type` ∈ {`query`, `unsupported`,
   `clarify`}. The agent returns without `is_safe`/execute for non-query answers so irrelevant
   or underspecified questions do not invent SQL.
2. **`--questions` on the bake-off** — `benchmark/run_bench.py` can point at any gold JSON
   (live set or the original ten). Dual success metrics were added: **SQL Eq** (execution
   equivalence vs gold) and **E2E Acc** (agent delivered query rows with no error **and** SQL Eq).
3. **Live bake-off + failure analysis** — DeepSeek / GPT-OSS / MiniMax were scored on the live
   set (prior DeepSeek ~62.5% SQL Eq). Failures were categorized in
   `benchmark/results/live_eval_failures.json` and an implementation plan
   (`IMPLEMENTATION_PLAN_LIVE_EVAL_FAILURES.md`).
4. **Safety validator fixes (no repair-on-reject)** — `is_safe` gained scoped CTE/subquery
   alias maps, derived-table alias registration, and correlated outer-ref resolution so valid
   SQL was no longer false-rejected (`Unknown column: c.genre_count`, `Unknown table or
   alias: a/pt`, unaliased scalar derived tables).
5. **Optional evaluation contracts** — `order_policy`, `tie_policy`, `date_grain`,
   `required_columns` on questions that need explicit product contracts (e.g. month grain,
   bag-within-ties). Contracts clarify acceptance; they were not used to grant credit for
   names-only bags.
6. **Prompt / schema calibration for live failures** — unsupported ≠ missing samples; FK-only
   joins; measure projection for threshold/above-average questions; MoM uses `%Y-%m` vs
   month-of-year `%m`; no SELECT `*Id`; growth projects period + base + rate; Invoice year
   samples via `strftime('%Y', InvoiceDate)` in schema context. Passes beyond the July “pass 5”
   landing are documented in `PROMPT_ITERATIONS.md`.
7. **Measured DeepSeek live regression** — after the above, DeepSeek agent × 3 repeats ×
   concurrency 1 reached **48/48 SQL Eq and 48/48 E2E**
   (`raw_bakeoff_20260814T090713Z.jsonl`, confirmed also on `…T090217Z.jsonl`). Same-settings
   re-score of the original **ten** gold questions with the current prompt is **18/30 = 60%**
   (`raw_bakeoff_20260814T091105Z.jsonl`): four questions miss on column-shape / ROUND / alias
   near-misses, not safety rejects. Combined 26-question view: **66/78 = 84.6%**
   (`benchmark/results/full_eval_metrics_deepseek.json`).

Every number cited for the August work was taken from those JSONL artifacts and
`benchmark/results/report_live_48.md` / `full_eval_metrics_deepseek.json` — not fabricated.
Live API spend for the August live-eval / regression loop remained well under the shared
project budget ledger (`benchmark/results/.spend.json`); see `COST_COMPARISON.txt` for the
latest measured $/query figures vs the earlier GPT-5.4 estimate.

## 2026-09 — Public-release cleanup, rename to Trellis, BIRD-SQL benchmarking

For the public release, I directed Claude Code to: strip every reference to the original
scenario this project was built under and reframe the requirements as my own; rename the
project to Trellis; fix a real bug where `Agent` validated generated SQL against a hardcoded
default database path regardless of which database it was actually connected to; generalize
`src/schema.py`'s sample-value heuristics from two hand-picked Chinook columns to a
cardinality/date-detection heuristic that works on arbitrary schemas; and add BIRD-SQL Mini-Dev
benchmarking end to end (dataset fetch script, loader, evidence-hint plumbing, a new runner, and
a difficulty-broken-down report).

While re-validating the CLI live before publishing, the agent discovered the original Fireworks
model IDs (`gpt-oss-20b`, the undated `deepseek-v4-flash` alias) had been retired from the
catalog, re-pinned them to their live replacements, re-verified pricing against Fireworks' own
docs rather than trusting the old figures, and in the process found that `benchmark/preflight.py`
had been silently validating against a stale response contract and never loading `.env` — both
fixed. It also re-ran the original ten dev questions live against the current model rather than
re-publishing the old headline number, found the honest score had dropped from 100% to 60%,
inspected all four failures by hand, and determined three were evaluation-contract artifacts (the
agent's own deterministic tie-breaking penalized by a gold query with no declared tie policy) and
one was a real recurring prompt ambiguity — writing up the finding instead of quietly patching the
prompt to restore the old number. Full account in `docs/DECISIONS.md`.

# Engineering Decisions

## 2026-07-12 — Full schema in prompt
**Decision:** Cache the compact 11-table Chinook schema and include it in every agent request.
**Why:** It fits in roughly 206 whitespace-delimited tokens and avoids 2–3 schema-discovery
round trips. Revisit when a production schema no longer fits comfortably in context; then use
retrieval or bounded schema-discovery tools.

## 2026-07-12 — One bounded repair
**Decision:** Validate with `EXPLAIN QUERY PLAN` and permit one repair after validation or
execution failure. Safety rejections never retry. **Why:** At most two LLM calls makes the
latency tail and cost predictable.

## 2026-07-12 — Structured output remains one field
**Decision (superseded 2026-08):** Originally `SQLResponse` contained only required `sql: str`.
The ten public questions were answerable against Chinook, so clarification fields were deferred.
**2026-08 update:** see “Semantic guardrail” below — `response_type` / optional `message` were
added after live-eval and product review showed irrelevant questions must not invent SQL.

## 2026-07-12 — SQL-only conversation history (deliberate BUILD_PLAN deviation)
**Decision:** `Turn` stores question, SQL, row count, and truncation; it drops BUILD_PLAN
§1/§3's `first_row`. **Benefit:** Follow-ups receive the query they need to modify without
persisting result row values or paying their prompt-token cost. **Cost/revisit trigger:**
revisit only if a measured follow-up suite shows that result values materially improve accuracy.
This written entry explicitly satisfies BUILD_PLAN §9's requirement to disclose rather than
silently make an architecture change.

## 2026-07-12 — Layered read-only safety
**Decision:** `sqlglot` SQLite AST validation is primary. It rejects multiple/non-read
statements, forbidden nodes/functions, and unknown physical identifiers. SQLite's authorizer,
`query_only`, disabled extension loading, progress timeout, and a read-only URI sit underneath.
This is deliberately belt-and-suspenders-and-belt: no one layer is presented as sufficient.

## 2026-07-12 — Reserve then settle one shared ledger
**Decision:** Reserve conservative uncached-input/max-output cost under an `asyncio.Lock`
before HTTP dispatch, then settle actual uncached/cached/output cost. CLI and benchmark use the
same persisted ledger. Cancellation is best effort only; the reservation is the hard cap.

## 2026-07-12 — Baseline is a same-model control
**Decision:** Agent runs on all candidates; the literal raw prompt runs only on
DeepSeek-V4-Flash, without schema, structured output, or repair. Safety remains universal.
This isolates architecture/prompt benefit. It is not a GPT-5.4 head-to-head; the reported
GPT-5.4 baseline numbers elsewhere in this repo are directional context only, not something
benchmarked live here.

## 2026-07-12 — Latency evidence
**Decision:** Concurrency 1 P50/P90 is authoritative for the interactive SLO. Concurrency 5 is
separate load evidence. TTFT is not captured because SQL cannot execute until completion.
**2026-08 note:** Live-regression reports also quote P95/max for the 48-run DeepSeek agent
arm because those runs are the primary latency evidence for the current prompt; the original
“no P95 at ~30 observations” caution still applies to small multi-model slices.

## 2026-07-12 — Candidate licensing
- GPT-OSS-20B weights: Apache 2.0.
- DeepSeek-V4-Flash repository and weights: MIT (official Hugging Face model card/license).
- MiniMax M3: MiniMax Community License, not an OSI-permissive license. Commercial use requires
  “Built with MiniMax M3” attribution plus notice below $20M annual revenue or prior written
  authorization above that threshold. Legal review is required before production selection.

## 2026-07-12 — Dependencies
No agent framework. `sqlglot` exists specifically for AST safety/baseline parsing; `pydantic`
derives the response schema. The remaining runtime dependencies are OpenAI, Rich, and dotenv.

## 2026-07-12 — Corrected DeepSeek-V4-Flash thinking control
**Problem:** `model_request_options` originally passed `extra_body={"enable_thinking": False}`.
The OpenAI SDK's `extra_body` kwarg splices its dict directly into the top-level JSON request
body rather than nesting it under an `"extra_body"` key, so this sent a bare `enable_thinking`
field that Fireworks' schema for this model rejects with "Extra inputs are not permitted."
**Fix:** use the standard OpenAI-compatible `reasoning_effort="none"` field instead, verified
live against the endpoint. GPT-OSS/Harmony models keep `reasoning_effort="low"` because they
reject `"none"` and only accept low/medium/high.

## 2026-07-12 — Baseline parser hardening
**Fixed:** `extract_baseline_sql` only caught `sqlglot.errors.ParseError`; a live raw-prompt
response containing an unbalanced backtick raised `TokenError` instead and crashed the harness.
Both exception types are now caught and converted into a `baseline-parse-failed` record.

## 2026-07-13 — Column-shape prompt guidance, and a self-correction on overfitting
**Problem observed:** The first live bake-off (70% / 70% / 60% exec acc for DeepSeek / GPT-OSS /
MiniMax) showed three questions failing identically across all three models with numerically
correct values — the agent returned raw entity columns (e.g. `FirstName, LastName, EmployeeId`)
where the gold answer used one concatenated name column, and one question had an implicit default
ordering the agent didn't infer. This pointed at a real, generalizable gap in `SYSTEM_PROMPT`
(no guidance on output column shape or default ordering), not a model-quality gap.

**First attempt (rejected on review):** The initial fix used the literal wording of the failing
eval questions as few-shot examples in the prompt (e.g. "Which employee has the most customers?").
This is teaching-to-the-test: it would inflate accuracy on this specific ten-question set without
generalizing to any other schema or question. This was caught and reverted before being adopted
as the final version — see the corrected version below.

**Adopted fix:** `SYSTEM_PROMPT` stated the column-shape rule using synthetic,
schema-unrelated examples, plus explicit measure/default-order guidance.

**Also fixed while investigating:** `Agent.ask()` `max_tokens` raised from 200 → 400 after
structured-output truncation.

**Honest result at the time:** exec acc improved to 90% / 70% / 80%, then after two more
prompt passes (see below) DeepSeek reached 100% on the **ten** gold questions. Remaining
brittleness and the overfitting lesson are unchanged: do not keep patching against the same
tiny set forever.

## 2026-07-13 — Two further prompt passes, then a July landing point
**Pass 4:** expanded measure/ordering/rank rules → 90% / 80% / 50–53%; DeepSeek regressed on
`q_005` after the name-combine rule was dropped.

**Pass 5 (July adopted):** restored combine-vs-separate name rules with measure/ordering →
**100% / 70% / 53.3%** on the ten-question set for DeepSeek / GPT-OSS / MiniMax. Repair rate 0%.

Tuning against those ten stopped at pass 5. Full five-pass history is in `PROMPT_ITERATIONS.md`.

## 2026-07-13 — Bake-off winner (July numbers; still the selected model)
**Decision:** DeepSeek-V4-Flash is the selected model. On the July ten-question bake-off it had
the best execution accuracy (100.0% vs GPT-OSS-20B 70.0% and MiniMax M3 53.3%), best P50, and
lowest $/query among the three. It remains the selected model after the August live-eval work.

**August honesty check:** with the **current** (live-tuned) prompt, DeepSeek scores **100%**
on the 16-question live regression set (48/48) and **60%** on a fresh re-score of the original
ten (`raw_bakeoff_20260814T091105Z.jsonl`). The July 100% figure must not be quoted as the
current Dev score without naming the prompt revision.

---

## 2026-08-13 — Semantic guardrail (`query` | `unsupported` | `clarify`)
**Decision:** Extend `SQLResponse` with required `response_type`, nullable `sql`, and nullable
`message`. Non-`query` responses return before `is_safe` / validate / execute.
**Why:** Irrelevant or underspecified questions must not generate or run SQL. Empty result
sets remain valid for answerable queries; missing schema *samples* must not force `unsupported`.
**Not done:** second LLM classifier; fuzzy/LLM grading.

## 2026-08-13/14 — Live regression set is not a generalization claim
**Decision:** Maintain `live_eval_questions.json` (16 harder questions) as a **visible regression
suite**. Report SQL Eq and E2E Acc honestly; never claim “100% accuracy” as product
generalization from this set alone.
**Why:** The set was used to drive fixes; treating it as a frozen holdout after iterative
prompt work would overstate generalization.

## 2026-08-14 — Dual metrics: SQL Eq + E2E Acc
**Decision:** Keep historical execution-equivalence as `sql_equivalent` / SQL Eq. Add
`e2e_success` = (`error is None` ∧ `response_type == "query"` ∧ `rows is not None` ∧
`sql_equivalent`). Report both in `benchmark/report.py`.
**Why:** A safety-rejected run can still have an offline-equivalent SQL string; E2E requires
the agent path to actually deliver results.

## 2026-08-14 — Fix `is_safe` scoping; do not repair safety rejects
**Decision:** Register subquery aliases as derived sources; use per-SELECT scoped alias maps
so CTE bodies / inner `AS c` do not overwrite outer bindings; resolve column qualifiers through
parent SELECT scopes (correlated refs); allow unaliased scalar derived tables. Unknown physical
tables/columns and `FORBIDDEN_*` stay rejected. **Still never route `safety-rejected` through
repair.**
**Why:** Live failures showed false rejects (`c.genre_count`, `Unknown table or alias: a/pt`,
`Derived tables require an alias`) that blocked otherwise correct SQL.

## 2026-08-14 — Optional evaluation contracts (strict default)
**Decision:** Optional `evaluation_contract` on gold JSON: `order_policy`, `tie_policy`,
`date_grain`, `required_columns`. Absent → prior behavior.
**Applied:** month grain + ties on `live_006`; bag-within-ties on `live_010`/`011`/`012`.
**Rejected for Live 48/48:** using `required_columns` as a scoring gate after aliases like
`playlist_count` vs `PlaylistCount` caused false negatives — removed from those questions;
diagnostic-only use remains available in the evaluator.
**Rejected:** `date_grain=month` on MoM `live_014` to accept `%m` (would conceal wrong
chronological identity). Evaluator already rounds floats to 2dp in `_normal`, so SQL `ROUND`
is product polish, not required for SQL Eq.

## 2026-08-14 — FK handling stays prompt-only this pass
**Decision:** Instruct “join only along listed FKs; never equate unrelated `*Id` columns.”
No AST FK join lint and no safety-reject for bad joins in this pass.
**Why:** Prefer measuring whether prompt guidance closes `live_009`-class misses before adding
repair-path complexity. Revisit only if that class returns after Live is green.

## 2026-08-14 — Prompt invariants for Live 48/48 (no second LLM call)
**Decision:** Consolidate `SYSTEM_PROMPT` projection/ranking/temporal rules rather than adding
a critique pass, second model, or `max_repairs > 1`.
**Key invariants (general, not live-ID-specific):**
- Aggregate threshold / above-average / “for each …” → project entity **and** measure;
  existence/absence without a measure may be labels-only.
- Never SELECT `*Id` unless asked — even when `GROUP BY` uses an Id.
- Measure-first ORDER BY; deterministic label secondary order for top-N / LIMIT / ROW_NUMBER;
  do not add secondary order merely for a full listing.
- `LIMIT`/top-1 only when the question asks solely for the top item.
- MoM / chronological series → `strftime('%Y-%m')`; month-of-year categories → `%m`.
- Growth: period key + base measure + derived rate; all periods; NULL first growth; ROUND % to 2dp.
**Schema:** sample Invoice years via `strftime('%Y', InvoiceDate) LIMIT 5` (no hardcoded `2021`).
**Outcome:** DeepSeek Live **48/48** SQL Eq and E2E (`raw_bakeoff_20260814T090713Z.jsonl`).
**Trade-off:** med input tokens rose (~1550 → ~1651 vs the mid-August live baseline). A shorter
compression attempt regressed `live_011`; winning wording was restored.

## 2026-08-14 — Explicitly not changing (still)
Read-only safety stack beyond scoped `is_safe` fixes; `max_repairs=1`; second LLM critique;
fuzzy/LLM grading; live-entity hardcoding in prompts; repair-on-safety-reject; global eval
loosening; new dependencies; RFT/fine-tuning; model switch away from DeepSeek for the PoC.

---

## 2026-09-22 — Model catalog drift: re-pinned model IDs, re-verified pricing, fresh live run
**Problem:** Revisiting this project after a gap, the CLI failed outright — `gpt-oss-20b` and the
undated `deepseek-v4-flash` alias used throughout the July/August work are no longer deployed on
Fireworks (`openai.NotFoundError: Model not found`). Checking `GET /v1/models` live against the
Fireworks API confirmed `gpt-oss-20b` has no replacement at the same size (only `gpt-oss-120b`
remains) and the undated DeepSeek alias now requires the dated snapshot `deepseek-v4-flash-0731`.
MiniMax M3's ID was unaffected.

**Decision:** Re-pin `MODEL_GPT_OSS` → `gpt-oss-120b` and `MODEL_DEEPSEEK` →
`deepseek-v4-flash-0731`; re-verify all three prices against
[docs.fireworks.ai/serverless/pricing](https://docs.fireworks.ai/serverless/pricing) rather than
trusting the July figures. Actual changes: GPT-OSS $0.07/$0.30 → $0.15/$0.60 (larger model, not
just a price change), DeepSeek $0.14/$0.28 → $0.22/$0.66 (same size class, genuine repricing),
MiniMax unchanged at $0.30/$1.20.

**Also found and fixed while re-validating:**
- `benchmark/preflight.py`'s conformance checker (`assert_exact_sql_response`) still validated
  against the *original* one-field `{"sql": ...}` contract from before the August semantic-guardrail
  change (`response_type`/`sql`/`message`). It had been silently checking the wrong schema for a
  month; every model "passed" preflight only because the check was too loose to notice. Rewrote it
  to validate against the live `SQLResponse` model instead of a hand-rolled key check.
- `benchmark/preflight.py`'s `main()` never called `load_dotenv()` (unlike `cli.py` and
  `run_bench.py`), so it silently ignored `.env` and only worked if `FIREWORKS_API_KEY` happened to
  already be exported in the shell. Fixed for consistency with the other two entry points.
- The preflight probe's `max_tokens=80` was sized for the old one-field schema; the current
  three-field schema plus MiniMax's verbosity needs more headroom. Raised to 150 after confirming
  MiniMax was truncating mid-response, not failing to conform.

**Fresh live re-validation, not just a config patch:** ran the current prompt against the current
`deepseek-v4-flash-0731` on the original ten dev questions (concurrency 1, 1 repeat;
`raw_bakeoff_20260923T050748Z.jsonl`). Raw SQL-Eq: **60%** (6/10), down from the historically
reported 100%. Inspecting all four "failures" by hand: `q_003` is a genuine name-combining
ambiguity the prompt has flip-flopped on before (see 2026-07-13 above); `q_006`, `q_008`, and
`q_009` are **not generation errors** — the agent added its own deterministic tie-breaking column
to `ORDER BY` (exactly what `SYSTEM_PROMPT` instructs for reproducible top-N results), which the
evaluator's default *strict* row-order comparison penalizes because these three gold queries never
declared an explicit tie policy. All four generated queries are inspected-correct or arguably
better SQL; none are hallucinated schema, wrong joins, or wrong aggregates. This is an evaluation-
contract gap (missing `tie_policy`/`evaluation_contract` entries on these four dev questions), not
a capability regression — recorded here rather than silently re-quoting the stale 100% figure.
**Not done:** backfilling `evaluation_contract` on the four affected dev questions to restore the
100% figure. Doing that now, after seeing which questions fail, would be exactly the
teaching-to-the-test mistake called out and reverted in the 2026-07-13 entry above — left as-is
and disclosed instead.

## 2026-09-23 — Jev (TypeSafe AI) approved as a decision layer for the BIRD path
**Decision:** TypeSafe AI's Jev "System One" decision model (`typesafe/jev-1.13`, called through
OpenRouter's alpha Decisions API with the team's OpenRouter key in `OPENROUTER_API_KEY`) may be
used in the BIRD benchmark and the BIRD test submission. **Scope:** decisions only. These are
the cascade escalate-or-ship gate, evidence and output-contract checks, the answerability
guardrail, schema-relevance scoring, and a selection tie-break. Jev never generates or executes
SQL. **Why:** these decisions need calibrated probabilities at low latency and cost, which is
what Jev is built for. The accuracy ceiling still comes from the generators and the selector.
**Conditions:**
- Each Jev decision is adopted only if it beats the agreement-only and small-LLM-judge
  baselines in the offline R5-J bake-off, checked per difficulty tier
  (`docs/SOTA_PLAN.md` §5-J).
- Thresholds are fitted per returned model version.
- Any Jev failure falls back to the agreement-only rule.
- Spend goes through the shared `BudgetGuard` ledger.

**Not decided:** Jev on production databases. Question, schema and sample values leave
Fireworks, so this needs a separate data review. Until then the `product` profile stays
Jev-free.

## 2026-09-23 — BIRD measurement protocol (SOTA plan v2)
**Decision:** BIRD's official EX (`set(pred) == set(gold)`, 30s timeout) is the headline BIRD
metric, and only SQL the agent delivered counts. The unit is the dataset **row**: all 500
Mini-Dev rows, including the duplicated question ids 137/138. Gold and prediction each
execute once (`score_bird`). Every run writes a meta sidecar with the dataset and prompt
hashes and the git commit.

**Splits:**
- Iteration happens on `train_dev` (4 train databases, 501 rows), because BIRD test uses
  unseen databases. It becomes a development set through use, so reports are per database
  plus a macro average.
- `train_lockbox` (7 more train databases across 7 domains, 974 rows; widened after the
  third review) and Mini-Dev are infrequent gates: at most 4 looks, 3 repeats each. Neither
  is used to choose between variants.
- Untouched dev (1,036 rows) is reported separately, on BIRD dev's own databases.

**Why:**
- The local evaluator disagreed with BIRD's on 30/500 rows.
- The earlier 498-row count dropped the duplicate rows.
- Tuning on Mini-Dev's own 11 databases can't show generalisation.
- 5 of Mini-Dev's 11 databases differ in content from BIRD dev's copies, which changes 23
  Mini-Dev and 60 dev gold results.
- Two identical T=0 runs flipped 6/60 answers, so decisions use repeats and paired McNemar
  flips by difficulty and by database.

**Also fixed:** `schema.py` rendered implicit foreign-key targets as `parent.None` (4 of 105
edges across two BIRD databases). They now resolve to the parent primary key, with a test
that every rendered edge resolves. Chinook's schema text is unchanged.

## 2026-09-23 — Cross-process spend ledger; candidate-only execution
**Problem (found by review, reproduced):** `BudgetGuard` read `.spend.json` once at start-up
and overwrote it on every settle. When three processes ran concurrently, the ledger recorded
$0.04 of $0.12 actually spent, and two processes crashed on a shared temp-file name. The
"hard cap" held only within one process. OpenRouter/Jev and Fireworks batch charges had no
path into it at all.

**Decision:**
- Every ledger read-modify-write holds an `fcntl` exclusive lock.
- Reservations live in the ledger, so every process sees all of them.
- Spend is tracked per source (`fireworks`, `fireworks-batch`, `openrouter`, `unsettled`).
- A reservation whose process died, or that is more than an hour old, is charged as spent,
  because its call may have been billed.
- `reserve_usd`/`settle(source=…)`/`record_charge` cover non-token-priced spend.
- `cost_usd(batch=True)` applies Fireworks' 50% batch rate.
- Version-1 ledgers migrate in place. Unix-only (`fcntl`), as is this project's toolchain.

**Also:** `src/db.py:execute_candidate` safety-checks and fully executes a candidate and
returns its result signature with no gold query involved. That is the executor for
cascades and hidden-test runs. `score_bird` now runs the candidate before gold, so a gold
timeout no longer loses the candidate's signature.

**Follow-up (third review, reproduced):**
- **Bug:** settling a reservation that had already been charged as stale added its actual
  cost on top, and settling again added it once more. $0.10 of real spend was recorded as
  $0.40. That would have overstated spend and halted experiments early.
- **Fix:** stale charges are remembered per token. A late settle replaces the stale charge
  with the actual cost, moving it from `unsettled` to its real source. Repeat settles are
  no-ops, via settled tokens remembered for 7 days.
- Reservations now carry their own `ttl_s`, so an hours-long batch job isn't charged as
  abandoned after the default hour.
- Batch pricing (`cost_usd(batch=True)`) is supported, but there is **no batch submission
  path yet**, so batch savings are not counted in any plan estimate.

## 2026-09-23 — SQLite spend ledger; content-pinned runs; two-metric acceptance
**Ledger:** two double-counting cases survived the JSON fix (fourth review, reproduced):
- a settle with an unknown cost finalised the estimate, so a later real cost couldn't
  correct it ($0.20 kept instead of $0.10);
- settled keys expired after 7 days, after which a repeat settle charged again.

Making keys durable in a JSON file that is rewritten on every call would grow without bound,
so the ledger is now **SQLite** (`benchmark/results/.spend.sqlite`, stdlib):
- an append-only charge journal (spend = its sum) and open reservation rows;
- settlement keys that never expire, and caller-supplied keys (e.g. a batch job id) so a
  different process can settle after a restart;
- every operation in a `BEGIN IMMEDIATE` transaction, so processes serialize on SQLite's
  lock;
- unknown outcomes and stale reservations book *provisional* charges that a real cost later
  reverses.

The legacy JSON ledger was imported once as an opening balance ($0.2817), and the original
file was kept as `.spend.json.migrated`.

**Run pinning:** run metadata now hashes content, not paths:
- each database file (cached by size and mtime);
- the effective system prompt per database (template + rendered schema);
- the generation config;
- the code state (diff + untracked files under `src/` and `benchmark/`).

`analyze flips` refuses to compare runs that differ in anything but the declared `--allow`
variable.

**Acceptance:**
- A change must clear its declared minimum on both the row-weighted Δ *and* the
  database-macro Δ, because one `train_dev` database is 258 of 501 rows.
- CIs come from a bootstrap that resamples questions within each database, with each
  question's repeats kept together.
- Borderline results trigger an audit of the deciding flips against gold.
- The lockbox gets 2 looks, not 4.
- Train splits have no difficulty labels, so per-tier checks use a gold-SQL complexity band.

**Follow-up (fifth review, reproduced):** a budget-stopped variant with one result, compared
with a complete 2-question × 2-repeat baseline, scored +100 pts with a CI of [100, 100].
- Runs now record `expected_rows`, `expected_repeats`, and `complete`.
- `analyze flips` accepts only full comparisons: complete runs, identical expected rows, and
  exactly 2 repeats per question. Partial overlap needs an explicit `--pilot`, and the
  report is then labelled not acceptance evidence.
- Phase 1 full runs are cumulative, each against the last accepted configuration, so the
  combination is what gets validated.

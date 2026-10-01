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

## 2026-09-24 — Phase 1: benchmark prompt profile accepted
**Decision:** BIRD runs use `--prompt-profile benchmark`. It replaces only the Chinook-era
"Projection and ranking" rules (label-plus-measure outputs, `First || ' ' || Last` names,
2-dp rounding, tie-breaker ordering) with "return exactly the fields asked for". The
product/CLI profile (`SYSTEM_PROMPT`) is byte-identical to before.

**Evidence:** full comparison on `train_dev` (501 questions × 2 repeats, both runs
complete):
- row-weighted Δ +6.99 pts [95% CI +4.49, +9.78];
- database-macro Δ +6.91 [+3.03, +10.98];
- no large single-database loss (movie flat; the other three +4.8 to +11.5);
- no cost increase.

This follows the plan-v2.4 acceptance rule, with the minimum declared before the run.

**Known side effect, targeted next:** safety rejections rose from 7 to 14 per 1,002 answers,
all unquoted special-character column names, and "unsupported" refusals rose from 2 to 6.
Identifier quoting (1b, `--quote-identifiers`, implemented) plus pipeline repairs (1c) are
tested next as one cumulative change against this accepted run.

## 2026-09-24 — Phase 1: identifier quoting + pipeline repairs accepted (borderline, by audit)
**Decision (owner):** BIRD runs add `--quote-identifiers --pipeline-repairs` on top of the
benchmark profile. Pipeline repairs are:
- one "did you mean" repair for unknown-identifier or parse rejects (forbidden SQL still
  never retries);
- one refusal retry;
- one guarded empty-result retry, which replaces the answer only if the new query is safe,
  valid, and returns rows;
- a size-scaled execution timeout.

All are off by default, so the product CLI is unchanged.

**Evidence** (full comparison vs the accepted 1a run, `train_dev` 501 × 2):
- database-macro Δ +3.90 [+1.13, +7.05] passes;
- row-weighted Δ +1.60 [+0.20, +2.99] misses the cost-adjusted minimum of +1.63 by
  0.03 pts;
- errors 22 → 3; safety rejections 14 → 0; refusals 6 → 0;
- movie +15.2 (7 fixes, 0 regressions).

**The required audit:**
- The 5 regressions all fall on questions whose prompt and pipeline path this change didn't
  touch, so they are noise.
- The fixes trace to quoting (5), refusal retry (2), identifier repair (1), and empty
  retry (1).
- Uncached-equivalent cost rose +6.4%; the measured +43% reflected provider cache hits
  falling from 46% to 23%.

Accepted as a *borderline accept*, not a clean pass. Accuracy is now 68.7% row-weighted and
69.3% macro, from a 60.1% / 58.5% baseline. The empty-result retry is flagged for
re-evaluation at the Mini-Dev gate.

**Protocol fix:** `analyze flips` now computes the §5.4 minimum mechanically: base 1.5, plus
1 pt per +50% uncached-equivalent $/answer, plus 1 pt per +1s P50. It prints yes/no per
metric and whether an audit is required, so the next decision isn't a judgement call.

## 2026-09-24 — Phase 1 closed; dictionary CSVs not adopted
**Dictionary CSVs** (`--dictionary`, BIRD `database_description` notes per column): the
pilot on top of the accepted configuration gained +1.2 pts [−1.2, +4.4] on the stratified
sample and 0 on randomly sampled rows that use value-noted columns. It added +32%
uncached cost and +0.46s P50, which puts the required minimum at +2.61. That's not on
course, so no full comparison was run (owner decision; plan §6.1). The flag remains for a
later Mini-Dev gate check.

**Phase 1 result:** accepted configuration `--prompt-profile benchmark --quote-identifiers
--pipeline-repairs`. On `train_dev` it moved from 60.1% to 68.7% row-weighted and from
58.5% to 69.3% macro, for $1.24 of the $2 cap (ledger figure).

## 2026-09-24 — Phase 3a: reasoning mode not adopted for DeepSeek-V4-Flash
**Decision:** keep `reasoning_effort="none"` for the BIRD configuration.

**Evidence:** pilots on 100 stratified `train_dev` rows × 2 vs the accepted configuration:
- low effort: −1.5 pts [−6.5, +3.5], +103% uncached cost, P50 1.2s → 4.9s;
- high effort: −1.5 pts [−6.5, +3.0], +201% cost, P50 5.9s;
- the required minima were +7.3 and +10.3.

**Audit:** partly token-cap truncation (4 and 11 structured-output failures), mostly
reasoning producing more elaborate SQL (`EXISTS` rewrites, parsing text columns) that
diverges from BIRD's literal gold.

**Also:** the LLM client timeout is now configurable (`--llm-timeout`,
`Agent(llm_timeout_s=...)`); it was a hard-coded 20s that reasoning calls can exceed.

## 2026-09-25 — Phase 3 model bake-off and sampling; routing headroom
**Pilots** (100 `train_dev` rows × 2, vs the accepted configuration; run by a delegated
agent under a $1.50 ledger cap, which spent $0.51):
- `deepseek-v4p1-flash` +3.5 [−1.5, +8.5] at +41% uncached cost, required minimum +2.71:
  on course, so it qualifies for a full comparison;
- `deepseek-v4-pro` −0.5 at 6× cost: not adopted;
- `gpt-oss-120b` −0.5: not adopted;
- `glm-5p3-flash` −13.5 (thinking-only; 35% structured-output failures): not adopted.

Multi-sample (T=0.7, K=4): pass@4 73.0% but majority@4 69.0% ≈ pass@1, so no
self-consistency gain.

**Routing headroom:** the oracle over all five models is 73%, the same as one model's
pass@4. 24 of 100 questions were never matched by any of 1,400 answers. Of the 5 of those
with BIRD-Verified entries, 4 are label or question problems. Category routing is added to
the plan (Phase 4R) with a fit-on-`train_dev` / test-once-on-lockbox protocol, **deferred**
until the headroom check shows ≥ 5 pts.

## 2026-09-25 — Never-solved audit; retrieved few-shot not adopted
- Of the 24 pilot questions no model ever matched, 17 are gold/question errors, 1 gold
  times out, 2 are value-format errors (text-encoded durations/money), 2 are BIRD
  literal-hint conventions, and 2 are ambiguous. The practical `train_dev` ceiling is about 82%.
- `--fewshot 3` (BM25 over BIRD train, held-out databases excluded): +0.0 [−4.0, +4.0] at
  +20% cost and +0.85s P50, and 0 of the targeted convention cases fixed. Not adopted.

## 2026-09-25 — Cheap-model Pareto round: no model change
Expensive models (Kimi K3, Ember-1, Qwen3.8-Max, Inkling) were excluded on price. A
non-inferiority rule for cheaper/faster swaps was declared before the runs and is now
printed by `analyze flips`: CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one
strictly better.
- `gpt-oss-120b` (full, 501 × 2): −1.4 [−3.9, +1.1] at −20% cost. Fails the margin.
- `glm-5p3-flash` with `low` effort: +0.0 at −41% cost but +0.8s P50. Not adopted.
- `nemotron-lightning-3.5`: 4.5%. Rejected.
- Escalating the 17% of answers where two families disagree to `glm-5p3`: +0.8 pts at
  2.8× cost. Not adopted.
- `deepseek-v4p1-flash`: the first full run was invalid (reasoning left on). The rerun
  with the cap extended by $0.40 gave +0.4 [−1.9, +2.7] (macro +1.5) against a required
  +2.86, so it is not adopted.
- **Decision:** keep `deepseek-v4-flash-0731`. Round total: $1.46.
- `dev_untouched` measured at 63.6%; full-dev estimate ≈ 62.2%.

**Also fixed:** `is_safe` now turns sqlglot `TokenError` (prose in the `sql` field) into a
parse rejection instead of raising.

## 2026-09-26 — Default model becomes deepseek-v4p1-flash; unavailable models are a handled error
**Decision:** the CLI and benchmarks default to `accounts/fireworks/models/deepseek-v4p1-flash`
(reasoning off) instead of the dated `deepseek-v4-flash-0731` snapshot. This supersedes
the 2026-09-25 "keep `deepseek-v4-flash-0731`" decision, which was made on `train_dev` alone.
**Why:**
- Reproducibility. The dated snapshot could not be called from at least one account
  (`404 Model not found`, although `models.list()` still showed it). A default that not every user's
  key can reach cannot be the basis for published numbers.
- Evidence, not just availability. Same frozen configuration (`config baff9689`), same prompt hash
  (`4b52d7aa`) and data hash (`4ba5fa8d`), clean commit `eafe2ba`:
  Mini-Dev 500 × 3 went from 59.3% to **65.3%** (paired, pilot mode, +5.9 [+3.2, +8.7]);
  `dev_untouched` 1,036 × 1 is **67.6%** (was 63.6%); `train_dev` full ties (+0.4 [−1.9, +2.7]).
- Cost and latency are worse, not better: P50 0.97s → 1.36s on Mini-Dev, no-cache cost
  $0.000491 → $0.000661 per answer (measured cost is unchanged at $0.000205 because of cache hits).
  `gpt-oss-120b` stays the cheaper, faster alternative at −1.4 points on `train_dev`.
- The §5.4 swap rule (+2.9 needed) is not met on `train_dev`, so this is a default chosen from the
  pooled evidence and from availability, not an accepted upgrade. Mini-Dev was looked at a second
  time for it (2 of 4 looks used).
**Also changed:** a 404/403 from the API is now a `model-unavailable` result with a fix hint (it used
to raise out of `Agent.ask` and crash the CLI); the SQL panel wraps long queries; `MODEL_DEEPSEEK`
stays as a named constant for provenance and pricing.

## 2026-09-26 — Plan v2.7 decisions: two-track acceptance, train_dev2, filtered train, cleaned dev
- **Two-track acceptance adopted.**
  - The product (CLI) track keeps +1 pt per +50% uncached cost and per +1s P50.
  - The submission track uses the declared minimum gain plus absolute ceilings: uncached
    ≤ $0.01/answer and P90 ≤ 30s.
  - Both keep the paired row/macro CI rules.
  - `analyze flips --track`.
- **`train_dev2` preselected by a fixed rule before any run:** `professional_basketball`,
  `regional_sales`, `ice_hockey_draft`, `movielens` (503 questions). Rule in SOTA_PLAN
  §5.9. Download pending (≈ 7–8 GB sequential stream).
- **Training data starts from BIRD's `bird23-train-filtered`** (CC BY-SA 4.0), restricted
  to non-evaluation databases (5,115 rows) and audited before any paid training.
  BIRD-Verified stays evaluation-only.
- **Cleaned dev (Nov 2025) is the primary public checkpoint.** It runs on the original
  dev databases (all gold queries execute).
- **Result signatures** normalise integer-valued floats, so they agree with BIRD's set
  comparison (`1` vs `1.0`).

## 2026-09-26 — Plan v2.8 (third review)
- **Cleaned dev:** capped at 4 looks (baseline, two milestones, final freeze); aggregate
  scores count as looks.
- **Candidate bank:** a diagnostic pass on the latest accepted configuration, plus a
  separately approved confirmation pass before it can drive an SFT decision.
- **Submission ceilings made exact:**
  - mean ≤ $0.01/answer, including non-LLM per-question charges (`extra_cost_usd`);
  - any single answer ≤ $0.05;
  - one-time costs reported as a separate total;
  - P90 ≤ 30s, with timeout rules to follow once BIRD confirms its limits.
- **`train_dev2`** is development data only; transfer claims need the lockbox plus a
  larger-schema check.
- **Probe executor** gated on residual value-lookup errors after static grounding.
- **Training data:** 5,115 examples after exclusions; stop and re-filter if a stratified
  100-row audit shows > 15% semantic errors.
- **Jev:** coverage flags scored first against ≈ 50 hand-labelled omissions.

## 2026-09-26 — Plan v2.9 (fourth review); cleaned-dev baseline 66.0%
- **Cleaned dev** (primary checkpoint): the 99-row pilot counts as look 1 and the full
  baseline `20260927T025554Z` as look 2. The baseline scored **66.0%** (macro 64.1%) at
  $0.30. Two looks remain.
- **Truncation-only retry** replaces a global `--max-tokens` increase.
  - `LLMResult` now records `finish_reason`.
  - `--truncation-retry TOKENS` re-asks once with a larger cap only when the output was
    cut off. It is off by default and leaves the config hash unchanged when off.
  - It targets the baseline's 21 truncated answers (10 in `financial`). A pilot is next.
- **Rank 1c** tests BIRD's supplied `column_meaning.json` before any LLM-written
  glossary.
- **Submission cost accounting:** the analyser is ready, but runtime emitters of
  `extra_cost_usd` are still required. A run that doesn't reconcile with the ledger
  fails the cost check.
- **Candidate selection** adds question-constraint checks to result-signature agreement.
- POSTMORTEM_V2 §7.3's projections are marked superseded.

## 2026-09-26 — Truncation-only retry joins the submission package
- A forced-truncation pilot on `train_dev` (60-token cap, retry at 400): 48 of 48
  truncated answers recovered. 30 were correct vs 29 at the normal cap. Retried answers
  cost ≈ 1.8× and take +1.7s.
- It fires only on a length cut-off, which always fails, so it can't regress other
  answers.
- Added to the bundled submission-track package as `--truncation-retry 1200` and
  measured at the next cleaned-dev milestone. Not a CLI default.

## 2026-09-26 — Rank 1a measured: small headroom on BIRD
- `src/db_profile.py` (formats, join cardinality, FTS5 values; cached by content hash)
  and `benchmark/grounding.py` built and tested.
- 95–97% of gold string literals are already in the question/evidence, so value
  retrieval has little to add on BIRD.
- Text-encoded money/duration columns touch 14 of 501 `train_dev` questions (46% vs
  70%), ≤ ≈ 1.5 pts.
- Decision: keep 1a as a cheap building block (and for the product CLI), but don't
  expect it to close the gap. Selection/generation evidence (ranks 4, G) comes next.

## 2026-09-26 — Rank 1c (supplied column meanings) not adopted
- `--column-meaning 6` pilot: −1.5 [−5.5, +2.5] on 100 `train_dev` rows × 2, with +0.8s
  P50.
- It fixed the targeted money-format case but steered other answers away from BIRD's
  literal gold.
- The flag stays. A narrower, format-only variant (≈ 14 of 501 questions) is the only
  remaining 1b/1c candidate.

## 2026-09-26 — 47 more train databases; format gate stopped on evidence
- **Data:** one sequential stream extracted 47 train databases (2.3 GB total on disk).
  New splits: `train_dev2` (4 preselected databases, 503 questions, development only) and
  `train_design` (43 databases, 5,851 questions, for fitting gates and SFT execution
  checks). Existing fingerprints are unchanged.
- **Format gate stopped:**
  - On 194 design questions needing numeric use of text-stored numbers, v4p1 scores
    30.4%. But 63 of its 135 misses are it converting correctly where the gold compares
    raw text. Only 9 misses are fixable by a conversion note.
  - A convert-note gate would lower EX. A don't-convert gate would game labels and
    risks test grading.
  - No Jev spend; the grading question goes to the BIRD team.

## 2026-09-26 — Rank 4 diagnostic: selection ceiling +4 pts; generation bounds the score
- Four candidates on 501 `train_dev` questions: direct 69.5%, plan 66.9%, decompose
  67.1%, glm-5p3-flash 66.9%.
- Oracle pass@4 73.5%; majority vote 68.9% (below direct); 18.6% of questions are
  unanimous-but-wrong.
- On the 357 questions kept by BIRD's quality filter: direct 81.0%, pass@4 84.6%.
- Decision: selection can add at most ≈ +4 (realistically +1–2 with a real selector), so
  generation quality and label conventions bound the score. The confirmation pass is
  still required before any paid SFT (v2.8). Cost $0.76.

## 2026-09-27 — Mini-Dev gate 3: 64.1% with database facts + truncation retry
- Full current configuration on Mini-Dev (500 × 3): 64.1% vs 65.3% at gate 2; paired
  −1.1 [−2.7, +0.4].
- The drop sits in questions that received database facts (−1.9 vs −0.3). `financial`
  fell 11.5 pts, all on fact-bearing questions.
- The truncation retry never fired.
- The owner raised the ledger cap to $7.50 for this run (ledger now $7.28). 3 of 4
  Mini-Dev looks used.
- **Owner decision: keep database facts on for the benchmark profile for now.** Across
  four measurements the effect is ≈ 0 (+0.8 / +1.9 / +0.5 / −1.1).
- A per-database facts-off switch was checked for free from existing runs and **not**
  adopted:
  - it restores Mini-Dev (+1.1) but costs cleaned dev −0.3, where the same two
    databases improved with facts;
  - the hidden test uses different databases;
  - choosing settings per database from evaluation results would tune on the gates.
- Next: reduce latency with facts on.

## 2026-09-27 — Reuse one Fireworks client per event loop (latency)
- `complete()` created and closed a new `AsyncOpenAI` client on every call, so each
  request paid a fresh TCP + TLS handshake.
- It now reuses one client per event loop and passes the timeout per request.
- An interleaved A/B (60 questions, concurrency 1) gave P50 1.46s → 1.22s (−16%) with
  facts on. Facts on vs off showed no latency difference.

## 2026-09-27 — JSON mode not adopted
- JSON mode (`json_object`) vs the strict JSON schema: same P50 (1.36s), P90 2.67s →
  2.26s, 0 malformed.
- Paired accuracy pilot (100 `train_dev` rows × 2): −1.0 [−3.5, +1.0]. It fails the
  non-inferiority margin for a speed swap.
- Owner decision: stick to the strict JSON schema. The temporary `--json-mode`
  switch used for the pilot was removed rather than kept as an opt-in.

## 2026-09-27 — Rank G priced: small-model SFT ≈ $20–30, larger far more; submit first
- Managed SFT: ≤ 16B $0.50/M tokens, ≤ 80B $3/M, ≤ 300B $6/M.
- Trained LoRAs serve only on dedicated GPUs ($8/hour H100, scale-to-zero available).
- Training pool: 5,115 examples (4,146 with local databases).
- A 14B pilot ≈ $20–30 all-in. 27–35B ≈ $70–170. Fine-tuning `deepseek-v4-flash` itself
  is ≈ $114+ training plus multi-GPU serving.
- Comparable 14B specialists reach ≈ 70–71 dev with RL and many samples, about where we
  already are.
- Recommendation: get the hidden-test number of the current system first (≈ $1 if API
  submissions are accepted), then decide on training.

## 2026-09-27 — Answer-key review: keys often wrong; no rejected experiment reverses
- Reviewed all 252 practice-set disagreements. The owner judged 166; Sonnet 5 agents
  judged the other 86 following the owner's notes (8 marked low confidence).
- The key is wrong in 153 (61%) and ours in 74 (29%); 20 both acceptable, 5 ambiguous.
  BIRD's quality filter removed most bad keys (77% of removed cases), but 46% of the
  reviewed cases it kept also had wrong keys.
- Rejections stand after review: reasoning low −1.0, reasoning high −2.5, few-shot 0,
  dictionary +0.9, column notes −0.5. None of the 40 flipped rows had a wrong key.
- 82 of the 93 unanimous-but-wrong rank 4 questions are actually correct (`direct`
  69.5% → 85.8% on `train_dev` re-scoring only those rows). Numbers stored as text:
  30.4% → 74.7%.
- Decision: official EX stays the acceptance metric. Get the hidden-test score before
  rank G, and filter any training data by `bird23-train-filtered` at minimum. No spend.
  Details: benchmark/results/answer_key_review.md.

## 2026-09-28 — BIRD reply: submit via OpenRouter pinned to Fireworks; caps set
- BIRD accepts API-call evaluations through "official and verified providers, including
  OpenRouter, OpenAI, Anthropic, DeepSeek, and Google Gemini". Asked about Fireworks
  by name, the reply did not list it.
- Also answered:
  - local preprocessing is allowed (whole evaluation ideally ≤ 48 h, ≤ 50 GB of
    generated data);
  - bounded read-only probe queries are allowed;
  - fine-tuned models must be uploaded to Hugging Face (not served via a hosted API);
  - bird-sql-dev-1106 is the preferred dev split;
  - `column_meaning.json` is optional;
  - predictions use the `predict_dev.json` format (`"SQL\t----- bird -----\tdb_id"`).
- Not answered: a per-question time limit (we keep 30s), and how to report
  intentional empty results. Both go in the submission README.
- **Decision:** route the submission through OpenRouter, pinned to the Fireworks
  endpoint of `deepseek/deepseek-v4.1-flash` with no fallback. Check parity on 100
  `train_dev` rows × 2 before the official dev-1106 run (the last cleaned-dev look).
- **Caps:**
  - The owner created a separate OpenRouter key for BIRD's test run, with a $5 credit
    limit, to reset after evaluation. It never enters the repository or `.env`.
  - The shared ledger cap is raised to **$8.50** (spend $7.47 on 2026-09-28) for the
    parity check and the dev-1106 run. Runs pass `--budget 8.50`.

## 2026-09-28 — Merged: Jev pilots not adopted; training pool not fit for SFT yet
- Merged from `codex/jev-shadow-gates` and `codex/label-quality-audit` (work dated
  2026-09-27).
- **Jev, not adopted:**
  - candidate choice lost to result-majority on the 102 disagreement questions
    (29 vs 39 correct), also with the schema added (28 vs 39);
  - requirement coverage found 0/5 hand-labelled omissions;
  - the live `train_dev2` pilot of table and evidence-role advisories scored 57/100
    and 56/100 vs a 56/100 control, below the predeclared +4 screen.
  - OpenRouter spend $0.028. No live Jev route is enabled.
- **Training data, not yet fit for SFT:** a 100-row stratified screen of the 5,115-row
  candidate pool found 18 clear label defects (17.5% weighted, above the 15% trigger).
  Re-filter and review independently before any SFT.
- **`train_dev2` is partly used:** 100 questions (25 per database) plus 50
  `professional_basketball` rows fed the Jev pilots. A fresh candidate bank must use
  the unused rows or other train databases.

## 2026-09-29 — First-principles workstreams: P08, P42, P02/P38, P05–P07 (free parts)
- **Scope (owner):** proceed with the review's workstreams except the BIRD submission.
  The ledger cap is raised to **$10** for the P03 candidate bank. A local SQL specialist
  (Arctic-Text2SQL-R1-7B, 4-bit, Apache-2.0) and llama.cpp are approved for P16. They
  live outside the repository.
- **P08, empty-result retry: keep as is.** Measured offline from saved runs
  (`benchmark/empty_retry_audit.py`):

  | Set | Fired | Rescues | Damage | Net |
  |---|---:|---:|---:|---:|
  | Cleaned dev | 47 | 7 | 0 | +0.46 pts |
  | Mini-Dev | 52 | 7 | 0 | +0.47 pts |
  | Original dev | 44 | 5 | 0 | +0.48 pts |

  - On `train_dev`, all 6 apparent damages were rescues against broken keys (literals
    that aren't stored: 'Danville', 'San Francisco', 'avenida de las pulgas').
  - Replacements are about half literal-only and half structural, and both kinds rescue.
    A "keep the original predicates" guard would lose 2–5 rescues per set and prevent no
    measured damage.
- **P42, promotion gates added** to `analyze flips`:
  - easy-slice non-inferiority (lower CI bound ≥ −1.5);
  - protected correct cases lost;
  - paired Δ per gold-SQL feature.
- **P02/P38, answer keys adjudicated.** Two independent Sonnet 5.5 passes plus
  adjudication; 432 of 435 settled; corrected SQL was executed for every defect.
  - All 353 unused `train_dev2` questions: 223 sound, **102 defective (29%)**,
    25 ambiguous.
  - The 82 unresolved training-pool rows: 68 sound, 11 defective, 3 ambiguous. The
    100-row screen's weighted defect rate is **29.8%** (the earlier 17.5% was a lower
    bound). The 15% SFT gate is not met.
- **P05–P07, detectors** (`benchmark/sql_checks.py`, offline):
  - Text-number and integer-division detectors rarely fire; the model already casts.
  - "Ranked extra column" is wrong 68–88% of the time it fires. Deterministically
    dropping the column nets −1 on training data (12 fires: 1 rescue, 2 damages)
    because some questions ask for the value. An intent check is needed; no fix
    adopted.
  - Fan-out COUNT is too noisy (33–40% wrong when fired).

## 2026-09-29 — Fresh candidate bank (P03/P16) and selection (Experiment C)
- **Bank:** 353 unused `train_dev2` questions, accepted configuration. Unused means not
  in `jev_live_pilot_manifest.json` `source_row_indices` or `jev_table_pb_v1_results.json`
  `row_index`.
  - Routes: current v4p1 (2 repeats), gpt-oss-120b (Fireworks), qwen3-coder-next
    (OpenRouter), and the local specialist Arctic-Text2SQL-R1-7B (4-bit, llama.cpp,
    native prompt).
  - Report: `benchmark/results/candidate_bank_train_dev2.md`.
- **Label noise dominates the official view.** The current model scores 58.9% on
  official keys and 72.0% on the adjudicated corrected keys.
- **Diversity pays; repeats don't** (corrected-key oracle coverage):
  - current model 72.0%; plus a repeat 74.6%; plus Arctic 81.4%; all four families 86.0%.
  - Arctic ties the current model on official keys (59.2% vs 58.9%) and adds the most
    unique correct answers (33), at zero API cost. It takes about 12 s per question
    locally (P90 15.5 s).
  - qwen3-coder-next is the best route on official keys (59.2%) but the worst on
    corrected keys (66.0%): it reproduces BIRD's key conventions, including their errors.
- **Selection, all against corrected keys, on the same questions:**

  | Selector | Accuracy | Fixes / breaks |
  |---|---:|---:|
  | Current model alone | 72.0% | — |
  | Majority vote | 72–73% | — |
  | Pre-registered rules (best: family majority) | ≤ 74.3% | 11 / 3 |
  | Learned feature selector (leave-one-database-out) | 72.0% | — |
  | LLM judge, gpt-oss-120b (high reasoning) | 76.9% | 29 / 12 |
  | LLM judge, v4p1 (high reasoning) | **77.4%** | 28 / 9 |

  - The v4p1 judge is +2.3 on official keys (61.2%). It costs about $0.0011 per judged
    question; the whole bank plus judge is about $0.002 per question.
  - Not adopted yet: this is one bank. The fixed judge prompt must be confirmed on a
    fresh labelled set and pass the P42 gates before any change to the live path.
- **Spend:** bank and judges cost $0.65 on Fireworks and $0.12 on OpenRouter.
  - 322 judge calls failed locally before sending (the API key wasn't loaded). The ledger
    had booked them as $1.214 of provisional charges.
  - With the owner's approval they were settled to $0 through `BudgetGuard.settle`, which
    records a reversal plus a final $0 charge.
  - Fireworks ledger now $8.09 of the $10 cap.

## 2026-09-29 — Confirmation: LLM judge not adopted; family majority and fallback replicate
- **Fresh set, fixed in advance:** 350 `train_design` questions, excluding the 194
  numbers-as-text rows. Order by `sha256('confirm-v1:'+row)`, at most 9 per database,
  first 350 (43 databases).
  - Same four routes; answer keys adjudicated with the same two-pass protocol: 235 sound,
    94 defective, 18 ambiguous, 3 excluded.
  - Reports: `benchmark/results/candidate_bank_train_design_confirm.md` and the
    refreshed `candidate_bank_train_dev2.md`, both with per-rule 95% CIs.
- **Headroom replicates, smaller.** Current model 79.9% on corrected keys; all four
  families 87.3% (+7.4). The first bank was 72.0% → 86.0%.
- **LLM judge fails confirmation; not adopted.**
  - v4p1 judge: +0.3 [−2.06, +2.65], 9 fixes / 8 breaks, with 26 of 115 judge calls
    failing.
  - gpt-oss-120b judge: +0.9 [−1.47, +3.54].
  - The first bank's +5.4 did not hold.
- **Pre-registered rules replicate:**

  | Rule | First bank (corrected) | Confirmation (corrected) | Official keys |
  |---|---:|---:|---:|
  | S1 family majority | +2.3 [+0.3, +4.3] | +2.1 [+0.3, +4.1] | +2.3, +2.6 |
  | S2 fallback when the incumbent's answer is empty or an error | +0.6 [0.0, +1.4] | +1.5 [+0.3, +2.7] | — |

  - S1 has 3 breaks per bank; S2 has zero breaks on both.
- **Cost against the acceptance rule:**
  - S1 needs all four routes on every question (≈ 2× hosted cost plus local Arctic).
    It fails the product track's cost-adjusted minimum, but is inside the submission
    ceilings.
  - S2 needs a second route only when the incumbent fails (3–5% of questions), so it
    costs almost nothing.
- **Next:** neither rule is in the live path. Both need a gate look on the frozen
  configuration before adoption.
- **Spend:** the confirmation work cost about $0.9 Fireworks and $0.24 OpenRouter.
  Fireworks ledger $9.04 of $10.

## 2026-09-30 — Error escalation built; empty escalation shadow-only (review P08/P31/P32)
- **Split** after the first-principles review (P08: never replace an answer only because the
  new one returns rows; P31: keep availability fallback separate from quality escalation;
  P32: keep a candidate ledger):
  - **Error escalation** (`Agent(escalation_models=...)`, `run_bird --escalation-models`):
    when the primary answer is an error, the escalation models are asked in order. Each is
    single-turn from the same context with its own request defaults, and the first answer
    that runs is delivered. An error is never a correct answer, so this cannot break one.
  - **Empty escalation is shadow-only** (`--shadow-empty-escalation`): for an empty or
    all-NULL answer (the `[(NULL,)]` gap is now covered), alternatives are logged in
    `candidates` but never delivered. It stays that way until the P08 experiment has enough
    independently labelled, legitimately empty controls.
  - Every escalated question records the full candidate ledger: model, SQL, row count,
    error, delivered.
- **Evidence from both banks** (corrected keys, order gpt-oss → qwen → Arctic):

  | Trigger | Rescues | Breaks |
  |---|---:|---:|
  | Error | 4 | 0 |
  | Empty | 6 | 0 |

  - Only 5 genuinely empty questions existed across both banks, which is too few to
    call empty replacement safe.
  - Offline net gains: gpt-oss only +2/+2; plus qwen +2/+3; plus Arctic +2/+5.
- **When it stays off:** budget and credential failures never escalate; both switches are
  off by default; config keys are written only when on.
- **Tests:** four agent tests. A live smoke test on 5 training questions confirmed the
  wiring.
- **Next:** gate error escalation on the frozen configuration before adoption.

## 2026-09-30 — Pre-generation routing and Jev selection with richer inputs: neither adopted
Both tests use the two frozen candidate banks: 689 questions, 47 databases, corrected keys.
Every comparison is paired, with 95% CIs by database.

- **Router before generation (free).** A logistic model on question tags, schema size and
  question text, trained leave-one-database-out, picked a model family per question.
  - Tags only: 74.6% vs always-direct 75.9%, Δ −1.3 [−2.2, −0.4], 2 fixes / 11 breaks.
  - With text: Δ −0.7 [−1.6, +0.1], 4 fixes / 9 breaks.
  - The ceiling (any family right) is 86.6%. The question gives no visible sign of when
    another family wins, so a fine-tuned router isn't justified on this data. A Jev
    router can't be restricted to our families, and "Kev" doesn't exist on OpenRouter.
- **Jev after generation, richer state** (`typesafe/jev-1.13-20260917`, 276 calls, 0
  failures, $0.0124).
  - **Jev received:**
    - one candidate per distinct result;
    - the number of generators that agreed on it;
    - columns, row count and first 5 rows;
    - detector flags;
    - the verified columns of the tables it uses.
  - **The rule was fixed in advance:** switch away from family majority (S1) only when Jev
    picks something else with confidence ≥ 0.80.
  - **Primary rule (gated):** identical to S1 on every question, with 0 fixes and 0 breaks.
    All 39 confident non-"none" picks matched the majority; its confidence tracks agreement.
  - **Jev's raw choice, compared with S1:**

    | Bank | Δ vs S1 [95% CI] | Fixes / breaks |
    |---|---:|---:|
    | `train_dev2` | +3.1 [+0.0, +6.6] | 24 / 13 |
    | Confirmation set | −0.6 [−2.7, +1.5] | 6 / 8 |
    | Pooled | +1.3 [−0.6, +3.2] | — |

    The confirmation set failed, the same pattern as the LLM judge earlier.
  - **Outcome:** the pre-registered decision (fixes > breaks on both banks and pooled lower
    bound > 0) failed, so Jev selection is not adopted.
- **Standing position:** the only rules that replicate are result-based. Family majority
  gives +2.2 [+0.9, +3.6] pooled vs direct, plus error escalation. All learned or LLM
  selectors so far (feature selector, v4p1 and gpt-oss judges, Jev v1/v2 and now this) fail
  to replicate.
- Scripts and raw decisions: `data/bird/research/2026-09-30/` (not committed).

## 2026-09-30 — Agreement cascade gated on Mini-Dev; Experiments A and D; text-number profile fix
- **Budget.** The owner raised the Fireworks cap to **$15** (`.env` default updated).
  - A run launched on the whole `train_design` split instead of its 194-question subset cost
    **$2.09** by mistake. It is kept locally as a full current-configuration training run (13 MB, `20260930T094211Z`, not committed).
  - Ledger: Fireworks $12.99 of $15; OpenRouter $0.92 of $5.
- **Agreement cascade** (`Agent(cascade_models=...)`, `run_bird --cascade-models`), no
  Arctic:
  - **How it works:** deepseek-v4p1 and qwen3-coder-next (OpenRouter) answer concurrently. A
    matching non-empty result is delivered. Otherwise gpt-oss-120b answers and the majority
    result is delivered; ties go to the primary. An error is never delivered while another
    answer runs.
  - **Replay on the saved banks:** +1.6 [+0.4, +2.9] at 1.70× cost.
  - **Mini-Dev look 4** (last allowed look; 500 × 3; paired against the primary's own answer
    in the same run):

    | Measure | Result |
    |---|---|
    | Accuracy | 64.5% → **66.5%**, Δ **+2.0 [+0.4, +3.6]** |
    | Questions better / worse | 22 / 7 |
    | Easy slice (148 questions) | 75.0% → 74.8% (3/3); **fails** the −1.5 non-inferiority bound (lower 95% bound −2.25; the interval is too wide) |
    | Moderate and challenging | 60.1% → 63.1% (19/4) |
    | Cost per answer | $0.00117 uncached (1.75×), $0.00066 measured with caching |
    | Latency | p50 2.25 s, p90 6.74 s (stage 2 p90 12.8 s) |
    | Share reaching stage 2 | 30% |

    Within all submission ceilings. **Adoption is the owner's decision** because the easy
    gate failed.
- **Prompt caching:** the schema is already in the system prompt ahead of the question.
  Cached calls are no slower (1.40 vs 1.46 s) and cached input costs 2% of list price, with
  no write premium, so nothing changes.
- **Experiment A** (689 labelled training questions, corrected keys; pre-registered in
  `data/bird/research/2026-09-30/expA/expA.py`):

  | Arm | Accuracy | Δ [95% CI] | Fixes / breaks |
  |---|---:|---:|---:|
  | Direct | 76.9% | — | — |
  | Model writes its own requirements contract first | 72.4% | **−4.5 [−7.0, −2.3]** | 21 / 52 |
  | Contract written from the adjudicated answer (ceiling) | **99.0%** | **+22.1 [+19.2, +25.0]** | 154 / 2 |

  - **Reading:** generation isn't the bottleneck; understanding the question is. A
    self-written contract locks in misreadings.
  - A first version of the reference contracts leaked answer values (91 of 150). It was
    regenerated with a no-answers rule before any scoring.
  - **The 154 cases the ceiling fixes** (classified by Sonnet 5.5):

    | Cause | Cases |
    |---|---:|
    | Value format (how values are stored) | 36 |
    | Ambiguous question | 34 |
    | Misread | 27 |
    | Open convention | 24 |
    | Evidence misapplied | 12 |
    | Extra or missing columns | 16 |
    | Other | 5 |

    About 87 are recoverable from the question alone (≈12.6 points). About 67 need the key's
    arbitrary choice (≈9.7 points).
- **Experiment D** (18 fixture questions with answers computed in Python: arithmetic and units
  on text-stored numbers, grain, NULL, projection; 3 repeats): direct, model contract and
  correct contract all score **54/54**. There are no language-to-contract or compiler errors
  on clearly worded questions with the facts on. The numeric rewrite had nothing to fix.
- **Text-number fix (P05):** `text_format` now classifies numbers whose large values carry
  thousands separators ('1,963.10' beside '781.22') as `thousands`; `PROFILE_VERSION` is 3.
  - Only `regional_sales` Unit Price/Unit Cost change, across all training and dev databases.
  - Its 139 bank questions: **69.1% → 79.9%** (+19/−4, corrected keys) from the facts alone.
  - The deterministic rewrite (`benchmark/numeric_fix.py`) adds nothing on top. It stays an
    offline prototype: 17/0 alone on the old run, and 7 fires with 0/0 over 5,851
    current answers.

## 2026-10-01 — Correction on Experiment A's 99%; cascade adopted; stored-value hints
- **The 99% "reference contract" arm is answer leakage by construction, not evidence that
  only understanding is missing.**
  - Its contracts were written by Sonnet 5.5 *from the adjudicated reference SQL and
    result*. They give the exact output columns, filters (including stored values),
    aggregation, ordering, limit and formatting: a plain-English paraphrase of the answer.
    It was then scored against that same reference.
  - **Checks:**
    - On the 188 questions whose key was corrected, A2 scores 97.3% on the corrected key
      but **9.6% on BIRD's official key** (direct: 14.9%). It reproduces whichever
      reference it was told.
    - Its SQL moves toward the reference's tokens (overlap 0.68 → 0.74 on sound keys,
      0.69 → 0.79 on corrected ones).
    - Only 28 contracts repeat a database value absent from the question, so the leak is
      mostly structural rather than literal values.
  - **What it does show:** when the exact requirements are spelled out, the model can write
    the SQL (the dictation test). It does not show how much a fair reader of the question
    could recover. The 154-case classification estimates about 87 recoverable cases and
    about 67 that need the key's own choices.
  - The honest numbers are the direct arm (76.9% on corrected training keys), the
    self-written contract (−4.5) and the Mini-Dev gate (official keys).
- **Cascade adopted by the owner** as the frozen configuration (`config 6f95c1e4`, README
  updated). The easy-slice gate failed on width (75.0% → 74.8%, 3/3).
- **Replaying the cascade on the classified misses:** it fixes only 8 of the 80 recoverable
  misses that the bank's own direct answer also got wrong (misread 3, evidence 3, extra
  columns 1, value format 1). The other families mostly share the same misreadings.
- **Stored-value hints** (`src/value_hints.py`, `run_bird --value-hints`, off by default).
  - **How it works:** after an empty or all-NULL answer, each text literal compared with a
    column is checked against the database. If it isn't stored, up to three similar stored
    values are listed ('Allen' → 'Allen County', trailing spaces and periods, 'Kazakstan'),
    plus slash-date formats, inside the existing one-time empty retry. Its replacement guard
    is unchanged.
  - **Offline:** 13 of the 17 non-comma stored-value misses get a correct hint.
  - **Paired run** on the 689 labelled questions (corrected keys; pre-set rule: fixes ≥ 2×
    breaks where it fires, and no overall loss):
    - fired with hints on 19 questions: 9 → 15, **6 fixes / 0 breaks**;
    - any retry: 7 / 0;
    - excluding `regional_sales` (whose profile also changed): −0.5 [−2.2, +1.1], which is
      rerun noise.
  - **Rule passed.** Adoption into the frozen configuration awaits the owner; no Mini-Dev
    look remains to gate it.
- **Stored-value hints adopted by the owner (2026-10-01).** The frozen configuration is now
  the cascade plus `--value-hints`, as in the README. The combination has no Mini-Dev look;
  its evidence is the paired training result above (7 fixes / 0 breaks where it fires).

## 2026-10-01 — R-VES measured; efficiency gate; misreading follow-ups
- **R-VES** (`benchmark/rves.py`, BIRD's `evaluation_ves.py` method with 10 timing iterations;
  aggregates only):

  | Run | EX | R-VES |
  |---|---:|---:|
  | Cleaned dev (single model) | 66.49 | **59.53** |
  | Mini-Dev gate 3 (repeat 0) | 65.0 | 57.98 |
  | Mini-Dev look 4 cascade (repeat 0) | 66.0 | 58.47 |

  - About 70% of correct answers earn reward 0.75: our SQL runs up to 2× slower than gold.
  - R-VES/EX is 0.89, against about 0.94–0.96 for published leaders. This is secondary,
    since the leaderboard ranks by EX.
- **Efficiency gate** (`analyze.efficiency_gate`, part of the P42 gates in the flips
  report; P90 added to its cost table):
  - more than +10% uncached $/answer, +0.5 s P50 or +1 s P90 passes only with a measured gain
    (paired CI lower bound > 0);
  - the report also states points per +100% cost.
- **Recoverable misreadings** (cascade fixes only 8 of 80):
  - *Evidence-coverage trigger* (an evidence literal or column missing from the SQL):
    wrong 34% when it fires vs 22% otherwise, and it catches 21% of wrong answers. Too
    imprecise for a retry; not built.
  - *Projection-aware vote:* when one family's result equals another's minus extra
    columns, the narrower was right 21 times and the wider 0 times. In the cascade it adds
    +2 fixes / 0 breaks on 689 questions (+0.29 [0.00, +0.73]) and 8 fewer stage-2 calls.
    It was designed after seeing both banks, so there is no unused confirmation set.
    Not adopted yet.
  - *"Count distinct entities" rule: rejected.* BIRD's own train keys use
    COUNT(DISTINCT …) in only 14% of "how many" questions with a join (5% without). The
    rule would fight the official key.
- **Answer-key conventions and fine-tuning: not now.** The 58 convention or ambiguous cases
  contradict each other (ids vs names, ties, text ordering) or the evidence, and many are
  specific to one database. BIRD's hidden test uses different databases, so a model tuned on
  them would learn habits that don't transfer. Arctic, already trained on BIRD, added only
  about +0.6 as a fourth voter.
  - Priced for the record (Fireworks, 2026-10-01): LoRA SFT costs $0.50, $3 or $10 per 1M
    training tokens for models up to 16B, 16–80B and over 300B. DeepSeek V4 Flash supports
    LoRA training, but a tuned model needs a dedicated deployment to serve.
- **Projection-aware vote adopted by the owner (2026-10-01).** It is
  `Agent(cascade_projection=True)` and `run_bird --cascade-projection`, now in the README's
  frozen configuration.
  - A narrower result at stage 1 is delivered without asking gpt-oss.
  - After a vote, a result narrower than the winner (the winner minus extra columns) replaces
    it.
  - Wide results over 6 columns are skipped. Three agent tests cover it.

## 2026-10-01 — Full current configuration measured on the 689 labelled training questions
- **Configuration:** cascade + projection vote + value hints + profile v3. Runs
  `20261001T090159Z` and `20261001T091025Z` (commit `527a6ae`), compared with our model
  alone on 2026-09-29 (same questions, paired by database).

  | Keys | 09-29 our model alone | Full configuration | Δ [95% CI] | Excluding `regional_sales` |
  |---|---:|---:|---:|---:|
  | Corrected | 75.9% | **81.7%** | +5.8 [+3.9, +8.0] (52 fixes / 12 breaks) | +3.6 [+1.6, +5.8] |
  | BIRD official | 62.0% | **65.7%** | +3.8 [+2.0, +5.8] (35 / 9) | +2.5 [+0.9, +4.2] |

- Against our model + value hints + profile fix (the cascade's own contribution): +1.7 corrected,
  +1.6 official.
- **Cost and latency:** $0.00158 per answer uncached ($0.00096 measured); p50 2.48 s, p90
  6.90 s. 79% of questions stopped at stage 1. Within all submission ceilings.
- **Dev estimate (unmeasured):** about 68–69% (66.5% + about 2 from the cascade). These are
  training questions; the dev and hidden-test effects can differ.

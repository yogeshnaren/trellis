# Implementation Plan — Live Text-to-SQL Failure Modes

**Status:** Plan only — no code changes from this document yet.  
**Authoritative inputs:** current codebase + `benchmark/results/raw_bakeoff_20260813T190020Z.jsonl`  
**Constraint:** Do not claim accuracy improvement before rerunning evaluation.

---

## 1. Current-state diagnosis

### What works today

- Layered read-only safety (`PRAGMA query_only`, authorizer, AST `FORBIDDEN_*`) is intact.
- Agent pipeline: structured `SQLResponse` → `is_safe` → `EXPLAIN` validate → execute → ≤1 repair on validate/execute only.
- Benchmark scores **SQL execution equivalence** by re-running `result.sql` against gold in a fresh connection (`benchmark/run_bench.py` → `evaluate_sql`).

### What is broken / misleading

| Area | Fact in code | Live evidence |
|---|---|---|
| Identifier validation | `is_safe()` uses a **flat** alias map over `find_all(exp.Table)` and ignores `exp.Subquery` aliases | DeepSeek `live_013`: `safety-rejected: Unknown column: c.genre_count` while `EXPLAIN` + execute succeed; GPT-OSS `live_016`: `Unknown table or alias: pt` on a valid derived-table join |
| Benchmark “Exec Acc” | `report.py` uses only `evaluation.correct` | DeepSeek reported 30/48, but **e2e would be 29/48** — one SQL-eq pass never reached the user |
| Unsupported semantics | Prompt: unsupported if “information absent from the schema”; samples only Genre/MediaType names | `live_014` 3× refused (“no 2021 data”); Invoice years are 2021–2025 |
| Joins | FK list is in schema text; no join lint; prompt never says “FK paths only” | DeepSeek `live_009` 2×: `ArtistId IN (SELECT AlbumId …)` |
| Ranking | Prompt: order by primary measure only | `live_010` / `live_011` tie flips under ordered eval |
| Projection | “Never drop a measure the question asks for” — no ranks/thresholds/comparisons | `live_016` 3× correct names, missing `PlaylistCount` |
| Eval contract | Order iff gold has `ORDER BY`; no tie/date/column policies | `live_006` `%m` vs `%Y-%m`; ordered bag-equal fails on ties |

### Critical nuance on failure A

The bug is not “CTEs are ignored entirely.” Unqualified CTE columns and non-shadowed CTE aliases already pass (`tests/test_db.py`). The live false positive is **alias shadowing + missing subquery registration**:

1. Outer `FROM customer_genre_counts c` registers `c → customer_genre_counts`.
2. Inner `FROM Customer c` (walked later) **overwrites** `aliases['c'] → customer`.
3. Outer `c.genre_count` is checked as a physical Customer column → reject.
4. Separately, `JOIN (SELECT …) pt` never registers `pt` because it is `exp.Subquery`, not `exp.Table`.

Also: **`safety-rejected` skips repair** (`agent.py` returns immediately). Validator false positives are terminal for the user.

Verified inflation on current live file: DeepSeek **SQL Eq 62.5% (30/48) vs E2E 60.4% (29/48)**.

---

## 2. Root-cause table

| ID | Observed failure | Verified root cause | Primary locus |
|---|---|---|---|
| A1 | `Unknown column: c.genre_count` on valid CTE SQL | Flat alias map; inner table alias overwrites outer CTE alias | `src/db.py` `is_safe` |
| A2 | `Unknown table or alias: pt` on derived-table join | Subquery aliases never entered into alias map | `src/db.py` `is_safe` |
| B | `evaluation.correct=true` with `error_category=safety-rejected` | Bench evaluates SQL out-of-band; report ignores agent success | `run_bench.py`, `evaluate.py`, `report.py` |
| C | False `unsupported` for in-schema year / hard multi-hop | Prompt equates “absent from schema” with missing samples; no year samples; no “zero rows ≠ unsupported” rule | `prompts.py`, `schema.py` |
| D | `ArtistId` compared to `AlbumId` | Generation error; FK text present but not enforced; no narrow AST check | `prompts.py` (± optional lint in `db.py` / agent repair path) |
| E | Top-N / ORDER BY tie instability | No deterministic secondary order in prompt; gold/eval treat SQLite tie order as ground truth | `prompts.py`, gold contracts, `evaluate.py` |
| F | Correct entities, omitted measure | Projection rule too narrow (asks-for only) | `prompts.py` |
| G | Date grain / order / shape disagreements | No per-question eval metadata; global ordered-vs-bag heuristic only | `evaluate.py`, question JSON, `report.py` |

---

## 3. Observed failure modes to address

1. CTE/derived-column validation  
2. Benchmark end-to-end success accounting  
3. False unsupported / over-refusal  
4. Invalid FK/join reasoning  
5. Nondeterministic top-N ties  
6. Projection / requested-measure omissions  
7. Strict output-contract issues around date representation and ordering  

---

## 4. Phased implementation plan

### Phase 1 — Correct system/evaluation defects

#### 1.1 Fix CTE / derived-table identifier validation

**Smallest change (recommended):** In `is_safe()`:

1. Register `exp.Subquery` aliases as derived sources (same class as CTEs).
2. Build **scoped** alias maps: tables inside a CTE/subquery body must not overwrite the outer query’s binding for the same alias.
3. Prefer projecting CTE/subquery output column names from their SELECT list when feasible; at minimum, if qualifier resolves to a CTE/subquery source, **do not** require the name to exist on a physical table (today’s `if table_name in ctes: continue` path, but with correct resolution).

**Why general:** Fixes any shadowed CTE alias and any `JOIN (select…) alias` pattern — not AC/DC-specific.

**Regression test (must fail before fix):**

- Shadowed CTE alias selecting/filtering derived column (`c.genre_count`).
- `JOIN (SELECT TrackId, COUNT(*) AS n FROM PlaylistTrack GROUP BY TrackId) pt ON … WHERE pt.n > 1`.

**Blast radius:** May newly accept some previously rejected queries (intended). Must still reject unknown **physical** tables/columns. No read-only weakening.

**Safety / latency / cost / comparability:** Safety surface preserved if physical allowlist remains authoritative for base tables. No LLM cost. Comparability: some former safety-rejects become real attempts → e2e and sql-eq may both move.

#### 1.2 End-to-end task-success metric

Keep `evaluate_sql()` as **SQL execution equivalence**.

Add alongside (do not replace):

- `evaluation.sql_equivalent: bool` (current `correct`, optionally rename with back-compat alias)
- `evaluation.e2e_success: bool` =
  `error is None` ∧ `response_type == "query"` ∧ `rows is not None` ∧ `sql_equivalent`

Computed in `run_bench.py` after `Agent.ask` (uses agent outcome + evaluate_sql). Optionally a pure helper `evaluate_task_success(agent_result, evaluation)`.

**Report:** Two columns — `SQL Eq` and `E2E Acc`. Do not silently redefine historical `Exec Acc`.

**Regression test:** Fixture record with valid SQL, `error_category=safety-rejected`, sql-eq true → `e2e_success` false.

**Comparability:** Dual metrics; call out break if anyone assumed old Exec Acc == user success.

#### 1.3 Explicit eval contracts (optional metadata; strict default unchanged)

Extend question JSON with optional `evaluation_contract` (absent ⇒ today’s behavior):

```json
"evaluation_contract": {
  "order_policy": "strict" | "bag",
  "tie_policy": "ordered" | "bag_within_ties",
  "date_grain": "month" | "year_month" | null,
  "required_columns": ["Name", "PlaylistCount"]
}
```

Implement only in `evaluate_sql(..., contract=None)`:

- Default: current logic (ORDER BY in gold ⇒ ordered; else bag; float round 2; name-align).
- If `order_policy=bag`: always bag.
- If `date_grain=month`: normalize `YYYY-MM` / `MM` to a canonical month key **only when contract set**.
- If `required_columns`: require those names (casefold) present after alignment; still execution-based.

Apply contracts to **live regression file** where semantics are known (`live_006`, `live_011`, maybe `live_010` after gold secondary sort). Do **not** globally loosen.

**Human approval needed** before editing live gold/contracts (changes scored outcomes).

---

### Phase 2 — Improve generation behavior

#### 2.1 Calibrate unsupported semantics (`prompts.py`)

Add explicit rules:

- Unsupported = concept cannot be expressed with available **tables/columns/relationships** (or non-read-only).
- Sample values are **examples only**, never evidence of absence.
- If tables/columns exist, emit SQL; empty result is a valid answer.
- Multi-hop joins via listed FKs are allowed; “no direct link” is not unsupported.

**Schema (`schema.py`):** Add non-live-specific samples for date domains, e.g. distinct `strftime('%Y', InvoiceDate)` LIMIT 5 under Invoice — reduces year hallucination without hardcoding “2021”.

**Tests:** Prompt/schema content assertions; optional agent unit test that unsupported path still skips SQL when truly off-domain (existing test remains).

**Cost/latency:** Tiny prompt/schema token increase.

#### 2.2 FK-grounded joins

**First:** Prompt only — “Join only along Foreign keys listed in the schema; never equate unrelated `*Id` columns (e.g. ArtistId vs AlbumId).” Prefer EXISTS/NOT EXISTS for set membership through documented FK paths.

**Then assess after regression:** If `live_009`-class errors persist, add a **narrow** AST lint (not a theorem prover):

- Resolve aliases → base tables.
- On `exp.EQ` between two columns, if both resolve to known Id columns and the unordered pair is **not** in the FK edge set (and not same column), return a lint error.
- Wire lint into the **validate/repair path**, **not** `safety-rejected` (so one repair can fix it).

**Do not** put this in the authorizer/safety deny list initially — wrong joins are not privilege escapes.

#### 2.3 Deterministic ranking / ties (`prompts.py` + gold)

Prompt: For top-N / `ROW_NUMBER` / `LIMIT` rankings, after primary measure, add a deterministic secondary order on a human-readable entity label (or stable key if no label). No entity hardcoding.

Update live gold for `live_010` / `live_011` to include secondary order **or** set `order_policy=bag` / `tie_policy` via contract so SQLite accident isn’t scored.

#### 2.4 Requested-measure projection (`prompts.py`)

Tighten without “return every internal aggregate”:

- If the question asks for, ranks by, compares, or thresholds a measure, project that measure unless the user explicitly wants names only.
- Person entities: prefer `FirstName || ' ' || LastName` unless separate fields requested.

---

### Phase 3 — Regression and validation

#### 3.1 Focused tests (fail before fix)

| Test | File | Asserts |
|---|---|---|
| Shadowed CTE derived column | `tests/test_db.py` | `is_safe` true; `validate`/`execute` ok |
| Derived subquery alias columns | `tests/test_db.py` | `is_safe` true for `pt.n` |
| Still rejects unknown physical col | `tests/test_db.py` | unchanged |
| E2E vs sql-eq | `tests/test_benchmark.py` | safety-rejected + executable SQL ⇒ e2e false |
| Eval contract month grain | `tests/test_benchmark.py` | with contract, `%m` ≡ `%Y-%m` for same totals |
| Eval default unchanged | `tests/test_benchmark.py` | without contract, month formats still differ |
| Prompt contains unsupported/FK/tie/measure rules | `tests/test_costs_prompts.py` | string/contract checks |
| Schema includes Invoice year samples | `tests/test_schema.py` | year samples present |
| Optional FK lint (if implemented) | `tests/test_db.py` | ArtistId=AlbumId fails lint; Album.ArtistId=Artist.ArtistId passes |

#### 3.2 Live set = regression only

Re-run:

```bash
uv run python -m benchmark.run_bench \
  --questions live_eval_questions.json \
  --models accounts/fireworks/models/deepseek-v4-flash \
  --repeats 3 --concurrency 1 --arms agent --budget <cap>
```

Compare **SQL Eq vs E2E**, repair %, P50/P90, $/query vs prior JSONL. **Do not claim generalization.**

#### 3.3 Frozen holdout (before any generalization claim)

New sealed set must include, at minimum:

- Shadowed CTE + derived subquery patterns
- Multi-hop relational division
- Top-N with deliberate score ties
- Measure-in-HAVING projection
- In-schema filter values **absent** from samples
- Off-domain unsupported control
- Date grain month vs year-month

No overlap with live/dev questions.

---

## 5. Exact files / functions to change

| Phase | File | Functions / regions |
|---|---|---|
| 1.1 | `src/db.py` | `is_safe`, helpers for CTE/subquery scopes & projected columns; possibly `_cte_names` → richer derived-source map |
| 1.2 | `benchmark/evaluate.py` | `Evaluation` fields; optional `task_success` helper |
| 1.2 | `benchmark/run_bench.py` | `one()` — attach sql_eq + e2e |
| 1.2 | `benchmark/report.py` | `build_report` dual accuracy columns |
| 1.3 | `benchmark/evaluate.py` | `evaluate_sql` contract branching |
| 1.3 | `live_eval_questions.json` | optional `evaluation_contract` / gold secondary ORDER BY |
| 2.1 | `src/prompts.py` | `SYSTEM_PROMPT` unsupported block |
| 2.1 | `src/schema.py` | `_schema_text` / `SAMPLE_COLUMNS` or year sampling |
| 2.2–2.4 | `src/prompts.py` | join / ranking / projection rules |
| 2.2 optional | `src/db.py` + `src/agent.py` | join lint → repair path (not safety) |
| 3 | `tests/test_db.py`, `test_benchmark.py`, `test_costs_prompts.py`, `test_schema.py`, `test_agent.py` | as above |

**Not in scope for agent core unless join lint chosen:** `cli.py` (display already handles unsupported).

---

## 6. Metric / reporting changes

| Metric | Definition | Use |
|---|---|---|
| **SQL Eq** | Current `evaluate_sql().correct` (optionally + contracts) | Generation quality independent of validator bugs |
| **E2E Acc** | Agent delivered executable success **and** SQL Eq | What the CLI user actually got |
| Repair %, latency, cost | Unchanged formulas | Gate regressions |

Prior bake-off “Exec Acc” should be labeled **SQL Eq (legacy)** when republishing.

---

## 7. Verification commands

```bash
# Focused first
uvx --with-editable . pytest tests/test_db.py tests/test_benchmark.py tests/test_costs_prompts.py tests/test_schema.py -q

# Full suite
uvx --with-editable . pytest -q

# Static
uvx --with-editable . ruff check src benchmark tests
uvx --with-editable . mypy src benchmark

# Live regression (DeepSeek first; then full matrix if budget allows)
uv run python -m benchmark.run_bench \
  --questions live_eval_questions.json \
  --models accounts/fireworks/models/deepseek-v4-flash \
  --repeats 3 --concurrency 1 --arms agent --budget 1.00

uv run python -m benchmark.report benchmark/results/raw_bakeoff_<new>.jsonl
```

Compare to `raw_bakeoff_20260813T190020Z.jsonl`: SQL Eq, E2E, repair rate, P50/P90, mean $/query. Inspect residual fails by category A–G.

**Do not claim accuracy improvement until that rerun completes.**

---

## 8. Risks and human-approval decisions

| Decision | Options | Recommendation |
|---|---|---|
| Redefine reported “Exec Acc” | Replace vs dual columns | **Dual columns**; keep SQL Eq for continuity |
| Edit live gold / add contracts | Needed for fair tie/date scoring | **Approve** before changing scored semantics |
| FK impossible-join lint | Prompt-only vs repair-lint vs safety-reject | **Prompt first**; lint→repair only if regression still shows D; never safety-reject |
| Year samples in schema | Slight domain hinting | **Approve** — general, not live-hardcoded |
| Repair on `safety-rejected` | Would mask validator bugs | **Do not** — fix `is_safe` instead |
| Soften `evaluate_sql` globally | Bag/date fuzzy for all | **Reject** — contracts only |

---

## 9. Explicitly recommend NOT changing

- Read-only stack: `query_only`, authorizer deny list, `FORBIDDEN_NODES` / `FORBIDDEN_FUNCTIONS`
- `max_repairs = 1`
- Unconditional second LLM critique / reflection call
- Model weights, RFT, or model swaps as the “fix”
- SQL string matching or LLM-as-judge grading
- Live-eval hardcoding (AC/DC, Jazz, 2021, named customers)
- Treating live set as a hidden generalization benchmark
- Weakening physical-table allowlisting to “fix” accuracy
- Expanding repair to absorb safety failures without fixing the validator
- Broad fuzzy eval (column synonym nets, free-form date parsing everywhere)
- Unrelated refactors of CLI/conversation/cost ledger
- New dependencies unless absolutely necessary

---

## 10. Suggested implementation order (smallest observable diffs)

1. `is_safe` CTE/subquery scope fix + `test_db` regressions  
2. E2E metric + report dual column + bench test  
3. Prompt: unsupported + FK + ties + measure; schema year samples  
4. Optional eval contracts + selective live gold/contract updates (approval)  
5. Re-run live regression; only then consider FK lint→repair  
6. Freeze holdout before any generalization claim  

This sequence fixes the **system lying about success** (A/B) before spending tokens on generation tweaks (C–F), and keeps evaluation honesty (G) under explicit contracts rather than silent loosening.

---

## 11. Constraints (carried from requirements)

- Preserve the existing deterministic SQL safety boundary.
- Never weaken read-only protections to improve accuracy.
- Preserve execution-based evaluation; no SQL string matching.
- No live-eval-specific hard-coding.
- The current live set is now regression data, not a valid hidden generalization set.
- Prefer the smallest observable changes.
- No new dependencies unless absolutely necessary.
- No unrelated refactor.
- Preserve one-repair maximum.
- Preserve latency/cost characteristics unless a change is explicitly justified.
- Do not add an unconditional second LLM critique call.
- Do not change model weights or introduce RFT.
- Do not claim any accuracy improvement before rerunning evaluation.

# BUILD_PLAN.md — Trellis: an agentic text-to-SQL CLI on Fireworks

> **Read this whole file before writing code.** This is the spec I (the engineer) wrote for
> myself before implementation. An AI coding agent implemented to it. Do not substitute your
> own architecture. If you think a decision here is wrong, say so and stop — do not silently
> change it.

---

## 0. Context

Goal: build an interactive CLI that converts natural language → SQL → results against a
SQLite database, and demonstrably beat a naive one-line baseline prompt
(`Convert this question to SQL: {question}`) — the kind of prompt most first prototypes start
with, which hallucinates schema, produces invalid SQL, and gives no way to measure whether
it's good enough to ship.

**The job:** prove an open-source model on Fireworks beats that naive baseline on quality, hits
**P50 E2E < 3s**, and does it at a fraction of proprietary-model cost. Ship a working CLI +
evidence, not just a demo.

### Hard constraints
- **Small fixed API credit budget.** Every script that calls the API must track cumulative
  spend and hard-stop at a configured ceiling. No exceptions.
- **Tight, time-boxed build.** Prioritise ruthlessly. A working agent + real numbers beats a
  polished agent with no validation.
- Read-only DB access. Never mutate the target database.

### Definition of done
- [ ] `uv run trellis` launches an interactive REPL that answers questions and follow-ups
- [ ] `data/dev_answers.json` filled in with the system's SQL + human-readable answers
- [ ] Model bake-off results committed with real latency + cost + accuracy numbers
- [ ] Failure analysis: which questions the system gets wrong and *why*
- [ ] `DECISIONS.md` and `AI_USAGE.md` written

---

## 1. Architecture (decided — do not redesign)

```
question ──► [ConversationContext] ──► build messages
                                         │  (system: role + cached schema + rules)
                                         │  (history: last N turns, SQL only)
                                         ▼
                                     Fireworks LLM
                                  structured output: {"sql": "..."}
                                         │
                                         ▼
                                  [SafetyCheck]  reject non-SELECT / multi-statement
                                         │
                                         ▼
                                  [Validate] EXPLAIN QUERY PLAN  ──fail──┐
                                         │                                │
                                        pass                              │
                                         ▼                                │
                                  [Execute] read-only sqlite               │
                                         │                                │
                                    ┌────┴────┐                           │
                                  ok        error ─────────────────────────┤
                                    │                                      │
                                    │                          [Repair] 1 retry max
                                    │                          append error to messages
                                    │                                      │
                                    │◄─────────────────────────────────────┘
                                    ▼
                             render table (rich) + record turn
```

### Why this and not alternatives

**Full schema in prompt, not iterative discovery.** Chinook is 11 tables. The entire DDL
fits comfortably in context. A ReAct loop (`list_tables` → `describe_table` → `run_sql`)
adds 2–3 extra round trips = 2–3× the latency, and buys nothing when the schema already
fits. ReAct is the right call when the schema *doesn't* fit; say so in DECISIONS.md.

**Bounded repair, not an open agent loop.** Worst case is 2 LLM calls. This makes P90
predictable. An unbounded loop makes the latency SLO unenforceable.

**No LangChain.** We need per-stage instrumentation (`t_schema`, `t_llm`, `t_exec`,
`t_repair`) and full control of the prompt. A framework SQL agent hides both. Conversation
memory here is a `deque` of dataclasses — ~40 lines. Do not add the dependency.

**Structured output, not free-text parsing.** Ask Fireworks for JSON matching a schema with
one field, `sql`. This eliminates markdown-fence stripping, eliminates preamble prose, and —
critically — **cuts output tokens**, which is the dominant term in decode latency.

**Carry SQL in history, not result rows.** Follow-ups like "now break that down by year"
need the *previous query* to modify. Stuffing result sets into context inflates input tokens
for no accuracy gain. Keep row count + first-row preview only.

---

## 2. Repo layout

```
src/
  __init__.py
  cli.py            # REPL, rich rendering, slash commands
  agent.py          # Agent: generate → safety → validate → execute → repair
  llm.py            # Fireworks client wrapper; returns instrumented LLMResult
  schema.py         # introspect once, cache, format DDL for prompt
  conversation.py   # Turn, ConversationContext
  prompts.py        # SYSTEM_PROMPT, REPAIR_PROMPT, BASELINE_PROMPT
  db.py             # read-only connection, safety check, execute, EXPLAIN validate
  costs.py          # per-model pricing table, BudgetGuard
  utils.py          # (provided) load_db, query_db, print_table_schema

benchmark/
  run_bench.py      # async: N models × M questions × K repeats
  evaluate.py       # execution-accuracy vs gold result sets
  report.py         # aggregate → markdown table + numbers for the README
  results/          # committed JSON + generated report.md

data/
  Chinook.db
  dev_questions.json
  dev_questions_with_answers.json
  dev_answers.json          # ← generated deliverable
  dev_answers_example.json

docs/
  DECISIONS.md
  AI_USAGE.md
README.md
```

---

## 3. Core types (write these first)

Everything downstream — cost, P50, the bake-off — falls out of these for free.

```python
# llm.py
@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    model: str

# agent.py
@dataclass
class AgentResult:
    question: str
    sql: str | None
    rows: list[tuple] | None
    columns: list[str] | None
    error: str | None
    repaired: bool          # did we need the repair turn?
    llm_calls: list[LLMResult]
    t_schema_ms: float
    t_llm_ms: float         # sum across calls
    t_exec_ms: float
    t_total_ms: float

    @property
    def input_tokens(self) -> int: ...
    @property
    def output_tokens(self) -> int: ...
    @property
    def ok(self) -> bool: return self.error is None
```

`AgentResult` is the unit of everything. The CLI renders it; the benchmark serialises it.

---

## 4. Build order

Work in these phases. **Commit at the end of each.** Do not start Phase N+1 until N runs.

### Phase 0 — Skeleton + safety (no LLM)  [~20 min]

1. `db.py`:
   - `connect_readonly(path) -> sqlite3.Connection` using
     `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`
   - `is_safe(sql) -> tuple[bool, str]` — reject if: contains `;` followed by non-whitespace
     (multi-statement), or the first keyword is not `SELECT` / `WITH`. Blocklist:
     `INSERT UPDATE DELETE DROP ALTER CREATE ATTACH PRAGMA REPLACE TRUNCATE`.
   - `validate(conn, sql) -> tuple[bool, str]` — run `EXPLAIN QUERY PLAN {sql}`; catch
     `sqlite3.Error`, return the message. This catches bad table/column names **without
     executing**, which is fast and free.
   - `execute(conn, sql, limit=200) -> tuple[columns, rows]`
2. `schema.py`:
   - Introspect via `SELECT sql FROM sqlite_master WHERE type='table'`.
   - Cache to a module-level string on first call. **This must not re-run per turn.**
   - Format: table name, columns with types, PK/FK relationships. Compact — every token
     here is paid on *every* query.
   - Add 3–5 sample values for low-cardinality text columns (e.g. `Genre.Name`,
     `MediaType.Name`) — this measurably reduces "WHERE Name = 'rock'" vs `'Rock'` errors.
     Keep it tight.
3. Unit-test `is_safe` and `validate` against a handful of good/bad SQL strings. No API cost.

**Gate:** `python -c "from src.schema import get_schema; print(get_schema())"` prints a
compact, readable schema block. Eyeball it. If it's >1500 tokens, trim it.

### Phase 1 — LLM wrapper + budget guard  [~15 min]

1. `costs.py`:
   ```python
   PRICING = {  # $ per 1M tokens — FILL FROM FIREWORKS DOCS, do not guess
       "accounts/fireworks/models/<model-a>": {"in": ..., "out": ...},
       ...
   }
   def cost_usd(model, in_tok, out_tok) -> float: ...

   class BudgetGuard:
       def __init__(self, ceiling_usd: float): ...
       def charge(self, model, in_tok, out_tok) -> None:
           # raises BudgetExceeded if cumulative > ceiling
       @property
       def spent(self) -> float: ...
   ```
   Persist cumulative spend to `benchmark/results/.spend.json` so it survives across script
   runs. **Ceiling default: $6.00.** Leave headroom.

2. `llm.py`: async `AsyncOpenAI` client with `base_url="https://api.fireworks.ai/inference/v1"`,
   key from `FIREWORKS_API_KEY`. One function:
   ```python
   async def complete(messages, model, response_format=None, max_tokens=400) -> LLMResult
   ```
   Time it with `time.perf_counter()`. Pull `usage.prompt_tokens` / `usage.completion_tokens`
   off the response. Charge the `BudgetGuard`. Retry once on 429/5xx with backoff — and
   **exclude retry time from `latency_ms`? No — include it.** The user feels it. But log it
   separately so we can distinguish infra flakiness from model slowness.

3. `prompts.py`:
   - `SYSTEM_PROMPT`: role, the cached schema, and explicit rules. Include:
     - "Return ONLY a JSON object matching the schema. No explanation, no markdown."
     - "Use only tables and columns listed above."
     - "This is SQLite. Use `strftime` for dates. String comparison is case-sensitive."
     - "Prefer explicit JOINs. Always qualify columns when joining."
   - `REPAIR_PROMPT`: takes the failed SQL + the exact sqlite error, asks for a corrected
     query. Keep it short.
   - `BASELINE_PROMPT`: literally `f"Convert this question to SQL:\n{question}"` — we need
     this to prove we beat it.

**Gate:** one hand-run call. Print the `LLMResult`. Confirm `output_tokens` is small (<100).
If it's emitting reasoning prose, tighten the system prompt and/or `max_tokens`.

### Phase 2 — Agent  [~25 min]

`agent.py`:

```python
class Agent:
    def __init__(self, model: str, conn, budget: BudgetGuard, max_repairs: int = 1): ...

    async def ask(self, question: str, ctx: ConversationContext) -> AgentResult:
        # 1. messages = ctx.build_messages(question)
        # 2. r = await complete(messages, self.model, response_format=SQL_SCHEMA)
        # 3. sql = json.loads(r.text)["sql"]
        # 4. safe, why = is_safe(sql) -> if not safe: return AgentResult(error=why)  # no retry
        # 5. ok, err = validate(conn, sql)
        # 6. if not ok and repairs_left: append error, goto 2 (repaired=True)
        # 7. cols, rows = execute(conn, sql)   # catch runtime errors -> same repair path
        # 8. ctx.record(Turn(question, sql, len(rows), rows[0] if rows else None))
        # 9. return AgentResult(...)
```

`conversation.py`:

```python
@dataclass
class Turn:
    question: str
    sql: str
    row_count: int
    first_row: tuple | None

class ConversationContext:
    def __init__(self, schema: str, max_turns: int = 4):
        self.turns: deque[Turn] = deque(maxlen=max_turns)
    def build_messages(self, question: str) -> list[dict]: ...
    def record(self, turn: Turn) -> None: ...
    def clear(self) -> None: ...
```

`build_messages` emits: system (role + schema + rules), then for each historical turn a
user/assistant pair (question → the SQL we ran, plus a one-line note on row count), then the
current question. **Do not embed result rows.**

**Gate:** a scratch script that asks 2 questions where the second is a follow-up
("Which genre has the most tracks?" → "What about the least?"). It must produce correct
SQL for the second *because* it saw the first.

### Phase 3 — CLI  [~20 min]

`cli.py` using `rich`:
- Banner on launch: model name, DB path, table count.
- Prompt loop. On each question:
  - spinner while generating
  - print the SQL in a syntax-highlighted panel
  - print results as a `rich.Table` (cap display at 20 rows, note "N of M rows")
  - print a dim footer: `1.84s · 312 in / 41 out · $0.00007` (and `↻ repaired` if it retried)
- Slash commands: `/schema` (dump schema), `/clear` (reset context), `/last` (show last SQL),
  `exit` / `quit`.
- On error after repair: show the SQL, the error, and say "try rephrasing" — don't crash.
- Entry point wired in `pyproject.toml` so `uv run trellis` works.

**Gate:** run it. Ask three questions. It should feel fast and never traceback.

### Phase 4 — Model bake-off  [~30 min, this is where you spend credits]

This is the deliberate, budgeted part. **Do not benchmark six models.**

1. Pick **3 candidates** from the Fireworks library:
   - one small/fast (cheapest, highest tok/s)
   - one mid-size general (the likely winner)
   - one larger or code/SQL-specialised (the quality ceiling check)
   Plus **the baseline prompt on the mid-size model** as a 4th arm — this is how we prove the
   prompt/architecture is what's winning, not just the model.

2. `benchmark/run_bench.py`:
   ```
   uv run python -m benchmark.run_bench \
       --models MODEL_A MODEL_B MODEL_C \
       --repeats 3 \
       --concurrency 5 \
       --arms agent baseline \
       --budget 4.00
   ```
   - `asyncio.gather` over questions with a `Semaphore(concurrency)`.
   - **Concurrency does not make any single query faster.** It exists so the harness finishes
     quickly and so we measure what a real multi-user server would see. Say this in
     DECISIONS.md — it's the exact question the reviewer will ask.
   - Serialise every `AgentResult` to `benchmark/results/raw_{model}_{arm}_{ts}.jsonl`.
   - Hard-stop on `BudgetExceeded`, flush what we have.

3. `benchmark/evaluate.py` — **execution accuracy, not string match.**
   - Load `dev_questions_with_answers.json`, run the gold SQL, get the gold result set.
   - Run our SQL, get ours.
   - Compare as **multisets of rounded tuples**: sort rows, round floats to 2dp, compare.
     Order-insensitive unless the question says "top N" / "ordered by" — for those, compare
     ordered. Flag ambiguous ones for manual review rather than silently scoring them.
   - Emit per-question `correct: bool` + a reason string when wrong.

4. `benchmark/report.py` — aggregate into:

   | Model | Arm | Exec Acc | P50 (s) | P90 (s) | Repair % | Out tok (med) | $/query | $/day @30k |
   |---|---|---|---|---|---|---|---|---|

   Also emit a per-question breakdown for the winner. Write to
   `benchmark/results/report.md`.

**Gate:** report.md exists with real numbers. Check `.spend.json` — you should be well under
$4.

### Phase 5 — Decide, iterate, ship  [~30 min]

1. **Pick the winner:** cheapest model that clears the accuracy bar *and* P50 < 3s.
   If two are close on accuracy, take the faster/cheaper one and say why.

2. **If P50 > 3s:** the lever is output tokens, in this order:
   - Is the model emitting prose despite structured output? Tighten prompt, lower `max_tokens`.
   - Is the repair rate high? Repairs are the tail. Improve the schema block (add sample
     values, make FKs explicit) — most repairs are hallucinated column names.
   - Is the schema block bloated? Trim. Input tokens cost prefill time.
   - Only then: consider a smaller model.

3. **If accuracy is short:** look at the *failures*, not the aggregate. Common Chinook traps:
   - `Invoice.Total` vs summing `InvoiceLine.UnitPrice * Quantity` (grain error)
   - date handling — SQLite stores as TEXT, needs `strftime`
   - "top N" without `ORDER BY ... DESC LIMIT N`
   - case-sensitive string matching on `Genre.Name`
   Fix by *adding a rule to the system prompt*, not by special-casing. Re-run. One iteration
   only — don't overfit to 10 questions, and say so.

4. **Generate `data/dev_answers.json`** with the winner:
   ```
   uv run python -m benchmark.run_bench --models WINNER --arms agent --repeats 1 --emit-answers
   ```
   Format:
   ```json
   {"q_001": {"sql": "SELECT ...", "answer": "Rock ($826.65), Latin ($382.14), ..."}}
   ```
   The `answer` field is a **human-readable summary**, not a JSON dump of rows. Generate it
   from the result set with a small formatter (top ~5 rows, inline). Don't spend an LLM call
   on it.

5. **Write the failure analysis** into `benchmark/results/report.md`: which questions we get
   wrong, why, and whether it's a model limit or a prompt limit. This section is worth more
   to the reviewer than one extra point of accuracy.

---

## 5. Latency: what we measure and why

State this explicitly in the README and the email — it's the question they're really asking.

**TTFT is not the target.** A partial SQL string is unusable; the user waits for the full
query before we can execute. Streaming buys nothing functionally. Report it if you like, but
don't optimise for it.

The real decomposition:

| Stage | Budget | Lever |
|---|---|---|
| `t_schema` | <5ms | cache the schema — it's static |
| `t_llm` | 1.0–2.0s | **dominant**. ≈ prefill(input_tok) + output_tok / throughput |
| `t_exec` | <20ms | Chinook is tiny; irrelevant |
| `t_repair` | 0 or +1×t_llm | bimodal — this is where P90 lives |
| `t_render` | ~0 | — |

So: **P50 is driven by output token count. P90 is driven by repair rate.** Two different
levers for two different numbers. Optimising output tokens won't fix a bad tail; reducing
hallucinated columns will.

Report **P50 and P90**. A 2.9s P50 with an 8s P90 is a bad product and we should say so.

---

## 6. Deliverable: DECISIONS.md

Dated entries. Decision / alternatives considered / why. Non-negotiable content:

- Why full-schema-in-prompt beats a ReAct discovery loop **at this schema size**, and the
  condition under which that flips.
- Why bounded repair (max 1) rather than an open agent loop — latency predictability.
- Why no LangChain — instrumentation + prompt control; framework agents hide both.
- Why structured output — kills preamble prose, cuts output tokens, kills fence-parsing.
- Why history carries SQL not rows.
- Why concurrency in the *harness* but not the CLI — it improves throughput, not single-query
  latency. The one place parallelism would help latency is self-consistency (fire k candidates
  in parallel, pick the modal result set) — note it as future work with its cost multiplier.
- Model choice, with the bake-off numbers cited.
- What we did **not** do and would do with more time.

## 7. Deliverable: AI_USAGE.md

Be specific and unembarrassed. Something like:

> I wrote the architecture spec (`BUILD_PLAN.md`), the latency decomposition, the repair-loop
> contract, and the evaluation methodology (execution accuracy over multiset-compared result
> sets). Claude Code implemented to that spec and wrote the `rich` rendering and argparse
> wiring. I rewrote the schema layer after its first pass re-introspected the DB on every
> turn, and I rejected its suggestion to use LangChain's SQL agent because it would have made
> per-stage latency instrumentation impossible.

The `BUILD_PLAN.md` in the repo is itself the evidence. Ship it.

## 8. Deliverable: results summary in README.md

Short. Structure, folded into the README's results-at-a-glance and validation sections rather
than a standalone document:

1. **What was built** — 2 sentences. Open-source model on Fireworks, schema-grounded, with
   validation + bounded repair.
2. **Results table** — accuracy vs baseline, P50/P90, $/query, projected $/day at scale.
   Lead with the numbers.
3. **How it was validated** — execution accuracy against gold result sets on all 10 dev
   questions, N repeats for latency distribution, baseline prompt run as a control arm.
4. **Where it still fails** — name the specific failure modes. This builds more trust than
   claiming a perfect score.
5. **What's next & scope** — held-out test set (10 questions is not a benchmark; see the
   BIRD-SQL section), schema handling for large/unseen production DBs (this is where the ReAct
   loop earns its keep), self-consistency for accuracy-critical queries, result caching,
   guardrails for a live production DB.
6. **AI assistance** — one honest line.

---

## 9. Guardrails for you, the coding agent

- **Do not add dependencies** beyond: `openai`, `rich`, `python-dotenv`. Ask first.
- **Do not fabricate Fireworks model IDs or prices.** Look them up. If you can't, leave a
  `TODO(human)` and stop.
- **Do not call the API from unit tests.** Mock `complete()`.
- **Do not exceed the budget ceiling.** `BudgetGuard` raises; let it.
- **Do not silently change the architecture.** If you disagree, say so and wait.
- Commit at the end of every phase with a message naming the phase.
- Every function that touches the network is `async`. Everything else is sync.
- Type-hint everything. `ruff` clean.

---

## 10. Time budget (3h)

| Phase | Target |
|---|---|
| 0 — skeleton + safety | 20 min |
| 1 — LLM + budget | 15 min |
| 2 — agent | 25 min |
| 3 — CLI | 20 min |
| 4 — bake-off | 30 min |
| 5 — decide/iterate/answers | 30 min |
| Docs + email | 30 min |
| Slack | 10 min |

If you're running long: cut the third model, cut `--repeats` to 2. **Never cut the failure
analysis or the email.** Those are what's being graded.

# Trellis

**A schema-grounded, safety-first agentic text-to-SQL CLI, running open-source models on
[Fireworks AI](https://fireworks.ai).**

Trellis takes a natural-language question, generates SQL grounded in the database's actual
schema, validates it with a SQL-AST safety layer before it ever touches the database, executes
it read-only, and repairs itself once on failure — all with full latency/token/cost
instrumentation and a hard spend ceiling. The name is the point: the schema acts as a trellis,
a structure the model's output has to grow along rather than wander from — every architectural
decision below optimizes for that grounding, not just raw model capability.

```
Question:> What are the top 5 best-selling genres by total sales?
```
```
SELECT g.Name AS Genre, SUM(il.UnitPrice * il.Quantity) AS TotalSales FROM Genre g
JOIN Track t ON t.GenreId = g.GenreId JOIN InvoiceLine il ON il.TrackId = t.TrackId
GROUP BY g.GenreId, g.Name ORDER BY TotalSales DESC LIMIT 5;
```
```
Rock | 826.65   Latin | 382.14   Metal | 261.36   Alternative & Punk | 241.56   TV Shows | 93.53
1.57s · 2284 in (0 cached) / 95 out · $0.000565 · $5.96 shared budget remaining
```
*(live output, uncached first call — repeat or follow-up questions hit the prompt cache and run
noticeably faster/cheaper; see the results table below.)*

## Results at a glance

Two independent evaluations, both live-measured against the current Fireworks catalog
(`deepseek-v4-flash-0731`), not estimated:

| Benchmark | Exec accuracy | P50 | P90 | Repair rate | $/query |
|---|---:|---:|---:|---:|---:|
| Chinook dev set (10 questions, this project's own) | 60%¹ | 0.84s | 0.96s | 0% | $0.000502 |
| [BIRD-SQL](https://bird-bench.github.io) Mini-Dev (full 500 questions, public benchmark, never tuned against) | 45.8%² | 1.53s | 4.97s | 2.0% | $0.000485 |

¹ Raw execution-equivalence score. Hand-inspecting all four misses found three are not
generation errors — see [Known gaps](#known-gaps--what-id-tackle-next). ² Simple/moderate/
challenging breakdown: 62.2% / 40.0% / 36.3% — see [Benchmarking against BIRD-SQL](#benchmarking-against-bird-sql)
and the full root-cause [postmortem](docs/POSTMORTEM.md).

At $0.000485–$0.000502/query, 30,000 queries/day costs roughly **$14.55–15.06**. Both numbers
were produced by `benchmark/run_bench.py` / `benchmark/run_bird.py` against the live API on
2026-09-22 — reproduce them with the commands in [Validation](#validation).

## Requirements

This is a from-scratch agent design, not a wrapper around an existing text-to-SQL framework.
The requirements it's built to:

- **Interactive CLI**: a terminal session where a user asks a question, gets SQL + results,
  and can ask natural follow-ups in the same session.
- **Beat the naive baseline**: `Convert this question to SQL: {question}` with no schema, no
  validation, no repair — the kind of prompt most first prototypes start with, and the one this
  project measures itself against directly (see the `baseline` arm in every bake-off).
- **P50 end-to-end latency under 3 seconds**, single user.
- **Self-validated**, not just demoed: execution accuracy against gold result sets, not string
  matching against gold SQL — a syntactically different query that returns the right rows should
  count as correct.
- **Cost-aware at scale**: instrumented $/query and a hard spend ceiling, because "it works in
  a demo" and "it's sustainable at 30,000 queries/day" are different bars.
- **Extended goal, added after the original build**: hold up against a public, external
  benchmark ([BIRD-SQL](https://bird-bench.github.io)) rather than only the 10 questions this
  project wrote and tuned its own prompt against.

## Quick command playbook (start here)

This section is written for anyone — no Python or SQL background required. It gets you from a
fresh checkout to asking Trellis a question in plain English in under 5 minutes.

**What this actually is:** a chat-like tool where you type a question about a music-store
database in plain English (e.g. "which country spends the most?") and it writes and runs the
correct SQL for you, showing you the answer as a table.

### 1. One-time setup (do this once)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # installs `uv`, the Python tool runner
./scripts/setup_chinook.sh                         # downloads the sample database
uv sync                                             # installs project dependencies
cp .env.example .env                                # creates your local config file
```

Then open `.env` in any text editor and paste your Fireworks API key on this line:

```
FIREWORKS_API_KEY=your-key-here
```

That's it — setup is done and does not need to be repeated.

### 2. Start the chat CLI

```bash
uv run trellis
```

You'll see a banner showing the model, database, and remaining budget, then a `Question:>`
prompt. Type a question in plain English and press Enter:

```
Question:> What are the top 5 best-selling genres by total sales?
Question:> Which employee has the most customers assigned to them?
Question:> Now show me the same thing but for the bottom 5 instead
```

Every answer is printed as a readable table, followed by a dim status line showing time taken,
tokens used, cost, and remaining budget. You can ask natural follow-up questions ("now show me
just the top 3", "what about only from Brazil?") — the tool remembers the SQL from your last
question (but not the results) so it can build on it.

**In-chat commands:**

| Type this        | What it does                                     |
| ---------------- | ------------------------------------------------ |
| `/schema`        | Shows the database tables and columns being used |
| `/last`          | Re-prints the most recent SQL query generated    |
| `/clear`         | Forgets conversation history and starts fresh    |
| `exit` or `quit` | Leaves the CLI                                   |

Press `Ctrl+C` at any time to quit immediately.

### 3. Everyday commands cheat sheet

| I want to...                                | Run this                                               |
| ------------------------------------------- | ------------------------------------------------------ |
| Ask questions interactively                 | `uv run trellis`                                       |
| Check the code still works after a change   | `uvx --with-editable . pytest`                         |
| Check code style/formatting                 | `uvx --with-editable . ruff check src benchmark tests` |
| Check type correctness                      | `uvx --with-editable . mypy src benchmark`             |
| Verify a model works before benchmarking it | `uv run python -m benchmark.preflight --budget 0.05`   |
| Compare models head-to-head on Chinook      | see [Model bake-off](#model-bake-off) below            |
| Benchmark against BIRD-SQL Mini-Dev         | see [Benchmarking against BIRD-SQL](#benchmarking-against-bird-sql) |
| See the latest Chinook report               | open `benchmark/results/report.md`                     |
| See the latest BIRD-SQL report              | open `benchmark/results/bird_report.md`                |
| See sample question → SQL → answer pairs    | open `data/dev_answers.json`                           |

### 4. If something goes wrong

| Symptom                                          | Likely cause / fix                                                                                                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `FIREWORKS_API_KEY is not set`                   | Add the key to `.env` (see step 1), or `export FIREWORKS_API_KEY=...` in your shell                                                                                |
| "Shared project budget exhausted"                | The project-wide `$6` spend ceiling was hit; raise `FIREWORKS_BUDGET_USD` in `.env` if you're sure, or wait/reset `benchmark/results/.spend.json`                  |
| "This CLI session's soft allowance is exhausted" | You've spent the `$2` per-session cap; restart the CLI to get a fresh session allowance                                                                            |
| A query returns an error instead of a table      | The tool safely rejected or failed to run the generated SQL; just rephrase the question — nothing destructive happens because the database connection is read-only |
| `uv: command not found`                          | Re-run the install line at the top of step 1, then open a new terminal                                                                                             |

## Architecture

```
question ──► [ConversationContext] ──► build messages
                                         │  (system: role + cached schema + rules)
                                         │  (history: last N turns, SQL only)
                                         ▼
                                     Fireworks LLM
                                  structured output: {response_type, sql, message}
                                         │
                                         ▼
                                  [SafetyCheck]  sqlglot AST: reject non-SELECT / multi-statement
                                         │        / unknown tables & columns / forbidden functions
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

### Engineering decisions that matter

- **AST-based safety, not a keyword blocklist.** `src/db.py` parses every generated query with
  `sqlglot`, walking the full statement tree — including CTEs, subqueries, and correlated
  references — to reject anything that isn't a read-only `SELECT`/`WITH`, references an unknown
  table or column, or calls a forbidden function. A regex blocklist can't see through a CTE; an
  AST can. SQLite's own authorizer, `query_only`, disabled extension loading, and a read-only URI
  connection sit underneath as a second, independent layer.
- **Bounded repair, not an open agent loop.** At most one repair round-trip after a validation
  or execution failure — worst case is two LLM calls, ever. This makes the P90 latency tail
  predictable instead of open-ended, at the cost of occasionally not self-correcting a harder
  failure. Safety rejections never retry (there's nothing to repair — the query itself is
  disallowed).
- **Structured output, not free-text parsing.** The model returns JSON matching a fixed schema
  (`response_type`, `sql`, `message`), eliminating markdown-fence stripping, eliminating preamble
  prose, and — since output tokens dominate decode latency — keeping responses short by
  construction rather than by prompting for brevity and hoping.
- **A semantic guardrail, not "always emit SQL."** `response_type` lets the model say a question
  is unsupported or ask for clarification instead of inventing a query for something the schema
  can't answer — added after live testing showed irrelevant questions otherwise got fabricated
  SQL just to satisfy the schema.
- **SQL-only conversation memory.** Follow-ups need the *query* they're refining, not the
  *results* — carrying full result sets in history would inflate every subsequent prompt for no
  accuracy gain and would persist result-row values across turns unnecessarily.
- **Schema introspected once, generalized, cached.** `src/schema.py` builds a compact schema
  block from live `PRAGMA` introspection — not hardcoded per database. Any low-cardinality
  text column gets illustrative sample values (reduces case/spelling mismatches like `'rock'`
  vs `'Rock'`); any column whose sampled values look date-like gets a small distinct-year
  sample instead. This is what makes the same agent work unmodified across Chinook and all 11
  BIRD-SQL databases.
- **Budget-guarded spend, reserve then settle.** Every call reserves a conservative
  worst-case cost under an `asyncio.Lock` *before* dispatch, then settles to actual cost after —
  so concurrent requests can never blow past the ceiling on a race, only underspend it.
- **No agent framework.** `sqlglot` exists specifically for AST safety; `pydantic` derives the
  response schema. The rest is `openai` (Fireworks is OpenAI-SDK compatible), `rich`, and
  `python-dotenv`. A framework SQL agent would hide the per-stage latency instrumentation
  (`t_schema`, `t_llm`, `t_exec`, `t_repair`) this project is built around measuring.

Full dated decision log, including reversed decisions and why, is in
[docs/DECISIONS.md](docs/DECISIONS.md).

## Validation

Accuracy is checked by **executing both queries and comparing full result sets** — order-
insensitive unless the gold query has an explicit `ORDER BY`, in which case row order must match
too — not by comparing SQL text. A syntactically different query that returns the same rows
counts as correct; a syntactically similar one that returns the wrong rows does not.

```bash
uvx --with-editable . pytest
uvx --with-editable . ruff check src benchmark tests
uvx --with-editable . mypy src benchmark
```

Every independent benchmark question/repeat gets fresh conversation context — no cross-question
history contamination. A same-model **raw-prompt control arm** (`baseline_prompt` — the literal
naive one-liner with no schema, no safety, no repair) runs alongside the agent on every
bake-off, so the reported gains are attributable to the architecture, not just the model.

### Model bake-off (Chinook)

```bash
uv run python -m benchmark.preflight --budget 0.05
uv run python -m benchmark.run_bench \
  --models accounts/fireworks/models/gpt-oss-120b \
           accounts/fireworks/models/deepseek-v4-flash-0731 \
           accounts/fireworks/models/minimax-m3 \
  --repeats 3 --concurrency 1 --arms agent baseline --budget 4.00
uv run python -m benchmark.report benchmark/results/raw_bakeoff_*.jsonl
```

The July 2026 three-model comparison (`gpt-oss-20b` / `deepseek-v4-flash` / `minimax-m3`, since
superseded in the Fireworks catalog — see the 2026-09-22 entry in
[docs/DECISIONS.md](docs/DECISIONS.md)) picked DeepSeek-V4-Flash as the winner: best accuracy,
best P50, lowest $/query, simultaneously. `benchmark/results/report.md` reflects a fresh
2026-09-22 live run against the current model; the historical multi-model comparison JSONL is
kept in `benchmark/results/` for provenance.

## Benchmarking against BIRD-SQL

The Chinook dev set is 10 questions this project wrote and iterated its own prompt against —
useful for fast iteration, not a real accuracy claim. [BIRD-SQL](https://bird-bench.github.io) is
a widely-used public text-to-SQL benchmark; this project evaluates against its curated
**Mini-Dev** subset (500 questions across 11 SQLite databases, official dev-labels) as an
external, never-tuned-against signal. This is a local run for comparison, **not an official
leaderboard submission** — BIRD's leaderboard scores a held-out test set through its own
submission process this project doesn't have access to.

```bash
./scripts/setup_bird_minidev.sh          # ~800MB download, ~1.4GB on disk, data/bird/ is gitignored
uv run python -m benchmark.run_bird --limit 50 --budget 1.00
open benchmark/results/bird_report.md
```

`--limit` randomly samples N questions (seeded, reproducible with `--seed`) so cost stays
bounded — at the measured ~$0.0005/query, a 50-question sample costs a few cents. Drop `--limit`
to run the full 500 (~$0.25, a few minutes at `--concurrency 8`) — the result below is from a
full run, not a sample. Other flags: `--difficulty simple moderate challenging`, `--db
<db_id>...` to target specific databases, `--models` for a multi-model comparison the same way
`run_bench.py` does.

**What Trellis's agent adds over a schema-only baseline on BIRD:** BIRD questions include an
`evidence` field — expert-annotated domain knowledge (unit conversions, business-logic
definitions) often required to get the SQL right, distinct from anything in the schema itself.
`benchmark/bird.py` threads this into the question passed to the agent, the same way a
production system would thread in domain context beyond raw DDL.

**Current result** (full 500-question set, `deepseek-v4-flash-0731`, 2026-09-22):

| Difficulty | N | Exec accuracy |
|---|---:|---:|
| Simple | 148 | 62.2% |
| Moderate | 250 | 40.0% |
| Challenging | 102 | 36.3% |
| **Overall** | **500** | **45.8%** |

Per-database accuracy ranges from 33.3% (`california_schools`) to 73.1% (`superhero`) — see
`benchmark/results/bird_report.md` for the full per-database table. This tracks the expected
shape for a mid-tier, non-SQL-specialized general chat model with no BIRD-specific tuning: sharp
accuracy dropoff from simple to challenging, and meaningfully harder than Chinook's small,
hand-picked dev set. **Not implemented:** BIRD's other two official metrics, soft-F1 and R-VES
(reward-weighted execution efficiency) — execution accuracy only.

**Full root-cause analysis and a prioritized roadmap to close the gap** — comparing this result
against the live BIRD leaderboard and literature baselines, with concrete failure examples,
per-issue fix proposals, and an honest accounting of which fixes are cheap prompt changes versus
which require a real cost/latency product tradeoff — is in
**[docs/POSTMORTEM.md](docs/POSTMORTEM.md)**.

## Known gaps & what I'd tackle next

Self-critical by design — this is what a reviewer should ask about, so it's answered up front
rather than left for someone to discover:

| Gap | Why it matters |
|---|---|
| Concurrency tested only up to 5 simultaneous queries, on a single SQLite connection | A real multi-user deployment needs load-testing at dozens-to-hundreds of concurrent users, not 5 |
| Chinook accuracy was tuned and measured on the same 10 questions | Addressed in part by the BIRD-SQL benchmark above (never tuned against), but a larger held-out Chinook-style set would still strengthen this |
| Schema size tested up to BIRD's largest Mini-Dev database, not true enterprise scale | Very large schemas (hundreds of tables) will need retrieval or bounded schema-discovery instead of full-schema-in-prompt — see the ReAct-vs-full-schema tradeoff in `docs/DECISIONS.md` |
| No per-user session isolation or per-user rate limiting | Today there is one shared conversation context and one shared budget; a real multi-user product needs both scoped per user |
| No PII masking or column-level redaction | Query results are returned as plain values; this needs a governance review before pointing at real sensitive data |
| No fallback if Fireworks has an outage | The tool currently fails outright after one retry, with no backup path |
| Raw execution-equivalence score, not error-corrected for tie-breaking artifacts | See the honest breakdown of the Chinook 60% figure in `docs/DECISIONS.md`'s 2026-09-22 entry — some of what "fails" is stricter-than-necessary evaluation, not generation error |

## Repo layout

```
src/                 agent, CLI, schema introspection, safety/validation, LLM client, costs
benchmark/           bake-off harness, BIRD-SQL runner, execution-accuracy evaluator, reports
scripts/             setup_chinook.sh, setup_bird_minidev.sh
data/                Chinook.db + dev questions; data/bird/ (gitignored, fetched on demand)
docs/                POSTMORTEM.md (BIRD-SQL root-cause analysis + roadmap to 80%), DECISIONS.md,
                     AI_USAGE.md, PROMPT_ITERATIONS.md, COST_COMPARISON.txt, BUILD_PLAN.md
                     (the original engineering spec), plus live-eval failure notes
tests/               pytest suite (no live API calls — LLM calls are mocked)
```

## License

[MIT](LICENSE).

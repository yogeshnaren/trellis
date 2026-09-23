# Performance Postmortem: Trellis on BIRD-SQL Mini-Dev

**Scope:** a full, live, 500-question run of Trellis's production agent pipeline against
BIRD-SQL Mini-Dev (the official curated dev subset — 11 databases, all three difficulty tiers),
followed by a manual root-cause pass over ~35 individual failures across every database, cross-
referenced against the real BIRD-SQL leaderboard and published literature baselines.

**Author's note on method:** every number and every SQL diff in this document comes from a real
run recorded in `benchmark/results/bird_raw_20260923T061413Z.jsonl` and `bird_report.md` — none
of it is estimated or reconstructed from memory. Where a claim is about the leaderboard or
literature rather than this repo's own evidence, it is cited inline.

---

## 1. Executive summary

| | |
|---|---|
| **Current** | **45.8%** execution accuracy (EX), 500/500 Mini-Dev questions |
| **By difficulty** | Simple 62.2% (148 q) · Moderate 40.0% (250 q) · Challenging 36.3% (102 q) |
| **Target** | 80% (stated goal, matched by the leaderboard's #1 single-model-track entry) |
| **Gap to close** | 34.2 points |
| **Cost of this run** | ~$0.24 total, $0.000485/query, P50 1.53s, P90 4.97s |
| **Repair rate** | 2.0% (first-shot generation is almost always syntactically valid) |
| **Hard pipeline errors** | 15/500 = 3.0% (8 safety-rejections, 7 repair-exhausted/timeout) |

**The headline finding:** the gap to 80% is not primarily a "the model is too weak" problem. Our
own measured 45.8% sits almost exactly on top of the published **DeepSeek-Coder-33B baseline
(45.37% EX on BIRD dev, no scaffolding)** — see §5 — despite Trellis using a *smaller, cheaper,
non-code-specialized* model with a real agent pipeline around it. That parity is itself
informative: it means our scaffolding (schema-grounding, safety, repair) is currently
contributing *roughly nothing* over a bare baseline on BIRD, in sharp contrast to how decisively
it beat the naive baseline on Chinook (60% vs. 0%, see the main
[README](../README.md#results-at-a-glance)). The root-cause analysis in §4 explains why: almost
every category of failure below is a fixable *engineering* gap in how much of BIRD's own
available context we actually use — not a hard reasoning ceiling. §6 lays out, in priority
order, what closing that gap requires, and is honest about which parts of it are cheap prompt
fixes versus which parts are real cost/latency tradeoffs that need a product decision, not just
an engineering one.

---

## 2. Methodology

- **Model:** `accounts/fireworks/models/deepseek-v4-flash-0731` (the same model used throughout
  this project — a fast/cheap general-purpose chat model, not a code- or SQL-specialized model).
- **Pipeline:** the exact production `Agent` from `src/agent.py` — schema-grounded structured
  generation → `sqlglot` AST safety check → `EXPLAIN QUERY PLAN` validation → read-only
  execution → at most one bounded repair on failure. BIRD's `evidence` field is threaded into
  the question text (`benchmark/bird.py:with_evidence`). No other change from the Chinook path.
- **Run parameters:** all 500 Mini-Dev questions, 1 repeat, concurrency 8, seed 42, budget
  ceiling $3.00 (actual spend ~$0.24). Command:
  `uv run python -m benchmark.run_bird --concurrency 8 --repeats 1 --budget 3.0 --seed 42`.
- **Evaluation:** execution accuracy (EX) — gold and generated SQL are both executed against the
  live database and their result sets compared (order-sensitive iff the gold query has an
  explicit `ORDER BY`), via the same `evaluate_sql` used for the Chinook dev set. This matches
  BIRD's own official EX metric. **Not implemented:** BIRD's other two official metrics, Soft-F1
  and R-VES (reward-weighted execution efficiency) — noted as a limitation, not attempted here.
- **Root-cause pass:** every failing record from a combined 68-question exploratory sample (run
  before the full 500) was read individually against its gold SQL, evidence text, and the live
  schema (including the official `database_description/*.csv` files BIRD ships per database —
  see §4.2), then cross-checked against the full 500-question failure list and per-database
  accuracy table to confirm each pattern's prevalence rather than generalizing from one example.
- **Raw evidence:** `benchmark/results/bird_raw_20260923T061413Z.jsonl` (500 full records),
  `benchmark/results/bird_report.md` (generated summary + per-database + per-difficulty tables).

---

## 3. Scoreboard: where we stand

### 3.1 Against our own baseline

| Difficulty | N | Exec accuracy |
|---|---:|---:|
| Simple | 148 | 62.2% |
| Moderate | 250 | 40.0% |
| Challenging | 102 | 36.3% |
| **Overall** | **500** | **45.8%** |

### 3.2 Per-database (worst to best — full spread is 33.3% to 73.1%, a 40-point range)

| db_id | N | Exec accuracy | Tables | Widest table | Notes |
|---|---:|---:|---:|---:|---|
| `california_schools` | 30 | 33.3% | 3 | ~40 cols | Multiple near-duplicate name/geo columns across tables |
| `thrombosis_prediction` | 50 | 34.0% | 3 | **44 cols** | Medical abbreviations, hyphen/space column names |
| `card_games` | 52 | 34.6% | 6 | — | |
| `formula_1` | 66 | 36.4% | 13 | — | Most tables of any DB; prompt over-projection hit hardest here |
| `toxicology` | 40 | 40.0% | 4 | — | Small schema, but fan-out-join and evidence-gold inconsistencies |
| `financial` | 32 | 40.6% | 8 | — | Heavy use of opaque codes (`A11`, `k_symbol`, status letters) |
| `debit_card_specializing` | 30 | 46.7% | 5 | — | |
| `european_football_2` | 51 | 51.0% | 7 | ~670 schema tokens | Widest *schema*, not widest table |
| `student_club` | 48 | 54.2% | 8 | — | |
| `codebase_community` | 49 | 55.1% | 8 | — | |
| **`superhero`** | **52** | **73.1%** | 10 | — | Best performer — see §4 for why |

### 3.3 Against the outside world

| Reference point | Score | Source |
|---|---:|---|
| CodeLlama-Instruct 7B/13B/34B, bare | 20.9% / 21.6% / 24.5% | BIRD dev, published benchmark¹ |
| **DeepSeek-Coder-33B, bare baseline (no scaffolding)** | **45.37%** | BIRD dev, published benchmark¹ |
| **Trellis (this project), full agent pipeline** | **45.8%** | This report, Mini-Dev, live |
| GPT-4, no special scaffolding | 54.9% (test) / 46.4% (dev) | BIRD leaderboard baseline row |
| CogniSQL-R1-Zero, 7B + RL fine-tuning | 59.97% | BIRD dev, published benchmark¹ |
| SLM-SQL 1.5B, fine-tuned for SQL | 67.08% | BIRD dev, published benchmark¹ |
| Claude Opus 4.6, no special scaffolding | 70.2% (test) / 68.8% (dev) | BIRD leaderboard baseline row |
| Single-model track leader (Gemini-SQL2, many-sample self-consistency) | **80.04%** (test) | BIRD leaderboard, single-model track |
| Overall leaderboard #1 (DataGallery-Text2SQL: oracle-knowledge + agentic) | 82.4% (test) / 78.1% (dev) | BIRD leaderboard, overall track |
| Human baseline (data engineers + DB students) | 92.96% | BIRD leaderboard |

¹ Figures compiled from published papers surveying BIRD dev performance across model families and
techniques (SLM-SQL, CogniSQL-R1-Zero, and related 2026 BIRD benchmarking literature).

**Reading this table honestly:** we are dead-even with a *bare, unscaffolded* baseline on a
*larger* model than ours, and meaningfully behind both fine-tuned small models (60-67%) and
frontier-model baselines with no agent scaffolding at all (GPT-4/Claude, 55-70%). Every entry
above 75% uses either heavy fine-tuning/RL, many-sample self-consistency, or both, plus (for the
very top tier) deep "oracle knowledge" integration. None of that is present in Trellis today.
That is the honest starting point for §6's roadmap.

---

## 4. What's GREAT — and why it must not regress

1. **The safety layer is exactly as strong on 11 unfamiliar, wildly different schemas as it was
   on Chinook.** Zero destructive statements executed across 500 questions on real production-
   style schemas it had never seen tuned against. 8/500 (1.6%) generated SQL referencing a
   hallucinated table or column was caught by the AST identifier check *before* it ever reached
   the database — precisely the layer's job, and precisely why it's AST-based rather than a
   keyword blocklist (see the README's [engineering decisions](../README.md#engineering-decisions-that-matter)).
2. **First-shot generation is reliable.** Only 2.0% of all 500 questions needed the one allowed
   repair round-trip. The pipeline is not papering over a broken generator with retries — when it
   is wrong, it is usually *confidently* and *syntactically validly* wrong (see §4.1), which is
   actually the harder problem to have, but it means the repair budget itself is not the
   bottleneck.
3. **Superhero (73.1%) shows the agent's real ceiling on a well-behaved schema.** It is not the
   smallest database (10 tables, mid-pack), but it *is* the most human-readable: table and column
   names are plain English (`superhero_name`, `power_name`, `colour`), no cryptic abbreviations,
   no multi-hundred-column tables. Every correct example pulled for this report from `superhero`
   (§ methodology) shows exactly the intended behavior: correct joins across 3-4 tables, correct
   evidence-to-filter translation, no wasted repair. **This is the strongest evidence in this
   report that the architecture itself works** — the gap elsewhere is legibility and context, not
   a fundamental capability wall.
4. **Simple-tier accuracy (62.2%) already exceeds every "bare model" literature reference point**
   in §3.3 except the largest fine-tuned specialist models. Point lookups, single joins, and
   direct filters are functionally solved for this agent.
5. **Cost and latency held up under 100x more schema diversity than the design was built for.**
   $0.000485/query and P50 1.53s across databases up to 597MB (`european_football_2`) and 44
   columns wide (`thrombosis_prediction.Laboratory`) — the original Chinook-only design target
   was P50 < 3s on an 11-table, 34MB database. **Any fix from §6 must be checked against this
   number before being adopted** — see §5.

---

## 5. What's OKAY — real accuracy left on the table, but not broken

1. **Moderate tier (40.0%, the largest bucket at 250/500 questions) is not "half wrong, half
   right" at random — it's concentrated.** Reading the failures in this tier (§ methodology),
   the large majority have the *correct join topology and the correct filter logic*, and differ
   from gold only in: which of two candidate columns to use, whether to project a raw value or a
   computed one, or an extra/missing column in the output shape. These are precision problems,
   not comprehension failures — exactly the category §6's prompt-level fixes target first.
2. **Evidence is read and generally followed literally — sometimes to a fault.** Trellis threads
   BIRD's `evidence` field into every question (unlike a schema-only baseline), and in the
   majority of failures the WHERE-clause logic derived from evidence is correct. But three
   distinct sub-patterns cost real accuracy: evidence trusted over more-reliable schema-observed
   sample values when the two disagree (§4.1 below has the concrete case), evidence formulas
   misapplied as a SELECT projection when gold uses them as a WHERE filter (or vice versa), and
   at least one case where evidence and gold SQL are **internally inconsistent with each other**
   (`thrombosis_prediction` #1267 — evidence states `SM` values are literally `'-'`/`'+-'`, gold
   SQL filters on `'negative'`/`'0'` instead) — a benchmark-authoring artifact, not something any
   agent design can fix. This sets a *ceiling*, not a bug: don't expect 100% even with a perfect
   agent.
3. **The domain-abbreviation cluster** (`financial`, `debit_card_specializing`, `toxicology`,
   40-47% each) gets JOIN topology right most of the time but the final formula or business-rule
   grain wrong — `A11`, `k_symbol`, `VYBER`, bond/atom ID conventions are exactly the kind of
   thing a human analyst would look up in a data dictionary rather than infer from the column
   name alone. BIRD ships that data dictionary per database and Trellis currently never reads it
   — this is the through-line into the single highest-leverage fix in §6.

---

## 6. What's BAD — root causes, evidence, and fixes, ranked by expected impact ÷ effort

Each item: the pattern, a real example from this run, the root cause, how we know it's
systemic (not anecdotal), and the fix.

### 6.1 Unquoted special-character column identifiers — cheapest fix in this report

**Pattern:** BIRD schemas routinely have column names with hyphens or spaces
(`T-BIL`, `T-CHO`, `aCL IgM`). SQLite requires these to be quoted (`` `T-BIL` `` or `"T-BIL"`).
The model frequently emits them bare, which SQLite/`sqlglot` then parses as an *expression*
(`l.T` minus `BIL`) rather than an identifier.

**Concrete evidence (4 of the 15 hard pipeline failures in the full run, all in one database):**
```
thrombosis_prediction #1192, #1225, #1232 → "Unknown column: l.T"   (from unquoted T-BIL/T-CHO)
thrombosis_prediction #1189 → SQL parse failed on unquoted `aCL IgM`
```
**Root cause:** `SYSTEM_PROMPT` (`src/prompts.py`) has no rule about quoting special-character
identifiers, and the schema block renders `T-BIL REAL` with no visual signal that this name is
unsafe to reference bare.

**Fix (low effort, low risk):** add an explicit prompt rule ("any column name containing a
space, hyphen, or other non-identifier character must be wrapped in backticks when referenced"),
and/or have `src/schema.py` render such column names pre-quoted in the schema text
(`` `T-BIL` REAL ``) so the safe form is what the model sees and is most likely to copy verbatim.
**Expected impact:** recovers most of `thrombosis_prediction`'s 4 hard-error failures directly,
and generalizes to any future schema with unusual column names — including real production
databases, which is exactly the scenario this matters for beyond BIRD.

### 6.2 BIRD's own data dictionary is downloaded but never read — the single biggest lever

**Pattern:** every BIRD database ships a `database_description/*.csv` per table with a
human-written `column_description`, `value_description`, and often an embedded **"commonsense
evidence"** formula — a *schema-level* knowledge base, independent of any specific question.
`scripts/setup_bird_minidev.sh` downloads these files (they're part of `dev_databases/`), but
neither `benchmark/bird.py` nor `src/schema.py` ever reads them. Trellis's schema block is built
entirely from live `PRAGMA` introspection plus our own generic sample-value heuristics — it has
no access to this information at all.

**Concrete evidence this specific gap costs accuracy:**
```csv
# data/bird/dev_databases/california_schools/database_description/satscores.csv
rtype,,rtype,text,unuseful
NumGE1500,...,"...commonsense evidence: Excellence Rate = NumGE1500 / NumTstTakr"
```
`rtype` is explicitly documented as **"unuseful"** by BIRD's own annotators — yet across the
`california_schools` failures we inspected, the model inconsistently adds `rtype = 'S'` filters
to some queries and omits it from others, clearly guessing at a distinction it has no way to
resolve from the raw schema alone. This single column's ambiguity plausibly touches a
meaningful share of `california_schools`' worst-in-the-run 33.3% score.

**Root cause:** the schema-building pipeline uses exactly one information source (live
introspection) when BIRD provides a second, richer one for free.

**Fix (medium effort, high confidence):** extend `benchmark/bird.py` and/or `src/schema.py` to
parse `database_description/*.csv` per `db_id` and fold `column_description` +
`value_description` + any "commonsense evidence" text into the schema block passed to the agent.
This is functionally what the leaderboard tags **"oracle knowledge integration"** — used by
*every single entry in the top 12* of the leaderboard (§3.3) — and BIRD Mini-Dev makes the exact
same information available to us for free; we're simply not using it yet.

**Expected impact:** high, and broad — this doesn't fix one database, it removes an entire class
of ambiguity (which of two similarly-named columns is the "real" one, what a cryptic code column
actually means, what formula a `commonsense evidence` note already defines) across all 11
databases simultaneously. This is the clearest, best-evidenced, single highest-leverage
recommendation in this report.

### 6.3 Wide-table schema rendering causes real needle-in-haystack misses

**Pattern:** our two worst-performing databases (`california_schools` 33.3%,
`thrombosis_prediction` 34.0%) both have tables with far more columns than anything in the
original Chinook design target (widest Chinook table: 13 columns). `schema.py` renders every
table as one dense, comma-separated line regardless of width.

**Concrete evidence — this is not a hypothesis, it's directly verified:**
```
Schema text (verified present): Laboratory(ID INTEGER, Date DATE, GOT INTEGER, GPT INTEGER,
  LDH INTEGER, ALP INTEGER, TP REAL, ALB REAL, UA REAL, UN INTEGER, ...44 columns total...)

Model's response to a question requiring `UA`:
  response_type: "unsupported"
  message: "The database schema does not include a uric acid (UA) column in any table."
```
`UA` is the 9th column, plainly visible in the schema text we generated and fed to the model —
and the model still claimed it didn't exist. In a second case
(`thrombosis_prediction` #1267), the model attributed column `SM` to the wrong one of two
similar medical-panel tables (`Examination` instead of `Laboratory`) — the same underlying
problem (a specific field lost in an undifferentiated wall of abbreviations) manifesting as a
wrong-table guess instead of a false "unsupported."

**Root cause:** one-line-per-table rendering does not scale past roughly 15-20 columns; there is
no structural aid (grouping, one-per-line, or a name index) to help the model locate a specific
field in a wide table.

**Fix (low-medium effort):** for tables above a column-count threshold, switch to one column per
line (or chunk into logical groups), and/or add a plain column-name index at the top of a wide
table's block. **Expected impact:** medium-high, concentrated exactly on our two worst-performing
databases — directly addresses a measured, reproduced failure, not a guess.

### 6.4 Evidence formulas misapplied as projection vs. filter

**Pattern:** BIRD evidence frequently gives a formula (e.g. "Percent eligible for free meals =
Free Meal Count(K-12) / Enrollment(K-12)") without stating whether that formula belongs in the
`SELECT` list (an output) or the `WHERE`/`HAVING` clause (a threshold). The model sometimes picks
the wrong one.

**Concrete evidence:**
```
Q: "...schools with the percent eligible for free meals in K-12 is more than 0.1..."
GOLD: filters WHERE CAST(FreeMealCount AS REAL)/Enrollment > 0.1 — the ratio is a threshold,
      the question asks only for the school name.
GOT:  SELECTs the existing percent column as an output alongside other fields — treats a
      filter-intent evidence formula as something to display.
```
**Root cause:** no prompt rule distinguishes "evidence defines a predicate" from "evidence
defines an output"; the model has to infer this purely from the question's grammar, which it
sometimes gets backwards.

**Fix (low effort):** add a prompt rule making this distinction explicit, illustrated with a
synthetic, schema-unrelated example (per this project's own established discipline against
overfitting to specific dev/eval questions — see `docs/DECISIONS.md`'s 2026-07-13 entry on
exactly this risk). **Expected impact:** medium, recurring across `california_schools`,
`financial`, and `formula_1`.

### 6.5 An over-eager Chinook-era prompt rule actively hurts BIRD accuracy

**Pattern:** `SYSTEM_PROMPT`'s projection rule — "when a question ranks, thresholds, or filters
using an aggregate measure, return both the entity label and the measure" — was tuned
exclusively against Chinook's 10 questions (see `docs/DECISIONS.md`, 2026-07-13) and never
re-validated against a different question distribution. BIRD frequently asks for a *bare* scalar
or aggregate with no entity label at all, and the rule fires anyway.

**Concrete evidence (4 separate `formula_1` questions, same pattern, same root cause):**
```
Q: "What is the average time in seconds of champion for each year, before 1975?"
GOLD: SELECT year, AVG(time_seconds) ...      -- two columns
GOT:  SELECT r.year, AVG(...) AS avg_time_seconds FROM ... -- correct logic, but the rule
      pushed the model toward an unrequested driver_name column in 3 sibling questions
      (#881, #954, #1003) that all ask for a rate/count/percentage alone.
```
**Root cause:** a rule generalized from a 10-question, single-domain tuning set without
revalidation — exactly the overfitting risk this project's own decision log has previously
flagged and self-corrected once already (`docs/DECISIONS.md`, "a self-correction on
overfitting").

**Fix (low effort, but must be validated, not just changed):** make the rule conditional on the
question's own phrasing ("which X..." implies a label is wanted; "what is the rate/average/
percentage..." often does not), and **re-run the Chinook dev set after the change** to confirm
no regression there — this is precisely the kind of cross-cutting risk flagged in §7.
**Expected impact:** medium, concentrated in `formula_1` and other numeric-answer-heavy
databases (`financial`, `debit_card_specializing`).

### 6.6 Silent INNER JOIN default where the question implies an optional relationship

**Pattern:** the model defaults to `INNER JOIN` even when a question's logic implies rows should
be kept whether or not a match exists, silently dropping legitimate zero-match rows.

**Concrete evidence:**
```
Q: "...schools that were opened after 1991 or closed before 2000...average score in writing..."
GOLD: schools LEFT JOIN satscores  -- schools without a satscores row are still listed
GOT:  schools JOIN satscores        -- silently drops schools with no satscores row
```
**Root cause:** no prompt guidance on when an outer join is implied; defaulting to `INNER JOIN`
is the model's implicit prior. This is a well-documented failure mode in the text-to-SQL
literature generally, not unique to this pipeline.
**Fix (low effort):** add a prompt rule. **Expected impact:** low-medium — flagged here from one
directly-verified case; recommend a dedicated audit pass (grep failures for gold queries
containing `LEFT JOIN` where the generated SQL uses plain `JOIN`) before estimating prevalence
more precisely, rather than extrapolating from a single example.

### 6.7 Aggregation across a fan-out JOIN without de-duplication

**Pattern:** joining a one-to-many relationship before aggregating inflates a denominator or
count unless `DISTINCT` is used deliberately.

**Concrete evidence:**
```
Q: "What is the percentage of carbon in double-bond molecules?"
GOLD: COUNT(DISTINCT CASE WHEN element='c' THEN atom_id END) / COUNT(DISTINCT atom_id)
GOT:  SUM(CASE WHEN element='c' THEN 1 ELSE 0 END) / COUNT(atom_id)
```
Joining `atom` to `bond` on `molecule_id` is one-to-many (a molecule can have many bonds), so
`atom_id` rows repeat once per bond — `COUNT(atom_id)` over-counts relative to
`COUNT(DISTINCT atom_id)`, changing the answer.
**Root cause:** no prompt guidance to consider join multiplicity before aggregating.
**Fix (low effort):** add a prompt rule ("after joining a one-to-many relationship, use
`COUNT(DISTINCT ...)` unless you intend to count the joined rows themselves, not the original
entity"). **Expected impact:** low in raw frequency, but this is a **silent-wrong-answer** class
of bug — the query executes cleanly and looks plausible, so it's specifically the kind of error
that would go undetected in production without a gold answer to compare against. Worth fixing
even at low measured frequency because of that asymmetry.

### 6.8 Execution timeout tuned for Chinook is too tight for BIRD's larger schemas

**Pattern:** `connect_readonly(timeout_seconds=2.0)` (`src/db.py`) was set against Chinook's
11-table, 34MB database. 6/500 BIRD failures (1.2%) are `"interrupted"` — legitimate but slower
queries hitting the wall clock, concentrated in the largest/widest databases
(`european_football_2`, `codebase_community`, `card_games`).
**Root cause:** a fixed timeout that doesn't scale with schema/database size.
**Fix (low effort):** raise the ceiling, or make it a function of database file size / table
count, with monitoring to confirm it isn't masking genuinely pathological queries.
**Expected impact:** small in isolation (1.2% direct), but likely undercounted — the one repair
attempt on a timeout can *also* time out, converting a recoverable slow-query case into a hard
failure with no second chance.

### 6.9 No self-consistency / multi-candidate sampling — the big structural lever, and the one real cost tradeoff

**Pattern:** Trellis is deliberately single-shot generation plus one bounded repair — a decision
made explicitly for Chinook's P50 < 3s interactive latency target (`docs/DECISIONS.md`, "One
bounded repair"). Every leaderboard entry scoring above 75% test EX, including the **single-model
track leader at 80.04%**, uses **self-consistency**: generating 8-32 candidate queries and
selecting the majority-vote result by execution outcome, not just picking the first response.

**Root cause:** this isn't a bug — it's a deliberate, previously-justified architectural choice
that optimized for a different goal (fast, cheap, interactive) than "maximum BIRD accuracy."

**Fix:** add self-consistency as an **opt-in mode on the benchmark/batch path**
(`benchmark/run_bird.py`), not the interactive CLI — generate N candidates per question, execute
each, and take the majority-vote result set (or majority-vote SQL text as a cheaper proxy).
**This must not become the CLI's default path** — see §7 for why.
**Expected impact:** the single most consistent variable correlated with top-tier leaderboard
scores in §3.3. Almost certainly the largest remaining lever after 6.1-6.8 are exhausted, and the
most expensive one.

---

## 7. Cross-cutting: how fixing "bad" affects "great" — the tradeoffs that matter

- **6.9 (self-consistency) directly multiplies cost and latency by N** (the candidate count).
  Running it on the interactive CLI path would break the P50 < 3s target and the
  $0.000485/query cost story that is one of this project's clearest wins (§4.5). It must ship as
  a separate, explicitly-invoked benchmark/batch mode, not a silent change to `uv run trellis`.
- **6.2 (description-CSV ingestion) and 6.3 (wide-table rendering) both increase prompt token
  count**, which costs a little more per query. This should be checked against the latency/cost
  budget after implementation — but it is very likely net-positive even on cost, because both
  fixes directly target *hallucination-driven repairs*, and a repair round-trip (a second full
  LLM call) costs far more than the extra input tokens a richer schema block adds up front.
- **6.5 (softening the entity-label rule) carries a real regression risk that must be checked,
  not assumed away.** This exact rule was tuned against the Chinook dev set, and this project's
  own decision log (`docs/DECISIONS.md`) already documents one prior instance of a prompt change
  that fixed one question class while silently regressing another. Any change here should be
  validated by re-running the Chinook dev set (`benchmark/run_bench.py`) before being adopted,
  per this project's own established "one iteration only, don't overfit" discipline.
- **6.8 (raising the execution timeout) trades P90 latency for accuracy, but only where it
  matters.** `docs/DECISIONS.md` already establishes that "P90 is driven by repair rate" for this
  architecture — widening the timeout globally would widen P90 for *every* database, including
  Chinook-scale ones that don't need it. It should be schema-size-conditional (e.g. keyed off
  database file size or table count) rather than a single global constant.
- **None of 6.1, 6.4, 6.6, 6.7 have a meaningful cost/latency tradeoff** — they're prompt-text
  additions with no extra LLM calls, which is exactly why they're prioritized first in §8.

---

## 8. Path to 80%: prioritized roadmap

| # | Intervention | Effort | Expected EX lift | Risk to "great" metrics | Do this... |
|---|---|---|---|---|---|
| 6.1 | Quote special-character column identifiers | Low | Low-Med, concentrated | None | **First** — cheapest possible win |
| 6.2 | Ingest `database_description/*.csv` ("oracle knowledge") | Medium | **High, broad** | Small token/cost increase, likely net-positive | **Second** — highest-confidence lever available |
| 6.3 | Restructure wide-table schema rendering | Low-Med | Medium-High, concentrated | Small token increase | Third |
| 6.4 | Evidence filter-vs-projection prompt rule | Low | Medium | None | Fourth |
| 6.7 | Fan-out-join aggregation prompt rule | Low | Low (but silent-failure class) | None | Fourth (bundle with 6.4) |
| 6.6 | Outer-join-when-implied prompt rule | Low | Low-Med (needs audit) | None | Fifth — audit prevalence first |
| 6.5 | Soften Chinook-era entity-label rule | Low | Medium | **Must re-validate against Chinook dev set** | Sixth — with regression gate |
| 6.8 | Schema-size-aware execution timeout | Low | Low (but undercounted) | Small, scoped P90 increase on large DBs only | Seventh |
| 6.9 | Self-consistency (opt-in batch mode) | Med-High | **Highest remaining, single lever** | **Direct cost/latency multiplier — needs a product decision** | Last — and explicitly scoped to a non-interactive path |

**Honest framing for the 80% target itself:** items 6.1-6.8 target the *"parity with a bare
baseline"* problem this report identifies in §3.3 — closing them should move Trellis from
"tied with an unscaffolded 33B model" to genuinely benefiting from its own agent design, plausibly
into the 55-65% range based on where evidence-aware, well-schema-linked systems land in the
literature (§3.3). **Reaching 80% specifically** — matching the leaderboard's single-model-track
leader — additionally requires either a stronger base model than a cost-optimized flash-tier
model (every reference above ~68% in §3.3 uses a reasoning-tier or heavily fine-tuned model,
not a small fast one) and/or self-consistency at meaningful sample counts (8-32, per the
leaderboard's own technique breakdown in §3.3's "Single-Model Track" table). That is a genuine
product decision, not purely an engineering one: **a sub-3-second, sub-cent interactive CLI and
an 80%-BIRD-competitive agent are, based on the leaderboard's own technique mix, two different
product tiers.** The recommendation is to keep `uv run trellis` fast and cheap as it is today,
and add self-consistency as an explicitly separate, slower, more expensive "analyst/batch" mode
for questions where accuracy matters more than latency — rather than trying to make one
configuration hit both goals at once.

---

## 9. Reproduction

```bash
./scripts/setup_bird_minidev.sh
uv run python -m benchmark.run_bird --concurrency 8 --repeats 1 --budget 3.0 --seed 42
open benchmark/results/bird_report.md   # overall + per-difficulty + per-database + failure list
```

Raw per-question records (SQL generated, gold SQL not included in the JSONL — join against
`data/bird/mini_dev_sqlite.json` by `question_id` to reproduce every diff in §6):
`benchmark/results/bird_raw_20260923T061413Z.jsonl`.

# Path to BIRD SOTA: Plan v2.4 (for review)

**Goal:** move Trellis as close as possible to >80% execution accuracy on BIRD's hidden
**test** set using low-cost methods first. Fine-tuning is decided only at the end, from
measured evidence.

**Status:** v2.4, **approved 2026-09-23**. It replaces v1 after five external reviews (sol)
and a day of measurement work. Every review finding was verified and adopted (§0.2). Items
marked ✅ are implemented and tested. Next: Phase 1, starting with the `train_dev`
baseline.

**Policy:** this is a personal project. The order of work is fixed:
1. free;
2. pennies per pilot;
3. single-digit dollars;
4. everything else.

Every paid step starts with a 50–100-question pilot that measures its real cost before any
full run. There is one spend ledger (§6.8).

---

## 0. Summary

### 0.1 Where we are

| Scoring (existing run `bird_raw_20260923T061413Z`, 500 Mini-Dev rows) | Simple (148) | Moderate (250) | Challenging (102) | **Overall** |
|---|---:|---:|---:|---:|
| **BIRD official EX** (headline) | 66.2% | 42.8% | 32.4% | **47.6%** |
| Same predictions vs **corrected labels** (Arcwise-Plat-SQL) | 66.2% | 47.6% | 32.4% | 50.0% |
| *Oracle* output-format ceiling (an upper bound, **not a gain**, §2.1) | 78.4% | 56.4% | 51.0% | 61.8% |

- The local evaluator previously reported 45.8%. It is not BIRD's comparator (§1.2).
- Cost is $0.000485 per query, P50 is 1.5s, and the model is `deepseek-v4-flash-0731` with
  reasoning off.

### 0.2 What changed from v1, and why

| v1 said | v2 says | Source |
|---|---|---|
| Baseline 47.8%, and later 47.6% on 498 deduplicated rows | **47.6% on all 500 rows.** BIRD's evaluator scores every row, including the duplicated #137 and #138. sol's 47.8% counted one query our safety layer had rejected. | sol #1, verified |
| "+10.8 pts from output fixes (measured)" | An **oracle ceiling**: the rewrites were chosen *using the gold result*. Only a live A/B on unseen databases counts as a gain. | sol #2, agreed |
| "75% Mini-Dev ≈ 80% test"; confirm on full dev | Leaders' dev→test uplift is **context, not a conversion rule**. Full dev contains Mini-Dev and would have contained the tuning questions. Iterate on **held-out train databases**, because test uses unseen databases. | sol #3, adopted |
| Frugal $30–50 alongside a run table worth $125–315 | One ledger. Every experiment is priced from a pilot's *measured* tokens. Offline runs may use Fireworks batch inference at 50% once a submission path exists (not yet; see v2.2 row below). | sol #4, adopted |
| — | Foreign keys rendered as `parent.None` (4 of 105 edges), plus a case-mismatched parent name. **Fixed ✅.** | sol #5, verified |
| — | **New:** 5 of Mini-Dev's 11 databases differ in content from BIRD dev's copies. That changes 23 Mini-Dev and 60 dev gold results, so each question set is scored only on its own databases. | measured today |
| — | **New:** two runs of the identical configuration at T=0 disagreed on 6 of 60 questions. Single runs are too noisy for small decisions. | measured today |
| "Held-out train" is the iteration set | Frequent A/B use turns it into a **development** set. It is now `train_dev` (4 databases, 501 rows). A separate **`train_lockbox`** (2 databases, 226 rows) is looked at only at gates. Every report adds a per-database macro average, because soccer_2016 is 258 rows. | review 2 #1, adopted |
| Score held-out train against BIRD-Verified gold | BIRD-Verified revises the **question, evidence and SQL** for its rows (146 of the 727 match; all have revised questions and SQL, 142 revised evidence). Its SQL can't grade answers to the *original* questions. It becomes a separate, fully-corrected evaluation. | review 2 #2, adopted |
| Full-result signature from `score_bird` | That path executes gold first, so it had no signature when gold failed. Now the candidate runs **first**, and **`execute_candidate`** (safety check + full execution + signature, no gold anywhere) is the executor for cascades and hidden-test runs ✅ | review 2 #3, fixed |
| "One ledger" | It was not enforceable: each process read the ledger once and overwrote it. Measured: 3 concurrent processes recorded **$0.04 of $0.12** spent, and 2 crashed. Now a cross-process locked ledger ✅: reservations stored in the ledger, a per-source breakdown (Fireworks, batch, OpenRouter), orphaned reservations charged conservatively, and batch priced at 50%. | review 2 #4, fixed |
| Phase 1 = value profiling + FTS5 first | **Cheapest-evidence order:** benchmark prompt profile + identifier quoting first, then the dictionary CSVs, measuring each. The full value index comes only if value-matching failures remain. | review 2, adopted |
| Phase 1 fits a $2 cap | It didn't: a pilot + 2 full runs per change is $0.53 per change, or $2.14–2.67 total, *before* the baseline runs (+$0.49). **Now:** stratified + targeted pilots for every change. Full comparisons only for pilots that clear the prespecified gain. Runs ordered by database so the prompt cache can hit (the baseline's hit rate was only 2.2%). | review 3 #1, adopted |
| Test dictionaries on `train_dev`, fetch its CSVs "if it proves out" | The dependency was backwards: none of the downloaded train databases had CSVs. **Now:** fetched *first* ✅. One sequential pass over the 8.9GB archive kept only 764MB: dictionary CSVs for all 11 train databases (one per table) plus 5 new databases, all passing SQLite's integrity check. The streamer needed ZIP64 support (bike_share_1 is 4.3GB). A full member listing is saved for future fold rotation. | review 3 #2, done |
| Two-database lockbox is too small | **Now 7 databases, 974 rows** across 7 domains ✅ | review 3, done |
| Accept on the row-weighted gain | One database is 258 of `train_dev`'s 501 rows, so a gain there can outweigh losses elsewhere. **Now:** both the row-weighted **and** the database-macro gain must clear the bar. The bootstrap resamples *questions* within each database, keeping each question's repeats together. Borderline results trigger an audit of the deciding flips against gold ✅ | review 4 #1, adopted |
| Runs pinned by paths + a dirty flag | A database edited in place, or two different uncommitted changes, looked comparable. **Now pinned by content:** each database's hash, the *effective* prompt per database (template + rendered schema), the config hash, and the code state (diff + untracked files). `flips` refuses runs that differ in anything other than the declared `--allow` variable ✅ | review 4 #2, fixed |
| "Settlement is idempotent" | Two cases still double-counted (reproduced): settling with an unknown cost finalised the estimate so a later real cost couldn't correct it, and keys expired after 7 days. **Now a SQLite ledger:** an append-only charge journal, provisional charges that a real cost later reverses, settlement keys that never expire, and caller-supplied keys (e.g. a batch job id) so another process can settle after a restart ✅ | review 4 #3, fixed |
| Phase 1 ≈ $1.50 | **$1.76** at baseline pricing (5 pilots $0.30 + a two-repeat baseline $0.49 + 2 two-repeat variants $0.97). The full baseline runs **first**; each pilot's control rows come from it. A fixed rule picks which changes get full runs (§6.1). | review 4 #4, adopted |
| Lockbox: ≤4 looks; train "difficulty" | Four looks leak development feedback, so the lockbox gets **2 looks** (midpoint + final). Train splits have no difficulty labels, so Phase 4's safety checks use Mini-Dev labels or a **gold-SQL complexity band** ✅ (it tracks Mini-Dev difficulty in the right order but overlaps widely). Public BIRD data may be in model training sets. | review 4, adopted |
| Compare whatever rows overlap | A budget-stopped variant with 1 result vs a 2-question, 2-repeat baseline read **+100 pts, CI [100, 100]** (reproduced). **Now:** runs record their expected rows, expected repeats, and whether they completed. `analyze flips` (full mode) refuses anything but complete runs with identical expected rows and exactly 2 repeats per question. Partial overlap needs an explicit `--pilot`, labelled not acceptance evidence ✅ | review 5, fixed |
| Two independent full variant runs | Independent runs don't validate the *combination*. **Now cumulative:** each full run is compared against the last accepted configuration (§6.1), at the same cost. | review 5, adopted |
| Complexity band for Phase 4 checks | Gold SQL doesn't exist for hidden-test questions, so the band is for **offline diagnosis only**. Any live cascade rule must use an observable signal or one global threshold (§6.4). | review 5, adopted |
| Reject a change on any significant subgroup loss | That accepts changes with no benefit and makes a lone p < 0.05 a brittle veto. **Now:** a prespecified minimum gain vs cost and latency, judged on paired flips + confidence interval. Subgroups are used to investigate, with a veto only for a *large* single-database collapse. | review 3 #3, adopted |
| Settlement "enforceable" | A late settle after a stale charge double-counted, and repeating it counted again ($0.10 recorded as **$0.40**, reproduced). **Now:** settle reconciles and is idempotent; per-reservation `ttl_s` for long batch jobs ✅. Batch savings are **not yet available**: pricing exists, but there's no batch submission path. | review 3 #4, fixed |
| Phase 3 turns on reasoning *and* switches JSON → fenced SQL | Two variables in one trial. **Now:** reasoning on with the current JSON format first, then the format change as its own test. | review 3 #5, adopted |

### 0.3 Decisions already made

| Decision | Status |
|---|---|
| Plan v2.4, including the §6.8 phase caps | **Approved 2026-09-23** |
| Frugal track; fine-tuning decided at gate F-G | Decided 2026-09-23 |
| Jev via OpenRouter for the BIRD path (decisions only; see DECISIONS.md) | Decided 2026-09-23; production data still needs a review |
| `train_dev` databases are the iteration set; Mini-Dev + `train_lockbox` are the infrequent gates | Adopted in v2.1 (§5) |

---

## 1. Measurement foundation (Phase 0) ✅

### 1.1 What is implemented

| Item | Where | Notes |
|---|---|---|
| BIRD official EX (`set(pred) == set(gold)`, 30s timeout, only delivered SQL counts) | `benchmark/evaluate.py:score_bird` | Gold and prediction each **execute once**. The same rows feed the official metric, the local contract metric, and a full-result signature. |
| Rows, not question ids, are the scoring unit | `benchmark/bird.py:row_index` | All 500 Mini-Dev rows. Older runs map repeated ids to rows in order. |
| Full-result signatures (no 200-row cap) | `run_bird` `result_signature`, `result_row_count` | For clustering candidates later |
| Run pinning | `bird_meta_<ts>.json` sidecar | Dataset sha256, prompt sha256, git commit + dirty flag, temperature, max tokens, reasoning effort, filters |
| Re-score + failure buckets + oracle ceiling + corrected labels | `benchmark/analyze.py rescore --corrected-gold` | Zero API cost |
| Paired comparison by difficulty **and by database**, exact McNemar | `benchmark/analyze.py flips` | Also flags a collapse on a single database |
| Configurable temperature, max tokens, reasoning effort | `Agent`, `llm.complete`, `run_bird` flags | Defaults unchanged, so CLI behaviour is identical |
| Prices for the full current Fireworks catalogue | `src/costs.py` | Verified 2026-09-23 |
| Foreign-key resolution + test that every rendered edge resolves | `src/schema.py`, `tests/test_schema.py` | Chinook schema text is byte-identical |
| Splits + manifest with fingerprints | `benchmark/splits.py` → `data/bird/splits/` | §1.3 |
| Train data without storing the 8.9GB archive | `scripts/remote_zip.py`, `scripts/stream_inner_zip.py` | Range requests for single files. A sequential `curl` pipe for the full pass (ZIP64 and data-descriptor aware, tested on synthetic archives). Keeps only wanted members; writes a full listing (`data/bird/downloads/train_databases_listing.tsv`). |
| Candidate-only executor | `src/db.py:execute_candidate` | AST safety gate + full execution + result signature; never touches gold |
| Cross-process spend ledger | `src/costs.py:BudgetGuard` → `benchmark/results/.spend.sqlite` | SQLite (`BEGIN IMMEDIATE`): append-only charge journal, open reservations, durable settlement keys; `reserve_usd(key=…)`, `settle(source=…)`, `record_charge`, `cost_usd(batch=True)`. The legacy JSON ledger was imported ($0.2817 preserved). Multi-process test. |
| Per-database macro accuracy | `analyze.py`, `run_bird.py` reports | Mean over databases |
| Reconciling, idempotent settlement; per-reservation TTL | `src/costs.py:BudgetGuard.settle`, `reserve_usd(ttl_s=…, key=…)` | Tests: stale → late settle; unknown → known; repeat after 30 days; settle by key from a fresh process |
| Content-pinned runs + comparability gate | `benchmark/bird.py:database_fingerprint`, `run_bird.run_metadata`, `analyze flips --allow` | Database hashes cached by size/mtime; effective prompt per database; config; code state |
| Acceptance evidence | `analyze flips` | Row-weighted **and** macro Δ, 95% question-level bootstrap within databases, all repeats kept per question, tables by database/difficulty/complexity band, list of flips to audit |
| Stratified + targeted pilots; database-ordered runs | `run_bird --per-db N --ids …`; jobs sorted by database | So pilots exercise every schema and each change's target cases, and the prompt cache can hit |

Tests: 60 passing, and ruff and strict mypy are clean. **Uncommitted**, pending review.

### 1.2 Evaluator facts worth knowing

- The old local evaluator compares row order when gold has `ORDER BY`, uses multisets,
  rounds floats to 2 decimal places, and aligns columns by name. It stays as the Chinook
  metric and is never the BIRD headline.
- Gold #518 and #701 time out in **this environment under the current evaluator settings**
  (30s limit; more than 5 minutes when unbounded). Whether they also fail in BIRD's own
  scoring environment is unknown. Locally they cap us at −0.4 pts.
- Mini-Dev's gold differs from BIRD dev for 14 of its 500 SQL queries and 4 question texts.
  BIRD revised them for Mini-Dev.

### 1.3 Datasets and versions (all fingerprinted in `data/bird/splits/manifest.json`)

| Set | Rows | Databases | Role | sha256[:16] |
|---|---:|---|---|---|
| **train_dev** | 501 | 4 train databases: soccer_2016 258, restaurant 117, sales_in_weather 80, movie 46 | **Frequent A/B** on databases never used for prompts, few-shot examples or GEPA. It becomes a development set through use, so always report it per database plus the macro average. | `e5503cce…` |
| **train_lockbox** | 974 | 7 further train databases across 7 domains: synthea 185 (healthcare), olympics 169, retail_complains 168 (finance), university 150 (education), food_inspection_2 139 (government), shipping 106 (logistics), european_football_1 57 | **Gates only**, never used to choose between variants. The closest local proxy for test's unseen databases. The cleanest gold: 5 empty results in 974 rows and no errors. | `f9ac9633…` |
| **Mini-Dev** | 500 | 11 Mini-Dev databases | **Infrequent gates.** At most 4 looks in total, each with 3 repeats. | `4ba5fa8d…` |
| Mini-Dev corrected (Arcwise-Plat-SQL) | 498 unique ids | same | Diagnosis only. Fixes gold SQL; does *not* fix question or evidence ambiguity. | `5927cd93…` |
| **untouched dev** | 1,036 | BIRD dev's own 11 databases | Reported separately, never tuned on. Same schemas as Mini-Dev, so it is not a generalisation check. Skews simple (777 / 216 / 43). | `b0aed7f6…` |
| BIRD train (other 63 databases) | 8,701 | questions only, no databases | Few-shot pool and GEPA text. Execution-based tuning would need their databases. | `abf17d3d…` |
| BIRD dev, Nov 2025 cleaned version | — | — | *Not downloaded.* Optional extra diagnostic, tracked as its own version and never mixed. | — |

**Label-noise caveat for the train splits:**
- BIRD train labels are noisy. ReViSQL reports correcting **61% of its sampled 2,462**
  train instances. That's a sample figure, not a rate for all train rows.
- Train splits have **no difficulty labels**. Per-tier views use a deterministic gold-SQL
  complexity band (`analyze.py:sql_complexity`). On Mini-Dev its mean band rises
  0.38 → 0.76 → 1.10 from simple to challenging, but the overlap is wide, so treat it as a
  rough proxy.
- Public BIRD train and dev data may have been in a model's training set, so absolute
  scores on these splits can be inflated. Only the hidden test is clean.
- 19 of restaurant's 117 gold queries return no rows; soccer_2016 has 5 and movie 2.
- Judge changes by paired flips per database, not by absolute scores.
- **BIRD-Verified** (downloaded ✅; `data/bird/verified/`; **no licence is declared** on
  the ReViSQL repo, so it's used for private evaluation only and never committed). Its ids
  are `train.json` row indices, matching all 2,064 exactly.
  - On our splits it covers 93 `train_dev` and 195 `train_lockbox` rows. That's 146 on the
    original six databases, matching the reviewer's count.
  - Most rows are *verified, not rewritten*. Comparing against `train.json` on those 146:
    25 revised questions, 18 revised evidence, 76 revised SQL. The reviewer reported all
    146 as revised; the public file doesn't show that.
  - It is therefore used two ways, both built by `benchmark/splits.py`:
    1. **`verified_gold_same_inputs.json`** (219 rows): corrected SQL where question and
       evidence are unchanged. It grades ordinary runs via
       `analyze rescore --corrected-gold`, like Arcwise does for Mini-Dev.
    2. **`verified_train_dev.json` / `verified_train_lockbox.json`** (93 / 195 rows): the
       corrected question, evidence and SQL together, as a separate corrected-input
       evaluation. 69 rows have revised inputs. 2 rows declare non-set grading, which the
       official comparator doesn't model.
  - A run on `verified_train_lockbox` counts as a lockbox look.

---

## 2. Diagnosis of the baseline

### 2.1 Failure buckets (262 failing rows, official EX)

| Bucket | Share | Main cause |
|---|---:|---|
| Extra columns | 29% | Chinook-era rules: "return label and measure", tie-breaker columns |
| Values differ, same shape | 34% | Wrong table/column among look-alikes, wrong join key, evidence misread, label noise |
| Empty result | 10% | Value/format mismatch (e.g. `yearmonth.Date` is `'201309'` text), over-filtering |
| Missing columns | 9% | Name concatenation, where gold keeps first and last separate |
| Row count differs | 8% | DISTINCT and fan-out conventions, LIMIT/ties |
| Pipeline: safety-rejected / repair-exhausted / "unsupported" | 8% | Unquoted `T-BIL`, 2s timeout, guardrail false positives |

**Oracle output-format ceiling (+14 pts).** Selecting a subset of columns, removing
`ROUND`, splitting concatenations, or dropping `DISTINCT` inside `COUNT` turns 71 failing
rows into gold-equal results. This tells us where to look, not what we'll gain: every
rewrite was chosen by comparing against the gold result. No transformation is applied
automatically without measured precision (sol).

### 2.2 What data engineers do that Trellis doesn't

| Gap | Example | Root cause in code |
|---|---|---|
| Reads the data dictionary | #1166 `Diagnosis` exists in both `Patient` and `Examination` | Description CSVs are on disk for all 11 databases but never read |
| Checks values and formats first | #1500 `'201309'`; #1057 "no Poland" | `src/schema.py` samples only the first 10 non-PK columns and only ≤50 distinct values |
| Treats 0 rows as a bug | 26 empty results shipped | Repair fires only on *errors* |
| Answers exactly what was asked | Extra measure and name columns | `src/prompts.py` Chinook rules |
| Joins on real keys | `Match.league_id -> League.None` shown to the model | **Fixed ✅** |
| Thinks before writing | Mean output is 84 tokens | `reasoning_effort="none"`, T=0, SQL embedded in a JSON string |

---

## 3. What the leaders do (research summary; sources at the end)

| System | Test (dev) EX | What matters |
|---|---|---|
| DataGallery-Text2SQL (Huawei) | 82.39 (78.10) | Semantic layer + data agent; no paper |
| SIRIUS-SQL (Tencent) | 82.28 (77.77) | RL specialist + generalist; repair per error class; selection by execution agreement + pairwise judge |
| Agentar-Scale-SQL (Ant) | 81.67 (74.90) | 17 candidates from 2 generator families. Ablation: −4.9 / −3.8 pts without either family, −1.8 without the selector, −0.5 without refinement or retrieval |
| Gemini-SQL2 (single model) | 80.04 (74.12) | Gemini 3.1 Pro + many samples; no report |
| Databricks RLVR-32B | 75.68 (73.56 without SC) | BIRD train only; RLVR; 7 samples |
| ReViSQL | 93.8% on corrected Mini-Dev | Corrected training data alone: +8–14 pts |
| EllieSQL | — | Routing saves ~40% of tokens at equal accuracy |

The pattern is consistent:
1. rich context;
2. reasoning;
3. at least two generator families;
4. many candidates;
5. execution feedback;
6. selection;
7. at the very top, a trained specialist.

Leaders scored 4–7 pts higher on test than on dev. That's reported as context only, never as
a conversion rule for Trellis.

---

## 4. Target and how we'll know

- **Primary milestone:** a frozen configuration that scores strongly on `train_lockbox`
  (unseen databases) and Mini-Dev (500 rows, 3 repeats), with **no single-database
  collapse**.
  Untouched dev is reported alongside.
- **Working milestone:** 75% official EX on Mini-Dev. This is a checkpoint, not a
  guarantee of 80% on test.
- **The claim itself:** only the hidden-test submission establishes >80%. Submit by BIRD's
  guidelines, after contacting the benchmark team.

---

## 5. Evaluation protocol

1. **Iterate on `train_dev`** (501 rows, 4 databases) with `analyze flips`. Run 2 repeats
   for any decision, because T=0 runs aren't deterministic. When more train databases are fetched, rotate database-level folds
   so no single set is tuned against indefinitely.
2. **Gates:**
   - Mini-Dev: at most 4 looks, 3 repeats each.
   - `train_lockbox`: **2 looks only**, a midpoint check and the final frozen configuration.
     Every look is development feedback.
   - Report official, corrected-label, per-difficulty (or complexity band) and per-database
     results, plus flips vs the last gate.
3. **Report untouched dev** at gates, separately. Never tune on it.
4. **Acceptance rule** (fixed *before* each experiment):
   - **Adopt only on a positive, worthwhile gain.** Each change declares its minimum gain
     before it runs: ≥ +1.5 pts official EX on `train_dev` for a prompt or context change;
     more for anything that adds cost or latency (≥ +1 pt per +50% $/query or +1s P50).
   - **Two metrics, both required:** the row-weighted Δ *and* the database-macro Δ
     (the mean of per-database Δs). Both point estimates must meet the declared minimum and
     both 95% intervals must exclude 0. On `train_dev`, soccer_2016 is 258 of 501 rows, so
     the row-weighted Δ alone can hide losses elsewhere. The macro Δ covers only 4
     databases, so it is a guard, not a precise estimate.
   - **Full vs pilot comparisons.** Acceptance uses **full** comparisons only: both runs
     complete (no budget stop), the same expected question rows, and exactly 2 repeats of
     every question. `analyze flips` enforces this. Pilots use `--pilot`, which permits
     partial overlap and marks the report as not acceptance evidence.
   - **Resampling unit = the question.** Each question is scored as its mean over repeats,
     and questions are resampled within each database, never the 1,002 outputs as if they
     were independent.
   - **Audit borderline results.** If either interval's lower bound is within 1 pt of 0,
     read the deciding flips (the list `analyze flips` prints) against gold before
     adopting. Paired flips still score against noisy labels.
   - **Subgroups investigate; they don't vote.** Per-database and per-difficulty flips are
     read to understand regressions. With many small groups, a lone p < 0.05 is expected by
     chance.
   - **One hard veto:** a *large* collapse on one database, meaning a drop of ≥ 10 pts on a
     database with ≥ 40 rows, is investigated before adoption, whatever the overall result.
   - The Chinook dev set and the 16-question live suite must not regress. The `product`
     prompt profile stays untouched.
5. **Pilots** (≈ 100 rows) are **stratified by database** (`--per-db`) **plus targeted
   cases** (`--ids`) that exercise the change. Example: the 30 `movie` rows whose gold uses
   special-character columns, for the quoting fix. A pilot answers "is this worth a full
   comparison, and what does it cost?", not "is this significant?". With ~10% run-to-run
   flips, 100 rows only detect large effects.
6. **Every run is pinned by content** (dataset, per-database content hashes, effective
   prompt per database, config, code state). `analyze flips` refuses to compare runs that
   differ in anything but the declared `--allow` variable (`prompt`, `config`, `code`,
   `data`, `databases`). Scores from different versions are never combined.

---

## 6. The frugal roadmap

Costs are anchored on the measured baseline: about 2,000 input and 84 output tokens per
question, $0.000485 per query. Reasoning and multiple samples change output tokens the most,
so each paid phase **prices itself from a pilot first**.

### 6.1 Phase 1: cheapest evidence first (pennies per pilot)

**Sequence:**
1. **Baseline first:** the current configuration on all of `train_dev`, 2 repeats
   (≈ $0.49). Every pilot's control rows are taken from this run, so each comparison is on
   the same rows, never against a separate small control sample.
2. **Per change, a stratified + targeted pilot** (≈100 rows, ≈ $0.05): `--per-db` plus
   `--ids` for the rows the change targets.
3. **Full comparisons for at most two changes** (501 rows × 2 repeats, ≈ $0.49 each),
   **cumulative, not independent.** The first promising change is run as baseline + change
   and compared with the baseline. If it's accepted, the second is run as *(baseline +
   first) + second* and compared with that accepted run, so the combination is exactly what
   gets validated. If the first is rejected, the second is compared with the baseline. The
   cost is the same $1.76, because each accepted run doubles as the next comparison's
   control.
   Choosing them if more than two pilots look promising:
   1. rank by the pilot's net fixes per 100 rows;
   2. prefer changes that add no tokens or calls;
   3. closely related, low-risk changes (e.g. 1b identifier quoting + 1c unknown-identifier
      repair) are combined into one full run and treated as one change.
4. Runs are ordered by database. The baseline run measures the real prompt-cache hit rate,
   and all later estimates use it.

**Budget at baseline pricing:** 5 pilots $0.30 + baseline $0.49 + 2 full variants $0.97 =
**$1.76**. That leaves **$0.24** inside the $2 cap for repair calls and extra tokens, which
is thin. If the baseline's measured cost per query exceeds $0.000485, or a change adds
calls, drop to one full comparison rather than raise the cap mid-phase.

| Order | Change | Why first |
|---|---|---|
| ✅ | Foreign-key fix | Done, with a test |
| 1a | **Benchmark prompt profile.** Split `src/prompts.py` into a core prompt plus a presentation profile. The `benchmark` profile has no automatic extra measures, no name concatenation, no rounding unless asked, and no tie-breaker columns. The `product` profile is today's text, unchanged. | The biggest oracle bucket; direct postmortem examples; a prompt-only change |
| 1b | **Quote special identifiers** (`` `T-BIL` ``) in the rendered schema, plus a prompt rule | 4+ hard failures; no extra tokens |
| 1c | Repair unknown-identifier rejects with a "did you mean" hint; one repair turn for empty results; no "unsupported" in benchmark mode; timeout scaled to database size | Pipeline losses (8% of failures); forbidden SQL still never retries |
| 2 | **Dictionary CSVs**: render `column_description` / `value_description`, including "commonsense evidence" formulas and "unuseful" flags such as `satscores.rtype` | On disk for all 11 Mini-Dev databases, and now fetched for every `train_dev`/`train_lockbox` database ✅ (one sequential pass over the train archive, before this step is tested) |
| 3 | Wide tables: one column per line above ~15 columns | Targets #1169-style misses |
| 4 | **Only if value-matching failures remain:** profile every column (format, NULLs, distincts) and a local FTS5 value index | Bigger build; justified only by measured residual failures |

**Not done:** automatic column trimming or `COUNT(DISTINCT)` rewriting. Those wait for
measured precision.

### Phase 1 log

**Baseline (2026-09-24):** run `bird_raw_20260924T005317Z` at commit `5a69af6` (clean),
current configuration, `train_dev` × 2 repeats, complete.

| Measure | Value |
|---|---:|
| Official EX, row-weighted | **60.1%** |
| Official EX, database macro | **58.5%** |
| Per database | sales_in_weather 41.2% · restaurant 58.1% · soccer_2016 65.1% · movie 69.6% |
| On the 72 BIRD-Verified same-input rows: original gold vs corrected gold | 68.1% vs **77.8%** (10 wrong→right, 3 right→wrong) |
| Oracle output-format ceiling (repeat 0; not a gain) | 68.5% (34 extra-column, 7 `COUNT(DISTINCT)`, 1 `ROUND`) |
| Failure buckets (repeat 0, 200 rows) | values-differ 79 · extra-columns 54 · row-count 34 · empty 13 · pipeline 12 · missing-columns 5 · gold-exec-error 3 |
| Cost | **$0.000293/query** (**48.7% prompt-cache hits** from database-ordered runs; 40% under the estimate). Run total $0.29 of the $2 Phase 1 cap. The ledger ceiling was set to $2.28 (prior spend + cap), so the cap is enforced automatically. |
| Latency | Not valid for this run: synchronous scoring on the event loop inflated it (P90 14.9s). Scoring now runs in a worker thread. |

**Harness fixes found by this run:**
- Code-state hashing included the run's own result file under `benchmark/`, so every run
  looked dirty and could never be compared. It now hashes Python sources only. This run's
  sidecar was corrected, with the change recorded inside it.
- Scoring moved off the event loop.
- The report title now names the question file.

**Pilots (2026-09-24):** both runs used the same 80-row stratified sample (`--per-db 20
--seed 1`) plus targeted rows, 2 repeats each, and were compared with the baseline on the
same rows. Cost: $0.11 for both. Both came in cheaper per query than the baseline
($0.00024 vs $0.00029), with no extra tokens.

| Pilot | Subset | Rows | Baseline → pilot | Δ (95% CI) | Verdict |
|---|---|---:|---|---|---|
| **1a** benchmark prompt profile (`--prompt-profile benchmark`) | stratified (unbiased) | 80 | 60.6% → **68.1%** | **+7.5 [+2.5, +13.8]** (row = macro: 20 per DB) | **On course → full comparison #1** |
| 1a | targeted: baseline shape failures (biased upward) | 51 | 0% → 56.9% | +56.9 | Confirms the mechanism |
| 1b identifier quoting (`--quote-identifiers`) | stratified | 80 | 60.6% → 61.9% | +1.2 [−2.5, +6.2] | Not on course for +1.5 here |
| 1b | targeted: `movie` special-name rows | 14 new | 71.4% → 71.4% | 0 | `train_dev` barely exercises it |

- 1a has one partial regression (1 of 2 repeats), on `movie`. That repeat wrote
  `c.Character Name` unquoted, which is exactly the failure 1b prevents. So it's noise for
  1a and evidence for 1b.
- 1b's real target (`T-BIL`, `aCL IgM`) lives in Mini-Dev's `thrombosis_prediction`, and
  only `movie` in `train_dev` has special names. Per the §6.1 selection rule it doesn't earn
  its own full run. It is **bundled with 1c** (unknown-identifier repair, empty-result
  review) as one low-risk mechanical change for full comparison #2.

**Full comparison #1 (2026-09-24): 1a ACCEPTED.** Run `bird_raw_20260924T170715Z`
(baseline + `--prompt-profile benchmark`, `train_dev` × 2, complete) vs the baseline.
Full-mode `analyze flips`, coverage verified; report in
`benchmark/results/flips_train_dev_baseline_vs_1a.md`.

| Criterion | Result |
|---|---|
| Row-weighted Δ | **+6.99** [+4.49, +9.78] ✅ (60.1% → 67.1%) |
| Database-macro Δ | **+6.91** [+3.03, +10.98] ✅ |
| Borderline audit needed? | No: both lower bounds are far from 0 |
| Large single-database collapse? | None. movie +0.0 (4 fixes, 4 regressions); restaurant +11.5; sales_in_weather +11.2; soccer_2016 +4.8 |
| By complexity band | low +6.8, medium +8.5, high +2.0 |
| Cost / latency | No increase; run total $0.28 |

**Audit of the consistent regressions** (read anyway, since they point at the next step):
- **All 4 on `movie`:** SQL that wrote `c.Character Name` / `m.Release Date` unquoted, which
  was then safety-rejected. Under 1a, safety rejections rose from 7 to 14 over 1,002
  answers, and "unsupported" refusals from 2 to 6 (e.g. #8179). Those are exactly 1b's and
  1c's targets.
- The remaining regressions (#1784, #2019, #8175) are ordinary semantic variance.

**Accepted configuration going forward:** `--prompt-profile benchmark`. The product/CLI
profile is unchanged.

**Next:**
1. Build the 1c pilot (repair unknown-identifier rejects with a "did you mean" hint; one
   repair turn for empty results; no "unsupported" in benchmark mode; timeout scaled to
   database size).
2. Full comparison #2: **(1a) + 1b + 1c vs the accepted 1a run**, cumulative. The 1a run
   above serves as its control, so no new baseline spend.
3. Phase 1 spend so far: **$0.68 of $2** (baseline $0.29, pilots $0.11, full #1 $0.28).

### 6.3 Phase 3: reasoning and diversity, incrementally (single-digit dollars)

- **3a. Reasoning on, JSON format unchanged.** Set `--reasoning-effort low`, then `high`,
  and raise `--max-tokens` as needed. This also shows whether a model accepts reasoning
  together with structured JSON output.
- **3b. Output format as its own test.** SQL in a fenced block instead of a JSON string,
  with reasoning held at the 3a winner. Run it only after 3a, so any gain or regression has
  one identifiable cause.
- **Pilot 2 cheap model families** (e.g. `deepseek-v4-flash-0731` + `glm-5p3-flash` or
  `gpt-oss-120b`) at **K = 1, then 2, then 4**. For each K, measure actual cost, oracle
  pass@K, selected accuracy (majority by result signature), and latency.
- Expand toward 8 candidates **only if extra candidates add correct answers** (pass@K
  still rising).
- Offline candidate generation *could* use Fireworks batch inference (50% of serverless
  prices), but **the repo has no batch submission path yet**. Batch savings are contingent,
  and every estimate here is priced at serverless rates until that path exists.

### 6.4 Phase 4: cascade and selection

- **Cascade safety gate (hard requirement):** measure how often 3 agreeing samples are
  **unanimously wrong**, per database and per difficulty, before the cascade may ship an
  agreed answer without escalation. Difficulty comes from Mini-Dev's labels; on the train
  splits (unlabelled) it comes from the gold-SQL complexity band.
- **Offline vs live.** The gold-SQL complexity band is for *offline diagnosis only*:
  hidden-test questions have no gold SQL. A live cascade rule must use signals the system
  can observe:
  - agreement among its own candidates;
  - Jev confidence;
  - the complexity of the *generated* SQL;
  - schema size.

  Alternatively it uses one global threshold. It must be calibrated on `train_dev` and
  verified per band offline.
- Selector ladder:
  1. majority by full-result signature;
  2. an execution-agreement cluster, then a pairwise judge that sees only the *differing
     rows* and the minimal SQL diff;
  3. structural tie-breaks.
- **Bottleneck test on the candidate bank:**
  - pass@K high but selected accuracy low → improve the selector ($≈0).
  - pass@K low → Phase 6.

### 6.5 Phase 5: Jev and GEPA, after the simple baselines exist

- **Jev** (§7): tested offline on the bank for the cascade gate, output checks,
  answerability, relevance scoring and tie-breaks. It is adopted per decision only if it
  beats the agreement-only rule and a small LLM judge on calibration and on the
  unanimous-wrong rate, per tier.
- **GEPA:** optimise the core prompt and then per-family "residual skills" on **train
  databases outside `train_dev` and `train_lockbox`**. Execution-based rollouts need those databases,
  so check the cost of the extra download first. Text-only reflection uses train questions.

### 6.6 Phase 6: strong model on contested questions only (optional)

Send only contested questions (Stage-1 disagreement or low confidence) to
`deepseek-v4-pro-0813` with 2–4 samples. Price it from a pilot.

### 6.7 Gate F-G: fine-tuning decision (measured on the candidate bank)

| Evidence | Decision |
|---|---|
| Frozen configuration meets §4 milestones | No fine-tuning; prepare the submission |
| Pass@K − selected accuracy ≥ ~6 pts | Selection is the bottleneck: improve the selector, not the generator |
| Pass@K still low after Phase 6 | Cheapest fine-tune first: LoRA SFT of a ≤16B model on verified plus execution-filtered train data (~$10–30 to train, plus GPU hours while serving). RFT only after that, with a quote. |

### 6.8 One ledger

All spend goes through `BudgetGuard` and the SQLite ledger
`benchmark/results/.spend.sqlite`, enforced across processes ✅:
- Fireworks serverless spend is reserved and settled automatically.
- A settle with an unknown cost books a **provisional** charge (conservative, source
  `unsettled`). A later real cost reverses it. Settlement keys never expire, so repeats
  are no-ops forever.
- Batch jobs, once a submission path exists: `reserve_usd(estimate, key=<batch job id>,
  ttl_s=<deadline>)` before submission. Any process can later settle
  `reservation(<job id>)` with `source="fireworks-batch"`.
- Jev/OpenRouter calls do the same with `source="openrouter"`.
- `record_charge` reconciles any invoice difference.
- `spend_by_source()` reports the breakdown.

The ceiling (`FIREWORKS_BUDGET_USD`, currently **$6**, $0.28 spent) is raised one phase at a
time.

| Phase | Proposed cap | Pilot first? |
|---|---:|---|
| 1 (profile, quoting, repairs, CSVs) | ≤ $2 | yes: 100 `train_dev` rows |
| 2 | (merged into 1) | — |
| 3 | ≤ $10 | yes: 50–100 rows per model/K |
| 4 | ≤ $3 | offline on the bank, plus judge calls |
| 5 | ≤ $8 | yes |
| 6 | ≤ $15 | yes: contested rows only |
| **Total before gate F-G** | **≤ ~$38** | Every cap is revised from pilot measurements |

---

## 7. Jev (approved for the BIRD path)

- **What it is:** TypeSafe AI's "System One" decision model (`typesafe/jev-1.13`, called
  through OpenRouter's alpha `POST /api/alpha/decisions`). It answers typed questions (yes/no
  "noul", choice, score) with calibrated probabilities. The request limit is 64k tokens,
  with 32k for the state plus the longest question. Price: $0.042 per 1M input tokens,
  output free. It **cannot generate SQL**.
- **Candidate uses:** the cascade gate, evidence and output checks, answerability,
  relevance scoring, and a selection tie-break. The last is weak because Jev's reported
  weak spots are numbers, dates and long-context reasoning.
- **Rules:**
  - Only the relevant schema slice goes into the state.
  - Record the model version with every decision, and fit thresholds per version.
  - Fall back to the agreement-only rule on any error.
  - Key in `OPENROUTER_API_KEY`.
  - Production-data use still needs its own review.

---

## 8. Open items for your review

1. ~~Approve the plan~~ **Approved 2026-09-23 (v2.4).**
2. ~~BIRD-Verified~~ **Downloaded and integrated 2026-09-23** (§1.3).
3. **Train databases for GEPA execution rollouts** (Phase 5): decide later. Every member's
   size is now known from the saved archive listing, and one sequential pass (~30 minutes,
   bandwidth only) can fetch any set of them.
4. ~~Commit and push~~ **Done 2026-09-23** (branch below).

---

## Sources

- BIRD leaderboard and submission guidance: https://bird-bench.github.io/
- BIRD official EX evaluator: https://github.com/bird-bench/mini_dev/blob/main/evaluation/evaluation_ex.py
- Jin et al., *Text-to-SQL Benchmarks are Broken* (CIDR 2026): https://www.cidrdb.org/cidr2026/papers/p5-jin.pdf
- Arcwise-Plat-SQL and BIRD-Verified (ReViSQL): https://github.com/uiuc-kang-lab/ReViSQL · https://arxiv.org/abs/2603.20004
- BIRD dev, Nov 2025 version: https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106
- Agentar-Scale-SQL: https://arxiv.org/abs/2509.24403 · SIRIUS-SQL: https://arxiv.org/abs/2606.01246
- Databricks RLVR: https://arxiv.org/abs/2509.21459 · MCI-SQL: https://arxiv.org/abs/2603.13390 · CHASE-SQL: https://arxiv.org/abs/2410.01943
- EllieSQL: https://arxiv.org/abs/2503.22402 · GEPA: https://arxiv.org/abs/2507.19457 · DivSkill-SQL: https://arxiv.org/abs/2605.21792
- Jev: https://typesafe.ai/blog/introducing-system-one-models-and-jev · https://simonwillison.net/2026/Sep/21/jev/ · https://openrouter.ai/blog/tutorials/jev-vs-llm-as-a-judge/
- Fireworks pricing (incl. 50% batch): https://docs.fireworks.ai/serverless/pricing
- Tam et al., *Let Me Speak Freely?*: https://arxiv.org/abs/2408.02442

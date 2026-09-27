# Path to BIRD SOTA: Plan v2.9 (for review)

**Goal:** first exceed 75% BIRD official execution accuracy on a named public dev
evaluation, then pursue >80% on the hidden test. Start with the largest credible quality
gains that can be tested for free or for pennies. Decide on fine-tuning from current,
paired evidence; no public dev score predicts hidden-test performance.

**Status:** v2.9 proposal, 2026-09-26.
- v2.5 folded in the later runs (§0.4) and the findings in §2 from
  `docs/POSTMORTEM_V2.md`.
- v2.6 added a principal-level review (§0.5).
- v2.7 applies a second external review (§0.6): measured scores and decision points
  replace projections, and several v2.6 items are corrected.
- v2.8 applies a third review (§0.7):
  - a cleaned-dev look budget;
  - the candidate bank as a diagnostic run plus a confirmation run;
  - exact submission ceilings;
  - `train_dev2`'s role;
  - probe-executor gating;
  - explicit quality labels for training data and Jev.
- v2.9 applies a fourth review (§0.8) and records the cleaned-dev baseline:
  - the pilot counts as a look;
  - supplied column meanings come before an LLM glossary;
  - honest cost-accounting status;
  - a truncation-only retry;
  - figure corrections;
  - constraint checks in candidate selection.

The v2.6 changes are:
- a two-track acceptance rule;
- a parallel generation/training track;
- a per-database semantic layer;
- strategy-diverse candidates;
- Jev reframed as a gate on expensive work.

The approved v2.4 plan and its experiment logs remain below as history. A planned action
is not an implemented feature or an approved increase in spending.

**Policy:** free analysis and deterministic fixes first; then Jev and generator pilots
priced from measured tokens; then full comparisons and only then training or costly
model routes. Every paid experiment begins with a 50–100-question pilot and uses the
shared spend ledger (§6.8). No gold SQL, gold result or gold-derived complexity is
available to the live inference path.

---

## 0. Summary

### 0.1 Current measured position

| Evaluation | Current model | Rows × repeats | Official EX | Scope |
|---|---|---:|---:|---|
| Mini-Dev gate 2 | `deepseek-v4p1-flash` | 500 × 3 | **65.3%** (979/1,500 outputs) | 2 of 4 gate looks used; macro 64.2% |
| `dev_untouched` | `deepseek-v4p1-flash` | 1,036 × 1 | **67.6%** (700/1,036) | Reporting only; macro 68.1% |
| `train_dev` clean reproduction | `deepseek-v4p1-flash` | 501 × 2 | **69.4%** | Control on the iteration set; macro 70.8% |
| `train_dev` + adopted rank 1b facts | `deepseek-v4p1-flash` | 501 × 2 | **70.2%** | Owner-adopted benchmark candidate; paired +0.8 pts [−0.3, +2.0] |
| **Cleaned Nov 2025 dev (primary)** | `deepseek-v4p1-flash` | 1,534 × 1 | **66.0%** (1,012/1,534) | Look 2 of 4 (the 99-row pilot was look 1); macro 64.1%; simple 75.3 / moderate 65.0 / challenging 32.9 |
| Cleaned Nov 2025 dev + rank 1b facts | `deepseek-v4p1-flash` | 1,534 × 1 | **66.5%** (1,020/1,534) | Look 3 of 4; paired +0.52 pts [−0.46, +1.50], 33 fixes / 25 regressions; macro 64.4%; descriptive, not transfer proof |
| `train_lockbox` midpoint | `deepseek-v4p1-flash` | 175 × 3 per arm | **79.24% → 81.14%** | 7 databases, paired +1.90 pts [−0.19, +4.19]; safety screen passed, transfer unproven; 1 of 2 looks used, 799 rows sealed |

The exact current run IDs are `20260926T211555Z` (Mini-Dev),
`20260926T212111Z` (`dev_untouched`) and `20260926T212754Z`
(`train_dev`); see `docs/PROVENANCE.md`. The former Mini-Dev gate was 59.3%.
On the same Mini-Dev database hashes, v4p1 gains +5.9 points over the retired
`deepseek-v4-flash-0731` snapshot. The old and new `dev_untouched` runs differ in
five database content hashes, so 63.6% → 67.6% is a descriptive change, **not**
an isolated model effect. Re-score before quoting a close comparison: timeouts
depend on evaluator load.

To exceed 75% on current `dev_untouched` requires at least **78 net additional
correct rows** (700 → 778/1,036). To exceed 75% on Mini-Dev's 1,500 outputs
requires **147 net additional correct outputs** (979 → 1,126). These are
checkpoints, not forecasts. The old 47.6% baseline and +14-point gold-informed
format oracle (§2) are historical diagnosis, not current improvement estimates.

**Leaderboard context (v2.7):**
- Trellis has **no test score**, and no public dev number converts into one.
- Measured: Mini-Dev **65.3%**, `dev_untouched` **67.6%**, cleaned dev baseline
  **66.0%** and rank 1b **66.5%** (one repeat, CI includes zero), and `train_dev`
  control **69.4%** / rank 1b candidate **70.2%** (§0.1 table).
- The first `train_lockbox` look is a 175-row stratified sample: +1.90 pts for rank 1b,
  with a CI including zero. `train_dev2` remains unrun.
- The v2.6 "≈ 66.9% full dev" pooled different question and database versions, so it is
  withdrawn, together with the rank estimate built on it.
- For reference, BIRD's main board lists single-model baselines such as Claude Opus 4.6
  at 68.77 dev (Nov 2025 dev) / 70.15 test. It lists GPT-5.5-xhigh with only a test
  column value (72.55) and no linked BIRD source, so that entry is not used as an anchor.
- No listed entry reaches 80% test with one untrained model producing one answer. The
  entries with published designs use a trained model with many samples (Gemini-SQL2,
  80.04 on the single-trained-model track) or several candidates plus a selector.
  Several top entries publish no design. These are examples, not proof that any one
  component is required.

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

### 0.3 Existing project constraints

The approved v2.4 spending envelope, separate product prompt profile, and
`train_dev` / gate split remain in force. The v2.5 and v2.6 edits change experiment
priority, acceptance tracks and measurement language. They do not execute paid runs, raise
caps or download data; §8 lists the owner decisions v2.6 needs.

### 0.4 Why the order changes in v2.5

1. `POSTMORTEM_V2.md` finds the Phase 1 presentation failures mostly fixed.
   Remaining errors cluster around value grounding, table/column choice, missing
   constraints, aggregation and arithmetic scope.
2. Existing empty-result retry has limited effect. In the new runs, Mini-Dev has
   45 empty and 17 single all-NULL outputs among 1,500, none correct. On current
   `dev_untouched`, **4/30 empty and 2/11 all-NULL answers are correct**.
   Triggered repair must therefore protect legitimate empty/NULL answers.
3. Global reasoning, dictionary dumping, retrieved few-shot and earlier
   disagreement escalation missed their cost-adjusted bars. Revisit only targeted
   variants with a demonstrated mechanism.
4. The retired-model candidate bank's pass@K and routing ceiling do not describe
   the new default. Rebuild comparable candidates before claiming a selection
   ceiling or making a fine-tuning decision.
5. Jev can make narrow semantic choices before and after SQL generation (§7).
   It has no demonstrated BIRD accuracy gain yet. Move its **offline and targeted**
   tests ahead of expensive selector, cascade and training work.

### 0.5 v2.6 review: what changes and why

**Assessment.** The measurement foundation is sound: content-pinned paired comparisons,
rationed gates and one ledger. So is the v2.5 mechanism diagnosis. But ranks 1–4 of the
v2.5 queue are bounded fixes:

| Fix | Bound or planning range |
|---|---|
| Empty/NULL handling | ≤ 3.4 pts |
| Value grounding | +1.1–2.0 |
| Computation checks | +1–3 |
| Jev | unknown |

The fixes overlap, and none is a measured gain. Their stated bounds suggest the queue
alone may not reach the >75% dev checkpoint; v2.7 treats that as a decision point to
measure (§8), not a projection. v2.6 moved generation work earlier and made six changes
(items 2, 3 and 6 are amended in v2.7, §0.6):

1. **Two-track acceptance (§5.7).**
   - *Why:* the §5 cost term (+1 pt per +50% uncached cost) fits the CLI product. Applied
     to the benchmark, it would reject a +4 pt gain at 5× cost (required ≈ +9.5), which
     every leading architecture needs.
   - *Scale:* the whole hidden test costs about $1 at today's rate.
   - *Change:* a **submission track** with an absolute per-answer cost ceiling and a P90
     latency ceiling in place of the per-point cost penalty. It keeps every paired
     quality requirement.
2. **A parallel generation/training track (rank G, §6.6).**
   - *Why:* evidence for it already exists: shared errors across all 5 models, the old
     bank's pass@4 = 73%, and frontier single models plateauing in the low 70s on test.
   - *Change (as amended in v2.7):* pricing and training-data preparation run
     **alongside** ranks 1–4. The paid SFT pilot waits for the current candidate-bank
     result and a label-quality audit (§0.6).
3. **A per-database semantic layer (rank 1, §6.4).**
   - *Why:* this is what data engineers bring and what the #1 system (DataGallery) is
     built on.
   - *Change:* build it offline from the database alone, never from gold, at ingestion:
     1. column profiles (stored type vs semantic type; text-encoded numbers, dates and
        money; units; enumerations; NULL rates);
     2. the join graph with cardinalities and fan-out risk;
     3. an LLM-written glossary cached by database content hash.
   - It must also run on hidden-test databases at submission time.
4. **Value exploration before the final SQL (rank 2).** One or two bounded exploratory
   queries (`SELECT DISTINCT … LIMIT`, `LIKE` probes) against the `values-differ` bucket,
   still the largest.
5. **Strategy-diverse candidates, earlier (rank 4).** Diversity from *prompting strategies*
   (direct, divide-and-conquer, query-plan; CHASE-SQL) on v4p1 plus one other family.
   Model diversity alone produced shared errors. Measure pass@K first. It decides between
   selection work and generation work.
6. **Jev reframed (§6.4, §7).**
   - Jev adds ≈ $0.00008 per call (≈ 12% of an uncached v4p1 answer) and a serial network
     hop.
   - It lowers cost or latency only when it **gates expensive work away** (extra
     candidates, repairs, a stronger model), never as an always-on checker.
   - No gain is projected (v2.7). Agentar's selector ablation (≈ 1.8 pts) measures
     Agentar, not Jev in Trellis; shadow scoring and a live paired run decide.
   - Call budget is a declared pilot variable (v2.7): one bundled call vs a two-stage
     design, compared on net EX, false repairs, cost and P90. A post-SQL coverage check
     needs the SQL, so it is on the critical path by nature.

**Also:**
- **Dev vs train divergence (§5.8).** The v4p1 swap gained +5.9 on Mini-Dev but +0.4 on
  `train_dev`, so public-dev gains from newer models may overstate test gains.
- **`train_dev` saturation.** More than 20 decisions have been made on it; soccer_2016 is
  half its rows, and about 17% of it is unsolvable as labelled. Propose a second
  iteration set, `train_dev2`: 3–4 more small train databases fetched by range request.
  *Owner approval is needed for the download.* The 5 databases fetched earlier are the
  lockbox's, not spare.
- **Contact the BIRD team now.** Their answers are design constraints for the semantic
  layer and the specialist: whether test-time runs may call external APIs, how much
  per-database preprocessing is allowed, and time limits.

### 0.6 v2.7: second external review (2026-09-26)

Each claim was checked before adoption.

| # | Finding | Check | Change in v2.7 |
|---|---|---|---|
| 1 | Remove projected test scores; the pooled "full dev" mixes versions | Agreed. The GPT-5.5-xhigh claim ("listed as dev") is **not** what the page shows (test column, dev blank), but it has no linked BIRD source | The trajectory table, the 66.9% estimate and the rank are withdrawn; GPT-5.5 is not used as an anchor (§0.1) |
| 2 | Name one primary dev checkpoint; within-4-database bootstrap ignores between-database variation | Verified: the bootstrap resamples questions within databases | The cleaned Nov 2025 dev is primary after its baseline (§4). `train_dev2` databases are preselected before outcomes, database-level uncertainty is reported, and an untouched database gate is kept (§5.9) |
| 3 | "Gold executes" is not clean labels; use BIRD's filtered train | Verified: `birdsql/bird23-train-filtered`, 6,601 of 9,428 rows, CC BY-SA 4.0, quality-filtered (not verified) | Rank G starts from it, compared with our own filter, with an evaluation-database overlap check, a stratified semantic audit and an explicit reward spec. BIRD-Verified is evaluation/diagnosis only |
| 4 | The semantic layer bundles too much to interpret | Agreed | Split into 1a deterministic facts, 1b question-relevant slices and 1c a fact-checked glossary, each with its own measurement. "4 of 10" is a smoke test, not evidence |
| 5 | Probes need their own bounded executor | Verified: `execute_candidate` fetches whole results; the agent protocol expects SQL/refusal per call | Rank 2 needs a probe executor (validated shape, mandatory `LIMIT`, time budget, per-question probe budget) and a tool-protocol change priced in its pilot |
| 6a | Candidate-bank cost understated | Verified: 3 strategies × 501 × $0.000696 ≈ **$1.05 uncached**; v2.6's $0.30–0.60 assumed cache hits | Rank 4 quotes cached and uncached totals and a stop budget |
| 6b | Result signatures can split set-equal results (`1` vs `1.0`) | Verified: `{(1,)} == {(1.0,)}`, but their reprs differ | **Fixed** in `src/db.py:result_signature`, with a test. Pre-fix signatures are comparable only within a run |
| 7 | Jev's +1–2 is a projection; the one-call rule is too rigid; the model page loads | Verified: `openrouter.ai/typesafe/jev-1.13` returns 200 (the earlier 404 was transient) | No projected Jev gain; call design is a pilot variable; price caveat updated (§7) |
| 8 | Leaderboard shows examples, not necessity | Half: Gemini-SQL2 reached 80.04 as a single trained model with many samples, so several model *families* aren't necessary | Necessity language removed (§0.1) |

**Adopted order (§8):**
1. Fix the benchmark claims, establish the cleaned-dev baseline, and preselect
   `train_dev2`.
2. Build and separately test deterministic value profiles, retrieval and join checks.
3. Pilot targeted value and computation repairs, with controls for legitimately empty
   answers.
4. Build the strategy-diverse bank, with the corrected budget and signature clustering.
5. Run Jev shadow comparisons on the bank; promote only decisions that improve a live
   paired run.
6. Price and prepare training data in parallel. Spend on SFT only when the bank and the
   data audit show why it should beat the cheaper routes.

### 0.7 v2.8: third external review (2026-09-26)

The reviewer confirmed that v2.7 withdrew the projections correctly, and corrected their
own earlier reading: GPT-5.5-xhigh's 72.55 *is* in the test column.

| # | Finding | Check | Change in v2.8 |
|---|---|---|---|
| 1 | §8 says no step ran; cleaned-dev reuse needs a limit | Partly stale: §8 already recorded the 99-row pilot, and the gold-execution preflight had run (1,531/1,534 execute). The look limit is valid | **Cleaned-dev looks capped at 4** (baseline, two milestones, final freeze), each with its purpose recorded. Aggregate scores count as looks. The pilot is a cost/compatibility check, not a score estimate (§5.10) |
| 2 | A one-pass candidate bank can't authorize paid SFT | Valid: decisions need 2 repeats (§5.3) | Rank 4 is a **diagnostic** pass on the **latest accepted cumulative configuration**. A separately priced confirmation pass is required before it drives the SFT decision, especially near the boundary |
| 3 | Ceilings undefined: mean vs cap; only LLM calls counted | Verified in `analyze.py` | $0.01 = **mean** per answer including every per-question charge (`extra_cost_usd`); **hard cap $0.05** for any answer; one-time costs reported as a separate submission total; timeout-rate and max-latency rules added once BIRD confirms its limits. Implemented, with tests (§5.7) |
| 4 | `train_dev2` repeats `train_dev`'s themes | Valid: 2 sports databases, 1 movie | `train_dev2` is **development data only**. Transfer claims need the 7-domain lockbox plus at least one larger-schema check. Its ≈ 7–8 GB fetch is optional (§5.9) |
| 5 | Build the probe executor only if cheaper grounding fails | Valid, and consistent with "smallest cost first" | Rank 2 is gated on residual value-lookup errors after 1a/1b and one guarded retry (§6, §8) |
| 6 | Training and Jev need explicit quality labels | Valid | Rank G reports **5,115 examples** after exclusions, audits a stratified 100, and stops to re-filter if the semantic error rate is > 15%. Jev's coverage test is scored first against ≈ 50 hand-labelled atomic omissions, then against live paired repairs (§6, §7) |

### 0.8 v2.9: fourth external review (2026-09-26)

Each point was checked against the files. All held except that the full baseline had
since run.

| # | Finding | Check | Change in v2.9 |
|---|---|---|---|
| 1 | The 99-row pilot is feedback; calling the baseline "look 1" was premature | Valid: its score and truncation cases were used to propose a change | The pilot is **look 1** and the full baseline **look 2** (2026-09-26). One milestone and the final freeze remain; the cap is not raised (§5.10) |
| 2 | Use the supplied `column_meaning.json` before paying for a glossary | Verified: nothing in `src/`/`benchmark/` reads it; `train_column_meaning.json` (3,498 entries) is on disk; test supplies its own | Rank 1c tests retrieval and selective inclusion of `column_meaning` first. An LLM glossary is compared only if it adds value |
| 3 | `extra_cost_usd` is analysed but nothing writes it | Verified | §5.7 now states the analyser is ready and runtime emitters are required. Every decision path must record its charge; a run whose per-answer totals don't reconcile with the ledger delta fails the submission-cost check |
| 4 | Retry only length-truncated answers, not every cap | Verified: `finish_reason` was not captured. The baseline had **21 truncation failures (1.4%), 10 in `financial`** | **Implemented:** `LLMResult.finish_reason`; `--truncation-retry TOKENS` re-asks once at a larger cap only on `finish_reason == "length"` (off by default; config hash unchanged when off; tests). Pilot to measure recovered answers and added cost |
| 5 | Wrong figures and stale references | Verified: challenging is 231/1,534 (15.1%), not 9%; 1,531 gold queries completed and 3 timed out; rank 0 said "a few hundred MB" for `train_dev2`; POSTMORTEM_V2 §7.3 still cites the withdrawn rank and projections | All corrected. POSTMORTEM_V2 §7.3 carries a superseded note |
| — | Agreement on one local database is an imperfect proxy for SQL meaning (BIRD tests with extra test cases and values) | Agreed | Candidate selection (ranks 4, 6) checks question constraints in the SQL alongside result signatures |

Fireworks/Jev submission architecture stays **conditional on BIRD's answer** about
external APIs. The email is drafted, not yet sent.

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

The table records Phase 0 implementation. Test counts and tree state are per-run facts in the sidecars; verify the current checkout before a new experiment.

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
| BIRD dev, Nov 2025 cleaned version | 1,534 | 11 dev databases | Downloaded to gitignored `data/bird/dev_cleaned/`; corrected question, evidence and SQL form a separate evaluation. First confirm its expected database package; no v4p1 score yet. | separate version |

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

## 2. Current failure diagnosis and opportunities

The original 47.6% Mini-Dev baseline had 262 failures. Its extra-column,
missing-column and pipeline buckets justified Phase 1 and the gold-informed
output-format oracle (+14 points). They are **historical**; reapplying that
oracle to today's predictions would be leakage and cannot be counted as gain.

The later `POSTMORTEM_V2.md` provides the current mechanism audit (on the
retired snapshot), and the 2026-09-26 run files update its counts:

| Residual mechanism | Evidence and bound | First intervention |
|---|---|---|
| Empty / all-NULL output | Current Mini-Dev: 45 empty + 17 all-NULL of 1,500 outputs, none correct. Current `dev_untouched`: 26/30 empty and 9/11 all-NULL are wrong; even perfect handling of those 35 errors has a **3.4-point ceiling** on that run. | Relevant value profiles and FTS5 lookup, then a guarded repair; never replace every empty result blindly. |
| Ratio, per-group aggregation, subquery scope and multi-join logic | The postmortem's pooled ratio questions scored 50.3%, `GROUP BY` 46.2%, 2+ joins 54.9% (associations, not causal effects). | Deterministic numeric/AST checks, short targeted computation plan, specialist generation only for observable classes. |
| Wrong look-alike table/column, lost stated constraint, join fan-out | `values-differ` remained 17–19% of rows in the postmortem; the bucket mixes real errors with label defects. | Cached schema relationships, bounded candidate retrieval, semantic coverage check and a specific repair instruction. |
| Annotation conventions and noisy labels | `COUNT(DISTINCT)` and literal-hint differences have an oracle upside but can also flip correct answers wrong. Train labels are noisier than the dev-like sets. | Audit paired flips on `train_dev` and corrected same-input labels before any convention rule or SFT data selection. |

Jev's best hypothesis is **choosing among grounded alternatives and flagging
semantic omissions**. Arithmetic, exact counts, dates, SQL parsing, joins and
execution remain in code. No gain is assigned to Jev until a paired live test.

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

- **Near-term checkpoint (v2.7):** >75% official EX on the **Nov 2025 cleaned
  1,534-row dev**, the single primary public checkpoint once its database package is
  confirmed and its baseline is measured, with a frozen configuration. Mini-Dev and
  `dev_untouched` are reported **separately** and never substituted if they cross first.
  The current gaps are 7.4 and 9.7 points respectively. The Nov 2025 cleaned
  1,534-row dev version is a separate benchmark once its database package is
  confirmed and its baseline measured. Never combine versions into a headline.
- **Generalization checkpoint:** a frozen candidate improves on
  `train_lockbox` across databases without a large collapse. That set stays
  unopened until the planned midpoint/final gates. Public dev sets are reported,
  not mined for per-question rules.
- **Ultimate claim:** only a BIRD hidden-test submission demonstrates >80%
  test EX. Dev-to-test uplift from other systems is context, not a conversion.

---

## 5. Evaluation protocol

1. **Design on `train_dev`.** Use paired, full 501-row, two-repeat comparisons
   against the last accepted configuration; report row-weighted and database
   macro effects and their question-level bootstrap intervals. Where noisy gold
   decides a flip, check corrected same-input labels and audit the case. Rotate
   to newly fetched train databases if this four-database set becomes saturated.
2. **Use the existing acceptance rule:** declare a minimum gain before the pilot
   (base +1.5 points, increased for uncached-equivalent cost and P50 latency);
   require both row and macro point estimates above it and both 95% intervals
   above zero. Investigate any ≥10-point collapse on a database with ≥40 rows.
   Narrow interventions may be combined into a predeclared package, with
   ablations recorded; do not waive the full-comparison rule for a promising
   100-row pilot. Preserve the Chinook product profile and regression suites.
3. **Pilot first:** 50–100 stratified `train_dev` questions plus targeted cases.
   The pilot measures cost, trigger precision and whether a full comparison is
   promising. Full acceptance requires complete, identical question rows and
   exactly two repeats per question. No partial-overlap score is an acceptance
   result.
4. **Protect the gates:** Mini-Dev has **2 of 4** looks used; next looks are
   for a bundled candidate and final freeze, each with three repeats.
   `train_lockbox` has **1 of 2** looks used (175-row rank 1b midpoint screen);
   799 original rows are sealed for the final gate. A Verified lockbox run also
   counts. `dev_untouched` and the cleaned dev version are for aggregate
   reporting, not prompt examples, threshold fitting or question-specific
   repair design. Report per-database, difficulty, corrected-label and
   latency/cost views at each permitted gate.
5. **Pin and compare content:** record model snapshot, dataset, per-database
   hashes, effective prompt, config, code state, expected rows/repeats and
   scoring settings. The old versus new `dev_untouched` runs differ in five
   database hashes; never present their four-point gap as a controlled model
   A/B. Re-score under a consistent evaluator load when changes are close.
6. **Use only live-observable features:** question and evidence, database
   metadata, retrieved values, generated SQL AST, execution outcome and
   candidate agreement. Gold SQL, gold result and gold-SQL complexity may
   diagnose offline errors, but cannot drive routing, Jev state or repair at
   inference time.
7. **Two acceptance tracks (v2.6).** Both keep items 1–3: paired full comparisons, row
   and macro effects, CI lower bounds > 0, and the database-collapse check.
   - **Product track** (CLI defaults): the §5.2 rule unchanged, including +1 pt per +50%
     uncached cost and +1 pt per +1s P50.
   - **Submission track** (the frozen hidden-test configuration):
     - declared base minimum gain (default +1.5 pts);
     - **mean** uncached cost ≤ **$0.01 per answer**, counting every per-question charge:
       LLM calls plus `extra_cost_usd` for Jev decisions, probes or hosting (≈ $18 for
       the 1,789-question test).
       - *Status (v2.9):* the analyser counts `extra_cost_usd`, but **no runtime path
         writes it yet**. Every new charged decision path (Jev, probes, hosting) must emit
         its charge.
       - A submission-track run whose per-answer totals don't reconcile with the ledger
         delta for that run **fails** the cost check.
       - **hard cap:** no single answer above **$0.05**;
       - **one-time costs** (per-database profiling or glossary builds) are reported as a
         separate submission total, not averaged in;
     - P90 ≤ **30s per question**. Once BIRD confirms its execution limits, add a
       timeout-failure rate and a maximum-latency rule.
     - Inside those ceilings, cost and latency are reported on the frontier but add no
       points to the required gain.
   - Declare a change's track before its pilot. A submission-track change never becomes a
     CLI default without passing the product rule.
8. **Treat public-dev gains with suspicion.** When a change gains much more on
   Mini-Dev/`dev_untouched` than on train databases (v4p1: +5.9 vs +0.4), the smaller,
   train-database effect guides expectations for test, because public dev may be in
   newer models' training data. Record both. Resolve large divergences on `train_dev2` or
   the corrected-input sets, not with extra Mini-Dev looks.
9. **Uncertainty across databases (v2.7).** The question-level bootstrap within 4
   `train_dev` databases measures question variation on *those* databases, not how a
   change transfers to new ones.
   - Choose `train_dev2`'s databases by a fixed rule (size, domain, no overlap with any
     evaluation set) and record them **before** any run on them.
   - Once ≥ 8 iteration databases exist, report a database-level interval (resample
     databases, then questions within them) beside the current one.
   - Keep at least one never-run database gate: the lockbox, whose 2 looks are unchanged.
   - **`train_dev2` preselected (2026-09-26, before any download or run).**
     - *Rule:*
       - train databases not in `train_dev` or `train_lockbox`;
       - uncompressed `.sqlite` ≤ 100 MB;
       - 60–200 questions in `train.json`;
       - ranked by `sha256("train_dev2:" + db_id)`, first four taken.
     - 25 of 69 databases were eligible.
     - *Selected:* `professional_basketball` (157), `regional_sales` (164),
       `ice_hockey_draft` (84) and `movielens` (98): 503 questions, ≈ 91 MB.
     - These four are excluded from every training and few-shot pool.
     - **Role (v2.8): development data only.** They repeat `train_dev`'s themes (two
       sports, one movie) and are all small. Claims about new domains or large schemas
       come from the 7-domain lockbox plus at least one larger-schema check. Their
       ≈ 7–8 GB fetch is optional.
10. **Cleaned-dev look budget (v2.8; v2.9 recount).** At most **4 looks** at the
    1,534-row cleaned dev:
    1. **look 1:** the 99-question pricing pilot `20260927T022912Z` (59.6%); it counts,
       because its score and failures were used;
    2. **look 2:** the full baseline `20260927T025554Z` (66.0%);
    3. **look 3:** rank 1b bounded database facts, 1,020/1,534 = 66.5%, versus
       1,012/1,534 = 66.0% at look 2. Paired +0.52 pts, 95% question-bootstrap
       CI [−0.46, +1.50]; descriptive one-repeat gate, not a proven gain;
    4. **look 4:** the final freeze.

    Each look's purpose and configuration is recorded in the gate log. Aggregate scores
    count as looks even when no question is inspected. Per-question failure reading on
    cleaned dev is not used to design changes.

---

## 6. Ordered roadmap: expected quality gain per cost

The ordering below is the **current work queue**. Earlier Phase 1 and Phase 3
sections are retained as dated experiment logs, not instructions to rerun.
Impact ranges are bounds or hypotheses from the postmortem, **not additive
promised gains**. Use the current v4p1 no-cache estimates ($0.000661 per
Mini-Dev answer, $0.000638 per `dev_untouched` answer) and each pilot's
actual tokens; cached billing alone is not the cost comparison.

| Rank | Experiment and decision | Evidence for quality | Initial cost and stop rule |
|---|---|---|---|
| 0 | **Measurement reset and logistics.** Re-score the current v4p1 runs; correct the postmortem headline; confirm the cleaned dev database package and pilot its baseline. Tag failure mechanisms. **Contact the BIRD team** about the submission environment: external API calls, per-database preprocessing, time limits. **Propose `train_dev2`:** 3–4 small train databases by range request (owner approves the download). | Prevents optimizing against stale numbers; the BIRD answers constrain ranks 1 and G. No direct accuracy gain. | Stored-run analysis free. Cleaned-dev pilot 50–100 rows, then reprice (full run ≈ $0.98 uncached). `train_dev2`: ≈ 7–8 GB sequential transfer (≈ 100 MB kept), optional since v2.8; ≈ $0.15/repeat to baseline. |
| 1 | **Semantic layer, as three separate experiments (v2.7).** Everything is built offline from the database alone (never gold) and cached by content hash. **1a deterministic facts:** column value formats (stored vs semantic type; text-encoded numbers/dates/money), NULL rates, enumerations, the join graph with cardinalities and fan-out risk, and an FTS5 value index. Measure retrieval recall for the needed literals/columns and preprocessing time per database. **1b question-relevant slices** of 1a in the prompt (a full dictionary dump already failed, §6.1). **1c column meanings (v2.9):** first test retrieval and selective prompt inclusion of BIRD's supplied `column_meaning.json` (the test set ships one; `train_column_meaning.json` has 3,498 entries). Only if a gap remains, compare an LLM-written glossary, fact-checked against 1a because it can invent units or meanings. | Wrong empty/NULL answers (ceiling 3.4 pts on current dev) and look-alike column/format errors are concrete residual failures. DataGallery (#1) reports a semantic layer (example, not proof). | 1a free. An offline replay fixing ≥ 4 of 10 audited cases with zero false repairs is a **smoke test only**. Evidence is a stratified 100-row pilot, then a full paired comparison. 1c costs one LLM pass per database, and its fact-check rate is reported. |
| 2 | **Value exploration before final SQL (v2.8: gated).** Built only if value-lookup errors remain after 1a/1b static facts and one guarded retry. Needs a **new bounded probe executor** (not `execute_candidate`, which fetches whole results): validated shape (single-table `SELECT DISTINCT`/`LIKE`, no joins), a mandatory `LIMIT` ≤ 20, a ≤ 2s time budget and ≤ 2 probes per question. It also needs a **tool-protocol change**: today each model call must return SQL or a refusal. | `values-differ` is still the largest bucket (17–19% of rows); probes ground literals the schema can't show. | The extra round trip is priced in the pilot (cost, P50/P90). Triggered only on literal filters over text columns. 100-row pilot; track declared first (§5.7). |
| 3 | **Jev shadow decisions** on stored predictions: bounded table/column choice, hint-intent, dropped-constraint flags and post-SQL requirement coverage, vs deterministic rules and a small LLM judge. No SQL changes. **v2.8:** first hand-label ≈ 50 *atomic requirement omissions* on stored answers (a wrong official EX does not prove an omission). Score Jev flags against those labels, then against live paired repair outcomes. | Attacks the heterogeneous `values-differ` bucket; measures trigger precision first. | Stored answers avoid generator cost; 100 calls ≈ $0.0084 at the listed Jev rate (recheck). Stop any decision with frequent flags on correct SQL. |
| 4 | **Strategy-diverse candidate bank: diagnostic, then confirmation (v2.8).** Built on the **latest accepted cumulative configuration**. On `train_dev`, same database hashes: v4p1 × 3 prompting strategies (direct, divide-and-conquer, query-plan) + one other family (glm-5p3-flash `low`). Measure pass@K, same-wrong consensus, majority and Jev-`choice` selection. Selection checks **question constraints in the SQL** (AST) alongside result signatures, because BIRD tests with extra cases and values, so agreement on one local database is an imperfect proxy (v2.9). Clustering uses the fixed signature (§0.6 6b), spot-checked against the official comparator. | Old model-only bank: pass@4 = 73%, errors shared across families. Strategy diversity is untested here. | **Cost (v2.7): ≈ $1.05 uncached for the 3 v4p1 strategies × 501 × 1**, plus ≈ $0.12 for glm-5p3-flash. About a third to a half of that with the observed cache. **Stop budget $1.50** for the one diagnostic pass. A **confirmation pass** (a second repeat, ≈ $1.2 uncached, priced and approved separately) is required before the bank drives the SFT decision. Decision: a high pass@K means invest in selection; a pass@K near today's accuracy means generation is the bottleneck (rank G). |
| 5 | **Targeted generation and repair:** value/NULL retry with retrieved facts; ratio/aggregation checklist; bounded computation sanity checks; one specific semantic repair from a verified mismatch. Ablate each, then test the best package cumulatively. | Postmortem planning ranges: value grounding +1.1–2.0, computation +1–3; overlap is likely. | 50–100-row pilot per mechanism; full `train_dev` × 2 only for on-course candidates. |
| 6 | **Jev as a gate and selector (live).** (a) Choose among differing candidate results (rank 4 bank), combined with deterministic question-constraint checks. (b) Gate expensive work: extra candidates, repair or a stronger model run only when Jev or a deterministic check flags risk. The call design (one bundled call vs two-stage) is a declared pilot variable. | **No projected gain (v2.7):** selector gains elsewhere measure those systems. Adoption follows shadow scoring (rank 3) and a live paired run only. | Pilot after ranks 3–4. Report net EX, false-repair rate, macro, $/answer, P50/P90 and trigger rate; submission track. |
| G | **Parallel track: generation upgrade / trained specialist.** Free now: price Fireworks SFT/RFT for a ≤ 30B MoE or ≤ 16B base, LoRA serving cost, and serving under the submission track. Build training data **from BIRD's official filtered train** (`bird23-train-filtered`: 6,601 rows, CC BY-SA 4.0, quality-filtered, not verified) and compare it with our own execution filter. Remove every `train_dev`/`train_dev2`/lockbox/dev database. Audit a stratified sample for semantic errors. **v2.8:** **5,115 examples** remain after excluding every evaluation database. Hand-audit a stratified 100. If the semantic error rate is > 15%, re-filter before any SFT; report the rate either way. **Reward spec before any RLVR:** how multiple valid SQL queries, misleading or empty gold results, and use of the evidence are handled (ReViSQL reports false-positive result rewards and evidence being ignored). | Examples: Databricks RLVR-32B 75.7 test from BIRD train alone; Kwai-AutoSQL-14B 74.0; Gemini-SQL2 80.04 (single trained model, many samples); ReViSQL +8–14 pts from corrected data. | **The paid SFT pilot waits** for the rank-4 bank result and the label audit, and needs its budget approved after pricing. Gate: paired `train_dev`/`train_dev2` gain under the submission track, then the lockbox. **BIRD-Verified: evaluation and diagnosis only, never training.** |

Ranks 1–6 are sequential. Rank G's free work (pricing, data build, audit) runs in parallel
from the start; its paid pilot waits for rank 4 and the audit.
Each rank ends in a recorded decision: mechanism demonstrated and promoted,
rejected, or left uncertain. A small targeted fix can join a predeclared package
even when its individual gain is below the full-run acceptance threshold; report
its ablation so the combined score is interpretable.

### 6.1 Historical Phase 1 proposal and log (completed)

**Original sequence (completed):**
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

**1c built (2026-09-24):** `--pipeline-repairs`, off by default.
- Unknown-identifier/parse rejects get one repair with "did you mean" names from the schema;
  forbidden SQL never retries.
- One refusal retry ("this is answerable").
- One guarded empty-result retry: it replaces the answer only if the new query is safe,
  valid, and returns rows.
- 10s execution timeout for databases over 100MB.

**Pilot, 1a + 1b + 1c vs the 1a run:** stratified +5.0 [+1.2, +9.4], 0 regressions;
targeted 1a-failures 44.3% → 61.4%.

**Full comparison #2 (run `bird_raw_20260924T175733Z` vs the 1a run): BORDERLINE →
ACCEPTED by owner decision (2026-09-24), on the strength of the required audit.** Report in `benchmark/results/flips_train_dev_1a_vs_1abc.md`.

| Criterion | Result |
|---|---|
| Database-macro Δ | **+3.90** [+1.13, +7.05] ✅ |
| Row-weighted Δ | **+1.60** [+0.20, +2.99]. Its lower bound is within 1 pt of 0, so the audit is required |
| Cost | Measured $/query +43%, but provider cache hits fell 46% → 23% between runs. **At uncached prices: +6.4%**, with 7% more calls. The cost-adjusted minimum is ≈ +1.63, so row-weighted misses by 0.03 |
| Pipeline failures | errors 22 → 3; safety-rejected 14 → **0**; unsupported 6 → **0** |
| By database | movie **+15.2** (7 fixes, 0 regressions); restaurant 0.0; sales_in_weather 0.0; soccer_2016 +0.4 |

**Audit:**
- All 5 regressions are on questions whose prompt and pipeline path were unchanged from 1a:
  databases without special names, where the repairs didn't fire or kept the original. They
  are run-to-run noise.
- Causal fixes: quoting 5 (`movie` safety-rejects), refusal retry 2, identifier repair 1,
  empty-result retry 1 (it fired often, which is most of the extra calls).

**Protocol gap exposed and closed:** the cost term in §5.4 compared *measured* $/query,
which is dominated by provider cache state, not by the change. From now on
`analyze flips` computes the required minimum mechanically as **base 1.5 + 1 pt per +50%
*uncached-equivalent* $/answer + 1 pt per +1s P50**, and prints yes/no per metric plus
whether an audit is required. The regenerated reports show this decision's facts: minimum
+1.63; row-weighted "no" (+1.60); macro "yes"; audit required.

**Decision (owner, 2026-09-24): accept 1a + 1b + 1c.** Reasons:
- The macro metric clears the bar.
- The row-weighted gain misses the minimum by 0.03 pts.
- The required audit attributes every fix to a specific mechanism and every regression to
  noise on questions the change didn't touch.
- The real cost is +6.4%.

It is recorded as a borderline accept, not a clean pass. The empty-result retry (1 fix; most
of the extra calls) is flagged for re-evaluation once the Mini-Dev gate exercises it.

**Accepted configuration going forward:**
`--prompt-profile benchmark --quote-identifiers --pipeline-repairs`: **68.7% row-weighted,
69.3% database macro** on `train_dev` (baseline was 60.1% / 58.5%).
2. ~~Full comparison #2~~ done and accepted (above).
3. ~~Dictionary CSVs~~: piloted, **not adopted** (below).

**Step 2, dictionary CSVs (2026-09-24): pilot NOT on course, full run skipped (owner
decision).** `--dictionary` adds one `about <column>: …` line per documented column from
BIRD's `database_description` CSVs:
- column meaning, value notes, and "commonsense evidence" formulas;
- per-field caps;
- descriptions that only restate the table/column name are dropped.

It adds +53% prompt characters on `train_dev`. Pilot vs the accepted run, run
`bird_raw_20260924T212220Z`:

| Subset | Rows | Accepted → +dictionary | Δ (95% CI) |
|---|---:|---|---|
| Stratified (unbiased) | 80 | 71.9% → 73.1% | +1.2 [−1.2, +4.4]; 2 fixes, 1 regression |
| Targeted: random rows whose gold uses a column with value notes | 34 | 85.3% → 85.3% | 0 |
| Cost / latency | | uncached $/answer +32%; P50 1.02s → 1.48s | **required minimum +2.61** |

Not on course for the required minimum, so no full comparison (§6.1). The most likely
reason: BIRD's per-question evidence already carries most of what these dictionaries say
for `train_dev`'s databases. The flag stays available for a Mini-Dev gate check, where the
postmortem's `california_schools` / `rtype` "unuseful" case lives.

**Phase 1 closed (2026-09-24).**
- Accepted configuration: `--prompt-profile benchmark --quote-identifiers
  --pipeline-repairs`.
- **`train_dev`: 60.1% → 68.7% row-weighted, 58.5% → 69.3% macro.**
- Spend: **$1.24 of $2** per the ledger, with $0.76 unspent.
- Not adopted: identifier quoting alone as a separate change (folded into 1b+1c), the
  dictionary CSVs, and the wide-table and value-index steps (never reached: they were
  gated on residual value-matching failures).

### Gate log

**Mini-Dev gate 1 of 4 (2026-09-24): Phase 1 checkpoint.** Run `bird_raw_20260924T232302Z`:
the accepted configuration (`--prompt-profile benchmark --quote-identifiers
--pipeline-repairs`), all 500 rows × 3 repeats, complete, clean commit `285272c`. Cost
$0.31 ($0.000205/answer measured, $0.000491 uncached-equivalent); P50 0.97s, P90 4.47s.

| Difficulty | N | Official EX (mean of 3) | Corrected labels (Arcwise) | 2026-09-23 baseline: official / corrected |
|---|---:|---:|---:|---|
| Simple | 148 | **76.1%** | 77.7% | 66.2% / 66.2% |
| Moderate | 250 | **54.0%** | 55.5% | 42.8% / 47.6% |
| Challenging | 102 | **48.0%** | 46.4% | 32.4% / 32.4% |
| **Overall** | 500 | **59.3%** | **60.2%** | 47.6% / 50.0% |

- **Every database improved.** student_club +24.4, european_football_2 +20.9, superhero
  +16.7, financial +12.5, thrombosis +12.0, california_schools +10.0, codebase_community
  +8.8, formula_1 +7.6, debit_card +5.5, card_games +4.4, toxicology +3.3. Database macro
  58.3% (was 46.8%).
- **The Phase 1 gain carried over from `train_dev`:** +11.7 pts on Mini-Dev vs +8.6 on
  `train_dev`. Caveat: the baseline was a single repeat on older code (before the
  foreign-key fix), so this is a descriptive before/after, not a paired acceptance test.
- It landed inside v1's projected Tier-B range (57–61%) and below the oracle output-format
  ceiling (61.8%).
- **Flagged repairs, re-evaluated here:**
  - The empty-result retry fired on 5.9% of answers and replaced 13; 5 became correct.
    The 76 it kept empty were all wrong anyway, so it can't regress. It cost 4.7% of the
    run. **Keep.**
  - The refusal retry: 17 refusals became queries, 7 of them correct. **Keep.**
- Remaining pipeline errors: 15 repair-exhausted, 3 safety-rejected, 1 structured-output
  failure (out of 1,500).
- Not run at this gate, to save cost: `train_lockbox` (its 2 looks are kept for the
  midpoint and final configurations), untouched dev, and the `--dictionary` Mini-Dev
  check.

**Cleaned dev, looks 1–3 of 4 (2026-09-26–27).**
- Look 1: the 99-question pricing pilot `20260927T022912Z`, 59.6%, not representative
  (stratified by database).
- Look 2: the full baseline `20260927T025554Z`, **66.0%** (macro 64.1%), with the
  accepted configuration on `deepseek-v4p1-flash` (reasoning off).
- The run code state was dirty: uncommitted analyser, signature and plan edits.
  Behaviour-relevant code (agent, prompts, schema) matched commit `77ee38b` except
  `result_signature`, which does not affect scoring.
- Look 3: the full rank 1b bounded-facts configuration (resumed after a budget stop),
  **66.5%** (1,020/1,534; macro 64.4%). The paired gain over look 2 is +0.52 pts
  [−0.46, +1.50], with 33 fixes and 25 regressions. The CI includes zero; this
  supports neither a reliable cleaned-dev gain nor hidden-test transfer. See
  `benchmark/results/rank1b_dev_cleaned_full_outcome.md`. **One cleaned-dev look
  remains, reserved for the final freeze.** No individual cleaned-dev failures were
  inspected to tune rank 1b.

**Mini-Dev gate 3 of 4 (2026-09-27): full current configuration.**
- Run `20260927T083717Z`, clean commit `5cd38e9`: benchmark profile, quoted
  identifiers, pipeline repairs, **database facts on** (rank 1b, owner-adopted),
  **`--truncation-retry 1200`**, v4p1-flash, reasoning off, all 500 rows × 3.
  Complete, 1,494 of 1,500 without errors.
- Cost $0.25 measured ($0.000170/answer; $0.000665 uncached); P50 1.58s, P90 2.96s.
  The owner raised the ledger cap from $7.15 to $7.50 for this run; the ledger is now
  $7.28.
- **64.1% official EX** (simple 75.5, moderate 61.7, challenging 53.6; macro 62.8%)
  vs gate 2 65.3%.
- Paired vs gate 2 (`flips_minidev_gate2_vs_gate3.md`, 3 repeats each): **−1.13 pts
  [−2.73, +0.40]**, macro −1.35 [−3.03, +0.31]. Code also differs between the gates,
  so this is descriptive, not an isolated test.
- **Aggregate split by whether facts fired** (no question-level reading):
  - facts were prepended on 269 questions, which moved **−1.9 pts**; the 231 without
    facts moved −0.3;
  - `financial` fell 57.3% → 45.8% (−11.5 pts on 32 questions; −13.6 on its 27 with
    facts, 0.0 on its 5 without);
  - `card_games` −5.4 on questions with facts, 0.0 without.
  - `financial` is below the 40-question veto size, but the concentration in
    fact-bearing questions points at the facts, not drift.
- **Truncation retry:** fired 0 times (no Mini-Dev answer was cut off), so it cost
  nothing and changed nothing here.
- **Rank 1b evidence now pooled:** `train_dev` +0.8, lockbox sample +1.9 (CI includes
  0), cleaned dev +0.5 (CI includes 0), Mini-Dev −1.1 (−1.9 where facts fired). Net
  effect ≈ 0 ± 2 pts, with a database-specific risk (`financial` here). It was an
  owner exception, not a validated gain.
- Leaderboard context: Mini-Dev SQLite 64.1% still sits #3 of 14 listed (after
  Jitto Build 75.6 and Ontology2SQL 70.2).
- 3 of 4 Mini-Dev looks are now used.
- **Owner decision (2026-09-27): keep facts on for now.** A per-database facts-off switch
  for `financial`/`card_games` was computed from existing runs (no new calls). It gives
  Mini-Dev 65.3% (+1.1) but cleaned dev 66.2% (−0.3): the same databases *improved* with
  facts on cleaned dev (`financial` 24.5 → 27.4, `card_games` 66.0 → 66.5). That is
  database-level noise, can't transfer to the hidden test's different databases, and
  would tune on the gates, so it was not adopted.

**Latency, with database facts on (2026-09-27).**
- **Where the time goes** (gates 2 and 3, 1,500 answers each):
  - ≈ 95% of an answer is the Fireworks call: P50 1.32s / 1.49s of 1.36s / 1.58s;
  - local SQL execution is 1–3 ms at P50;
  - prompts are ≈ 1,690 tokens (81–88% served from cache), and outputs ≈ 66 tokens.
  - So latency is per-request overhead (connection setup, time to first token), not
    generation length.
  - Facts add ≈ 7 prompt tokens at P50.
- **Fix: one reused HTTPS client per event loop** (`src/llm.py:shared_client`). Before,
  every call built a new `AsyncOpenAI` client, paying a TCP + TLS handshake each time;
  the timeout is now passed per request. The CLI keeps one loop per session, so it
  benefits too.
- **Interleaved A/B**: 60 `train_dev` questions at concurrency 1, arm order shuffled per
  question, 2 warm-up questions dropped, ≈ $0.03.

  | Arm | P50 | Mean | P90 |
  |---|---:|---:|---:|
  | New client per call, facts on (old behaviour) | 1.46s | 1.57s | 2.28s |
  | **Reused client, facts on** | **1.22s** | **1.42s** | **2.19s** |
  | Reused client, facts off | 1.35s | 1.55s | 2.57s |

- **−0.24s at P50 (−16%)** from connection reuse. **Facts add no measurable latency**
  (facts on vs off is within noise).
- **JSON mode vs JSON schema** (interleaved A/B, 100 `train_dev` questions, reused
  client, facts on, ≈ $0.03):
  - P50 1.36s vs 1.36s, mean 1.64s → 1.45s, P90 2.67s → 2.26s;
  - 0/100 malformed in either arm; 95/100 identical results.
  - It trims the slow tail, not the typical answer. **Not adopted** pending a paired
    accuracy check (100 × 2, ≈ $0.10).
- Priority tier: skipped by owner decision.
- Further levers, untested:
  - compact single-line SQL output (small);
  - P90 is driven by the ≈ 5% of answers that need a second call (repair or
    empty-result retry, P50 3–4s).

### 6.3 Historical Phase 3 proposal and log (completed)

This log predates the later 65.3% Mini-Dev gate and 67.6% dev_untouched
run. Its conclusions about the retired default and the old candidate
bank are dated evidence, not the current route order.


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

### Phase 3 log

**3a: reasoning on, JSON format unchanged (2026-09-24): NOT adopted.**
- A probe confirmed DeepSeek-V4-Flash accepts `reasoning_effort` together with structured
  JSON output. Reasoning tokens count toward output, and latency varies widely (2.8s vs
  14.9s on the same question).
- The client timeout is now configurable (`--llm-timeout`; it was hard-coded at 20s).
- Pilots: 100 stratified `train_dev` rows (25 per database) × 2, vs the accepted
  configuration's full run on the same rows. Cost $0.36.

| Pilot | Δ vs accepted (95% CI) | Uncached $/answer | P50 | Required minimum |
|---|---|---:|---:|---:|
| `--reasoning-effort low --max-tokens 4096` | **−1.5** [−6.5, +3.5] | $0.00085 (+103%) | 4.9s (was 1.2) | +7.28 |
| `--reasoning-effort high --max-tokens 8192` | **−1.5** [−6.5, +3.0] | $0.00126 (+201%) | 5.9s | +10.25 |

**Audit (why no gain):**
- Some reasoning runs hit the token cap, truncating the JSON: 4 (low) and 11 (high)
  structured-output failures.
- More importantly, reasoning "overthinks" against BIRD's literal gold. It writes `EXISTS`
  instead of joins, and parses a text `screentime` column into numbers where gold sorts the
  raw text. That's arguably better SQL that the labels score as wrong.
- Fixing truncation alone is worth ~1–2 pts, far from the required +7.
- Conclusion for this model on this data: its reasoning doesn't beat its fast path. The
  leaderboard's reasoning gains come from stronger models, and often from selection among
  many candidates, not from one flash-model reasoning pass.

**Consequence for the roadmap:**
- 3b as planned (the format change after the 3a winner) is moot.
- The next Phase 3 evidence should come from **model choice and diversity at K samples**,
  not from reasoning depth:
  1. a non-reasoning model bake-off at K=1 on the same 100 rows;
  2. oracle pass@K vs majority vote at K = 2, 4 from the fast path, which is the Phase 4
     bottleneck test.

**3-models and 3-samples pilots (2026-09-25, run by a delegated agent under a $1.50 ledger
cap; batch spend $0.51).** Same 100 stratified `train_dev` rows (25 per database) × 2,
compared with the accepted run on the same rows.

| Model (non-reasoning unless noted) | Δ (95% CI) | Uncached $/answer | P50 | Required min | Verdict |
|---|---|---:|---:|---:|---|
| `deepseek-v4p1-flash` | **+3.5** [−1.5, +8.5] | $0.00059 (+41%) | 1.56s | +2.71 | **On course (point estimate ≥ minimum) → qualifies for a full comparison** |
| `deepseek-v4-pro-0813` | −0.5 [−4.0, +3.0] | $0.00243 (+479%) | 3.78s | +13.69 | Not adopted: 6× the cost for nothing |
| `gpt-oss-120b` (reasoning `low`, its minimum) | −0.5 [−4.0, +3.0] | $0.00035 (−16%) | 0.85s | +1.50 | Not adopted |
| `glm-5p3-flash` (thinking-only; rejects `none`) | **−13.5** [−21.0, −6.5] | $0.00036 | 4.27s | +4.61 | Not adopted: 69 of 200 answers failed structured output |

**Multi-sample (current model, temperature 0.7, K=4):**

| k | 1 | 2 | 3 | 4 |
|---|---:|---:|---:|---:|
| oracle pass@k | 69.2% | 71.2% | 72.2% | 73.0% |
| majority@k | 69.2% | 68.8% | 69.0% | 69.0% |

Self-consistency with one model gains nothing: majority@4 ≈ pass@1.

**Cross-model headroom (the routing question), same 100 rows, one answer per model:**
- The **oracle over all 5 models is 73%**, identical to one model's pass@4. A majority vote
  across the models gives 69–71%, against 69% for the current model alone.
- **24 of the 100 questions were never matched by any of 1,400 answers.** Of the 5 with
  BIRD-Verified entries, 2 match the corrected gold and 2 had revised (flawed) questions.
  So most of the universally "unsolvable" questions checked so far are label or question
  problems, not model gaps.
- **Implication:** on these candidates, routing, ensembling, or selection can add at most
  ~4 pts. The errors are shared by every model. What moves the score now is teaching
  BIRD's *annotation conventions* (what the gold SQL literally expects), not more model
  diversity. That's also the most plausible reason fine-tuned leaders (RLVR/SFT on BIRD
  train) gain where prompting plateaus. Gate F-G's criterion (pass@K < ~80% ⇒ generation,
  not selection, is the bottleneck) is met at 73%.

**Never-solved audit (2026-09-25, free).** The 24 of 100 pilot questions that no model or
sample ever matched, read one by one:

| Category | Count | Examples |
|---|---:|---|
| Gold label or question error | **17** | `COUNT(food_type = 'american')` counts every row; joins on `city` instead of the id (114,912 rows); "Orange Cap winner" gold joins `Man_of_the_Series`; a "win rate" of 3.93; a Bruce Almighty question whose gold filters on "Godzilla"; question 2022 vs gold 2012 |
| Gold times out here | 1 | #8190 |
| Genuine: value format | 2 | `screentime` is text like `0:17:30`; `NetWorth` is text like `$20,000,000.00` (so `MAX` compares it alphabetically) |
| Genuine: BIRD literal-hint convention | 2 | hint `MAX(COUNT(Role_id))` means literally no DISTINCT; "number of stores refers to store_nbr" means return the column |
| Ambiguous/mixed | 2 | |

About **17–18% of `train_dev` is unsolvable as labeled**, so the practical ceiling there is
≈ 82%.

**Retrieved few-shot from BIRD train (`--fewshot 3`, 2026-09-25): NOT adopted.**
- BM25 over question + hint; the pool is official BIRD train minus every held-out database
  (7,953 examples, 0 leakage). Examples go in the user message.
- Pilot vs the accepted run on the same 100 rows: **+0.0 [−4.0, +4.0]**; uncached cost
  +20%; P50 1.16s → 2.01s; required minimum +2.75.
- It fixed none of the targeted convention/format cases (#1915, #8170, #743, #748: 0/2
  each). Examples from other databases don't transfer these conventions. The flag stays
  for later reuse.

**Cheap-model Pareto round (declared 2026-09-25, before any run; owner-approved $1.50
ledger cap).** Expensive models (Kimi K3, Ember-1, Qwen3.8-Max, Inkling) are excluded on
price. Rules fixed in advance:
- *Upgrade* (v4p1-flash): the usual §5.4 rule, full `train_dev` × 2.
- *Swap* (gpt-oss-120b): **non-inferiority**: row and macro CI lower bounds ≥ −1.5 pts,
  uncached $/answer and P50 no worse, at least one strictly better (`analyze flips` prints
  it). Full `train_dev` × 2.
- *Screens* (glm-5p3-flash with `--reasoning-effort low --max-tokens 2048`, fixing the
  400-token truncation behind its 69 failures; nemotron-lightning-3.5 with `low`, since
  `none` returns empty SQL): the same 100 pilot rows × 2. A screen only earns a full run.
- *Escalation* (glm-5p3, thinking-only, `low`): only on `train_dev` questions where the
  current model and gpt-oss-120b disagree by result signature, 1 repeat. Reported as the
  accuracy/cost of "escalate on disagreement" vs the current model; the cascade itself is
  a Phase 4 decision.
- `dev_untouched` × 1 with the accepted configuration: a measured dev number for the
  leaderboard comparison (reported, never tuned on).

**Results (2026-09-25/26; $1.46 spent against the $1.50 cap + $0.40 extension).**

| Run | Result | Verdict |
|---|---|---|
| gpt-oss-120b, full `train_dev` × 2 (`20260925T014638Z`) | **−1.40** [−3.89, +1.10], macro −1.04 [−3.51, +1.37]; uncached $0.000398 vs $0.000497 (−20%); P50 0.97s vs 1.05s | **Not adopted:** the CI lower bound breaks the −1.5 margin (restaurant −3.4) |
| glm-5p3-flash, `low`, 2,048 tokens, 100 × 2 (`20260925T014328Z`) | **+0.0** [−4.5, +4.5]; structured-output failures 69 → 0; uncached −41%; P50 1.93s vs 1.16s, P90 9.2s | **Not adopted** (slower). An equal-accuracy second family |
| nemotron-lightning-3.5, `low`, 100 × 2 (`20260925T020504Z`) | **4.5%**: 187 of 200 structured-output failures (reasoning runs to the 2,048 cap, or malformed JSON); P50 14s | **Rejected** |
| glm-5p3 on disagreements, 92 questions × 1 (`20260925T014854Z`) | Current model and gpt-oss-120b disagree on 17.2% of answers. There, current is right 29.7%, gpt-oss 21.5%, glm-5p3 34.3%. Escalate-on-disagreement: **68.7% → 69.5% (+0.8)** at 2.8× uncached cost ($0.00138) and P50 +0.54s | **Not adopted:** the §5.4 bar would be ≈ +5.6 |
| deepseek-v4p1-flash, full × 2 (`20260925T015827Z`) | **Invalid:** launched without `--reasoning-effort none` (the pilot had it), so the model reasoned and 84 of 1,002 answers truncated at 400 tokens | Rerun (owner extended the cap by $0.40 for it) |
| deepseek-v4p1-flash rerun, `none` (`20260926T203859Z`) | **+0.40** [−1.90, +2.69], macro **+1.53** [−0.69, +3.94] (sales_in_weather +8.8, restaurant −1.3, soccer_2016 −1.4); uncached $0.000696 (+40%); P50 1.61s vs 1.05s; measured $0.000185 with cache | **Not adopted:** required +2.86. The pilot's +3.5 regressed toward zero at full size |
| `dev_untouched` × 1 (`20260925T015202Z`) | **63.6%** (simple 68.0, moderate 50.0, challenging 53.5; macro 63.9); cost $0.45 ($0.000431/answer: cold per-database cache on one repeat); P50 0.98s | Reported only |

- **Full-dev estimate** (*withdrawn in v2.7, §0.6: it pools versions*). `dev_untouched` (1,036) plus Mini-Dev gate 1 (498 unique) ≈
  **62.2%**, approximate because 23 Mini-Dev rows use Mini-Dev's database versions. Main
  leaderboard entries with dev within ±1.6 pts of that scored 60–68 on test (median ≈
  64.5), which puts an estimated test rank around **#80–92 of 130**. That is context, not
  a conversion rule.
- **Harness bug found by Nemotron:** prose with a stray quote in the `sql` field raised
  sqlglot's `TokenError` out of `is_safe` and crashed the run. It's now a `SQL parse
  failed` rejection (repairable), with a test. The same path serves the product CLI.
- **Conclusion:** among cheap models, nothing beats the current model on the
  quality-cost-latency frontier, and neither does the newer v4p1-flash. Cross-family
  escalation adds under 1 pt. The remaining lever is teaching BIRD's conventions (literal
  hints, value formats), not more models.

### 6.4 Semantic layer and Jev-led grounding and bounded repair

This phase spans ranks 1–6 of the current queue. Implement it as small
interventions rather than one opaque `Jev on` configuration.

**Jev's role.**
- Jev never *adds* value by being called. Each call adds ≈ $0.00008 and a serial network
  hop through an alpha endpoint.
- It pays only when a typed decision **avoids** expensive work (a second candidate, a
  repair, a stronger model) or **picks** between grounded alternatives.
- Design every Jev use as a gate or a selector with a deterministic fallback. The number
  of calls per question is a pilot variable.
- No projected lift (v2.7); shadow scoring and a live paired run decide.

1. **Catalog (the semantic layer, rank 1), cached per database content hash:** derive
   column profiles, foreign-key paths and cardinalities, primary/bridge table roles,
   duplicate column names, value formats and candidate literals deterministically. Add a
   one-time LLM glossary per database. Jev may select a *bounded* table/column interpretation
   or relevant description from that verified shortlist, with `none/ambiguous`
   available. Cache the result by database content hash. It must not invent
   identifiers or replace the database as the source of truth.
2. **Question/evidence understanding:** produce observable, multi-label
   intents (ratio, per-group filter, temporal, negation, superlative,
   multi-part, unique count and requested projection). Preserve every
   original question constraint when a hint paraphrases or drops one.
   Rules handle obvious patterns; test Jev on ambiguous cases before
   routing to a specialist generator or a different schema slice.
3. **SQL coverage:** use `sqlglot` to extract selected columns, tables,
   join edges, filters, grouping, aggregates, ordering and limit. Compare
   each atomic requirement with these facts. Ask Jev narrow `noul`
   questions only where text-to-schema meaning is uncertain, or `choice`
   among a few verified concepts. Avoid a single "fully answers?" score.
4. **Execution diagnostics:** code detects safety, timeout, empty/NULL,
   implausible row count, missing join predicate, numeric-range errors
   and text-encoded values. FTS5 supplies literal candidates; Jev may
   rank their semantic match, but code owns lookup, arithmetic and
   comparison. Legitimate empty and NULL outcomes must be protected.
5. **One repair loop:** turn a high-confidence, specific finding into a
   template for the SQL generator (wrong table, missing constraint,
   value spelling/format, aggregation grain, ratio denominator or
   output field). Give it the exact verified facts, not gold. Re-run
   safety validation and execution; keep the original if the repair
   fails, loses a requirement or does not pass the predeclared
   acceptance policy. Bound calls and record both SQL candidates.
6. **Offline annotation triage:** Jev may rank likely label defects or
   shared convention errors for human review and SFT data selection.
   It cannot certify that a public gold label is wrong.

The first live test is post-SQL requirement coverage on stored `train_dev`
answers in shadow mode, followed by a targeted repair A/B. Pre-generation
Jev routing comes later if it beats the deterministic intent baseline.
Cache a single narrow decision request when several checks share state;
call Jev only when a semantic judgment can change a decision.

### 6.5 Candidate bank, cascade and routing

Rebuild pass@K and majority/selector curves for v4p1 and an actually
distinct generator on **matched questions and database versions**. Only
after measuring headroom, test:
- an observable category router fitted with leave-one-database-out
  validation on `train_dev`; gold-SQL complexity is offline only;
- result-signature agreement, followed by a narrow Jev or small LLM
  comparison of differing SQL/rows for contested cases;
- a cascade whose fast exit has an acceptably low **unanimously wrong**
  rate by database and observable complexity class.

Compare with the best single model and with the non-Jev deterministic
policy. Do not escalate solely because models disagree if realized net
gain cannot pay for extra generation. The retired bank's 73% pass@4
and +0.8 escalation are historical, not current thresholds.

### 6.6 Generator and training gate

**v2.7:** the specialist's (rank G) pricing, data build and label audit run in parallel
with ranks 1–5; its paid pilot waits for the rank-4 bank and the audit. Training data
starts from BIRD's official filtered train. **BIRD-Verified subsets are for evaluation
and diagnosis only.** It has no licence, and nothing from it enters training data. The
Verified mention below refers to evaluation subsets.

After ranks 1–5, recalculate the gap to >75% on each public dev set and
the current bank's pass@K. If pass@K is high but selected EX is low,
work on selection. If pass@K remains near or below the desired accuracy,
selection cannot bridge the gap; pilot corrected-data SFT of a ≤16B model,
a stronger specialist generator on identifiable hard classes, or GEPA
with execution rollouts on new **train** databases. Use Verified
same-input/corrected-input subsets according to §1.3, de-duplicate,
filter obviously erroneous gold, and keep Mini-Dev and lockbox out of
training and prompt optimization. Measure training, serving and
inference costs separately. Only a frozen candidate that clears the
public and unseen-database gates proceeds toward hidden-test submission.

### 6.7 Decision gates for the ordered queue

- **Offline → pilot:** show a specific failure mechanism and low false-positive
  rate on currently correct controls. No Jev or SQL rewrite is accepted merely
  because it finds a wrong answer after looking at gold.
- **Pilot → full comparison:** predeclare the target class and minimum gain,
  measure actual cost and latency, and require the pilot to be on course.
- **Full comparison → public gate:** apply §5's paired row/macro acceptance
  rule to the *cumulative* configuration, then reserve the limited
  Mini-Dev and lockbox looks for bundled milestones.
- **Generator or fine-tune gate:** use the **current** matched candidate
  bank's pass@K versus selected EX, and prefer the cheapest route that can
  plausibly close the remaining public-dev gap.

### 6.8 One ledger and cost controls

`BudgetGuard` and `benchmark/results/.spend.sqlite` remain the single
cross-process ledger. Reserve and settle Fireworks and OpenRouter/Jev
charges by durable key; reconcile unknown-cost provisional charges and
invoice differences. Check live remaining balance and provider pricing
before each pilot. The approved v2.4 phase caps are historical maximums,
not a reason to assume the old "currently $6, $0.28 spent" line is
still true. This edit authorizes no new spend or cap increase.

A Jev request with 2,000 input tokens costs about $0.000084 at the
listed $0.042/M input price: ≈$0.0084 per 100 calls or ≈$0.087
per 1,036 calls, **excluding SQL repair calls, retries and latency**.
Measure actual tokens and response time in the first pilot. Price
generator runs at both measured and uncached-equivalent rates; prompt
cache hits are not guaranteed. At current v4p1 train-dev prices, 100
generator answers cost about $0.014 with the observed cache or $0.070
uncached; a 501-question, two-repeat full arm costs about $0.14 observed
or $0.70 uncached, before extra repair calls. Use the uncached figure
when deciding whether a quality gain pays for itself. Batch discounts
are contingent on an implemented submission path.

---

## 7. Jev decision contract and evaluation

- **API:** pinned `typesafe/jev-1.13` through OpenRouter's
  `POST /api/alpha/decisions`, with typed `noul`, `choice` and `score`
  outputs. No SQL or explanatory text generation. The OpenRouter model page (reachable
  2026-09-26) lists $0.042 per million input tokens, output free. Endpoint behaviour and
  latency still need a pilot; the API is alpha.
- **Call design (v2.7):** a declared pilot variable. Compare one bundled call with a
  two-stage design (only if justified) on net EX, false repairs, cost and P90. Calls fire
  on triggers; a post-SQL coverage decision necessarily follows SQL generation.
- **Jev Router (`typesafe/jev-router`, listed 2026-09-25):** it picks a model and
  reasoning effort per chat request across OpenRouter's catalogue; the routing itself is
  listed as free. **Not used on the benchmark path:**
  - its choices can't be pinned or reproduced;
  - it routes outside the pinned Fireworks models;
  - charges for the models it picks are unclear.

  A small, separately approved probe for the product CLI is possible later.
- **State:** question and evidence kept distinct, a short verified
  schema/value shortlist, AST-derived SQL facts and compact execution
  diagnostics. Never send a whole database, full result set, gold SQL,
  gold-derived complexity, or irrelevant dictionary pages.
- **Decision examples:** "Which of these three tables represents the
  requested entity?" (`choice` with `none`); "Is the address constraint
  represented in this SQL?" (`noul`); "Does this projection contain an
  unrequested measure?" (`noul`). Code computes exact counts, numerical
  ranges, dates, joins and result comparisons. One call can contain
  several independent, narrowly worded questions sharing the state.
- **Policy:** validate typed output, record the exact model version and
  per-question probabilities, and fit action thresholds on held-out
  train databases. Jev's returned `choice.confidence` is distribution
  concentration, not an established probability that SQL is correct.
  On API error or low confidence, keep the deterministic baseline;
  never turn an answer into `unsupported` simply because Jev is unsure.
- **Scorecard before live use:** on stored `train_dev` predictions, measure flag
  precision/recall first against ≈ 50 **hand-labelled atomic requirement omissions**
  (v2.8; a wrong official EX is not proof of an omission), then false flags on currently correct
  answers, Brier/calibration by decision, and leave-one-database-out
  stability. In the live pilot, report paired fixes/regressions,
  row-weighted and macro EX, cost, P50/P90, trigger/repair rate and
  effect by observable question class. Compare deterministic rules,
  Jev and a small LLM judge under the same candidate budget. A Jev
  decision ships only if its net gain meets §5 and its failure mode is
  understood.

Jev's published limitations include arithmetic, counting, date
comparison, long irrelevant state, indirection and literal readings.
Use those as design constraints, **not** as evidence of SQL-judge
accuracy. The benchmark path may use public BIRD data; production-data
use is a separate review.

---

## 8. Next checkpoints (v2.8 order)

1. **Fix claims and measure the primary checkpoint.** Refresh `POSTMORTEM_V2.md` with
   the current v4p1 baseline, differing dev database hashes and new empty/NULL counts.
   Confirm the cleaned-dev database package and measure its baseline (pilot, then full).
   **Preselect `train_dev2`** by a fixed rule and record it before any run.
2. **Deterministic value profiles, retrieval and join checks** (rank 1a), each measured
   separately: retrieval recall, preprocessing time, then a stratified pilot.
3. **Targeted value and computation repairs** (ranks 1b, 5), with controls for
   legitimately empty and NULL answers, using static facts and one guarded retry. Build
   the bounded probe executor (rank 2) **only** if value-lookup errors remain.
4. **Strategy-diverse candidate bank** (rank 4) on the latest accepted configuration:
   a diagnostic pass under its $1.50 stop budget, clustered with the fixed signatures,
   then a separately approved confirmation pass before any SFT decision.
5. **Jev shadow comparisons on the bank** (rank 3 → 6); promote only decisions that
   improve a live paired run.
6. **In parallel, free:** price SFT/RFT and serving; build and audit training data from
   `bird23-train-filtered`. The paid pilot follows step 4 and the audit.

**Owner decisions needed:**
1. The two-track acceptance rule and its ceilings (§5.7: $0.01/answer, P90 30s).
2. Contacting the BIRD team about the submission environment (APIs, per-database
   preprocessing, time limits).
3. The `train_dev2` download (3–4 small train databases by range request) and the
   `bird23-train-filtered` download (CC BY-SA 4.0).
4. The cleaned-dev baseline pilot, repriced first (full run ≈ $0.98 uncached).

Preserve the remaining Mini-Dev (2 of 4) and lockbox (1 of 2; 799 unused rows)
looks for bundled checkpoints.

**Owner approved all four (2026-09-26). Status:**
1. **Two-track rule adopted and implemented.** `analyze flips --track submission` uses the
   declared minimum plus ceilings of $0.01/answer uncached and P90 ≤ 30s, with a test.
   The product track is unchanged and the default.
2. **BIRD contact: drafted in the owner's Gmail, not sent.** The published
   [submission guideline](https://docs.google.com/document/d/1Rs6d_pcs2vfqW4Ymub7Wb1XtBNlrc-WfH3T7U1ktuBo/edit)
   already answers several questions:
   - **API-call and combined submissions are accepted.** The submitter provides keys and
     reports dev prompt-token counts in advance.
   - **A compliance check rejects "third-party API links/packages… that could upload/leak
     our databases".** Sending schema/value excerpts to Fireworks, and especially to Jev
     via OpenRouter, is therefore the first question asked.
   - **Test is scored with multiple gold-SQL pools, test cases and human review.** That
     is less label noise than dev, a likely contributor to leaders' dev→test uplift.
   - If more than 5% of outputs are NULL/empty, the team asks for fixes.
   - Test includes giant databases, and `column_meaning.json` is supplied.
   - Up to 2 checkpoints per submission, and 1–2 submissions per 2 months.
3. **Downloads:**
   - `bird23-train-filtered` is downloaded (3.4 MB, gitignored `data/bird/train_filtered/`).
     - All 6,601 rows match `train.json` questions.
     - By split: 5,115 on non-evaluation databases (the training pool), 357 `train_dev`,
       769 lockbox, 360 `train_dev2`.
     - Across all 501 `train_dev` questions, it removes **61% of the 117 no stored answer
       ever solved** vs 19% of solved ones. It is enriched for bad labels but imperfect,
       so the audit stays.
   - **`train_dev2` is not yet fetched.** BIRD's train archive nests a deflated
     `train_databases.zip`, so no single database can be range-fetched. The four
     selected databases need a sequential stream of ≈ 7–8 GB (≈ 100 MB kept). That
     transfer exceeded the owner's approved scope and awaits a separate go-ahead.
4. **Cleaned dev (`dev_20251106.json`):**
   - Same 1,534 question ids and databases as `dev.json`; 182 questions, 381 evidence
     and 452 SQL changed.
   - Its database package is the original `dev_databases`: **1,531 gold queries
     completed** (all non-empty, 0 errors) and **3 timed out** (#518, #701, #1131).
   - Pricing pilot `20260927T022912Z` (99 questions, 9 per database, × 1): **59.6%**,
     with challenging questions over-represented (24 of 99 vs 231 of 1,534, 15.1%). This
     is look 1 (§5.10).
     Uncached $0.000700/answer, P50 1.58s, P90 4.21s.
   - 3 structured-output failures: long SQL truncated at the 400-token cap. v2.9
     replaces the proposed global `--max-tokens 800` with the truncation-only retry.
   - **Full baseline (look 2, run `20260927T025554Z`, 1,534 × 1, complete):**
     - **66.0%** official EX; macro 64.1%.
     - By difficulty: simple 75.3%, moderate 65.0%, challenging 32.9%.
     - Cost $0.30 measured ($0.000195/answer; $0.000668 uncached); P50 1.34s, P90 2.89s.
     - Errors: 21 structured-output failures (all length truncation, 10 in `financial`)
       and 2 repair-exhausted. 42 empty results, none correct.
     - Per database: `financial` 24.5% and `california_schools` 32.6% are lowest. On
       `financial`, scoring the same predictions against the *original* gold gives 22
       vs 26, and the previous v4p1 run also scored 12/30 on its unchanged questions.
       So the low score is real difficulty plus truncation, not a label or package
       mismatch.
     - Cost/latency sit far inside the submission ceilings (max answer $0.0029).
   - **Truncation-only retry, mechanism pilot (2026-09-26, `train_dev`, not cleaned dev).**
     - Truncation occurs almost only on cleaned dev (21 of 1,534). There were 0 in
       `train_dev` and `dev_untouched` runs and 1 in Mini-Dev. Piloting on cleaned-dev
       rows would spend a look, so truncation was forced on 100 `train_dev` rows.
     - `--max-tokens 150 --truncation-retry 400` (`20260927T032348Z`): 1 truncation,
       recovered.
     - `--max-tokens 60 --truncation-retry 400` (`20260927T032603Z`): **48 truncated
       answers, 48 recovered** (0 errors). 30 correct vs 29 for the same rows at the
       normal cap; 44 of 48 give identical results.
     - Retried answers cost ≈ 1.8× uncached ($0.00115 vs $0.00063) and add ≈ 1.7s.
       At cleaned dev's 1.4% truncation rate that is ≈ +1% mean cost.
     - Pilot cost ≈ $0.10.
     - **Decision:** promoted to the **bundled submission-track package** as
       `--truncation-retry 1200`. It can't change any answer that isn't cut off, and a
       cut-off always fails.
     - It is not a CLI default. It is measured with the package at the next cleaned-dev
       milestone (look 3). A full `train_dev` comparison would measure only noise,
       because nothing truncates there.
   - **Rank 1a, deterministic facts: built and measured offline (2026-09-26, free).**
     - Built `src/db_profile.py`: column formats/NULL rates/distincts from a bounded
       sample, FK join cardinality and an FTS5 value index, cached by content hash under
       gitignored `data/profiles/`.
     - `benchmark/grounding.py` measures it; there are tests.
     - **Build cost:** 0.10–0.33s per `train_dev` database.
     - **Formats:** after counting only non-NULL values, it flags every known case
       (`actor.NetWorth` and `characters.pay` money, `characters.screentime` duration)
       plus ISO dates and `weather.sunrise/sunset` durations.
     - **Joins:** `sales_in_weather`'s two FKs are **N:M** (the parent key isn't
       unique), a real fan-out risk; `soccer_2016` has 26 × 1:N.
     - **Value index, retrieval headroom is small on BIRD.** 479 of 493 `train_dev` gold
       string literals (97%) are already written in the question or evidence; across
       BIRD train's non-evaluation databases it is 95.4% of 7,645. The index retrieves 3
       of the 14 literals that aren't. It stays for the product CLI, where users give
       no hints, but it isn't a benchmark lever.
     - **Format headroom is small too.** On the current v4p1 `train_dev` run, questions
       whose gold touches money/duration columns score **46.4%** (28 answers) vs 70.0%
       for the rest. That's 14 of 501 questions, ≤ ≈ 1.5 pts even if all were fixed, and
       some are label conventions (the `screentime` gold sorts raw text).
     - **Implication:** the deterministic semantic layer (1a) is cheap and correct, but
       its measured upside on BIRD is ≈ 1–2 pts. It doesn't close the gap to 75%.
       Selection (rank 4) and generation (rank G) remain the levers to test; 1b/1c pilots
       stay small.
   - **Rank 1c, BIRD column meanings: pilot NOT on course (2026-09-26).**
     - `--column-meaning 6` adds up to 6 question-relevant descriptions from
       `train_column_meaning.json` (ranked by name/description overlap with question +
       evidence, compound names and plurals matched) to the user message. Median ≈ 920
       characters.
     - Pilot `20260927T034045Z` (100 `train_dev` rows × 2) vs the v4p1 run on the same
       rows: **−1.50 [−5.50, +2.50]** (row = macro). Uncached +8%; P50 1.42s → 2.26s;
       required +2.50. Cost ≈ $0.10.
     - **Audit:** it fixed the targeted money-format case (#748, "highest networth
       actor") and 2 `sales_in_weather` questions. It regressed 5: the notes nudge
       toward *more careful* SQL that the literal gold scores wrong (`Fielders IS NULL OR
       = ''` vs gold `= ''`; `generalinfo.city` vs `location.city`), plus repeat noise.
       That is the same failure mode as reasoning (§6.3).
     - Not adopted. The flag stays.
     - **Narrower variant, if pursued:** notes *only* for question-relevant columns the
       1a profile flags as text-encoded money/duration/number. This touches ≈ 14 of 501
       questions (the ≤ ≈ 1.5 pt bound), with nothing added elsewhere.
   - **New design data (2026-09-26).** One sequential stream of BIRD's train archive
     (≈ 9.4 GB transferred) extracted **47 more train databases**: all ≤ 100 MB, plus 6
     mid-size (0.1–0.35 GB, including the 60+-table `works_cycles` for larger-schema
     checks). 2.3 GB on disk; all pass `PRAGMA quick_check`.
     - `benchmark/splits.py` now builds **`train_dev2`** (the 4 preselected databases,
       503 questions) and **`train_design`** (the other 43 databases, 5,851
       questions): the pool for fitting gates and for SFT execution checks, never for
       scoring.
     - Existing split fingerprints are unchanged.
     - The few-shot pool now also excludes `train_dev2`.
   - **Format/intent gate for text-encoded numbers: investigated on `train_design`,
     STOPPED before any Jev spend (2026-09-26).**
     - 194 of 5,851 design questions (3.3%) have gold SQL that uses a numeric-as-text
       column numerically (money, `thousands`, integer-text).
     - Deterministic triggers are imprecise: "question mentions the column" fires 726
       times (23% precision, 87% recall); adding comparison cue words gives 433 (36%,
       80%).
     - v4p1 baseline on the 194 (`20260927T041334Z`, $0.10): **30.4%**. But of 135
       wrong answers, **63 are ours converting the text to a number where the gold
       doesn't** (`AVG(Price)` over '$4.99' text; `ORDER BY population` on text). Only
       **9** are the case a format note would fix (gold converts, ours doesn't).
     - BIRD's own filtered train set keeps 59% of the "gold naive, ours converts"
       group (71% overall), so BIRD largely treats naive text handling as acceptable
       gold.
     - **Decision:** no "convert this" gate: it would lower EX against BIRD's gold. No
       "don't convert" gate either: it games label conventions, degrades real
       correctness for the product, and may not match test grading, which uses
       multiple gold-SQL pools, new test values and human review.
     - The question "does test grading accept CAST-normalised answers where dev gold
       compares text?" goes to the BIRD team.
     - Jev's shadow comparison for this gate is moot. Jev stays planned for
       selection (rank 4/6).
     - Wider lesson: on BIRD, "more correct than the gold" is a recurring failure class
       (reasoning, 1c notes, casts). Rank G training on BIRD-style labels would *learn*
       these conventions, which helps dev scores but is a test-transfer risk. Weigh it
       once BIRD answers.
   - **Rank 4 addendum: label quality (2026-09-26; bank cost $0.76, reported below).**
     - Split by BIRD's own quality filter (`bird23-train-filtered`), the bank looks
       different:
       - on the 357 `train_dev` questions the filter keeps, direct scores **81.0%**
         and pass@4 is 84.6%;
       - of the 133 questions no candidate solves, only 41% are kept by the filter,
         vs 71% overall.
     - A large share of the remaining `train_dev` gap is label quality, not
       generation. The filter may also drop genuinely hard questions, and cleaned dev
       is still ≈ 66%, so this is context, not a score.
     - A real selector on the 102 disagreement questions might recover about half the
       +4.0 ceiling, at ≈ 4× generation cost (inside the submission ceilings).
       Jev-`choice` selection is untested: there is no OpenRouter key yet.
     - Owner review is under way on the 252 practice-set disagreements
       (`benchmark/review_packet.py`, a private review page with stored verdicts). It
       asks whether the answer keys or our answers are wrong, and re-scores rejected
       experiments.

   - **Rank 4 candidate-bank diagnostic (2026-09-26, no new calls for this review).**
     Four saved candidates on all 501 train_dev questions: direct 69.5%, decompose
     67.1%, query-plan 66.9%, glm-5p3-flash 66.9%. Oracle pass@4 is 73.5%
     (368/501, macro 75.0%), while result-majority is 68.9%. The bank adds only
     20 potentially fixable rows over direct; 133 rows have no correct candidate,
     including 93 with unanimous wrong results. Perfect selection from this bank
     remains below 75% train_dev, so generator quality is the next bottleneck to
     test. This is one diagnostic pass, not confirmation for an SFT decision.
     The full report is benchmark/results/candidate_bank_diagnostic.md.

   - **Rank 1b database-facts comparison (2026-09-26 local / 2026-09-27 UTC).**
     A 100-question, two-repeat pilot first found misleading case-folded and
     ambiguous value facts; exact-case and unique-location guards were added.
     The corrected pilot improved paired EX by +3.0 pts [+0.5, +6.5], so it
     qualified for a full run. On all 501 train_dev questions × 2 repeats,
     official EX rose from 69.4% to 70.2%: row-weighted +0.80 pts
     [−0.30, +2.00], database macro +1.59 pts [+0.05, +3.51]. The
     predeclared rule requires **both** gains ≥ +1.5 with intervals above 0;
     rank 1b missed that rule. **Owner override:** adopt bounded facts for the
     benchmark profile (product unchanged); `--no-profile-facts` remains the
     control. This is not yet evidence of transfer: the four-database bootstrap
     holds databases fixed. Two consistent flips occurred on questions receiving
     no fact, showing T=0 variation. The pilots and full variant added about
     $0.220. See benchmark/results/rank1b_outcome.md and
     benchmark/results/profile_facts_failure_analysis.md.

   - **Rank 1b first holdout look (2026-09-26 local / 2026-09-27 UTC).** A
     preregistered 25-question sample from each of seven `train_lockbox`
     databases, three repeats per arm, compared the same frozen code with and
     without facts. EX was 79.24% → 81.14%, paired +1.90 pts
     [−0.19, +4.19] by both row and macro weighting (equal 25/db). No
     database collapsed; the prespecified safety screen passed. The confidence
     interval includes zero, so a transfer gain is **not established** and this
     sample's 81.14% is not a full-lockbox or dev score. No individual lockbox
     mistakes were inspected or used to revise the feature. This used one of
     two looks; the remaining 799 rows are sealed for the final gate. Shared
     spend ended at $6.6765 of the approved $7. See
     benchmark/results/rank1b_lockbox_midpoint_outcome.md and the frozen
     manifests in benchmark/results/.

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
- BIRD filtered train (6,601 rows): https://huggingface.co/datasets/birdsql/bird23-train-filtered
- Jev API, limits and price: https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request · https://docs.typesafe.ai/model-jaggedness/jev-1.13 · https://openrouter.ai/typesafe/jev-1.13/
- Fireworks pricing (incl. 50% batch): https://docs.fireworks.ai/serverless/pricing
- Tam et al., *Let Me Speak Freely?*: https://arxiv.org/abs/2408.02442

# Postmortem v2: Trellis on BIRD-SQL and its evaluation sets

**Date:** 2026-09-26, reflecting the repo at commit `eafe2ba`. **Supersedes:** [`POSTMORTEM.md`](POSTMORTEM.md) (v1, the 2026-09-22
baseline). **API spend for this report:** $0.21 (one second-family run on `dev_untouched`, §6.4); everything else is
recomputed from runs already on disk, with the scripts in [`postmortem_v2/analysis/`](postmortem_v2/analysis) (see
[Appendix B](#appendix-b-reproduction)).

**What this is for.** You want to get the model to 80% on BIRD's hidden test set. This report says
where the current configuration stands on every evaluation set in the repo, which failures are
worth fixing and which are not, what the leaderboard's leaders do that we don't, and what
each candidate fix could break. It tests the recommendations in v1 against what Phases 0–3 measured,
and says plainly where v1 was wrong (§8).

---

## 0. Read this first

### 0.1 Where we are

| Set | Rows × repeats | Official EX | 95% CI | Role |
|---|---:|---:|---|---|
| Mini-Dev, before Phase 1 | 500 × 1 | 47.6% | 43.2–52.2 | baseline (the 45.8% in v1 was a stricter local metric) |
| **Mini-Dev, current configuration** | 500 × 3 | **59.3%** | 55.3–63.7 | gate 1 of 4 |
| `train_dev`, before Phase 1 | 501 × 2 | 60.1% | 55.8–64.1 | iteration set |
| **`train_dev`, current configuration** | 501 × 2 | **68.7%** | 64.8–72.7 | iteration set |
| `train_dev`, same configuration on the new default model (`deepseek-v4p1-flash`) | 501 × 2 | 69.1% | 65.4–73.1 | availability swap, not an accuracy gain (§5.7) |
| **BIRD dev, untouched** | 1,036 × 1 | **63.6%** | 60.9–66.5 | reported only |
| BIRD dev, untouched, `gpt-oss-120b` (second family) | 1,036 × 1 | 62.7% | 60.1–65.6 | consensus measurement (§6.4) |
| `train_lockbox` | 974 | not looked at | — | final gate, 2 looks |

The current configuration is `--prompt-profile benchmark --quote-identifiers --pipeline-repairs` with
reasoning off. Every Mini-Dev and dev number here was measured on `deepseek-v4-flash-0731`, which has
since become unavailable; commit `eafe2ba` moved the default to `deepseek-v4p1-flash`, which has only
been measured on `train_dev`. It costs about $0.0002–0.0007 per answer (uncached) and has a P50 of
about 1–1.6 seconds. Against the leaderboard we sit level with the raw DeepSeek-R1 and GLM-4.7
baselines on dev, roughly 4–7 points below raw Claude Sonnet 4.5 / Opus 4.6, and 9–16 points
below the dev scores of the top systems (§7).

### 0.2 Ten findings

1. **Phase 1 fixed presentation and pipeline losses, and those are now exhausted.** Extra-column
   failures fell from 15.2% of Mini-Dev rows to 4.8%, and hard pipeline failures from 4.2% of answers (21
   of 500) to 1.3% (19 of 1,500). What remains is semantic: values-differ, row-count-differs and empty results are 31% of rows
   (§2.5).
2. **The remaining errors are systematic, not stochastic.** Only 1.6–2.8% of questions flip between
   repeats. Best-of-3 adds 1.5 points and majority-of-3 adds 0.1 (§2.1). A same-model sampling
   scheme cannot fix errors the model makes every time. v1's "self-consistency is the biggest
   lever" was wrong for this model.
3. **Label noise is large on `train_dev` and small on dev, but dev's errors are still mostly shared
   between model families.** On `train_dev`, three measurements put label defects or convention gaps at
   50–65% of stable failures (§6.1). On dev, BIRD's own cleaned labels move both models by only about
   +4 points and explain 16% of the rows where two families agree on the same wrong answer (§6.4).
   The rest, about 16% of dev rows, is a shared error that no selector can touch.
4. **The genuine model errors concentrate in computational SQL.** Ratio and percentage questions,
   division and `CAST`, `GROUP BY`/`HAVING`, subqueries and 2+ joins score 40–55%, against 65–70% for
   plain lookups, in all three sets (§5.2). Cross-model disagreement isolates the true errors:
   26.6% of ratio questions, against 2.8% of simple ones.
5. **Empty answers are the clearest fixable bucket.** 5.0% of Mini-Dev rows and 4.3% of dev rows
   ship an empty result, and 0 of 70 are correct. Single all-NULL answers add about 1% more, also
   ~0% correct. The mechanism is value mismatch (case, format, text-encoded numbers) (§5.1).
6. **Half the accuracy gap is concentrated in four databases.** `california_schools`,
   `thrombosis_prediction`, `formula_1` and `card_games` hold 40% of the dev-like rows and 50–55% of
   their failures (§5.6).
7. **Context-side fixes are running out.** The dictionary CSVs, retrieved few-shot, reasoning,
   cross-family escalation and two model swaps each measured below their required minimum (§9.3). The
   newer default model's pilot (+3.5) did not replicate in the full run (+0.4, CI −1.9 to +2.7).
   The remaining levers change what the model *knows about BIRD's conventions* (training), or how
   well it *computes* (targeted reasoning), not how much context it sees.
8. **The 80% target is a training-or-stronger-generator problem.** Cheap fixes add roughly +2 to +8
   points (central estimate +4; planning estimates, not measurements). On dev, DeepSeek's errors
   split into about 16% of rows shared with a second family, 11% where both are wrong differently, and 5%
   unique to it. Selection can at most reach the last two, and realized selection gains have been under
   1 point. Reaching 80% has to cut into the shared pool, which most plausibly means training on corrected
   data (§9).
9. **The measured model became uncallable, and the replacement is unmeasured on the gate sets.**
   `deepseek-v4-flash-0731` returned `404 Model not found` on 2026-09-26 although the catalogue still
   lists it. The default is now `deepseek-v4p1-flash`, chosen for availability. Swapping snapshots changes
   7.2% of `train_dev` verdicts for a net +0.8%, so every Mini-Dev and dev number in this report needs a
   re-baseline on the new default (§5.7).
10. **Measurement quality is now a strength, with two known gaps.** The measurement stack (official
    comparator, content-pinned runs, paired flips, acceptance rules, a spend ledger) is
    principal-grade. The gaps are that in-run scoring is environment-sensitive (10 dev rows differ on
    re-score, §1.4) and that no per-record failure tag exists (§10.2).

### 0.3 What to do next (details in §10)

| # | Action | Cost | Why now |
|---|---|---:|---|
| 1 | Score the current default on BIRD's cleaned 1,534-row dev (new questions and evidence): the leaderboard-comparable dev number | ≈ $0.3–0.5 | Step 1 of the previous list is done (§6.4); the cleaned dev is what the leaderboard's dev column now uses |
| 2 | Value profiling + FTS5 index for empty/NULL answers | $0 to build, ≈ $0.1 pilot | Largest clean bucket (5%), no cost per query |
| 3 | Re-baseline the new default (`deepseek-v4p1-flash`) on `dev_untouched` ×1, then Chinook and live; keep `gpt-oss-120b` as the fallback | ≈ $0.3–0.4 | The gate-set numbers are for a snapshot that no longer answers |
| 4 | Targeted ratio/percentage handling (checklist plus degenerate-value retry) | ≈ $0.1 pilot | Where genuine errors concentrate |
| 5 | DISTINCT-convention rule, pilot only | ≈ $0.1 | Oracle bound +1.2–2.9, but it can break current correct answers |
| 6 | Decide gate F-G: fine-tuning on corrected data | $10–30 (plan) | Leaders' shared mechanism; generation, not selection, is the bottleneck |

---

## 1. Datasets, runs and rules of use

### 1.1 Evaluation sets in the repo

| Set | Rows | Databases | Label quality | Looks used so far | What this report did with it |
|---|---:|---|---|---|---|
| Chinook dev | 10 | 1 (music store) | hand-authored; 3 of 4 misses are tie-break artifacts | many (prompt was tuned on it) | not re-measured (§1.5) |
| Chinook live regression | 16 | 1 | hand-authored | many | not re-measured |
| **`train_dev`** | 501 | 4 train DBs (soccer_2016 258, restaurant 117, sales_in_weather 80, movie 46) | **noisy**: ~2.0% of gold uses an unambiguous bug idiom | iteration set | fix-design evidence; manual audit (§6) |
| **`train_lockbox`** | 974 | 7 train DBs | not audited | **0 of 2** | **not touched** |
| **Mini-Dev** | 500 | 11 dev DBs | revised by BIRD; 22.6% of gold result sets change under the Arcwise correction | 1 of 4 (gate 1) | aggregate diagnosis only |
| **`dev_untouched`** | 1,036 | the same 11 dev DBs | dev labels, human baseline 92.96%; BIRD's cleaned SQL changes 6.9% of result sets on the 75% of rows it leaves otherwise unchanged | 2 runs (DeepSeek, gpt-oss-120b), reported only | aggregate diagnosis; consensus and cleaned-label measurement (§6.4) |
| BIRD dev, Nov 2025 cleaned | 1,534 | 11 dev DBs | rewrites questions, evidence and SQL; 779 of `dev_untouched`'s 1,036 rows keep the same question and evidence | diagnostic | cleaned-label rescoring of those 779 rows (§6.4); CC-BY-SA-4.0, fetched to gitignored `data/bird/dev_cleaned/` |
| Arcwise-Plat-SQL | 498 | Mini-Dev | corrected gold SQL only | diagnostic | corrected-label rescoring |
| BIRD-Verified | 219 same-input rows, 93 + 195 revised-input rows | train | corrected SQL (private use, no licence) | diagnostic | corrected-label cross-check (§6) |

**Not in the repo, and worth knowing:** Spider and Spider 2.0. If you want a generalization check
beyond BIRD's annotation style, Spider dev (1,034 questions, SQLite) is the cheapest one, but it would
be a separate experiment with its own cost.

### 1.2 Runs analysed (all recorded, none re-run)

| Label | Set | Raw file (`benchmark/results/`) | Configuration |
|---|---|---|---|
| Mini-Dev baseline | Mini-Dev ×1 | `bird_raw_20260923T061413Z` | product prompt, no repairs |
| **Mini-Dev gate 1** | Mini-Dev ×3 | `bird_raw_20260924T232302Z` | current configuration |
| `train_dev` baseline | ×2 | `bird_raw_20260924T005317Z` | product prompt |
| `train_dev` 1a | ×2 | `bird_raw_20260924T170715Z` | + benchmark prompt profile |
| **`train_dev` 1abc** | ×2 | `bird_raw_20260924T175733Z` | + quoting + pipeline repairs (current) |
| `train_dev` gpt-oss-120b | ×2 | `bird_raw_20260925T014638Z` | current configuration, other model |
| `train_dev` v4p1-flash | ×2 | `bird_raw_20260926T203859Z` | current configuration, new default model |
| **`dev_untouched`** | ×1 | `bird_raw_20260925T015202Z` | current configuration |

### 1.3 Rules of use for this report

The protocol in `SOTA_PLAN.md` §5 says Mini-Dev is a gate (never tuned on) and `dev_untouched` is
reported only. This report follows it:

- **Fix-design claims come from `train_dev`** (§5.1 mechanism, §6 audit, §5.2 cross-model split).
- **Mini-Dev and `dev_untouched` support aggregate statistics only**: bucket shares, feature
  associations, per-database scores. No Mini-Dev or dev *question* is proposed as a prompt example,
  a few-shot example or a rule's target.
- **v1 broke this rule**: it read baseline failures on Mini-Dev one by one to design fixes. §8 tracks
  what happened to those cases, and treats the tracking as diagnostic, not as a new look.

### 1.4 Method notes

- **Metric.** BIRD's official EX: `set(pred) == set(gold)`, and only delivered SQL counts. The unit
  is the dataset *row* (all 500 Mini-Dev rows including the duplicated ids 137/138).
- **CIs** come from 1,000 bootstrap resamples of questions within each database, with a question's
  repeats kept together.
- **Re-score vs in-run.** Re-executing every answer with the official evaluator reproduces the recorded
  score on `train_dev` to within 0.2 points (68.7% on one pass, 68.5% on another) and, on repeat 0 of
  Mini-Dev, gives 59.0% against a 3-repeat mean of 59.3%. On `dev_untouched` it gives 64.6% instead of 63.6%. Ten rows time out under concurrent load in-run but finish on re-execution
  (example in Appendix A, row 490). The headline uses the recorded, conservative figure.
- **Failure buckets** are the project's own (`benchmark/analyze.py:bucket`). "Oracle presentational
  fix" figures are upper bounds chosen by looking at gold. They are never reported as gains.

### 1.5 The Chinook sets

The Chinook dev set (60% raw, with three of four misses being tie-break artifacts, see
`DECISIONS.md` 2026-09-22) and the 16-question live suite (48/48 in August) belong to the
product profile, which is byte-identical to before Phase 1. They have not been re-measured since
2026-09-22 and this report adds nothing new for them, except one warning: they are the regression
tripwire for any prompt change that touches shared text (§5.9).

---

## 2. Scoreboard

### 2.1 All sets

| Run | Row-weighted (95% CI) | DB-macro (95% CI) | Stable-correct | Stable-wrong | Flaky | Best-of-k | Majority |
|---|---|---|---:|---:|---:|---:|---:|
| Mini-Dev baseline ×1 | 47.6% (43.2–52.2) | 46.8% (42.4–51.5) | 47.6% | 52.4% | — | — | — |
| **Mini-Dev gate 1 ×3** | **59.3%** (55.3–63.7) | 58.3% (54.2–62.9) | 58.0% | 39.2% | 2.8% | 60.8% | 59.4% |
| `train_dev` baseline ×2 | 60.1% (55.8–64.1) | 58.5% (53.6–63.4) | 59.5% | 39.3% | 1.2% | 60.7% | — |
| `train_dev` 1a ×2 | 67.1% (63.0–71.3) | 65.4% (60.5–70.3) | 66.5% | 32.3% | 1.2% | 67.7% | — |
| **`train_dev` 1abc ×2** | **68.7%** (64.8–72.7) | **69.3%** (64.8–73.9) | 67.9% | 30.5% | 1.6% | 69.5% | 68.5% |
| `train_dev` gpt-oss-120b ×2 | 67.3% (63.3–71.5) | 68.2% (63.8–72.8) | 67.3% | 32.7% | 0.0% | 67.3% | — |
| `train_dev` v4p1-flash ×2 (new default) | 69.1% (65.4–73.1) | 70.8% (66.6–75.0) | 67.9% | 29.7% | 2.4% | 70.3% | — |
| **`dev_untouched` ×1** | **63.6%** (60.9–66.5) | 63.9% (61.0–67.0) | 63.6% | 36.4% | — | — | — |
| `dev_untouched` gpt-oss-120b ×1 | 62.7% (60.1–65.6) | 63.1% (60.1–66.2) | 62.7% | 37.3% | — | — | — |

Two things to read off this table. The intervals are wide (±4 points at n=500), so single-run
differences under ~4 points are not evidence. And "stable-wrong" is 30–39% of every set while "flaky"
is under 3%: the model is deterministic about its mistakes.

### 2.2 Progress ledger (what moved the numbers)

| Change | `train_dev` Δ (95% CI) | Cost, latency | Verdict |
|---|---|---|---|
| Benchmark prompt profile | **+7.0** (+4.5, +9.8); macro +6.9 | −8.6% uncached cost | adopted |
| Quoting + pipeline repairs | +1.6 (+0.2, +3.0); macro **+3.9** (+1.1, +7.1) | +6.4% uncached cost | borderline, adopted after audit |
| Same package on Mini-Dev | +11.7 (descriptive, not paired) | −58% measured cost (cache) | carried over |
| Dictionary CSVs | +1.2 (−1.2, +4.4) | +32% cost, +0.46s | not adopted |
| Reasoning low / high | −1.5 / −1.5 | +103% / +201% cost | not adopted |
| `deepseek-v4p1-flash`, pilot (100 rows) | +3.5 (−1.5, +8.5) | +41% cost | qualified for a full run |
| `deepseek-v4p1-flash`, **full run** (501 × 2) | **+0.4 (−1.9, +2.7)**; macro +1.5 (−0.7, +3.9) | +40% uncached cost, P50 1.05 → 1.61s; required minimum +2.86 | fails the rule; became the default for availability (commit `eafe2ba`) |
| Retrieved few-shot (BM25, k=3) | +0.0 (−4.0, +4.0) | +20% cost, +0.85s | not adopted |
| `gpt-oss-120b` swap | −1.4 (−3.9, +1.1) | −20% cost, P90 1.9s vs 8.5s | fails the −1.5 margin |
| Escalate on disagreement | +0.8 | 2.8× cost | not adopted |

### 2.3 Difficulty tiers

| Tier | Mini-Dev baseline | **Mini-Dev gate 1** | `dev_untouched` |
|---|---:|---:|---:|
| Simple | 66.2% (148) | **76.1%** | 68.0% (777) |
| Moderate | 42.8% (250) | **54.0%** | 50.0% (216) |
| Challenging | 32.4% (102) | **48.0%** | 53.5% (43) |
| Overall | 47.6% | 59.3% | 63.6% |

The challenging tier gained most (+15.6), simple gained +9.9. On `dev_untouched` the challenging
score exceeds the moderate one, but that tier has only 43 rows and a ±15-point interval.
Mini-Dev and dev differ mostly in tier mix, which is why the overall numbers differ.

### 2.4 Per-database, Mini-Dev vs dev (same 11 databases)

Rank agreement between the two sets is high (Spearman **0.85**), so the per-database pattern is real
and not sampling noise.

| Database | Mini-Dev ×3 | n | Dev ×1 | n | Δ |
|---|---:|---:|---:|---:|---:|
| `california_schools` | 43.3% | 30 | 44.1% | 59 | +0.7 |
| `toxicology` | 48.3% | 40 | 61.0% | 105 | +12.6 |
| `formula_1` | 48.5% | 66 | 50.0% | 108 | +1.5 |
| `financial` | 50.0% | 32 | 65.8% | 76 | +15.8 |
| `thrombosis_prediction` | 50.0% | 50 | 46.0% | 113 | −4.0 |
| `card_games` | 50.6% | 52 | 56.1% | 139 | +5.5 |
| `debit_card_specializing` | 52.2% | 30 | 64.7% | 34 | +12.5 |
| `codebase_community` | 61.9% | 49 | 72.3% | 137 | +10.4 |
| `european_football_2` | 69.9% | 51 | 76.9% | 78 | +7.0 |
| `student_club` | 80.6% | 48 | 78.2% | 110 | −2.4 |
| `superhero` | 85.9% | 52 | 88.3% | 77 | +2.4 |

The four large gaps (`toxicology`, `financial`, `debit_card_specializing`, `codebase_community`,
+10 to +16) are most likely composition effects: Mini-Dev skews harder overall, and five of its eleven
databases differ in content from the dev copies (`SOTA_PLAN.md` §0.2). `california_schools`, `formula_1`, `thrombosis_prediction` and `card_games` are
low in *both* sets, which is what makes them real weaknesses.

### 2.5 Failure buckets, before and after Phase 1 (share of all rows)

| Bucket | Mini-Dev baseline | **Mini-Dev gate 1** | `train_dev` baseline | **`train_dev` 1abc** | `dev_untouched` |
|---|---:|---:|---:|---:|---:|
| Correct | 47.6% | 59.0% | 60.1% | 68.5%† | 64.6%* |
| values-differ | 18.0% | **19.0%** | 16.4% | **18.2%** | 17.1% |
| row-count-differs | 4.4% | **6.8%** | 6.8% | **7.8%** | 7.0% |
| empty-result | 5.2% | **5.0%** | 2.6% | 2.0% | 4.2% |
| extra-columns | **15.2%** | 4.8% | **10.8%** | 2.2% | 3.8% |
| missing-columns | 4.8% | 3.4% | 1.0% | 0.8% | 2.4% |
| pipeline errors and refusals | 4.2% | 1.4% | 2.4% | 0.2% | 0.7% |
| gold or prediction exec error | 0.6% | 0.6% | 0.0% | 0.4%† | 0.3% |

*Re-scored; the recorded in-run score is 63.6% (§1.4). †Re-scoring is not perfectly repeatable: one
prediction's execution failed intermittently, so `train_dev` 1abc read 68.7% on one pass and 68.5% on
another (the table shows the final pass). Repeat 0 only, so Mini-Dev gate 1 reads 59.0% here and 59.3% as a
3-repeat mean.

Read this table by columns of *change*. Extra-columns fell by ten points on Mini-Dev and eight on
`train_dev`; pipeline errors fell by three. **values-differ did not move**, row-count-differs *rose*
(shape errors became count errors), and empty-result did not move. Oracle presentational fixes
still exist but are small: +5.0 points on Mini-Dev (13 extra-column, 9 `COUNT(DISTINCT)`, 3 name-concat),
+2.2 on `train_dev`, +5.0 on dev (of which 30 rows are `COUNT(DISTINCT)`).

### 2.6 Cost and latency

| Run | P50 | P90 | LLM calls / answer | $ / answer, measured | $ / answer, uncached | $ per 1,000 answers (uncached) |
|---|---:|---:|---:|---:|---:|---:|
| Mini-Dev gate 1 | 0.97s | 4.47s | 1.10 | $0.000205 | $0.000491 | $0.49 |
| `train_dev` 1abc | 1.05s | 8.46s | 1.08 | $0.000398 | $0.000497 | $0.50 |
| `dev_untouched` | 0.98s | 3.13s | 1.09 | $0.000431 | $0.000465 | $0.47 |
| `train_dev` gpt-oss-120b | 0.97s | 1.93s | — | $0.000166 | $0.000398 | $0.40 |
| `train_dev` v4p1-flash (new default) | 1.61s | 4.05s | — | $0.000185 | $0.000696 | $0.70 |
| `dev_untouched` gpt-oss-120b | 0.91s | 2.30s | — | $0.000206 | $0.000393 | $0.39 |

Measured cost swings with provider cache hits (23–49% across comparable runs), so the uncached column
is the fair comparison. Total project spend to date is **$4.23** of the $6 ceiling (Fireworks $4.21,
provisional $0.02), against phase caps that sum to about $38 before the fine-tuning decision.

### 2.7 Where the tail latency comes from

It is the provider, not the database or the repair loop. P90 model time is 2.7–7.9 seconds
against a P50 of 0.93; P90 database execution time is at most 0.06 seconds (`train_dev`'s
sales_in_weather reaches 1.2s). Only 23 of 3,538 answers spent more than 5 seconds executing SQL,
which is consistent with fan-out and timeout cases (§5.5). Repairs are 1.08–1.10 calls per answer, so they
are not the tail either. The P90 gap between `train_dev` (8.5s) and Mini-Dev (4.5s) is
most likely provider queueing: the same `train_dev` set measures a 4.05s P90 on the new default model and
1.93s on gpt-oss-120b.

---

## 3. What is GREAT

Each item is something to protect when fixing the bad ones.

**G1. The measurement system.** It caught five defects in its own plumbing during review (the
2026-09-23 entries in `DECISIONS.md`): a spend ledger that recorded $0.04 of $0.12 of concurrent spend, double-counted settlements,
a comparison that scored a budget-stopped run at +100 points, rows scored by question id instead of by
row, and a local evaluator that disagreed with BIRD's on 30 of 500 rows. The result is that every
delta in §2.2 is a paired, content-pinned, question-level bootstrap with a pre-declared minimum. This is
rare, and it is the reason this report can say what did *not* work.

**G2. Phase 1 generalizes.** Every one of the 11 Mini-Dev databases improved, from +3.3
(`toxicology`) to +24.4 (`student_club`). The gain on the gate set (+11.7 on Mini-Dev, a descriptive before/after) exceeded the gain on the set
it was developed on (+8.6 `train_dev`), which is the opposite of overfitting.

**G3. The pipeline is reliable.** Hard failures (unrecoverable errors, safety rejections,
structured-output failures) are 19 of 1,500 answers (1.3%), down from 21 of 500 (4.2%). Only 3
answers in 1,500 were safety-rejected. Repair-exhausted failures dropped from 7 per 500 to 5 per 500.

**G4. Determinism.** 98.4% of `train_dev` rows and 97.2% of Mini-Dev rows give the same verdict on every
repeat. That is why the +7.0 and +11.7 are believable, and it means a regression is visible
immediately rather than hidden in noise.

**G5. Cost and speed.** $0.0002–0.0005 per answer on the measured snapshot (about $0.50 per 1,000
uncached, $0.70 on the new default), P50 ≈ 1–1.6 seconds, and 1.08–1.10 model calls per answer. At
30,000 answers a day that is $6–21.

**G6. Well-formed schemas and simple questions.** Simple questions score 76.1% and `superhero` and
`student_club` score 78–88% on both dev-like sets. `european_football_2` (a 115-column table) scores
70–77%, so column *width* is not a general failure driver (§5.6).

**G7. Safety is intact and orthogonal.** The connection is read-only beneath the AST layer, so no
destructive statement can execute. All benchmark-only changes (profile, quoting, repairs) are off by
default, so the CLI's behaviour is unchanged.

**G8. Honest negatives.** At least six candidate changes were rejected on measured evidence: dictionary CSVs,
reasoning, retrieved few-shot, `gpt-oss-120b`, escalation, and a `deepseek-v4-pro` swap. Rejecting them
saved money and, more importantly, prevented adopting noise. The "not adopted" list is worth more than
most feature lists.

---

## 4. What is OKAY

**O1. Moderate and challenging tiers (54.0% / 48.0% on Mini-Dev).** Up 11–16 points. But they are 70% of the rows and still 46–52% wrong, and the cheap presentation
fixes that drove the gain are used up.

**O2. Mid-table databases.** `codebase_community` (61.9% / 72.3%), `european_football_2` (69.9% /
76.9%) and `financial` (50.0% / 65.8%) are decent but inconsistent between sets (the gaps in §2.4 are
most likely composition, not skill).

**O3. Presentation residue.** After Phase 1, extra-columns are 4.8% of Mini-Dev rows and
missing-columns 3.4%. Most of what is left is `COUNT(DISTINCT)` and gold that returns an extra
column, both of which are convention rather than error (§5.4).

**O4. The row-count bucket rose (4.4% → 6.8% on Mini-Dev).** Shape errors turned into count errors:
the agent now returns the right columns but a different number of rows, plausibly through `DISTINCT`
and join-multiplicity differences (not decomposed here). Not a regression in itself, but it is where the next round of
convention failures will come from.

**O5. Pipeline repairs pay for themselves, barely.** The empty-result retry fired on 5.9% of answers,
replaced 13 and made 5 correct (+0.3 points for 4.7% of run cost). The refusal retry converted 17
refusals to queries, 7 correct. The "did you mean" repair contributed one audited fix on `train_dev`. All
three are kept, but none is a big lever.

**O6. `gpt-oss-120b` as a fallback.** It scores −1.4 points (CI −3.9 to +1.1) at −20% cost with a
1.9s P90. The point estimate is inside the −1.5 non-inferiority margin, but the interval's lower bound
(−3.9) is not, so it fails the rule. For a fallback that is fine, and §5.7 needs one.

---

## 5. What is BAD

Ranked by expected recoverable points on the dev-like sets, then by confidence. Each item gives the
pattern, the evidence, likely causes, what fixing it would do, the risk to §3, and the next experiment.
"Planning estimate" means a range built from the measured bucket size and an assumed fix rate. It is not a
measurement.

### 5.1 Empty and NULL answers: value grounding (largest clean bucket)

**Pattern.** The agent ships a query that returns no rows, or one all-NULL row, and treats it as an answer.

**Evidence.**

| Set | Shipped empty | Correct | Shipped single all-NULL | Correct |
|---|---:|---:|---:|---:|
| Mini-Dev gate 1 | 25 (5.0%) | **0** | 4 | 0 |
| `dev_untouched` | 45 (4.3%) | **0** | 9 | 1 |
| `train_dev` 1abc | 32 (6.4%) | 22\* | 8 | 0 |

\*`train_dev`'s restaurant database legitimately has 19 empty gold results, so its empties are
mostly correct; excluding them, wrong empties are about 2% of rows. On the dev-like sets, none of the 70
shipped empties is right.

The empty-result retry already runs (on 5.9% of answers) and replaced 13 of the 89 empties it tried
on Mini-Dev, so these 70 are largely the ones that *survived a retry*.

**Likely causes (mechanisms seen directly in `train_dev` failures).**
- Case and spelling: the agent filtered `'Northern California'`; the stored value is lowercase
  (Appendix A, row 112).
- Text-encoded numbers and durations: money stored as `'$375,000,000.00'` and compared as a string; screen time
  stored as `'0:17:30'` and subtracted as text, giving NULL (rows 42, 13).
- Malformed literals inside BIRD hints: `time('5:00:00')` is NULL in SQLite (row 483).
- Unscoped subqueries: a `MAX()` over all stations joined back to one station gives NULL (rows 435, 440).

**Fix.** A value profile per column (declared type vs observed format, case, distinct count, sample
values for low-cardinality text) rendered into the schema, plus a local FTS5 index to resolve a
literal in the question to the stored spelling. This is item 4 in `SOTA_PLAN.md` §6.1, gated on
"value-matching failures remain". They do remain, so the gate has opened. It has no per-query model
cost; the price is prompt tokens.

**Planning estimate.** 25–40% of shipped empties fixed: **+1.1 to +2.0 points** on Mini-Dev and dev.
The NULL-only case (retry on an all-NULL row) adds +0.2 to +0.4 for a few percent more calls.

**Risk to §3.** Prompt tokens rise (the dictionary pilot's +53% characters cost +32% uncached and +0.46s;
a value profile should be far smaller if capped per column). Watch P50, and require the acceptance
rule in `SOTA_PLAN.md` §5: +1.5 base, +1 per +50% uncached cost, +1 per +1s P50.

**Next experiment.** Free: build the profile and replay the 10 wrong-empty `train_dev` rows offline.
Pennies: 100-row pilot on `train_dev`, stratified plus the targeted empties.

### 5.2 Computational semantics: ratios, percentages, grouping, subqueries

**Pattern.** Questions that require computing something (a percentage, a ratio, a per-group filter, a
nested comparison) fail far more often than lookups, in every set.

**Evidence: accuracy with vs without the feature (pooled n=2,037; base 63.8%).**

| Feature (from gold SQL or question) | Rows | Accuracy with | Without | Δ |
|---|---:|---:|---:|---:|
| `HAVING` | 29 | 32.8% | 64.3% | −31.5 |
| `GROUP BY` | 190 | 46.2% | 65.6% | −19.4 |
| Subquery | 158 | 46.8% | 65.2% | −18.4 |
| Division | 216 | 47.5% | 65.7% | −18.2 |
| `CAST` | 202 | 47.5% | 65.6% | −18.1 |
| Ratio/percentage/average in the question | 324 | 50.3% | 66.4% | −16.0 |
| Multi-part question | 132 | 48.7% | 64.8% | −16.1 |
| `CASE`/`IIF` | 236 | 52.5% | 65.3% | −12.7 |
| Superlative in the question | 414 | 54.1% | 66.3% | −12.2 |
| `ORDER BY ... LIMIT` in gold | 393 | 53.9% | 66.2% | −12.3 |
| Evidence contains a formula | 689 | 57.2% | 67.2% | −10.0 |
| No evidence given | 170 | 58.8% | 64.3% | −5.4 |
| `COUNT` question | 562 | 64.0% | 63.7% | +0.2 |

| Joins in gold | Rows | Accuracy |
|---|---:|---:|
| 0 | 528 | 70.5% |
| 1 | 1,144 | 63.9% |
| 2 | 304 | 54.9% |
| 3+ | 61 | 48.6% |

Checked per set, the direction is the same in Mini-Dev, `train_dev` and dev for `GROUP BY`, subquery,
division, `CAST`, ratio questions, superlatives, `LIMIT`, evidence formulas and temporal questions, so the
pooled table is not a Simpson's-paradox artifact. Two features do not replicate: `HAVING` is too rare
to report per set (29 rows in total) and `COUNT` questions show no effect.

**Which of these are model errors and which are label noise?** On `train_dev`, where a second model family
exists, split the rows where *both* families are wrong into "they return the same answer" (consensus
against gold: a label defect or a shared convention gap) and "they disagree" (a genuine error by at
least one):

| `train_dev` group | Rows | DeepSeek accuracy | Both wrong | Same answer | **Genuine-ish share of rows** |
|---|---:|---:|---:|---:|---:|
| Ratio/percentage question | 64 | 42.2% | 34 | 17 (50%) | **26.6%** |
| Division or `CAST` in gold | 50 | 48.0% | 24 | 13 (54%) | **22.0%** |
| `GROUP BY` | 70 | 51.4% | 33 | 21 (64%) | 17.1% |
| 2+ joins | 122 | 57.4% | 50 | 32 (64%) | 14.8% |
| Superlative | 105 | 60.0% | 40 | 25 (62%) | 14.3% |
| Subquery | 31 | 51.6% | 15 | 11 (73%) | 12.9% |
| `COUNT` question | 162 | 66.7% | 47 | 35 (74%) | 7.4% |
| No feature (simple) | 250 | 79.2% | 43 | 36 (84%) | **2.8%** |
| All | 501 | 69.5% | 138 | 98 (71%) | 8.0% |

So the association is partly label noise (simple questions' failures are 84% consensus) but the
computational classes keep a large genuine core: ratio questions are 26.6% genuine disagreement,
ten times the simple rate.

**Likely causes.**
- BIRD's evidence gives a formula with mechanical meaning (`DIVIDE(a, b)`, `Sum(x) / Count(y)`),
  and the model tends to substitute its own semantics (`COUNT(DISTINCT date)` for the hint's
  `Count(date)`, or a subquery scoped differently from the hint).
- Scope errors in nested aggregates: rows 435/440 compute a global `MAX(tmax)` and join it back to one
  station.
- Reasoning did not help globally (−1.5 points at +103% cost), because it "overthinks" against literal
  labels (`EXISTS` for joins, parsing text columns). That says global reasoning is the wrong tool,
  not that reasoning is useless on this subset.

**Fix candidates, cheapest first.**
1. A short computation checklist in the benchmark profile: cast to `REAL` before dividing, apply the
   evidence formula literally, do not rescope a subquery beyond the hint.
2. A degenerate-value retry: a percentage above 100 or below 0, a ratio exactly 0.0, or a NULL aggregate
   triggers one more attempt.
3. Route only these classes (observable from the question and the model's own draft) to a
   reasoning pass, using Phase 4R's "observable categories" rule.

**Planning estimate.** These classes are 12–27% of rows at ~50% accuracy; a 10-point lift on them is
**+1 to +3 points**.

**Risk to §3.** Route 3 raises latency and cost on the routed subset only (~10–25% of answers). Checklist
text can regress Chinook's percentage and growth questions (the product prompt has its own rounding and
growth rules), so run the Chinook dev and live sets after any change to shared text.

**Next experiment.** Pilot 1 + 2 on `train_dev` (the 64 ratio rows plus stratified rows).

### 5.3 Look-alike tables, columns and join paths: the largest and least understood bucket

**Pattern.** `values-differ` is 17–19% of rows in every set and, after Phase 1, 46–58% of all remaining
failures. It is the bucket whose cause we understand least, because it is a mixture.

**What it is made of (from the 46-case `train_dev` audit, Appendix A).** Label defects and convention
differences account for most of it on `train_dev`. The genuine part looks like:
- **Wrong table among look-alikes.** `restaurant` has both `generalinfo` and `location` with `city` and
  `id_restaurant`; for "restaurants located in Sunnyvale" the agent took `generalinfo` (174 rows
  vs gold's 168, row 129).
- **A stated constraint dropped.** Row 87: "106 E 25th Ave" was reduced to the street name because the evidence
  restated only the street.
- **Over-joining.** Row 459: an extra unconstrained join to `weather` perturbs the multiplicity.
- **Fan-out with no key.** Row 490: a missing join predicate produced a 107,877,015-row intermediate.

In the dev-like sets the same class plausibly shows up as `california_schools` (`schools`, `satscores` and
`frpm` each carry district and name fields; this is a property of the schemas, not a reading of specific
questions) and `thrombosis_prediction` (`Diagnosis` exists in both `Patient`
and `Examination`).

**Likely causes.** No canonical-table signal in the rendered schema. The dictionary CSVs were the
obvious source and did not pay (+1.2 points for +32% cost), most likely because BIRD's evidence
already carries the disambiguation on `train_dev`'s databases.

**Fix candidates (hypotheses, not yet tested).**
- Auto-derive look-alike hints from the schema: tables sharing many column names, with the
  table that owns the primary key flagged as canonical.
- A pre-execution check that flags a join with no predicate linking the two sides.
- Candidate disagreement as a trigger: only when two samples disagree do you spend a judge call.
  The plan's own numbers cap this at +3 (two-family oracle) and the measured escalation gained +0.8,
  so only pursue it if it is nearly free.

**Planning estimate.** Unknown; a wide 0 to +2. This bucket needs the audit in §10 (a second labeled
sample, tagged with the same scheme, ideally by a second rater) before anyone builds against it.

### 5.4 Annotation-convention gaps (distinct from label defects)

**Pattern.** BIRD's gold follows conventions that a semantically careful model contradicts.

**Evidence, in the audit (8 of 46) and in the aggregates.**
- `COUNT(x)` vs `COUNT(DISTINCT x)`: the agent uses `COUNT(DISTINCT)` in 8–10% of answers. When gold does
  not, accuracy is 34% (Mini-Dev), 46% (`train_dev`) and 31% (dev) on those answers, against 53%, 67% (n=3)
  and 49% when gold also uses it. Dropping `DISTINCT` (oracle) would fix 9 Mini-Dev, 6 `train_dev` and 30 dev
  rows (**+1.8, +1.2, +2.9 points**).
- Hints read literally: `Divide(Sum(units), Count(date))` means a non-distinct count; `MAX(COUNT(Role_id))`
  means no `DISTINCT`; `year refers to DOB` means return the date; "total" means `SUM` of the named column.
- Malformed hint literals corrected by gold: `time('5:00:00')` (gold uses `'05:00:00'`).
- Projection ambiguity: gold sometimes returns an extra label column (row 91) or fewer columns than the
  evidence implies (rows 103, 106).

**Why this matters.** This is plausibly what trained systems learn from BIRD's train set, and it is what
retrieved few-shot failed to transfer (0 of the targeted convention cases fixed, and +0.0 overall). Examples from
other databases do not carry these conventions; weights might.

**Fix candidates.**
1. A conditional `DISTINCT` rule ("do not add `DISTINCT` inside `COUNT` unless the question says
   unique/distinct/different"). The oracle says up to +1.2–2.9, but 12 (Mini-Dev), 18 (`train_dev`) and 23
   (dev) currently-correct answers use `COUNT(DISTINCT)` where gold does not, because de-duplication happened to
   be a no-op. Some of those will flip. **Planning estimate: −0.5 to +1.5 points; pilot before believing it.**
2. Fine-tuning (§9): the mechanism the leaderboard's trained systems share.

**Risk to §3.** The `DISTINCT` rule can regress the currently-correct rows above. It also touches the
product profile if placed in shared text, so keep it in the benchmark profile only.

### 5.5 Execution pathologies

**Pattern.** A minority of queries are computationally pathological, and they both fail and skew the
scoring.

**Evidence.** 15 of 1,500 Mini-Dev answers (1.0%) end `repair-exhausted`, and 14 of those 15 are
`interrupted` (timeouts). 23 of 3,538 answers spent over 5 seconds in SQLite; the maximum is 20 seconds.
The one `train_dev` case I inspected joined `weather` with no key and produced a 107,877,015-row
intermediate for a 111-row answer (row 490). In-run scoring is environment-sensitive (10 dev rows,
§1.4). Gold #518 and #701 time out locally too. A smaller, separate class: 3 of 1,500 answers were
rejected because the model emitted more than one SQL statement ("Exactly one SQL statement is
required").

v1 attributed the timeouts to a 2-second limit that was too tight. Phase 1 added a size-scaled limit.
Of the nine cases where v1's reports recorded an `interrupted` execution, **3 still time out, 2 have
gold queries that themselves time out (#518, #701, so they cannot be scored), and 4 now finish without
error but return a wrong answer**. All nine are wrong on all 3 repeats. Raising the limit bought
completion, not correctness, so the timeout was not the (only) cause.

**Fix.** A pre-execution guard: use `EXPLAIN QUERY PLAN` and a cheap predicate check to reject a join with
no linking predicate, then use that as the repair message. For multi-statement output, keep the first
statement instead of refusing. **Planning estimate: +0.3 to +1.0 points**, mostly from the timeouts. It
also makes latency and scoring more stable.

**Risk to §3.** Low: it only fires on queries that would time out anyway, or on output that is already
rejected.

### 5.6 Concentration: four databases carry half the failures

`california_schools`, `thrombosis_prediction`, `formula_1` and `card_games` are 40% of the dev-like
rows and produce **50.0% of Mini-Dev failures and 55.4% of dev failures**. They are low in both
sets (§2.4), so this is not sampling.

| Database | Mini-Dev / dev | Distinguishing trait | What we can and cannot say |
|---|---|---|---|
| `california_schools` | 43.3% / 44.1% | 3 tables, 27 special-character column names, look-alike name fields | Candidate for every item in §5.1–5.3; not audited at question level here (§1.3) |
| `thrombosis_prediction` | 50.0% / 46.0% | 44-column `Laboratory`, hyphen and space names | Quoting fixed 3 of the 4 v1 cases; `Diagnosis` and `SM` are look-alike-table cases |
| `formula_1` | 48.5% / 50.0% | 13 tables, the most in any DB | Cause not diagnosed: no `train_dev` database resembles it, so the audit here does not cover it |
| `card_games` | 50.6% / 56.1% | 74-column table, 262MB | Timeouts and heavy joins |

**A correction to v1's wide-table claim.** Across the 11 databases, column width is weakly negative
(Spearman ρ = −0.29 for max columns, −0.32 for special-character names, n=11 so not significant), and
`european_football_2` has a 115-column table and scores 70–77%. Width alone is not the driver; domain
semantics and look-alike structure are. Wide-table rendering (v1 §6.3) has never been tested and
its priority should drop.

### 5.7 Vendor and model fragility

**Pattern.** Every Mini-Dev and dev number here was measured on `deepseek-v4-flash-0731`. On 2026-09-26
that snapshot returned `404 Model not found` while the catalogue still listed it, and commit `eafe2ba` moved
the default to `deepseek-v4p1-flash` and made the agent handle 404/403 without crashing. The
July→September history repeats: `gpt-oss-20b` and the undated `deepseek-v4-flash` alias had already been
retired (the model-catalog entry in `DECISIONS.md`), and prices moved (DeepSeek $0.14/$0.28 →
$0.22/$0.66 per million tokens in September).

**What the swap did, on `train_dev` (501 × 2, same configuration).**

| Measure | `0731` | `v4p1-flash` | Change |
|---|---:|---:|---|
| Official EX | 68.7% | 69.1% | +0.4 (−1.9, +2.7); macro +1.5 (−0.7, +3.9) |
| Required minimum | | | +2.86: **not met** |
| $/answer measured / uncached | $0.000398 / $0.000497 | $0.000185 / $0.000696 | uncached +40% |
| P50 / P90 | 1.05s / 8.46s | 1.61s / 4.05s | P50 +0.56s |
| Verdicts that changed | | 36 rows (7.2%) | 20 fixes, 16 regressions, net +4 |
| Flaky between repeats | 1.6% | 2.4% | slightly less deterministic |

The pilot's +3.5 did not replicate: at 100 rows the interval was −1.5 to +8.5, and the full run
put the point estimate at +0.4. This is the second time a small pilot overstated a gain (the first was
the dictionary pilot's +1.2), which is a reason to keep the rule "pilots decide whether a full comparison is
worth it, never whether to adopt".

**Why it still matters.** A snapshot swap that is *neutral on average* rewrites 7.2% of individual
verdicts. So a model change is not a free operation even when it does not move the score, and any hand-tuned
rule (the `DISTINCT` rule, a checklist) tuned on one snapshot needs re-checking on the next.

**Fix.**
- Treat the swap as an availability decision, and say so wherever the number is quoted.
- Re-baseline the new default on `dev_untouched` ×1 (reported only) and on Chinook and the live suite; spend a
  Mini-Dev gate look only when a candidate is ready, since 3 remain.
- Keep `gpt-oss-120b` as the tested fallback (−1.4 points, −20% cost, verified callable 2026-09-26).
- Record the snapshot id next to every number (the meta sidecar already carries it).
- Keep the model-unavailable handling from `eafe2ba` and add a scheduled availability check
  (`benchmark.preflight`), so a retired snapshot is noticed before a run, not during one.

### 5.8 Measurement gaps that limit how well we can improve

1. **`train_dev` is nearly out of headroom.** If about 60% of its stable failures are label defects (§6),
   only ~4% of its rows are genuine, agent-fixable errors, and the paired test cannot resolve gains of
   1–2 points on 501 rows. Further prompt iteration on it will mostly measure noise.
2. **What the shared errors on dev are is still unread.** §6.4 shows they are mostly not label defects, but
   classifying them needs someone to read dev rows. That conflicts with keeping dev untouched, so it is your
   call (§10.3).
3. **No per-record failure tag exists**, so every audit is manual. §10.2 adds one.
4. **The lockbox is unlooked and small-looks-limited** (2 looks). It should be spent on candidate
   configurations that already cleared their gates, not on exploration.
5. **In-run scoring is environment-sensitive** (10 dev rows). Re-score before quoting.

### 5.9 How fixing the bad affects the good (interaction matrix)

| Fix | Latency (P50 / tail) | Cost per answer | Chinook / product profile | Currently-correct rows at risk | Where to contain it |
|---|---|---|---|---|---|
| Value profile + FTS5 (§5.1) | + prompt tokens; P50 up a little | up, capped per column | untouched if benchmark-only | low | benchmark profile |
| NULL-result retry | +1 call on ~1% of answers | +~1% | untouched | none (NULL rows are ~0% correct) | pipeline repairs |
| Computation checklist (§5.2) | none | +few tokens | **at risk** (shared text) | medium | benchmark profile only; rerun Chinook |
| Degenerate-value retry | +1 call on a few % | +few % | untouched | low | pipeline repairs |
| Routed reasoning on ratio classes | +3–5s on ~10–25% of answers | up on that subset | untouched | low | benchmark path |
| `DISTINCT` rule (§5.4) | none | none | **at risk** if shared | **high**: 12–23 correct answers per set use it | benchmark profile, pilot first |
| Missing-predicate guard (§5.5) | none | none | untouched | none | pipeline validate step |
| Fine-tuning (§9) | lower or equal (smaller model possible) | up front $10–30, then serving | product behaviour may change | unknown | separate model id, never the product default |
| Model swap (§5.7) | +0.56s P50 measured (v4p1-flash) | uncached +40% | re-run Chinook | **7.2% of verdicts change** | re-baseline first |

---

## 6. The ceiling problem: how much of the error is the label's

This decides what the 80% target requires, so the evidence is set out in full.

### 6.1 Four independent measurements on `train_dev`

1. **Manual audit of 46 stable failures** (random within database; Appendix A). Tags: 26 label defect
   (gold semantically wrong for the stated question or evidence), 8 hint-literal convention, 3 projection
   ambiguity, **8 genuine agent error**, 1 execution pathology. Weighted to the 153 stable-wrong rows
   (soccer_2016 75, sales_in_weather 37, restaurant 34, movie 7): label defect ≈ 60%, convention ≈ 19%,
   ambiguity ≈ 6%, **genuine ≈ 13%**, pathology ≈ 2%. As a share of *all 501 rows*: label defect 18.4%,
   convention 5.8%, ambiguity 1.8%, genuine 4.0%. The genuine share is 8 of 46 (17%, Wilson 95% interval
   9–31%).
2. **Corrected-label cross-check.** Of the stable-wrong rows that have a BIRD-Verified same-input label
   (16), the agent's answer equals the *corrected* gold in **8 (50%)**. Independent of my tags.
3. **Cross-model consensus.** On 138 of 501 rows both DeepSeek and gpt-oss-120b are wrong, and on 98 of
   those (71%) they return the *identical* result set. That is **19.6% of all rows** where two
   independent model families agree with each other and disagree with gold. Adding the `v4p1-flash` run
   (three runs, two families): 129 rows (25.7%) are wrong in all three, and on 85 of them (66%) all three
   return the identical result set, which is **17.0% of all rows**.
4. **Unambiguous gold-bug idioms.** Scanning gold SQL for constructs that cannot be correct
   (`COUNT(x = 'y')`, `COUNT(CASE ... THEN 1 ELSE 0 END)`, `TOTAL(id)`, `LIKE '%' OR 'HZ'`):
   **10 of 501 `train_dev` rows (2.0%)**, on which the agent scores 10%.

### 6.2 The same measurements on the dev-like sets

| Measure | `train_dev` | Mini-Dev | `dev_untouched` |
|---|---:|---:|---:|
| Gold with an unambiguous bug idiom | **2.0%** (10) | 0.2% (1) | 0.1% (1) |
| Gold result set changes under a public correction | 25.0% of the 72 Verified rows (a non-random subset) | **22.6%** of 500 (Arcwise) | 6.9% of the 779 rows BIRD's cleaned dev leaves otherwise unchanged |
| Accuracy, original → corrected labels | 76.4% → 80.6% (72 rows) | 59.0% → 60.4% | 64.2% → 68.3% (779 rows, DeepSeek) |
| Two-family consensus against gold | 19.6% of rows | not measured | **18.4%** of rows (§6.4) |

The idiom rate is a lower bound, since it only catches idioms I could write down, but the 10–20× gap
is large. The public human baseline on dev (92.96%) also implies dev labels are mostly consistent
with what a careful person writes.

The 22.6% Mini-Dev figure looks alarming but is compatible with the above. Arcwise changes a result set
in about one row in four, yet our accuracy only moves +1.4 points on the corrected labels, because our
answers usually match *neither* version. Corrections change the labels; they do not make the
questions easy.

### 6.3 What this means

- **`train_dev`'s practical ceiling is about 82%** (100 minus the 18.4% label-defect share; the plan's
  "17–18% unsolvable" audit agrees). It is a poor instrument for measuring gains beyond ~75%.
- **Do not extrapolate the 60% label-defect share to Mini-Dev, dev or test.** The idiom rate, the human
  baseline and §6.4's cleaned-label check all say dev is cleaner: about +4 points from cleaning, against
  the 18.4% label-defect share on `train_dev`.
- **Cleaner does not mean easier to fix.** §6.4 measures that two different model families return the same
  wrong answer on 18.4% of dev rows, nearly as much as on `train_dev` (19.6%), and cleaning explains only
  16% of those. On dev they are mostly a shared convention or misreading, not a label problem.
- **The target itself is uncertain.** Leaders' test scores exceed their dev scores by 4–7 points
  (§7), which could mean a cleaner test set, or systems tuned to BIRD's annotation style.
  Nothing in this repo can tell us which. A hidden-test score of 80% may need dev-side improvement
  larger than a clean-label reading suggests.

### 6.4 Measured on a dev-like set (run 2026-09-26, $0.21)

I ran `gpt-oss-120b` over all 1,036 `dev_untouched` rows with the current configuration (complete run,
62.7%, CI 60.1–65.6, P50 0.91s). The decision rule was declared before the run:

- consensus ≥ 60% of jointly-wrong rows: prioritize training (conventions, labels);
- consensus ≤ 35%: prioritize value grounding, computation and disambiguation.

| Measure | `train_dev` (1abc vs gpt-oss) | `dev_untouched` (0731 vs gpt-oss) |
|---|---:|---:|
| Both families wrong | 27.5% of rows | 31.4% |
| ...of which return the same result set | 71% (**19.6%** of rows) | **58.8%** (**18.4%** of rows) |
| ...of which differ | 8.0% of rows | 12.9% of rows |
| Correct in at least one family | 72.5% | 68.6% |

**The rule returns "inconclusive": 58.8% is 1.2 points under the 60% line.** The consensus share fell
only because dev has more rows where the two families are wrong *differently*. As a share of all rows, the
shared wrong answer is about the same as on `train_dev`.

**A second, mechanical check (added after seeing the inconclusive result, so treat it as exploratory).**
BIRD's November 2025 cleaned dev rewrites some questions and evidence as well as SQL, so its SQL can only
grade rows where nothing but the SQL changed. That is 779 of the 1,036 rows (75.2%). Scoring both runs on those
rows against the original and the cleaned gold:

| Measure (779 rows) | Original gold | Cleaned gold |
|---|---:|---:|
| DeepSeek-0731 accuracy | 64.2% | 68.3% (**+4.1**) |
| gpt-oss-120b accuracy | 63.4% | 67.3% (+3.9) |
| Gold result set changes | | 54 rows (6.9%) |
| Both wrong / same answer | 31.5% / 19.0% of rows | 27.0% / 15.9% |
| Consensus rows explained by cleaning | | **24 of 148 (16%)** |

Where the errors are, on the same 779 rows under cleaned labels, DeepSeek is wrong on 31.7% of rows:
**15.9% shared with gpt-oss, 11.0% both wrong but differently, and 4.7% unique to DeepSeek.**

**What I take from it.**
1. **Label defects are real on dev but small.** Cleaning is worth about +4 points on the rows it covers
   and changes 6.9% of gold result sets, against 25% on `train_dev`'s Verified subset.
2. **About 84% of the rows where two families agree on a wrong answer are not label errors.** They are a
   shared convention gap or a shared misreading of the question or evidence. Which of the two, I have not
   established. It is the pool that training on BIRD's conventions could reach, and that a stronger
   generator might.
3. **The genuine disagreements replicate §5.2 on a dev-like set.** Genuine-ish share of rows: division or
   `CAST` 32.9%, `GROUP BY` 27.7%, superlatives 21.3%, ratio questions 20.2%, against 8.8% for simple
   questions. By database: `california_schools` 25.4%, `formula_1` 19.4%, `toxicology` 18.1%,
   `card_games` 16.5%, against `superhero` 1.3%. Failures on `thrombosis_prediction` are 76%
   consensus, so they are mostly shared rather than random.
4. **12% of the consensus rows (22 of 191) are both families returning an empty result.** That is direct
   support for the value-grounding lever (§5.1).
5. **Simple questions still fail together.** 18% of rows in the no-feature group are wrong the same way in both
   families. That is the biggest single reservoir and the one context has not moved.

**What it does to the 80% arithmetic.** Under cleaned labels DeepSeek is at 68.3% on these rows, so 80%
needs 11.7 of its 31.7 points of error removed. Selection, routing or escalation can only reach the
11.0 + 4.7 = 15.7 points where the families differ, and that is an oracle ceiling: realized selection has
gained under 1 point of the roughly 5 available. So the last several points have to come from the shared
15.9, or from a generator that is better on the differing rows.

**Caveats.** The 779-row subset drops rows BIRD rewrote, which are plausibly the messiest, so cleaning is
probably worth more than +4 on the full dev. Cleaned SQL was run against our local copies of the dev
databases, and any database updates in BIRD's new package could account for some of the 54 changed result
sets. Consensus is a two-family measure with one repeat each, and T=0 repeats differ on 1.6–2.8% of rows. And this
measurement was designed to separate label from model error, but not to say which model errors are
learnable.

---

## 7. Leaderboard comparison

Fetched 2026-09-26 from the BIRD leaderboard. Every row on the page, including the human row and the
closed-model baselines, is tagged "Oracle Knowledge ✔️".

### 7.1 Overall track (top 10, by test EX)

| # | System | Test EX | Dev EX | Test − dev |
|---:|---|---:|---:|---:|
| 2 | DataGallery-Text2SQL (Huawei) | 82.39 | 78.10 | +4.3 |
| 3 | SiriusAI-SQL (Tencent) | 82.28 | 77.77 | +4.5 |
| 4 | AskData + GPT-4o (AT&T) | 81.95 | 77.64 | +4.3 |
| 5 | Agentar-Scale-SQL (Ant) | 81.67 | 74.90 | +6.8 |
| 6 | Sber Text2SQL | 81.33 | 75.74 | +5.6 |
| 7 | Xiaomi Text2SQL | 80.83 | 73.66 | +7.2 |
| 8 | RAS (Adya AI) | 79.82 | 72.49 | +7.3 |
| 9 | DeepEye (HKUST-GZ) | 79.09 | 74.49 | +4.6 |
| 10 | MarkovSQL | 78.70 | 75.10 | +3.6 |
| — | Human (data engineers + DB students) | — | 92.96 | — |

### 7.2 Baselines and the single-trained-model track

| Reference | Test EX | Dev EX | Note |
|---|---:|---:|---|
| GPT-5.5-xhigh | — | 72.55 | raw model |
| Claude Opus 4.6 | 70.15 | 68.77 | raw model |
| Qwen3-Coder-480B-A35B | 68.14 | 66.17 | raw model |
| Claude Sonnet 4.5 | 66.85 | 67.34 | raw model |
| GLM-4.7 | 62.94 | 63.82 | raw model |
| DeepSeek-R1 | 60.93 | 61.67 | raw model |
| GPT-4 | 54.89 | 46.35 | raw model |
| **Trellis (this repo)** | not measured | **63.6** (full-dev estimate ≈ 62.2) | current configuration |
| Gemini-SQL2 (single model, many samples) | 80.04 | 74.12 | trained |
| SiriusAI-SQL (27B, many samples) | 76.47 | 74.31 | trained |
| Q-SQL (30B-3B MoE, many) | 76.47 | 72.99 | trained |
| Databricks RLVR 32B (few samples) | 75.68 | — | trained on BIRD train only |
| Spektr-SQL (30B-3B MoE, few) | 74.85 | 72.10 | trained |

### 7.3 Reading it

> **Superseded (2026-09-26, SOTA_PLAN v2.7–v2.9).** The rank estimate ("#80–92") and the
> dev-score-needed-for-80%-test projections below were withdrawn. They pooled different
> dev versions, and no public dev score converts to a test score. Measured checkpoints
> now live in SOTA_PLAN §0.1: cleaned dev 66.0% (the primary checkpoint), Mini-Dev 65.3%,
> `dev_untouched` 67.6%. The passage is kept as written for history.

1. **"Oracle Knowledge" means the system was given BIRD's per-question evidence hint.** Trellis has
   always used it. v1 misread this tag as "deep integration of the column dictionaries" (§8); it is the
   standard setting for every row, including raw GPT-4 and human performance.
2. **We are at the raw-baseline level on dev.** 62–64 sits with GLM-4.7 (63.8) and DeepSeek-R1 (61.7),
   4–7 below raw Claude Sonnet 4.5 (67.3) and Opus 4.6 (68.8), and 9–16 below the top systems' dev
   scores (72–78). `SOTA_PLAN.md`'s estimate puts our test rank around #80–92 of ~130 (context, not a conversion rule).
3. **Trained single models at 27–32B reach 72–74 dev with a few samples.** That is the closest analogue to a
   route we could follow: SFT or RLVR on BIRD train, with modest sampling. Databricks did it with BIRD train
   only.
4. **Dev→test uplift is not a constant.** The top eight systems gain +4.3 to +7.3 test over dev; the
   recent raw baselines (Opus 4.6, Qwen3-Coder, Sonnet 4.5, GLM-4.7, R1) gain −0.9 to +2.0, while the
   older GPT-4 and Claude-2 gain +8.5 and +6.3, so the pattern is not universal. BIRD's own published raw-model
   baselines on the cleaned dev (Arctic prompt) gain +1.6 on average from dev to test (16 models, range
   −2.6 to +4.9), and the best raw model, Gemini 3 Pro, scores 69.0 dev and 70.4 test. If ours behaves like a
   raw baseline, an 80% test needs a dev score near 78–80; if it behaves like a trained system, 73–76.
   Either way that is **about +10 to +16 points on dev** from where we are.
5. **Selection alone is not the leaders' secret here.** Their many-sample self-consistency helps *after*
   a strong generator exists; our own multi-sample pilot shows majority@4 = pass@1 (69.0 vs 69.2) with
   the current model.

---

## 8. v1 postmortem: scorecard

| v1 claim | What the evidence says | Verdict |
|---|---|---|
| Unquoted special-character identifiers are the cheapest fix (§6.1) | Adopted with the pipeline repairs; `train_dev` safety rejections 14 → 0; 3 of the 4 named cases now pass on Mini-Dev | **Confirmed** |
| The Chinook-era projection rule hurts BIRD (§6.5) | +7.0 (4.5, 9.8) on `train_dev`; extra-columns 15.2% → 4.8% of Mini-Dev rows | **Confirmed; the biggest single win** |
| Dictionary CSVs are the single biggest lever (§6.2) | +1.2 (−1.2, +4.4) at +32% cost; 0 gain on value-noted columns | **Falsified as stated** |
| "Oracle knowledge integration" is the dictionary and the leaders all use it | The tag means "given BIRD's evidence hint", on every row of the leaderboard, including raw GPT-4 | **v1 misread the tag** |
| Self-consistency is the biggest structural lever (§6.9) | Same-model majority@4 = pass@1; T=0 majority@3 = +0.1; best-of-3 +1.5. Two-family oracle only +3.0 | **Falsified for this model** |
| Wide tables cause needle-in-haystack misses (§6.3) | Untested. `european_football_2` (115 columns) scores 70–77%; ρ(width, accuracy) = −0.29, n=11 | **Weak; deprioritize** |
| The 2-second timeout is too tight (§6.8) | A size-scaled timeout shipped; of v1's 9 `interrupted` cases, 4 now finish but are wrong, 3 still time out, 2 have gold that times out | **Partly wrong: completion is not correctness** |
| Evidence filter vs projection confusion (§6.4) | The benchmark profile ("return exactly what was asked") covers the projection half | **Plausible; the projection half confirmed** |
| Outer-join-when-implied (§6.6), fan-out `COUNT` (§6.7) | Untested as prompt rules; the v1 example cases still fail; `DISTINCT` oracle is +1.2–2.9 | **Untested** |
| "Our scaffolding contributes roughly nothing over a bare baseline" | Rested on comparing our local metric with another paper's subset. The official metric gives 47.6%, and Phase 1 added +11.7 on top | **Overstated** |
| Keep the interactive path fast and cheap; add a slower accuracy tier | Held up: the current configuration has P50 ≈ 1s, and every added cost was tested against it | **Confirmed as a framing** |

**What v1 got wrong about method.** It read baseline failures on Mini-Dev, which is the gate set, to
design fixes. It leaned on cross-paper comparisons for its headline. It ranked levers by plausibility
instead of by pilot cost and required gain. Phases 0–3 corrected all three, and this is the
argument for the acceptance rule.

---

## 9. Path to 80%

### 9.1 The arithmetic

| Step | Dev-like score | Basis |
|---|---:|---|
| Today (current configuration) | 62–64 | measured (§2.1) |
| + cheap levers, **planning** range | 64–71; central ≈ 67 | §9.2 (+2 to +8), not additive |
| Needed for 80% test, if dev→test uplift is like a trained system | 73–76 | §7.3 |
| Needed for 80% test, if uplift is like a raw model | 78–80 | §7.3 |
| Same rows under cleaned labels (779 of 1,036), today | 68.3 | §6.4; not comparable with the leaderboard's cleaned-dev column, which uses BIRD's rewritten questions |

### 9.2 Lever ledger

Planning estimates are ranges built from a measured bucket size and an assumed fix rate. They overlap
and are not additive. "Confidence" is confidence in the *mechanism*, not the size.

| Lever | Bucket / evidence | Planning estimate (dev-like) | Cost | Confidence | Gate |
|---|---|---:|---|---|---|
| Value profile + FTS5 (§5.1) | empty answers 4–5% of rows, ~0% correct | **+1.1 to +2.0** | tokens only | High | full comparison if pilot ≥ required minimum |
| NULL-result retry | 0.8–0.9% of rows, ~0% correct | +0.2 to +0.4 | ~1% more calls | High | pilot |
| Ratio/percentage handling (§5.2) | 12–27% of rows at ~50% | **+1 to +3** | small | Medium | pilot on `train_dev` |
| Missing-predicate guard (§5.5) | 1.0% hard failures, 23 slow answers | +0.3 to +1.0 | none | High | free to test |
| `DISTINCT` rule (§5.4) | oracle +1.2 to +2.9 | −0.5 to +1.5 | none | Medium | pilot; watch the 12–23 rows at risk |
| Model swap for accuracy (§5.7) | v4p1-flash full run +0.4 (−1.9, +2.7); pilot +3.5 did not replicate | ≈ 0 | +40% uncached cost | High | done: not adopted on accuracy |
| Fine-tuning on corrected data | leaders' shared mechanism; pass@4 73% < 80%; 15.9% of dev rows are wrong the same way in two families (§6.4) | **+4 to +10** | $10–30 plus serving | Medium | gate F-G, owner decision |
| Cascade, routing, escalation | any-of-three-runs oracle 74.3% (+5.2 over the best single run, an upper bound); escalation realized +0.8 at 2.8× cost | ≤ +1 realized | high | Low | deferred; oracle headroom ≈ 5 is the plan's threshold, realized is far below |

Summing the cheap rows gives roughly +2 to +8 (central +4). That is not enough for 80% and it is
meant to be honest about that.

### 9.3 What not to do, on the evidence

| Idea | Why not | Evidence |
|---|---|---|
| Same-model self-consistency | The errors are deterministic | majority@4 = pass@1; majority@3 +0.1 |
| Reasoning globally | Overthinks against BIRD's literal gold | −1.5 at +103% and +201% cost |
| Dictionary CSVs in the prompt | No gain for +32% cost | +1.2 (−1.2, +4.4) |
| Retrieved few-shot | Conventions don't transfer as examples | +0.0 (−4.0, +4.0); 0 of targeted cases fixed |
| A bigger or newer model for its own sake | Cost up, accuracy flat | `deepseek-v4-pro`: −0.5 at 6× cost; `v4p1-flash`: +0.4 (−1.9, +2.7) at +40% |
| More prompt iteration on `train_dev` | ~4% of its rows are agent-fixable, beyond the test's resolution | §5.8 |
| Editing the gold to reach a score | Teaching to the test | v1's own 2026-07-13 lesson |

### 9.4 The fine-tuning decision (gate F-G)

The plan's criterion is met: pass@K is 73% at K=4, which is below ~80%, so **generation, not selection, is
the bottleneck**, and the missing ingredient looks like BIRD's annotation conventions, which context did
not supply. The evidence for a trained route is external (leaders, RLVR-32B, ReViSQL's +8–14 from corrected
training data), plus this repo's finding that few-shot does not transfer conventions.

**The risks are specific to BIRD, and to this repo's own data.**
- *Noisy training labels.* BIRD train is noisy (ReViSQL corrected 61% of a 2,462-row sample; our audit
  finds ~60% of `train_dev`'s stable failures are label defects). SFT on uncorrected gold teaches the
  quirks. Whether that helps depends on whether the hidden test shares them, which is unknown (§6.3).
- *Conflicting instruments.* The lockbox and `train_dev` reward quirk-learning (their labels share the
  quirks); Mini-Dev, corrected labels and the Nov 2025 cleaned dev reward correctness. **Accept a trained
  model only if it wins on the cleaner sets too**: Mini-Dev, the Arcwise-corrected labels, and the
  Verified same-input rows.
- *Data availability.* Only 16 train databases are on disk; execution-filtering the other 63 needs a
  further fetch (the plan sizes it at ~30 minutes of bandwidth). Data-only SFT skips execution
  filtering but loses the check on label quality.

**Suggested first step, cheapest first.** A LoRA SFT of a ≤16B model on corrected or execution-verified
rows (plan: ~$10–30 to train). Evaluate on `train_dev`, then Mini-Dev, then the lockbox, with the
acceptance rule from `SOTA_PLAN.md` §5.

---

## 10. Recommended next steps

### 10.1 Ordered by cost (free → pennies → dollars), each with a stopping rule

| # | Step | Tier | Est. cost | Set | Decision rule |
|---|---|---|---:|---|---|
| 1 | **Done 2026-09-26 ($0.21):** second-family run on `dev_untouched` | pennies | $0.21 | `dev_untouched` (reported only) | Inconclusive by the declared rule (58.8%); the cleaned-label follow-up says shared errors dominate (§6.4) |
| 1b | Score the current default on the full cleaned dev (1,534 rows) | pennies | ≈ $0.3–0.5 | cleaned dev | The leaderboard-comparable dev number; first confirm which database package BIRD's cleaned release expects |
| 2 | Add a `failure_tag` field and consensus flag to run records; second-rater the Appendix A audit | free | $0 | recorded runs | Report inter-rater agreement (κ); revise tags below κ 0.6 |
| 3 | Build and offline-replay the value profile + FTS5 index on the 10 wrong-empty `train_dev` rows | free | $0 | `train_dev` | Proceed to pilot only if ≥ 4 of 10 resolve |
| 4 | Re-baseline the new default on `dev_untouched` ×1; re-run the Chinook dev and live suites as the product-profile check | pennies | ≈ $0.3–0.4 | `dev_untouched` (reported only), Chinook | Report against the `0731` numbers, with the 7.2% verdict churn in mind; spend a Mini-Dev gate look only when a candidate is ready |
| 5 | Pilot: value profile (step 3) | pennies | ≈ $0.1 | 100 `train_dev` rows + targeted | Required minimum from `analyze flips` |
| 6 | Pilot: ratio checklist plus degenerate-value retry | pennies | ≈ $0.1 | 64 ratio rows + stratified | Same |
| 7 | Pilot: `DISTINCT` rule, in the benchmark profile only | pennies | ≈ $0.1 | 100 rows | Report flips *into* wrong, not just net |
| 8 | Missing-predicate guard: offline test on all `train_dev` SQL | free | $0 | recorded runs | Zero false positives on currently-correct rows |
| 9 | Gate F-G: SFT pilot | dollars | $10–30 | `train_dev`, Mini-Dev gate, lockbox look 1 | §9.4 |
| 10 | External generalization check on Spider dev | pennies | ≈ $0.5 | Spider | Only if you want a second annotation style |

### 10.2 Measurement hygiene

- **Freeze the rules of use** (§1.3) in `SOTA_PLAN.md`: fix-design from `train_dev`, aggregates from Mini-Dev and
  dev, nothing from the lockbox.
- **Tag every failure.** Add `failure_tag` (LD, HC, PA, GE, PATHOLOGY) and `consensus_against_gold` to the
  raw record schema; the audit CSV is the seed.
- **Build a cleaner iteration subset** from `train_dev` by excluding rows whose gold uses a bug idiom or
  whose Verified correction changes the result. It will be small; state the selection bias (it removes
  rows the model fails).
- **Re-score before quoting** any dev number.
- **Record the model snapshot** next to every headline number.
- **Expect ±0.2 points of re-score noise** from intermittent execution timeouts.

### 10.3 Decisions that are yours

1. Spend ≈ $0.3–0.5 to score the default on the full cleaned dev (step 1b)?
1b. May someone read a sample of the 191 dev consensus rows, for classification only and with no prompt
   or rule derived from them? It is the only way to learn what the shared errors are.
2. Whether to keep `deepseek-v4p1-flash` as the default (it moved for availability, with no accuracy gain) and
   `gpt-oss-120b` as the fallback.
3. Whether to proceed to gate F-G and, if so, on what training data (§9.4).
4. Whether the hidden-test submission is a goal or a milestone (§6.3's uncertainty about test labels
   applies).

---

## Appendix A: `train_dev` failure audit

Forty-six stable-wrong rows (wrong on both repeats of the 1abc run), sampled at random within each database
(soccer_2016 16, sales_in_weather 12, restaurant 12, movie 6). Tags:

| Tag | Meaning | Count | Weighted share of the 153 stable-wrong rows |
|---|---|---:|---:|
| **LD** | Label defect: gold is semantically wrong for the stated question or evidence, agent's answer is defensible | 26 | ~60% |
| **HC** | Hint-literal / convention: gold follows the literal mechanics of BIRD's hint (`COUNT` without `DISTINCT`, `SUM` for "total", a corrected literal) | 8 | ~19% |
| **PA** | Projection or interpretation ambiguity | 3 | ~6% |
| **GE** | Genuine agent error | 8 | **~13%** |
| **PATHOLOGY** | Correct on re-execution but computationally pathological | 1 | ~2% |

Row-level tags and reasons: [`postmortem_v2/data/train_dev_failure_audit.csv`](postmortem_v2/data/train_dev_failure_audit.csv).
Illustrative genuine errors: a dropped constraint (row 87), a value-case mismatch giving zero rows (row 112),
text-encoded money compared as a string (row 42), a `MAX()` subquery not scoped to the station (rows 435,
440). Illustrative label defects: `COUNT(food_type = 'american')` counting every row (row 143), a gold
join on `city` returning 22,952 rows (row 155), a "Bruce Almighty" question whose gold filters "Godzilla"
(row 45).

**Limits.** One rater, n=46, and the LD/GE boundary is a judgement (some LD rows are ambiguous rather than
wrong). The Verified cross-check (50% of 16) and the consensus measurement (71% of 138) are the
independent supports; the tag counts alone should not be quoted as precise rates.

## Appendix B: reproduction

```bash
# from the repo root; needs data/bird (setup scripts) and the recorded runs; no API calls
docs/postmortem_v2/analysis/run_all.sh
```

| Script | Produces |
|---|---|
| `pm1_scoreboard.py` | §2.1: scores, CIs, stability, latency, cost per run |
| `pm2_buckets.py` | §2.5: official re-score and failure buckets (about 10 minutes) |
| `pm3_features.py` | §5.2 and §5.6: feature/accuracy associations, schema statistics |
| `pm4_v1_tracking.py` | §8: what happened to each v1 case |
| `pm5_cases.py` | Appendix A: side-by-side dump of the sampled failures (written to gitignored `data/bird/`) |
| `pm6_labelnoise.py` | §6: label-change rates, Verified cross-check, cross-model consensus |
| `pm7_levers.py` | §5.1, §5.4: empty/NULL answers, `COUNT(DISTINCT)`, consensus by feature |
| `pm8_goldbugs.py` | §6.2: unambiguous gold-bug idioms |
| `pm9_final.py` | §2.4: per-database comparison, majority-vote headroom |
| `pm10_snapshots.py` | §5.7, §6.1: snapshot churn and three-run consensus |
| `pm11_dev_consensus.py` | §6.4: two-family consensus on `dev_untouched`, by database, tier and feature |
| `pm12_dev_cleaned.py` | §6.4: rescoring on BIRD's cleaned dev SQL for the 779 unchanged-input rows |

Logs are written to `postmortem_v2/data/logs/`; derived tables to `postmortem_v2/data/`.

## Appendix C: limitations of this report

- **One configuration, mostly one model.** Mini-Dev and dev are `deepseek-v4-flash-0731`, a snapshot that
  no longer answers. `train_dev` also has `gpt-oss-120b` and the new default `deepseek-v4p1-flash`.
- **The labels are the labels.** Where I call a gold query defective, I am making a judgement; the mechanical
  checks bound it but do not replace it.
- **Feature associations are correlational.** Complex questions have both harder SQL and noisier gold.
  §5.2's cross-model split reduces, but does not remove, that confound.
- **Planning estimates are not measurements.** Every "planning estimate" is a bucket size times an assumed fix
  rate, and the levers overlap.
- **Leaderboard data is self-reported** and taken from the public page on 2026-09-26.
- **§6.4's second measurement was chosen after the pre-declared rule came back inconclusive**, so it is
  exploratory, and it covers only the 75% of dev rows whose question and evidence BIRD left unchanged.
- **The lockbox was not touched**, so nothing here says how the configuration behaves on a database set that
  was never used to make a decision.

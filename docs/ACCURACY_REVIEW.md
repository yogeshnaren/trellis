# Trellis accuracy review (2026-09-28)

A review of every saved BIRD run, the leaderboard, data audits and error patterns. It uses no new benchmark runs and no model-API spend. The interactive version of this report is a private artifact page (https://claude.ai/artifact/D6pbXgqWMnD6y4dErDAipd); this file records the same findings and numbers.

- **Hidden-test score: pending.** No test projection or leaderboard rank is given.
- **Privacy rule:** evaluation sets (cleaned dev, Mini-Dev, original dev) appear only as aggregates, and cells under 10 questions are suppressed. The lockbox appears only as its published aggregate. Individual questions are cited for training splits only.
- **Headlines use each run's recorded official EX**; re-execution of gold SQL was used only to tag result shapes.
- **Associations are not causes.** Pattern tables show where misses concentrate; causes come from the audit (section 6) and paired lever evidence (section 3).

Contents: 1 At a glance · 2 Leaderboard · 3 Our scores · 4 Difficulty · 5 Patterns · 6 Why wrong / right · 7 Data & audits · 8 Cost, stability & next steps · 9 Method · Appendix: audit labels

## 1. At a glance

### How Trellis answers a question (latest scored configuration)

| Step | What it does | In live path |
|---|---|---|
| Schema render | Full schema with keys and a few sample values | yes |
| Database facts | Up to 4 facts: text-stored formats, exact value locations, non-unique joins | yes |
| Generation | deepseek-v4p1-flash, T=0, no reasoning, strict JSON schema, benchmark prompt | yes |
| Safety check | AST gate: SELECT/WITH only, read-only connection | yes |
| Execute | Local SQLite, full result | yes |
| Repair / retries | 1 repair on error; empty-result and refusal retry; truncation retry at 1,200 tokens | yes |
| Candidates & selection | Single answer; no candidate bank or selector | no |

### Scores on every set we hold

| Set | EX | Coverage | 95% CI | Macro | Kind | Sample? | Run and configuration |
|---|---:|---|---|---|---|---|---|
| Cleaned dev (BIRD dev-1106) | 66.5% | 1,020/1,534 answers (1,534 questions × 1) | 64.1–68.9 | 64.4% | evaluation (aggregates) | full set | `rank1b_cleaned_dev_full`, deepseek-v4p1-flash, benchmark profile, facts, commit `2f4366d` |
| Mini-Dev (gate 3) | 64.1% | 962/1,500 answers (500 questions × 3) | 60.0–68.2 | 62.8% | evaluation (aggregates) | full set | `20260927T083717Z`, deepseek-v4p1-flash, benchmark profile, facts, truncation retry, commit `5cd38e9` |
| Original dev, untouched rows | 67.6% | 700/1,036 answers (1,036 questions × 1) | 64.7–70.4 | 68.1% | evaluation (aggregates) | full set | `20260926T212111Z`, deepseek-v4p1-flash, benchmark profile, commit `eafe2ba` |
| train_dev (practice set) | 70.2% | 703/1,002 answers (501 questions × 2) | 66.2–74.1 | 72.4% | training | full set | `20260927T060549Z`, deepseek-v4p1-flash, benchmark profile, facts, commit `1a0bd06` |
| train_dev2 pilot | 56.0% | 56/100 answers (100 questions × 1) | 46.2–65.8 | 56.0% | training | 100 of 503 questions (25 per database), Jev-pilot control arm | `20260927T095517Z`, deepseek-v4p1-flash, benchmark profile, facts, truncation retry, commit `fc584fd` (dirty) |
| Numbers stored as text (train_design) | 30.4% | 59/194 answers (194 questions × 1) | 23.9–36.9 | 35.1% | training | 194 targeted questions whose gold uses text-stored numbers numerically; scored before database facts | `20260927T041334Z`, deepseek-v4p1-flash, benchmark profile, commit `77ee38b` (dirty) |
| train_lockbox midpoint (sealed) | 81.14% | vs 79.24% without facts; paired +1.9 [-0.19, +4.19] | — | — | sealed (published aggregate) | 175 of 974 questions (25 per database × 7), 3 repeats per arm | 1 of 2 looks used; 799 rows sealed. Only the published aggregate is shown. |
| BIRD hidden test | pending | — | — | — | — | — | Submission via OpenRouter pinned to Fireworks is next |

**Not fully evaluated with the current configuration:** train_dev2 (only a 100-question pilot); the full train_lockbox (799 rows sealed); the original full dev (the untouched 1,036-row subset was scored before database facts); the Mini-Dev legacy baseline (47.6%; Official re-score; the old local metric showed 45.8%).

**Audit headline:** of the 167 wrong training-set answers the audit could settle, the answer key was wrong in **73**; our answer was wrong (alone or with the key) in **75**; both acceptable 12; ambiguous 7 (section 6).

## 2. Leaderboard comparison

Scores accessed 2026-09-28 from the [BIRD leaderboard](https://bird-bench.github.io/); every score below was checked against the live page. Capability cells are filled only where a paper or submission page supports them (sources in the notes below the table); otherwise `?` (undisclosed). A company's product architecture does not count as evidence for its BIRD submission. Leaders' dev versions are mostly unstated; Trellis's dev figure is cleaned dev (dev-1106), so the dev columns are not directly comparable.

Legend: ✓ has it · ◐ partial · ✗ no · ? undisclosed

| # | System | Dev | Test | Size | Schema linking | Value retrieval | DB profiling | Examples | Several generators | Candidates | Trained selector | Repair | Fine-tuned | RL | Exec checks | Optimizer |
|---:|---|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | **Trellis** (this project) | 66.49* | pending | API | ✗ | ◐ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ | ✗ |
| 1 | DataGallery-Text2SQL (Huawei 2012 Labs) | 78.1 | 82.39 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 2 | SiriusAI-SQL (Tencent Data Computing Platform) | 77.77 | 82.28 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 3 | AskData + GPT-4o (AT&T CDO - DSAIR) | 77.64 | 81.95 | UNK | ? | ? | ✓ | ? | ? | ? | ? | ? | ✗ | ✗ | ? | ? |
| 4 | Agentar-Scale-SQL (Ant Group) | 74.9 | 81.67 | UNK | ✗ | ✓ | ? | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ◐ | ? |
| 5 | Sber Text2SQL (SberData Research) | 75.74 | 81.33 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 6 | Xiaomi Text2SQL (Xiaomi ITP & Data) | 73.66 | 80.83 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 7 | RAS (Adya AI) | 72.49 | 79.82 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 8 | DeepEye (HKUST(GZ)) | 74.49 | 79.09 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 9 | MarkovSQL (Anonymous) | 75.1 | 78.7 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 10 | DeepEye-SQL (HKUST(GZ)) | 74.49 | 78.42 | 27B | ✓ | ✓ | ? | ◐ | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ | ? |
| 11 | Spektr-SQL (Amazon Ads - SpektrBot) | 73.09 | 78.31 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 12 | LongData-SQL (LongShine AI Research) | 74.32 | 77.53 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 13 | AxisSQL (UST) | — | 76.86 | 31B | ✓ | ✓ | ◐ | ✓ | ◐ | ◐ | ? | ✓ | ? | ? | ✓ | ? |
| 14 | GT-ChatBI-SQL (MR Tech) | 75.95 | 76.8 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 15 | Zhiwen-Lingsi-Agent (China Telecom, TeleAI) | 73.53 | 76.63 | UNK | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |

\* cleaned dev (dev-1106).

### Capability evidence (non-undisclosed cells)

**AskData + GPT-4o** ([paper](https://arxiv.org/abs/2505.19988))

- DB profiling: **yes**. Abstract says the BIRD submission used database profiling alone as its metadata source. ([source](https://arxiv.org/abs/2505.19988), accessed 2026-09-28)
- Fine-tuned: **no**. Abstract says the submission used no specially tuned model (GPT-4o). ([source](https://arxiv.org/abs/2505.19988), accessed 2026-09-28)
- RL: **no**. No tuned model was used per the abstract, so no RL-trained model. ([source](https://arxiv.org/abs/2505.19988), accessed 2026-09-28)

**Agentar-Scale-SQL** ([paper](https://arxiv.org/abs/2509.24403))

- Schema linking: **no**. Paper says it has no built-in schema linking and feeds the full schema in two formats. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- Value retrieval: **yes**. Retrieves relevant database cells by embedding similarity. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- Examples: **yes**. ICL generator uses examples retrieved by embedding similarity. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- Several generators: **yes**. Combines an RL-tuned reasoning generator with an ICL generator using different schema formats. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- Candidates: **yes**. Default 9 ICL + 8 reasoning candidates = 17 before refinement and selection. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- Trained selector: **yes**. A reasoning selector fine-tuned with GRPO on about 8.5k training samples runs pairwise tournaments. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- Repair: **yes**. Includes an SQL fixer and an SQL revisor stage. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- Fine-tuned: **yes**. Reasoning generator and selector are fine-tuned from an OmniSQL-32B base. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- RL: **yes**. GRPO training on BIRD training data only. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)
- Exec checks: **partial**. RL reward is execution-based; inference-time execution use in the fixer was not confirmed in text I read. ([source](https://arxiv.org/html/2509.24403), accessed 2026-09-28)

**DeepEye-SQL** ([paper](https://arxiv.org/abs/2510.17586))

- Schema linking: **yes**. Combines three linking techniques: direct LLM analysis, reverse-from-SQL, and value matching. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- Value retrieval: **yes**. Embedding search with an HNSW index returns top-5 similar values per text column. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- Examples: **partial**. One of three generators is ICL-based; how demonstrations are chosen was not confirmed. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- Several generators: **yes**. Three generators: skeleton-based, ICL-based and divide-and-conquer. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- Candidates: **yes**. Reported as three candidates, one per generator strategy (not cross-checked in tables). ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- Trained selector: **no**. Selection is confidence-aware and execution-guided; the system is training-free. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- Repair: **yes**. Deterministic checkers trigger targeted LLM revision when they find errors. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- Fine-tuned: **no**. Paper states it uses open-source models without any fine-tuning. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- RL: **no**. Training-free system; no RL stage. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)
- Exec checks: **yes**. A Syntax-Logic-Quality tool chain tests candidates before selection. ([source](https://arxiv.org/html/2510.17586), accessed 2026-09-28)

**AxisSQL**

- Schema linking: **yes**. Pipeline stage 2 is schema linking. ([source](https://github.com/ShaikNagurShareef/AxisSQL), accessed 2026-09-28)
- Value retrieval: **yes**. Pipeline stage 1 is value retrieval for grounding. ([source](https://github.com/ShaikNagurShareef/AxisSQL), accessed 2026-09-28)
- DB profiling: **partial**. README studies profiling and LLM-summarised column metadata only as an optional scaling knob. ([source](https://github.com/ShaikNagurShareef/AxisSQL), accessed 2026-09-28)
- Examples: **yes**. Config points to a file of few-shot examples for in-context learning. ([source](https://github.com/ShaikNagurShareef/AxisSQL), accessed 2026-09-28)
- Several generators: **partial**. Stage 3 samples diverse candidates; distinct generator models or strategies were not confirmed. ([source](https://github.com/ShaikNagurShareef/AxisSQL), accessed 2026-09-28)
- Candidates: **partial**. Candidate count N is a configurable width; the value used for the submission is not stated. ([source](https://github.com/ShaikNagurShareef/AxisSQL), accessed 2026-09-28)
- Repair: **yes**. Stage 4 is checker-style SQL revision. ([source](https://github.com/ShaikNagurShareef/AxisSQL), accessed 2026-09-28)
- Exec checks: **yes**. Aggregation agent runs candidates and verifies results. ([source](https://github.com/ShaikNagurShareef/AxisSQL), accessed 2026-09-28)

**Trellis** (from this repository)

- Schema linking: **no**. Renders the full schema; no pruning step. (`src/schema.py`)
- Value retrieval: **partial**. Local full-text value index feeds exact value-location facts only. (`src/db_profile.py, benchmark/profile_context.py`)
- DB profiling: **yes**. Offline per-database profile: text formats, NULL rates, join cardinality. (`src/db_profile.py`)
- Examples: **no**. Retrieved few-shot tested (+0.0) and not adopted. (`docs/DECISIONS.md`)
- Several generators: **no**. One generator; the 4-candidate bank is a diagnostic only. (`benchmark/bank.py`)
- Candidates: **no**. 1 answer per question. (`src/agent.py`)
- Trained selector: **no**. None; Jev (LLM) selection lost to majority vote. (`jev_shadow_outcome.md`)
- Repair: **yes**. One repair on execution error; empty, refusal and truncation retries. (`src/agent.py`)
- Fine-tuned: **no**. Off-the-shelf model. (`src/costs.py`)
- RL: **no**. None.
- Exec checks: **yes**. AST safety gate, read-only execution, empty-result retry. (`src/db.py`)
- Optimizer: **no**. None.

### Single-trained-model track

| System | Dev | Test | Size |
|---|---:|---:|---|
| Gemini-SQL2 | 74.12 | 80.04 | UNK |
| Gemini-SQL (Multitask SFT + Gemini-2.5-Pro) | 73.27 | 77.14 | UNK |
| SiriusAI-SQL | 74.31 | 76.47 | 27B |
| Q-SQL | 72.99 | 76.47 | 30B-3B-MoE |
| Databricks RLVR 32B | — | 75.68 | 32B |
| Spektr-SQL | 72.1 | 74.85 | 30B-3B-MoE |
| Sophon-Text2SQL-32B | 72.43 | 74.79 | 32B |
| ELG-SQL | 73.4 | 74.51 | 32B |

### Research report vs our measured evidence

| Report recommends | What we measured | Status | Scope |
|---|---|---|---|
| Build database intelligence / grounding first | Four grounding levers ≈ 0 on BIRD: facts +0.8 [−0.3, +2.0] (train_dev), +0.52 [−0.46, +1.50] (cleaned dev), −1.1 (Mini-Dev); column notes −1.5; dictionary +0.9. BIRD hints already carry 95–97% of gold literals. | Contradicted | On BIRD; untested for no-hint (product) use |
| Generate genuinely different candidates | Same-model variants (plan-first, decompose) −2.3 to −2.5 each; the old 4-candidate bank's oracle was 73.5% vs 69.5% direct (that bank, its noisy gold). | Partial | Other model families not tried |
| Learned selector, not majority vote | Jev (untrained LLM) chose 29 correct vs majority's 39 on 102 disagreements. No trained selector tested. | Untested | Zero-shot LLM selection contradicted |
| Semantic contract / requirement checks | Jev requirement coverage found 0/5 hand-labelled omissions. | Weak | One variant |
| Execution-guided repair | Quoting + repairs +1.6 [+0.2, +3.0] on train_dev. | Supported |  |
| More reasoning helps | Reasoning low −1.5, high −1.5 (train_dev, 100 questions). | Contradicted | For this model |
| In-context examples | Few-shot 0.0 [−4.0, +4.0]. | Contradicted | Static retrieved few-shot only |
| Train a SQL specialist (SFT → RL) | Training-pool screen: 18 clear defects in 100 rows (17.5% weighted), 82 unresolved; gate is 15%. | Untested | Data gate not met; BIRD requires downloadable weights |
| Counterfactual (perturbed-data) verification | Not built. | Untested | Relevant: BIRD grades test with new test values |
| Adaptive, confidence-gated compute | Not built. | Untested |  |
| Benchmark labels are noisy | Answer-key review: key wrong in 153 of 252 selected disputes; this audit: 73 of 167 settled wrong training answers. | Supported | Selected cases, not a set-wide rate |

### Research-report claims we checked

| Status | Claim | Note | Source |
|---|---|---|---|
| verified | Agentar candidate oracle upper bound 84.29% vs 74.90% final selected accuracy | Both on the dev set (Figure 3 upper bound with all generators; Table 2 final EX). Paper does not say which dev version. The 9.39 gap is arithmetic. | [link](https://arxiv.org/html/2509.24403) |
| verified | Agentar test breakdown 949/555/285 with 86.83/78.20/71.23 | Table 3, BIRD test. Weighted average of the three is 81.67, matching the leaderboard test EX. | [link](https://arxiv.org/html/2509.24403) |
| verified | CHASE-SQL loses 4.17 without the learned selector | BIRD dev: 73.01 full vs 68.84 with self-consistency (-4.17); a ranker agent gives 65.51. | [link](https://arxiv.org/html/2410.01943) |
| not found | XiYan-SQL loses 4.04 with a single generator | Table 8 (BIRD dev) shows -2.91 without the fine-tuned generator and -2.74 without the selection model; no single-generator row or -4.04. Other paper versions unchecked. Report's -3.13 and -1.24 also not found. | [link](https://arxiv.org/pdf/2411.08599) |
| verified | CHESS loses 4.76 without entity retrieval | Ablation on the subsampled dev set: 64.62 to 59.86, not the full dev set. Table selection -6.12, column selection -5.44, revision -6.80 also match; the 72.4% with correct context is on full dev. | [link](https://arxiv.org/html/2405.16755) |
| verified | DeepEye loses 2.1 without value retrieval | It is the DeepEye-SQL paper, not the DeepEye system (arXiv 2603.28889). BIRD dev, Qwen3-Coder-30B-A3B, full system 73.5. | [link](https://arxiv.org/html/2510.17586) |
| verified | Arctic unfiltered synthetic data 64.9 to 64.6 vs 66.5 filtered | Table 4, Qwen2.5-Coder-14B with GRPO, BIRD dev: 64.9 no synthetic, 64.6 unfiltered, 66.5 filtered. | [link](https://arxiv.org/html/2505.20315) |
| verified | BIRD evidence raises GPT-4 test EX from 34.88 to 54.89 | Table 2 of the BIRD paper, test set. GPT-4 dev is 30.90 without and 46.35 with knowledge. | [link](https://arxiv.org/html/2305.03111) |
| verified | DataGallery reports 82.39 test EX and 77.64 R-VES, with method details still to come | Page also gives dev 78.10 on 1,534 questions and says more details will follow in an arXiv preview. | [link](https://datagallery.cn/benchmark) |
| verified | AskData test submission used profiling alone with GPT-4o and no tuned model | Stated in the abstract; the report's other AskData points (query-log mining, SQL-to-text) are only described there as techniques the authors explored. | [link](https://arxiv.org/abs/2505.19988) |
| verified | Every overall leaderboard row is tagged Oracle Knowledge (postmortem note) | All 18 rows I read in the page source carry the tick. Sources disagree on whether human 92.96 sits in the dev or test column (page source and BIRD paper say test; postmortem and one live-page read say dev). | [link](https://raw.githubusercontent.com/bird-bench/bird-bench.github.io/main/index.html) |

## 3. Our scores

### What moved the number (paired evidence only)

Each row compares two runs on the same questions; repeats are averaged per question first. Intervals are question-level bootstraps within databases. ↑ fixes / ↓ regressions are question counts. Compare rows within a set.

| Set | Lever | Questions | Δ points | 95% CI | Macro CI | Fixes | Regressions | Verdict |
|---|---|---:|---:|---|---|---:|---:|---|
| train_dev | Benchmark prompt profile | 501 | +6.99 | [+4.49, +9.78] | [+3.03, +10.98] | 49 | 13 | helps |
| train_dev | Identifier quoting + pipeline repairs | 501 | +1.60 | [+0.20, +2.99] | [+1.13, +7.05] | 14 | 5 | helps |
| train_dev | Model v4-flash-0731 → v4p1-flash | 501 | +0.40 | [-1.90, +2.69] | [-0.69, +3.94] | 24 | 23 | not distinguishable from 0 |
| train_dev | Database facts (rank 1b) | 501 | +0.80 | [-0.30, +2.00] | [+0.05, +3.51] | 11 | 5 | not distinguishable from 0 |
| train_dev | Reasoning, low effort | 100 | -1.50 | [-6.50, +3.50] | [-6.50, +3.50] | 4 | 7 | not distinguishable from 0 |
| train_dev | Reasoning, high effort | 100 | -1.50 | [-6.50, +3.00] | [-6.50, +3.00] | 4 | 8 | not distinguishable from 0 |
| train_dev | Few-shot examples | 100 | +0.00 | [-4.00, +4.00] | [-4.00, +4.00] | 3 | 3 | not distinguishable from 0 |
| train_dev | Data dictionary | 114 | +0.88 | [-0.88, +3.07] | [-0.57, +3.17] | 2 | 1 | not distinguishable from 0 |
| train_dev | Column notes (rank 1c) | 100 | -1.50 | [-5.50, +2.50] | [-5.50, +2.50] | 3 | 5 | not distinguishable from 0 |
| train_dev | Model → gpt-oss-120b | 501 | -1.40 | [-3.89, +1.10] | [-3.51, +1.37] | 22 | 26 | not distinguishable from 0 |
| train_dev | Strategy: query plan first | 501 | -2.50 | [-4.59, -0.40] | [-5.08, -0.02] | 11 | 24 | hurts |
| train_dev | Strategy: decompose | 501 | -2.30 | [-4.29, -0.20] | [-5.14, +0.15] | 12 | 24 | hurts |
| train_dev | Model → glm-5p3-flash | 501 | -2.50 | [-4.69, -0.20] | [-6.19, -0.80] | 15 | 26 | hurts |
| mini_dev | Model v4-flash-0731 → v4p1-flash | 500 | +5.93 | [+3.20, +8.73] | [+2.94, +8.79] | 62 | 28 | helps |
| mini_dev | Database facts + truncation retry | 500 | -1.13 | [-2.73, +0.40] | [-3.03, +0.31] | 20 | 30 | not distinguishable from 0 |
| dev_untouched | Model v4-flash-0731 → v4p1-flash | 1036 | +3.96 | [+2.12, +5.89] | [+2.06, +6.43] | 74 | 33 | helps |
| dev_untouched | Model → gpt-oss-120b | 1036 | -0.87 | [-2.90, +1.06] | [-3.08, +1.38] | 52 | 61 | not distinguishable from 0 |
| cleaned_dev | Database facts (rank 1b) | 1534 | +0.52 | [-0.46, +1.50] | [-0.82, +1.41] | 33 | 25 | not distinguishable from 0 |
| train_dev2_pilot | Jev starting-table advisory | 100 | +1.00 | [+0.00, +3.00] | [+0.00, +3.00] | 1 | 0 | not distinguishable from 0 |
| train_dev2_pilot | Jev evidence-role advisory | 100 | +0.00 | [+0.00, +0.00] | [+0.00, +0.00] | 0 | 0 | not distinguishable from 0 |

### Every saved run

Leaderboard systems publish no scores on our training sets and cannot be run here. Lockbox runs are excluded (sealed).

| Run | Question set | Configuration | Questions | Rep. | Correct / answers | EX | Commit |
|---|---|---|---:|---:|---:|---:|---|
| `20260924T005317Z` | train_dev.json | deepseek-v4-flash-0731 | 501 / 501 | 2 | 602 / 1,002 | 60.1% | `5a69af6` |
| `20260924T025109Z` | train_dev.json (sample) | deepseek-v4-flash-0731, benchmark profile, no quoting/repairs | 131 / 501 | 2 | 167 / 262 | 63.7% | `6d18d06`* |
| `20260924T025240Z` | train_dev.json (sample) | deepseek-v4-flash-0731, product profile | 94 / 501 | 2 | 119 / 188 | 63.3% | `6d18d06`* |
| `20260924T170715Z` | train_dev.json | deepseek-v4-flash-0731, benchmark profile, no quoting/repairs | 501 / 501 | 2 | 672 / 1,002 | 67.1% | `6d18d06`* |
| `20260924T174901Z` | train_dev.json (sample) | deepseek-v4-flash-0731, benchmark profile | 115 / 501 | 2 | 158 / 230 | 68.7% | `1694580`* |
| `20260924T175733Z` | train_dev.json | deepseek-v4-flash-0731, benchmark profile | 501 / 501 | 2 | 688 / 1,002 | 68.7% | `1694580`* |
| `20260924T212220Z` | train_dev.json (sample) | deepseek-v4-flash-0731, benchmark profile, dictionary | 114 / 501 | 2 | 175 / 228 | 76.8% | `731c642`* |
| `20260924T232302Z` | mini_dev_sqlite.json | deepseek-v4-flash-0731, benchmark profile | 500 / 500 | 3 | 890 / 1,500 | 59.3% | `285272c` |
| `20260924T234400Z` | train_dev.json (sample) | deepseek-v4-flash-0731, benchmark profile, reasoning low | 100 / 501 | 2 | 134 / 200 | 67.0% | `0100aa3`* |
| `20260924T234952Z` | train_dev.json (sample) | deepseek-v4-flash-0731, benchmark profile, reasoning high | 100 / 501 | 2 | 134 / 200 | 67.0% | `0100aa3`* |
| `20260925T004347Z` | train_dev.json (sample) | glm-5p3-flash, benchmark profile | 100 / 501 | 2 | 110 / 200 | 55.0% | `4ec49c8`* |
| `20260925T004655Z` | train_dev.json (sample) | deepseek-v4p1-flash, benchmark profile | 100 / 501 | 2 | 144 / 200 | 72.0% | `4ec49c8`* |
| `20260925T005017Z` | train_dev.json (sample) | deepseek-v4-pro-0813, benchmark profile | 100 / 501 | 2 | 136 / 200 | 68.0% | `4ec49c8`* |
| `20260925T005138Z` | train_dev.json (sample) | gpt-oss-120b, benchmark profile, reasoning low | 100 / 501 | 2 | 136 / 200 | 68.0% | `4ec49c8`* |
| `20260925T005619Z` | train_dev.json (sample) | deepseek-v4-flash-0731, benchmark profile | 100 / 501 | 4 | 277 / 400 | 69.2% | `4ec49c8`* |
| `20260925T011431Z` | train_dev.json (sample) | deepseek-v4-flash-0731, benchmark profile, 3-shot | 100 / 501 | 2 | 137 / 200 | 68.5% | `a9ab833`* |
| `20260925T014328Z` | train_dev.json (sample) | glm-5p3-flash, benchmark profile, reasoning low | 100 / 501 | 2 | 137 / 200 | 68.5% | `a9ab833`* |
| `20260925T014638Z` | train_dev.json | gpt-oss-120b, benchmark profile | 501 / 501 | 2 | 674 / 1,002 | 67.3% | `a9ab833`* |
| `20260925T014854Z` | train_dev.json (sample) | glm-5p3, benchmark profile, reasoning low | 92 / 501 | 1 | 33 / 92 | 35.9% | `a9ab833`* |
| `20260925T015202Z` | dev_untouched.json | deepseek-v4-flash-0731, benchmark profile | 1036 / 1036 | 1 | 659 / 1,036 | 63.6% | `a9ab833`* |
| `20260925T015827Z` | train_dev.json | deepseek-v4p1-flash, benchmark profile | 501 / 501 | 2 | 648 / 1,002 | 64.7% | `a9ab833`* |
| `20260925T020504Z` | train_dev.json (sample) | nemotron-lightning-3p5-30b-a3b, benchmark profile, reasoning low | 100 / 501 | 2 | 9 / 200 | 4.5% | `a9ab833`* |
| `20260926T203859Z` | train_dev.json | deepseek-v4p1-flash, benchmark profile | 501 / 501 | 2 | 692 / 1,002 | 69.1% | `a9ab833`* |
| `20260926T211555Z` | mini_dev_sqlite.json | deepseek-v4p1-flash, benchmark profile | 500 / 500 | 3 | 979 / 1,500 | 65.3% | `eafe2ba` |
| `20260926T212111Z` | dev_untouched.json | deepseek-v4p1-flash, benchmark profile | 1036 / 1036 | 1 | 700 / 1,036 | 67.6% | `eafe2ba` |
| `20260926T212754Z` | train_dev.json | deepseek-v4p1-flash, benchmark profile | 501 / 501 | 2 | 695 / 1,002 | 69.4% | `eafe2ba` |
| `20260926T214735Z` | dev_untouched.json (sample) | gpt-oss-120b, benchmark profile | 55 / 1036 | 1 | 26 / 55 | 47.3% | `512bbb6` |
| `20260926T215536Z` | dev_untouched.json | gpt-oss-120b, benchmark profile | 1036 / 1036 | 1 | 650 / 1,036 | 62.7% | `512bbb6` |
| `20260927T022912Z` | dev_20251106.json (sample) | deepseek-v4p1-flash, benchmark profile | 99 / 1534 | 1 | 59 / 99 | 59.6% | `77ee38b`* |
| `20260927T025554Z` | dev_20251106.json | deepseek-v4p1-flash, benchmark profile | 1534 / 1534 | 1 | 1,012 / 1,534 | 66.0% | `77ee38b`* |
| `20260927T032348Z` | train_dev.json (sample) | deepseek-v4p1-flash, benchmark profile, truncation retry | 100 / 501 | 1 | 74 / 100 | 74.0% | `77ee38b`* |
| `20260927T032603Z` | train_dev.json (sample) | deepseek-v4p1-flash, benchmark profile, truncation retry | 100 / 501 | 1 | 73 / 100 | 73.0% | `77ee38b`* |
| `20260927T034045Z` | train_dev.json (sample) | deepseek-v4p1-flash, benchmark profile, column notes | 100 / 501 | 2 | 140 / 200 | 70.0% | `77ee38b`* |
| `20260927T041334Z` | train_design.json (sample) | deepseek-v4p1-flash, benchmark profile | 194 / 5851 | 1 | 59 / 194 | 30.4% | `77ee38b`* |
| `20260927T043815Z` | train_dev.json (sample) | deepseek-v4p1-flash, benchmark profile, reasoning low, truncation retry, strategy decompose | 12 / 501 | 1 | 9 / 12 | 75.0% | `483a106`* |
| `20260927T043833Z` | train_dev.json (sample) | deepseek-v4p1-flash, benchmark profile, reasoning low, truncation retry, strategy plan | 12 / 501 | 1 | 9 / 12 | 75.0% | `483a106`* |
| `20260927T044613Z` | train_dev.json | glm-5p3-flash, benchmark profile, reasoning low, truncation retry | 501 / 501 | 1 | 335 / 501 | 66.9% | `483a106`* |
| `20260927T045227Z` | train_dev.json | deepseek-v4p1-flash, benchmark profile, reasoning low, truncation retry, strategy plan | 501 / 501 | 1 | 335 / 501 | 66.9% | `483a106`* |
| `20260927T045254Z` | train_dev.json | deepseek-v4p1-flash, benchmark profile, reasoning low, truncation retry, strategy decompose | 501 / 501 | 1 | 336 / 501 | 67.1% | `483a106`* |
| `20260927T054448Z` | train_dev.json (sample) | deepseek-v4p1-flash, benchmark profile, facts | 100 / 501 | 2 | 144 / 200 | 72.0% | `3b09665` |
| `20260927T055053Z` | train_dev.json (sample) | deepseek-v4p1-flash, benchmark profile, facts | 100 / 501 | 2 | 149 / 200 | 74.5% | `1a0bd06` |
| `20260927T060549Z` | train_dev.json | deepseek-v4p1-flash, benchmark profile, facts | 501 / 501 | 2 | 703 / 1,002 | 70.2% | `1a0bd06` |
| `20260927T072828Z` | dev_20251106.json | deepseek-v4p1-flash, benchmark profile, facts | 1534 / 1534 | 1 | 930 / 1,387 | 67.0% | `2f4366d` |
| `20260927T073427Z` | dev_20251106.json (sample) | deepseek-v4p1-flash, benchmark profile, facts | 148 / 1534 | 1 | 90 / 148 | 60.8% | `2f4366d` |
| `20260927T083717Z` | mini_dev_sqlite.json | deepseek-v4p1-flash, benchmark profile, facts, truncation retry | 500 / 500 | 3 | 962 / 1,500 | 64.1% | `5cd38e9` |
| `20260927T095517Z` | jev_live_pilot_questions.json | deepseek-v4p1-flash, benchmark profile, facts, truncation retry | 100 / 100 | 1 | 56 / 100 | 56.0% | `fc584fd`* |
| `20260927T095645Z` | jev_live_pilot_questions.json | deepseek-v4p1-flash, benchmark profile, facts, truncation retry | 100 / 100 | 1 | 57 / 100 | 57.0% | `fc584fd`* |
| `20260927T095825Z` | jev_live_pilot_questions.json | deepseek-v4p1-flash, benchmark profile, facts, truncation retry | 100 / 100 | 1 | 56 / 100 | 56.0% | `fc584fd`* |
| `rank1b_cleaned_dev_full` | dev_20251106.json | deepseek-v4p1-flash, benchmark profile, facts | 1534 / 1534 | 1 | 1,020 / 1,534 | 66.5% | `2f4366d` |

\* uncommitted edits at run time (pinned by the run's code hash).

## 4. Difficulty

Training splits have no BIRD difficulty labels, so they use a SQL-complexity proxy (low / medium / high).

| Set | Difficulty | Questions | Accuracy | 95% CI | Missed |
|---|---|---:|---:|---|---:|
| Cleaned dev (BIRD dev-1106) | challenging | 231 | 33.8% | 27.7–39.9 | 153.0 |
| Cleaned dev (BIRD dev-1106) | moderate | 443 | 65.0% | 60.6–69.5 | 155.0 |
| Cleaned dev (BIRD dev-1106) | simple | 860 | 76.0% | 73.2–78.9 | 206.0 |
| Mini-Dev (gate 3) | challenging | 102 | 53.6% | 44.1–63.1 | 47.3 |
| Mini-Dev (gate 3) | moderate | 250 | 61.7% | 55.9–67.6 | 95.7 |
| Mini-Dev (gate 3) | simple | 148 | 75.5% | 68.6–82.3 | 36.3 |
| Original dev, untouched rows | challenging | 43 | 65.1% | 50.7–79.5 | 15.0 |
| Original dev, untouched rows | moderate | 216 | 55.6% | 48.9–62.2 | 96.0 |
| Original dev, untouched rows | simple | 777 | 71.0% | 67.9–74.2 | 225.0 |
| train_dev (practice set) | proxy: high | 51 | 47.1% | 33.5–60.6 | 27.0 |
| train_dev (practice set) | proxy: low | 243 | 79.6% | 74.6–84.7 | 49.5 |
| train_dev (practice set) | proxy: medium | 207 | 64.7% | 58.2–71.2 | 73.0 |
| train_dev2 pilot | proxy: high | 11 | 72.7% | 45.1–100.3 | 3.0 |
| train_dev2 pilot | proxy: low | 44 | 59.1% | 44.4–73.8 | 18.0 |
| train_dev2 pilot | proxy: medium | 45 | 48.9% | 34.1–63.7 | 23.0 |
| Numbers stored as text (train_design) | proxy: high | 18 | 16.7% | -1.0–34.4 | 15.0 |
| Numbers stored as text (train_design) | proxy: low | 80 | 38.8% | 28.0–49.5 | 49.0 |
| Numbers stored as text (train_design) | proxy: medium | 96 | 26.0% | 17.2–34.9 | 71.0 |

**Published comparison:** Agentar-Scale-SQL on the BIRD **test** set: simple 86.83, moderate 78.2, challenging 71.23 ([source](https://arxiv.org/html/2509.24403)). A different set and version: use it for scale, not as a paired comparison. No other top system publishes a verifiable split.

## 5. Patterns (associations, not causes)

Each tag is computed automatically from the question, hint, answer-key SQL, database or our saved answer. **Missed** counts question-equivalents lost (a question wrong in 1 of 2 repeats counts 0.5). **Lift** is the tag's accuracy minus the set's. "Outcome" tags are review signals describing how a wrong answer differs from the key. Per-answer tags (outcome, pipeline signal) count answers. Top 20 tags by missed questions per set; the full breakdown by database and difficulty is in the interactive page.

### Cleaned dev (BIRD dev-1106): base 66.5%, 1,020/1,534 answers (1,534 questions × 1)

| Tag | Family | Questions | Accuracy | Lift | Missed |
|---|---|---:|---:|---:|---:|
| definition / synonym | evidence | 1156 | 66.3% | -0.1 | 389.0 |
| aggregate | sql | 738 | 59.5% | -7.0 | 299.0 |
| no database facts in prompt | signal (per answer) | 809 | 66.2% | -0.2 | 273.0 |
| database facts in prompt | signal (per answer) | 725 | 66.8% | +0.3 | 241.0 |
| joins 1 | sql | 848 | 72.5% | +6.0 | 233.0 |
| same shape, different values | outcome (per answer) | 231 | 0.0% | -66.5 | 231.0 |
| value mapping | evidence | 683 | 67.2% | +0.7 | 224.0 |
| large schema (>80 columns) | size | 583 | 61.8% | -4.7 | 223.0 |
| medium schema (31–80 columns) | size | 742 | 71.2% | +4.7 | 214.0 |
| single value | shape | 841 | 74.7% | +8.2 | 213.0 |
| several rows | shape | 505 | 61.6% | -4.9 | 194.0 |
| formula | evidence | 472 | 59.3% | -7.2 | 192.0 |
| subquery | sql | 233 | 31.3% | -35.2 | 160.0 |
| CASE / IIF | sql | 232 | 32.3% | -34.2 | 157.0 |
| superlative | intent | 330 | 54.2% | -12.2 | 151.0 |
| ratio / percent / average | intent | 290 | 49.0% | -17.5 | 148.0 |
| DISTINCT | sql | 342 | 58.5% | -8.0 | 142.0 |
| long (>150 chars) | evidence | 264 | 46.6% | -19.9 | 141.0 |
| temporal | intent | 369 | 62.9% | -3.6 | 137.0 |
| list / name | intent | 393 | 65.7% | -0.8 | 135.0 |

Tag combinations ≥ 3 points worse (or better) than every parent tag alone, ranked by missed questions:

| Tags together | Questions | Accuracy | Parent accuracies | Missed |
|---|---:|---:|---|---:|
| aggregate + subquery | 195 | 26.7% | 59 / 31 | 143.0 |
| definition / synonym + DISTINCT | 269 | 54.6% | 66 / 58 | 122.0 |
| long (>150 chars) + aggregate | 190 | 40.0% | 47 / 59 | 114.0 |
| large schema (>80 columns) + aggregate | 233 | 55.8% | 62 / 59 | 103.0 |
| CASE / IIF + subquery | 104 | 1.9% | 32 / 31 | 102.0 |
| DISTINCT + aggregate | 160 | 42.5% | 58 / 59 | 92.0 |
| long (>150 chars) + CASE / IIF | 128 | 28.9% | 47 / 32 | 91.0 |
| several rows + large schema (>80 columns) | 210 | 56.7% | 62 / 62 | 91.0 |
| formula + large schema (>80 columns) | 188 | 52.1% | 59 / 62 | 90.0 |
| superlative + aggregate | 173 | 48.5% | 54 / 59 | 89.0 |

### Mini-Dev (gate 3): base 64.1%, 962/1,500 answers (500 questions × 3)

| Tag | Family | Questions | Accuracy | Lift | Missed |
|---|---|---:|---:|---:|---:|
| definition / synonym | evidence | 418 | 64.3% | +0.2 | 149.0 |
| joins 1 | sql | 304 | 66.1% | +2.0 | 103.0 |
| aggregate | sql | 252 | 60.5% | -3.7 | 99.7 |
| value mapping | evidence | 292 | 66.1% | +2.0 | 99.0 |
| database facts in prompt | signal (per answer) | 269 | 64.8% | +0.7 | 94.7 |
| same shape, different values | outcome (per answer) | 104 | 0.0% | -64.1 | 92.7 |
| formula | evidence | 232 | 60.2% | -3.9 | 92.3 |
| single value | shape | 286 | 70.3% | +6.2 | 85.0 |
| no database facts in prompt | signal (per answer) | 231 | 63.4% | -0.8 | 84.7 |
| large schema (>80 columns) | size | 199 | 58.1% | -6.0 | 83.3 |
| medium schema (31–80 columns) | size | 231 | 69.5% | +5.4 | 70.3 |
| several rows | shape | 157 | 58.0% | -6.2 | 66.0 |
| ratio / percent / average | intent | 134 | 55.5% | -8.7 | 59.7 |
| long (>150 chars) | evidence | 141 | 60.3% | -3.9 | 56.0 |
| temporal | intent | 141 | 62.6% | -1.5 | 52.7 |
| superlative | intent | 107 | 56.4% | -7.7 | 46.7 |
| division | sql | 102 | 55.6% | -8.6 | 45.3 |
| joins 2 | sql | 87 | 48.3% | -15.8 | 45.0 |
| list / name | intent | 123 | 63.7% | -0.4 | 44.7 |
| ORDER BY + LIMIT | sql | 97 | 57.0% | -7.1 | 41.7 |

Tag combinations ≥ 3 points worse (or better) than every parent tag alone, ranked by missed questions:

| Tags together | Questions | Accuracy | Parent accuracies | Missed |
|---|---:|---:|---|---:|
| medium schema (31–80 columns) + joins 1 | 135 | 73.3% | 70 / 66 | 36.0 |
| several rows + large schema (>80 columns) | 67 | 48.8% | 58 / 58 | 34.3 |
| single value + medium schema (31–80 columns) | 144 | 76.4% | 70 / 70 | 34.0 |
| superlative + large schema (>80 columns) | 56 | 47.0% | 56 / 58 | 29.7 |
| value mapping + count | 76 | 61.8% | 66 / 67 | 29.0 |
| large schema (>80 columns) + ORDER BY + LIMIT | 50 | 47.3% | 58 / 57 | 26.3 |
| aggregate + subquery | 48 | 45.1% | 60 / 49 | 26.3 |
| CASE / IIF + joins 1 | 52 | 50.0% | 54 / 66 | 26.0 |
| aggregate + joins 2 | 41 | 38.2% | 60 / 48 | 25.3 |
| date function + joins 1 | 53 | 52.2% | 56 / 66 | 25.3 |

### Original dev, untouched rows: base 67.6%, 700/1,036 answers (1,036 questions × 1)

| Tag | Family | Questions | Accuracy | Lift | Missed |
|---|---|---:|---:|---:|---:|
| definition / synonym | evidence | 779 | 68.8% | +1.2 | 243.0 |
| joins 1 | sql | 595 | 67.4% | -0.2 | 194.0 |
| single value | shape | 621 | 70.5% | +3.0 | 183.0 |
| same shape, different values | outcome (per answer) | 175 | 0.0% | -67.6 | 175.0 |
| aggregate | sql | 414 | 62.6% | -5.0 | 155.0 |
| large schema (>80 columns) | size | 384 | 60.9% | -6.6 | 150.0 |
| medium schema (31–80 columns) | size | 513 | 71.5% | +4.0 | 146.0 |
| value mapping | evidence | 437 | 71.2% | +3.6 | 126.0 |
| several rows | shape | 330 | 64.5% | -3.0 | 117.0 |
| formula | evidence | 280 | 62.5% | -5.1 | 105.0 |
| count | intent | 282 | 66.7% | -0.9 | 94.0 |
| list / name | intent | 261 | 65.1% | -2.4 | 91.0 |
| joins 0 | sql | 301 | 70.8% | +3.2 | 88.0 |
| ORDER BY + LIMIT | sql | 192 | 54.7% | -12.9 | 87.0 |
| superlative | intent | 202 | 58.9% | -8.7 | 83.0 |
| temporal | intent | 224 | 65.2% | -2.4 | 78.0 |
| different row count | outcome (per answer) | 74 | 0.0% | -67.6 | 74.0 |
| DISTINCT | sql | 162 | 61.1% | -6.5 | 63.0 |
| none | evidence | 146 | 59.6% | -8.0 | 59.0 |
| ratio / percent / average | intent | 121 | 62.8% | -4.8 | 45.0 |

Tag combinations ≥ 3 points worse (or better) than every parent tag alone, ranked by missed questions:

| Tags together | Questions | Accuracy | Parent accuracies | Missed |
|---|---:|---:|---|---:|
| formula + joins 1 | 158 | 59.5% | 62 / 67 | 64.0 |
| ORDER BY + LIMIT + joins 1 | 118 | 51.7% | 55 / 67 | 57.0 |
| several rows + large schema (>80 columns) | 133 | 57.9% | 65 / 61 | 56.0 |
| large schema (>80 columns) + aggregate | 118 | 54.2% | 61 / 63 | 54.0 |
| single value + joins 0 | 197 | 75.6% | 71 / 71 | 48.0 |
| large schema (>80 columns) + ORDER BY + LIMIT | 97 | 50.5% | 61 / 55 | 48.0 |
| value mapping + aggregate + joins 1 | 109 | 56.9% | 63 / 70 / 60 | 47.0 |
| formula + large schema (>80 columns) | 102 | 56.9% | 62 / 61 | 44.0 |
| list / name + large schema (>80 columns) | 95 | 57.9% | 65 / 61 | 40.0 |
| none + large schema (>80 columns) | 76 | 51.3% | 60 / 61 | 37.0 |

### train_dev (practice set): base 70.2%, 703/1,002 answers (501 questions × 2)

| Tag | Family | Questions | Accuracy | Lift | Missed |
|---|---|---:|---:|---:|---:|
| definition / synonym | evidence | 478 | 70.4% | +0.2 | 141.5 |
| value mapping | evidence | 384 | 71.2% | +1.1 | 110.5 |
| single value | shape | 338 | 72.2% | +2.0 | 94.0 |
| aggregate | sql | 233 | 62.7% | -7.5 | 87.0 |
| same shape, different values | outcome (per answer) | 85 | 0.0% | -70.2 | 82.5 |
| formula | evidence | 198 | 59.3% | -10.8 | 80.5 |
| no database facts in prompt | signal (per answer) | 217 | 63.6% | -6.6 | 79.0 |
| large schema (>80 columns) | size | 258 | 69.6% | -0.6 | 78.5 |
| small schema (≤30 columns) | size | 243 | 70.8% | +0.6 | 71.0 |
| database facts in prompt | signal (per answer) | 284 | 75.2% | +5.0 | 70.5 |
| joins 1 | sql | 245 | 71.4% | +1.3 | 70.0 |
| temporal | intent | 140 | 63.2% | -7.0 | 51.5 |
| count | intent | 162 | 68.8% | -1.3 | 50.5 |
| long (>150 chars) | evidence | 97 | 51.5% | -18.6 | 47.0 |
| different row count | outcome (per answer) | 47 | 0.0% | -70.2 | 44.5 |
| superlative | intent | 105 | 58.6% | -11.6 | 43.5 |
| list / name | intent | 141 | 72.3% | +2.2 | 39.0 |
| several rows | shape | 118 | 67.4% | -2.8 | 38.5 |
| joins 2 | sql | 98 | 61.7% | -8.4 | 37.5 |
| ORDER BY + LIMIT | sql | 93 | 61.8% | -8.3 | 35.5 |

Tag combinations ≥ 3 points worse (or better) than every parent tag alone, ranked by missed questions:

| Tags together | Questions | Accuracy | Parent accuracies | Missed |
|---|---:|---:|---|---:|
| formula + aggregate | 123 | 52.9% | 59 / 63 | 58.0 |
| long (>150 chars) + aggregate | 75 | 43.3% | 52 / 63 | 42.5 |
| small schema (≤30 columns) + aggregate | 104 | 59.6% | 71 / 63 | 42.0 |
| formula + long (>150 chars) | 78 | 46.8% | 59 / 52 | 41.5 |
| formula + large schema (>80 columns) | 92 | 55.4% | 59 / 70 | 41.0 |
| value mapping + small schema (≤30 columns) + aggregate | 85 | 56.5% | 72 / 62 / 60 | 37.0 |
| temporal + aggregate | 69 | 55.1% | 63 / 63 | 31.0 |
| value mapping + superlative | 63 | 53.2% | 71 / 59 | 29.5 |
| formula + value mapping + large schema (>80 columns) | 58 | 51.7% | 58 / 55 / 70 | 28.0 |
| superlative + aggregate | 59 | 53.4% | 59 / 63 | 27.5 |

### train_dev2 pilot: base 56.0%, 56/100 answers (100 questions × 1) (sample: 100 of 503 questions (25 per database), Jev-pilot control arm)

| Tag | Family | Questions | Accuracy | Lift | Missed |
|---|---|---:|---:|---:|---:|
| definition / synonym | evidence | 76 | 57.9% | +1.9 | 32.0 |
| joins 1 | sql | 69 | 55.1% | -0.9 | 31.0 |
| formula | evidence | 51 | 51.0% | -5.0 | 25.0 |
| aggregate | sql | 47 | 48.9% | -7.1 | 24.0 |
| database facts in prompt | signal (per answer) | 43 | 44.2% | -11.8 | 24.0 |
| single value | shape | 60 | 61.7% | +5.7 | 23.0 |
| same shape, different values | outcome (per answer) | 21 | 0.0% | -56.0 | 21.0 |
| superlative | intent | 42 | 52.4% | -3.6 | 20.0 |
| no database facts in prompt | signal (per answer) | 57 | 64.9% | +8.9 | 20.0 |
| large schema (>80 columns) | size | 25 | 32.0% | -24.0 | 17.0 |
| several rows | shape | 32 | 50.0% | -6.0 | 16.0 |
| value mapping | evidence | 38 | 60.5% | +4.5 | 15.0 |
| temporal | intent | 26 | 42.3% | -13.7 | 15.0 |
| list / name | intent | 27 | 44.4% | -11.6 | 15.0 |
| medium schema (31–80 columns) | size | 50 | 72.0% | +16.0 | 14.0 |
| ratio / percent / average | intent | 19 | 26.3% | -29.7 | 14.0 |
| small schema (≤30 columns) | size | 25 | 48.0% | -8.0 | 13.0 |
| different row count | outcome (per answer) | 13 | 0.0% | -56.0 | 13.0 |
| ORDER BY + LIMIT | sql | 28 | 57.1% | +1.1 | 12.0 |
| CAST | sql | 17 | 29.4% | -26.6 | 12.0 |

Tag combinations ≥ 3 points worse (or better) than every parent tag alone, ranked by missed questions:

| Tags together | Questions | Accuracy | Parent accuracies | Missed |
|---|---:|---:|---|---:|
| superlative + joins 1 | 27 | 44.4% | 52 / 55 | 15.0 |
| formula + temporal | 21 | 38.1% | 51 / 42 | 13.0 |
| formula + superlative | 28 | 57.1% | 51 / 52 | 12.0 |
| formula + single value | 34 | 64.7% | 51 / 62 | 12.0 |
| small schema (≤30 columns) + aggregate | 18 | 33.3% | 48 / 49 | 12.0 |
| single value + small schema (≤30 columns) | 17 | 35.3% | 62 / 48 | 11.0 |
| small schema (≤30 columns) + joins 1 | 18 | 38.9% | 48 / 55 | 11.0 |
| formula + list / name | 16 | 37.5% | 51 / 44 | 10.0 |
| ORDER BY + LIMIT + joins 1 | 18 | 44.4% | 57 / 55 | 10.0 |
| superlative + ORDER BY + LIMIT + joins 1 | 16 | 37.5% | 54 / 44 / 44 | 10.0 |

### Numbers stored as text (train_design): base 30.4%, 59/194 answers (194 questions × 1) (sample: 194 targeted questions whose gold uses text-stored numbers numerically; scored before database facts)

| Tag | Family | Questions | Accuracy | Lift | Missed |
|---|---|---:|---:|---:|---:|
| definition / synonym | evidence | 173 | 32.4% | +2.0 | 117.0 |
| formula | evidence | 152 | 32.2% | +1.8 | 103.0 |
| large schema (>80 columns) | size | 124 | 26.6% | -3.8 | 91.0 |
| joins 1 | sql | 123 | 30.1% | -0.3 | 86.0 |
| aggregate | sql | 114 | 25.4% | -5.0 | 85.0 |
| single value | shape | 116 | 28.4% | -2.0 | 83.0 |
| same shape, different values | outcome (per answer) | 78 | 0.0% | -30.4 | 78.0 |
| superlative | intent | 99 | 27.3% | -3.1 | 72.0 |
| temporal | intent | 90 | 24.4% | -6.0 | 68.0 |
| ORDER BY + LIMIT | sql | 97 | 30.9% | +0.5 | 67.0 |
| value mapping | evidence | 86 | 26.7% | -3.7 | 63.0 |
| long (>150 chars) | evidence | 74 | 33.8% | +3.4 | 49.0 |
| count | intent | 55 | 16.4% | -14.1 | 46.0 |
| ratio / percent / average | intent | 60 | 25.0% | -5.4 | 45.0 |
| CAST | sql | 57 | 31.6% | +1.2 | 39.0 |
| list / name | intent | 52 | 28.9% | -1.6 | 37.0 |
| GROUP BY | sql | 52 | 28.9% | -1.6 | 37.0 |
| division | sql | 46 | 23.9% | -6.5 | 35.0 |
| one row, several columns | shape | 38 | 26.3% | -4.1 | 28.0 |
| joins 0 | sql | 45 | 37.8% | +7.4 | 28.0 |

Tag combinations ≥ 3 points worse (or better) than every parent tag alone, ranked by missed questions:

| Tags together | Questions | Accuracy | Parent accuracies | Missed |
|---|---:|---:|---|---:|
| superlative + large schema (>80 columns) | 59 | 18.6% | 27 / 27 | 48.0 |
| value mapping + aggregate | 59 | 22.0% | 27 / 25 | 46.0 |
| formula + long (>150 chars) | 63 | 38.1% | 32 / 34 | 39.0 |
| superlative + temporal | 49 | 20.4% | 27 / 24 | 39.0 |
| superlative + single value | 58 | 32.8% | 27 / 28 | 39.0 |
| ratio / percent / average + single value | 44 | 18.2% | 25 / 28 | 36.0 |
| formula + superlative + single value | 53 | 35.9% | 29 / 30 / 33 | 34.0 |
| temporal + large schema (>80 columns) + ORDER BY + LIMIT | 42 | 19.1% | 22 / 22 / 24 | 34.0 |
| superlative + GROUP BY | 38 | 23.7% | 27 / 29 | 29.0 |
| GROUP BY + ORDER BY + LIMIT | 39 | 25.6% | 29 / 31 | 29.0 |

## 6. Why wrong / why right

**Scope:** every wrong answer on the training splits without an owner verdict: 190 cases, including re-checks of the 86 earlier Sonnet 5 verdicts. The owner's own 166 verdicts stand as they are.

**Method:** each case was read twice, independently, by Sonnet 5.5 (`claude-sonnet-5-5`, confirmed on every run). Stage 1 asks whether the answer key is valid; Stage 2 names the mechanism when our answer is wrong. Reviewers ran bounded, read-only probes of the training databases. A case is settled when both passes agree and neither is low confidence; otherwise a third, adjudicating pass re-verified the data. Low-confidence adjudications stay disputed for the owner.

**Result:** 167 settled (139 by two agreeing passes, 28 by adjudication); 23 still disputed.

### Who is right? (settled cases)

| Verdict | Cases | Share |
|---|---:|---:|
| Answer key wrong | 73 | 44% |
| Our answer wrong, key right | 33 | 20% |
| Both wrong | 42 | 25% |
| Both acceptable | 12 | 7% |
| Question ambiguous | 7 | 4% |

### By set

| Set | gold wrong | model wrong | both wrong | both acceptable | uncertain | disputed |
|---|---|---|---|---|---|---|
| train_dev2 pilot | 15 | 10 | 6 | 3 | 4 | 6 |
| Numbers as text (train_design) | 28 | 18 | 24 | 6 | 1 | 5 |
| train_dev | 30 | 5 | 12 | 3 | 2 | 12 |

### Mechanisms behind our wrong answers (75 settled model-side cases)

A case can have several mechanisms.

| Mechanism | Count | Share of model-side cases |
|---|---:|---:|
| Computation (CAST, integer division, rounding, arithmetic) | 24 | 32% |
| Grouping / aggregation (GROUP BY, denominator, DISTINCT, nesting) | 20 | 27% |
| Output shape (extra, missing or unrequested columns or rows) | 16 | 21% |
| Value matching (literal, format, case, mapping) | 14 | 19% |
| Join (path, key, fan-out) | 8 | 11% |
| Hint misread | 7 | 9% |
| Wrong or missing table/column | 5 | 7% |
| Filter logic (missing filter, AND/OR, NULL) | 4 | 5% |
| Dates and time | 2 | 3% |
| Other | 1 | 1% |
| Advanced SQL | 1 | 1% |

**Reading:** the top three mechanisms (computation, grouping/aggregation and output shape) are about computing and presenting the answer, not about finding tables or values. That is consistent with the measured ≈ 0 effect of the retrieval-style levers (database facts, column notes, dictionary).

### Why right

Only paired lever evidence establishes causes of gains (section 3): the benchmark prompt profile (+7.0 on train_dev), the v4p1 model (+5.9 on Mini-Dev, +4.0 on original dev) and identifier quoting with repairs (+1.6). Tag associations (section 5) do not establish causes.

### How far to trust the reviewer

**Blind calibration:** 60 cases the owner had already judged, with the owner's verdicts and notes hidden. Agreement **42/60** (70%).

| Owner's verdict | Cases | Agreed | Agreement |
|---|---:|---:|---:|
| key_wrong | 23 | 16 | 70% |
| ours_wrong | 24 | 19 | 79% |
| both_ok | 10 | 7 | 70% |
| ambiguous | 3 | 0 | 0% |

| Reviewer confidence | Cases | Agreed | Agreement |
|---|---:|---:|---:|
| high | 26 | 23 | 88% |
| medium | 22 | 17 | 77% |
| low | 12 | 2 | 17% |

Blind: the owner's verdicts and notes were hidden. Mapping: gold_wrong→key_wrong, model_wrong/both_wrong→ours_wrong, both_acceptable→both_ok, uncertain→ambiguous. Three high-confidence disagreements were re-checked against the databases; the agent was right in all three (train_dev:488, train_dev:94, train_design:5265). Owner verdicts on cases with several of our answers may refer to a different answer, so agreement is a lower bound. An earlier 20-case trial with a less specific rubric agreed 12/20.

**Spot-check:** Independent database check of 8 settled 'key wrong' calls (sampled across the three sets): 7 confirmed by our own probes or by the key's SQL alone; 1 (train_dev:82) is a convention mismatch: the key follows the hint's capitalised 'San Francisco' while the data is lowercase, which the owner has treated as ambiguous.

Calibration disagreements (owner vs agent):

| Case | Owner | Agent | Confidence | Agent's reason |
|---|---|---|---|---|
| `train_dev:241` | key_wrong | uncertain | low | Question asks Man of the Series (one player per season, which is what ours returns) but the hint maps it to Man_of_the_Match, which the key follows; hint contradicts question. |
| `train_design:1464` | ambiguous | both_acceptable | medium | Same comparison and same winner; ours answers 'female' where the key returns the label 'female White students'. |
| `train_dev:293` | ambiguous | gold_wrong | low | SP Narine never won the Orange Cap (no Season row), so empty is correct; the key lists seasons he played and unrelated player ids. |
| `train_design:5265` | key_wrong | both_wrong | high | side values carry trailing spaces ('South ') and population is text with commas; key uses 300000 and 'South ' vs 'North', ours casts '31,867' to 31 and 'South' matches nothing; correct is about 8-3=5. |
| `train_design:1508` | ours_wrong | gold_wrong | medium | Hint says MAX(grad_cohort); key sums overlapping breakdown rows per year (2005) but the total row peaks in 2012 (1679 vs 1647), which ours returns. |
| `train_design:1669` | both_ok | uncertain | low | No 2013 elite user has an average of exactly 1 or 5 (values are 2.5 to 4.5), so the ratio is 0/0; ours gives NULL and the key gives two zeros that are not a ratio. |
| `train_dev:271` | ours_wrong | uncertain | medium | Hint's Fielders = '' matches nothing because no-fielder rows are NULL (88 of 296); the key returns 0 and ours handling NULL gives 88, so the hint literal decides the result. |
| `train_dev:94` | ours_wrong | gold_wrong | high | Stored food_type is 'indian', so the key's 'Indian restaurant' filter matches nothing (and it selects id_restaurant, not the label the hint names); taj express is the answer, which answer 1 misses by returning nothing. |
| `train_design:4617` | key_wrong | both_wrong | medium | Key does integer W/G and returns 0; ours uses SeriesPost with round 'SC' (real value is 'SCF') so it returns NULL, and TeamsSC has integer W and G for MTL to average instead. |
| `train_dev:454` | key_wrong | both_acceptable | low | Snowfall max is at station 15 with one store: ours counts stores (1) per the question, key returns the store number (19) per the hint mapping to store_nbr. |
| `train_design:4580` | both_ok | gold_wrong | low | GWG is text so the key's sort is wrong (true max is 16, Esposito or Goulet); ours casts and returns Esposito, though as a player id and one of tied leaders. |
| `train_dev:47` | ours_wrong | uncertain | low | Many restaurants tie at the top review (25 at 4), so the top 4 are arbitrary; hint's review = 4 also supports a different reading, and only answers 3 and 4 reproduce the key's pick. |
| `train_design:4592` | both_ok | model_wrong | low | Edmonton has the highest PKC (417) in both, but ours returns the code 'EDM' where the question names teams and the key returns 'Edmonton Oilers'. |
| `train_dev:427` | key_wrong | both_acceptable | medium | depart is NULL for every row of store 3's station, so no day qualifies; key's CASE gives 0 and ours' SUM over no rows gives NULL. |
| `train_design:4645` | key_wrong | model_wrong | low | One left-wing row with weight 220 has NULL playerID; ours returns it as an extra NULL row (340 vs 339 ids) where the key excludes it. |
| `train_design:1472` | ambiguous | both_acceptable | low | Ours follows the hint's literal sum of all grad_cohort rows per year (2167) while the key averages only the total rows (gender B, race X: 544.67); both readings are plausible. |
| `train_dev:64` | key_wrong | both_acceptable | low | Key takes the city from location (225 rows have NULL city there) and ours from generalinfo (never NULL), giving 1094 vs 1103 ids; the question does not say which. |
| `train_dev:488` | ours_wrong | gold_wrong | high | Key joins sales to weather without matching dates, inflating the sum to 739746; answer 0 matches on date (714) and answer 1 repeats the key's bug. |

### Still disputed (23): for owner review

| Case | Pass A | Pass B | Adjudicator (low confidence) | Pass A reason |
|---|---|---|---|---|
| `jev_live_pilot_questions:41` | uncertain (low) | uncertain | uncertain | 'both US or UK' is ambiguous (intersection 2812 vs union 68440 actors) and the key counts actor-movie rows (114976) without DISTINCT. |
| `jev_live_pilot_questions:49` | gold_wrong (low) | gold_wrong | gold_wrong | Key takes one arbitrary row among 9 movies tied at the minimum single rating (1754754 averages 3.9); ours picks the lowest-rated movie by average, a reasonable reading. |
| `jev_live_pilot_questions:50` | both_acceptable (low) | both_acceptable | both_acceptable | Key gives an unlabelled per-team-season ratio (1536 rows) while ours gives one overall home-win percentage; question wording and hint formula support either. |
| `jev_live_pilot_questions:69` | both_acceptable (low) | both_acceptable | both_acceptable | Key counts any coach who coached STL and ever won an award; ours requires the award year to match the STL season; 'from STL team' allows either. |
| `jev_live_pilot_questions:77` | model_wrong (low) | model_wrong | both_acceptable | Hint says cities means City Name; ours adds an unrequested Region column (key returns only distinct city names). |
| `jev_live_pilot_questions:99` | both_acceptable (low) | both_acceptable | both_acceptable | Same team (Todd Roberts); key counts orders both placed and shipped in 2019 (128), ours counts orders shipped in 2019 (134); the hint's separate definitions support either. |
| `train_design:1456` | model_wrong (low) | model_wrong | model_wrong | Ours sums grad_100 for Asian rows over every race and gender row (overlapping totals) instead of the hint's SUM(race='A')/SUM(grad_cohort) percentage. |
| `train_design:4478` | gold_wrong (low) | both_wrong | gold_wrong | Hint says percentage = W/GP*100 but the key returns the bare fraction; ours applies *100 and returns the same six goalie-seasons keyed by playerID. |
| `train_design:4534` | model_wrong (low) | both_acceptable | model_wrong | Both find Boudreau ('Gabby'), but the question asks which coach and the nickname; ours returns only the nickname and omits the coach identity. |
| `train_design:4535` | gold_wrong (medium) | both_acceptable | gold_wrong | NAS has the top PP% and Trotz is its sole 2011 coach; ours returns his full name, while the key returns only coachID and its Coaches join is not restricted to 2011. |
| `train_design:5210` | uncertain (low) | both_acceptable | both_wrong | Question says average beat of all crimes (ours: 12743 cases) but hint restricts the average to population<52000 (25265 cases); the key also returns a count rather than the requested case numbers. |
| `train_dev:177` | model_wrong (low) | both_acceptable | model_wrong | Hint defines role as Role_Id (key returns 1); ours returns Role_Desc 'Captain' instead. |
| `train_dev:267` | gold_wrong (low) | uncertain | uncertain | Key returns a percentage of ball count over all innings-1 runs, not an average; average runs per ball in overs 2-24 of innings 1 is 1.2806 (ours[1]); ours[0] divides by sum of over ids. |
| `train_dev:301` | uncertain (low) | gold_wrong | uncertain | Question is unanswerable as worded (no game has zero runs); key is broken (3.7M rows), ours counts games with any dot ball, which equals all 133 Delhi matches. |
| `train_dev:304` | uncertain (low) | both_acceptable | uncertain | Ranking by bowling skill is not well defined; key orders by the numeric skill id, ours[1] matches that (with ties at ids 14/13) and ours[0] orders alphabetically by skill name. |
| `train_dev:322` | uncertain (low) | uncertain | uncertain | Key is empty (broken); question does not say which innings or whether extras count; ours[0] adds both innings' runs over 17 overs, ours[1] picks innings 1 with extras (172/17=10.1). |
| `train_dev:323` | uncertain (low) | uncertain | uncertain | Key is empty (uses wrong match id); innings and extras are unspecified, ours[0] combines both innings, ours[1] uses innings 1 only. |
| `train_dev:351` | both_acceptable (low) | uncertain | both_acceptable | Question order suggests left/right (key) but the garbled hint puts right-hand bat in the numerator (ours); the hint does not settle the direction. |
| `train_dev:363` | uncertain (medium) | uncertain | both_acceptable | Hint defines Superover as win_type='wickets' (307 matches) which contradicts the question and the Outcome table's real 'Superover' value (6 matches). |
| `train_dev:420` | both_wrong (medium) | gold_wrong | gold_wrong | Key drops the 2009 filter (56 matches all years); ours counts wickets-wins by either team among DD's 15 matches (11/15) instead of DD's own wins by wickets (7 of 15). |
| `train_dev:440` | uncertain (low) | both_wrong | uncertain | Key has no date join (yearly ratio) and answer 0 lacks the sales-date filter; the hottest day is tied (08-01 gives 61.45%, 08-03 gives 29.79%, combined 50.7%) so answer 1's single-day pick cannot be confirmed. |
| `train_dev:475` | both_acceptable (low) | both_acceptable | both_acceptable | Key and answer 0 rank individual store-day-item records (station 13 twice), a plausible reading; answer 1 uses distinct stations (13, 2, 20) but adds an unrequested max_units column. |
| `train_dev:489` | both_acceptable (low) | both_acceptable | both_acceptable | Hint's item_nbr suggests counting items (key: 111, though only 3 items had units>0) while 'how many items sold' also reads as total units (answer 1: 122 date-matched); answer 0 lacks the date join. |

### Earlier answer-key review (252 selected disputes)

| Verdict | Cases |
|---|---:|
| ours_wrong | 74 |
| key_wrong | 153 |
| both_ok | 20 |
| ambiguous | 5 |

Owner 166, Sonnet 5 agents 86 (those 86 were re-checked in this audit). Selected disputes, not a rate for any whole set.

## 7. Data quality and audits

**No set we hold has a complete, independent semantic audit.** Every audit below covers a sample or a selection; read its denominator and selection method before using its numbers. Label defects found in selected disputes do **not** give a set-wide ceiling.

### Audits we ran

| Audit | Denominator | Selection | Reviewed by | Checked by | Result |
|---|---|---|---|---|---|
| Answer-key review (packet) | 252 cases | Selected disputes: flipped rows of 5 rejected experiments, 93 unanimous-wrong bank questions, 194 numbers-as-text questions | Owner 166; Sonnet 5 agents 86 | 3 database spot-checks | Key wrong 153, ours wrong 74, both OK 20, ambiguous 5 |
| Stable-failure audit (postmortem v2) | 46 of 153 stable-wrong train_dev rows | Random within database | One reviewer | Read-only queries | 26 label defect, 8 convention, 3 ambiguity, 8 genuine, 1 pathology |
| Model-error triage | 24 stable-wrong train_dev rows | Hash-selected, ≤ 6 per database | One reviewer | Database results | 18 gold defects, 1 genuine model error, 3 both suspect, 2 uncertain |
| Training-pool screen | 100 of 5,115 candidate SFT rows | Stratified across 43 databases | One reviewer | Read and query | 18 clear defects (17.5% weighted); 82 unresolved |
| Gold-idiom scan | All rows of each set | Mechanical pattern scan | Script | n/a | train_dev 10/501 (2.0%); Mini-Dev 1/500; dev_untouched 1/1,036 |
| Corrected-label comparisons | Mini-Dev 500; train_dev 72; dev 779 | Public corrections (Arcwise, Verified, dev-1106) | Third parties | Re-scoring | Result sets change 22.6% / 25% / 6.9%; our accuracy +1.4 / +4.2 / +4.1 pts |
| Sonnet 5.5 two-stage audit (this review) | 190 wrong training answers + 60 calibration cases | All wrong answers on training splits without an owner verdict (includes re-checks of the 86 earlier agent verdicts) | Sonnet 5.5, two independent passes + adjudication | Two independent Sonnet 5.5 passes with bounded read-only probes; settled if both agree and neither is low confidence; otherwise a third adjudicating pass re-verifies the data; low-confidence adjudications stay disputed | 167 settled, 23 disputed; blind agreement with owner 42/60 |

### Public BIRD data with any audit

| Dataset | What | Coverage | Fully audited? | Licence | Accessed |
|---|---|---|---|---|---|
| [BIRD dev Nov 2025 (bird-sql-dev-1106 / birdsql/bird_sql_dev_20251106)](https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106) | Re-worded questions, corrected evidence and SQL in the BIRD dev split. | 1,534 rows; card says all instances were reviewed by a BIRD-team panel; counts of changed rows and error rates are not published. | partial | CC-BY-SA-4.0 | 2026-09-28 |
| [BIRD-Verified (ReViSQL)](https://arxiv.org/html/2603.20004v2) | Expert-corrected BIRD Train instances (questions, evidence, gold SQL) used to train ReViSQL. | 2,462 rows: 2,500 sampled from BIRD Train, 38 dropped as unanswerable; whole train set not audited; 61.1% of sampled rows had at least one error. | no | not confirmed (code and data via the paper's GitHub link) | 2026-09-28 |
| [BIRD-Platinum (Bridgewater AIA Labs write-up)](https://www.bridgewater.com/aia-labs/putting-task-expertise-into-rl-to-achieves-state-of-the-art-on-text-to-sql) | Cleaned BIRD Train subset released after LLM plus human-expert audit with second-expert verification. | Write-up says 2.5k instances sampled from BIRD Train; released row count not stated, and I could not confirm it is the same release as BIRD-Verified. | no | not stated on the page I read | 2026-09-28 |
| [Arcwise-Plat-SQL / Arcwise-Plat (corrected BIRD Mini-Dev, Jin et al.)](https://arxiv.org/html/2601.08778v3) | Mini-Dev with gold SQL corrected (Plat-SQL) or SQL plus ambiguous questions/evidence resolved (Plat). | All 498 unique Mini-Dev examples audited (263 = 52.8% had errors) via automated detection then manual checks; Mini-Dev is only a 500-row subset of dev and residual errors are not ruled out. | partial | paper says CC BY 4.0; repo badge says CC-BY-SA 4.0 | 2026-09-28 |
| [Corrected BIRD Dev random subset (Jin et al.)](https://github.com/uiuc-kang-lab/text_to_sql_benchmarks) | Manual correction of a random sample of the original BIRD Dev split. | 100 randomly sampled examples out of 1,534; authors did not correct the full dev set. | no | CC-BY-SA 4.0 per repo badge | 2026-09-28 |
| [birdsql/bird23-train-filtered](https://huggingface.co/datasets/birdsql/bird23-train-filtered) | Filtered BIRD Train kept for schema consistency and faithful answers. | 6,601 of 9,428 rows kept (about 30% removed); card says quality-checked but exact procedure and error rates are not published; validated only by SFT parity on Qwen2.5-3B. | partial | CC-BY-SA-4.0 | 2026-09-28 |
| [BIRD Mini-Dev](https://huggingface.co/datasets/birdsql/bird_mini_dev) | 500 question-SQL pairs from the 11 dev databases with MySQL and PostgreSQL variants. | 500 rows compiled from community feedback; card claims no independent audit; Jin et al. later found errors in 52.8% of its 498 unique rows. | no | CC-BY-SA-4.0 | 2026-09-28 |
| [Wretblad et al. 2024 noise study of BIRD dev](https://arxiv.org/abs/2402.12243) | Two annotators labelled noisy questions and erroneous gold SQL in selected BIRD dev domains. | Financial 106 examples (49% noisy) plus 20 each from four other domains (Table 1, five domains); how the 20-row samples were chosen was not checked by me. | no | not stated in paper (annotations published on GitHub) | 2026-09-28 |

BIRD-Verified has no clear licence: private evaluation only, never training data (project rule).

## 8. Cost, stability and next steps

### Cost and latency per answer (submission ceilings: $0.01 uncached, $0.05 max, P90 ≤ 30s)

| Set | Measured $ | Uncached $ | Max answer $ | P50 | P90 | Within ceilings |
|---|---:|---:|---:|---:|---:|---|
| Cleaned dev (BIRD dev-1106) | 0.00023 | 0.00067 | 0.0028 | 1.78s | 3.62s | yes |
| Mini-Dev (gate 3) | 0.00017 | 0.00067 | 0.0029 | 1.58s | 2.96s | yes |
| Original dev, untouched rows | 0.00017 | 0.00064 | 0.0031 | 1.37s | 3.03s | yes |
| train_dev (practice set) | 0.00015 | 0.00070 | 0.0027 | 1.71s | 3.17s | yes |
| train_dev2 pilot | 0.00035 | 0.00062 | 0.0013 | 1.66s | 2.98s | yes |
| Numbers stored as text (train_design) | 0.00049 | 0.00126 | 0.0081 | 2.15s | 3.83s | yes |

### Repeat stability (T = 0)

| Set | Questions | Right/wrong flips | Result differs |
|---|---:|---|---|
| Mini-Dev (gate 3) | 500 | 26 (5.2%) | 52 (10.4%) |
| train_dev (practice set) | 501 | 7 (1.4%) | 24 (4.8%) |

Differences under about 1.5 points need paired evidence.

### Headroom, with its limits

The old 4-candidate bank's oracle was 73.5% vs 69.5% for the direct answer on train_dev. That is an oracle **for that bank and its noisy answer keys**, not for the current configuration. In the reviewed disputes, 82 of the bank's 93 "unanimous but wrong" answers were judged correct: a sign of training-set label noise, not a set-wide ceiling.

### Next steps, ranked by evidence

| Step | Cost | Why |
|---|---|---|
| Submit the current system to the BIRD hidden test | ≈ $1 | Only way to learn the real standing and the dev→test gap; test is graded with several answer keys and human review. |
| Fresh candidate bank on unused train_dev2 rows with other model families | a few $ | Decides whether generation or selection is the bottleneck (pass@K vs selected). |
| Invest in selection only if pass@K rises substantially | — | Zero-shot LLM selection already lost to majority; a trained selector needs a richer bank. |
| Clean training labels before any fine-tuning | free–$ | 17.5% clear defects in the screened sample exceeds the 15% gate. |
| Targeted fixes for confirmed genuine errors | free | The audit's top model-side mechanisms are computation (casts, integer division, rounding), grouping/aggregation and output shape; fix them on training sets only, never from dev. |

## 9. Method and reproducibility

- Aggregates come from each run's raw records and metadata sidecars in `benchmark/results/` (recorded official EX, config and dataset hashes, commit). Totals were asserted against the recorded headlines: 1,020/1,534 (cleaned dev), 962/1,500 (Mini-Dev gate 3), 700/1,036 (dev_untouched), 703/1,002 (train_dev).
- Pattern tags follow the v2 postmortem tagger (`docs/postmortem_v2/analysis/pm3_features.py`), extended with question intent, evidence type, answer-key result shape, outcome and pipeline signals. Gold SQL was executed locally only to tag result shapes.
- Leaderboard research: a Sonnet 5.5 research pass with a source URL per claim; the operator then checked every overall and single-model score against the live leaderboard (23/23 matched).
- Audit reviewers used the owner's judging principles (question first; hint formulas followed; unrequested columns or rows count against us; text-sorted numbers are wrong; hint literals that don't match stored values → ambiguous; the key is overruled only when clearly broken).
- Evaluation sets were never read question by question. The lockbox was not opened.

## Appendix: audit labels for training-set cases

Status: settled (two agreeing passes), adjudicated (third pass), disputed (for owner review). Case ids are `<question file>:<row>`.

| Case | Database | Status | Verdict | Mechanisms | Confidence | Cause |
|---|---|---|---|---|---|---|
| `train_design:1003` | app_store | adjudicated | both_wrong | join | medium | Key multiplies text '$' prices (evaluates to 0) so its pick is arbitrary; ours takes the global max (Minecraft, no reviews) so the inner join returns nothing; B right. |
| `train_design:1026` | app_store | settled | gold_wrong | — | high | Price is text like '$1.49'; key's AVG(Price) treats it as 0 (0.0); ours strips '$' and casts (0.134). |
| `train_design:1036` | app_store | settled | gold_wrong | — | high | Key compares the string literal 'Content Rating' to 'Everyone 10+' so it matches nothing (NULL), and Price is text; ours gives 0.617 over 34 apps. |
| `train_design:1448` | college_completion | adjudicated | both_wrong | value_grounding, computation | high | California is the right state (3120 male 2013 cohort rows) but 268 of 350 med_sat_value entries are the text 'NULL' and cast to 0, so ours gives 255.7 vs true 1091.4; key is broken; A right. |
| `train_design:1449` | college_completion | settled | both_wrong | projection | medium | Question asks to name the state and list its institutes; ours lists institutes (California is right) but omits the state; the key's Alabama row comes from a broken GROUP BY. |
| `train_design:1450` | college_completion | adjudicated | both_wrong | grain_aggregation | medium | MIN(grad_cohort) ties at 0 in most states so ours' Alabama is arbitrary (least total is Alaska, 12162) and the key returns one institute instead of a list; B right. |
| `train_design:1451` | college_completion | settled | gold_wrong | — | high | Key compares grad_cohort as text (so '1043' < '200') and returns grad_cohort instead of the requested fte_value; ours casts correctly and returns chronname and fte_value. |
| `train_design:1455` | college_completion | adjudicated | both_wrong | hint_misread, grain_aggregation | medium | Ours sums cohorts over overlapping gender B/F/M rows and race X totals (10.56) whereas B share of the X total is 19.4%; key's 4.7 is neither the hint's ratio nor a real share; B right. |
| `train_design:1456` | college_completion | disputed | model_wrong | hint_misread, grain_aggregation | low | Ours sums grad_100 for Asian rows over every race and gender row (overlapping totals) instead of the hint's SUM(race='A')/SUM(grad_cohort) percentage. |
| `train_design:1471` | college_completion | settled | gold_wrong | — | high | Key compares grad_cohort > 500 as text, which wrongly admits values like '99' and drops 4-digit ones; ours casts to integer. |
| `train_design:1507` | college_completion | settled | gold_wrong | — | high | Key orders grad_cohort as text and returns carrington.edu; the numeric maximum (3349) is www.uwc.edu, as ours returns. |
| `train_design:1509` | college_completion | settled | both_wrong | value_grounding | medium | state_appr_value is text with 'NULL' strings, so ours' MAX() picks 'NULL' (DC) instead of Wyoming (659.39); the key's nested query ignores the top-appropriation state and uses a global minimum. |
| `train_design:1510` | college_completion | settled | both_wrong | grain_aggregation, hint_misread | medium | Ours returns a count of rows per year (3.0), not a student count; the key averages grad_cohort across overlapping B/M/F rows (64.33) while gender='B' rows alone average 96.5. |
| `train_design:1515` | college_completion | settled | both_wrong | predicate, value_grounding | medium | Ours picks the 'United States' pseudo-state whose appropriation is the text 'NULL', so it returns NULL; the key has no state filter and averages every institution. |
| `train_design:1914` | citeseer | settled | model_wrong | hint_misread | medium | The hint defines average as count(ML papers)/count(all papers); ours returns the raw ML count (590) instead of the ratio. |
| `train_design:2393` | disney | settled | gold_wrong | — | medium | Key orders total_gross as text ('$5...' > '$3...') and returns The Aristocats; numerically the top is The Jungle Book ($364M), as ours returns. |
| `train_design:2420` | disney | settled | model_wrong | computation, value_grounding | high | Ours casts total_gross like '$246,082,029' to REAL without stripping '$' and commas (all become 0), so the ordering is arbitrary; the real maximum is Moana. |
| `train_design:2445` | disney | settled | model_wrong | computation, value_grounding | high | Ours applies MAX() and CAST directly to '$'-prefixed text, returning Gnomeo and Juliet with NULL; the top-grossing movie is Star Wars: The Force Awakens. |
| `train_design:2473` | disney | settled | model_wrong | computation, projection | high | Ours casts '$'-text gross to 0 so the order is arbitrary (Snow White) and it returns the movie title; the top movie with a song is The Lion King, song 'Circle of Life'. |
| `train_design:2479` | disney | settled | model_wrong | computation | high | Ours strips '$' but not commas, so every gross casts to a small number and the >100M count is 0; the true share is 18/27 = 66.67%. |
| `train_design:2488` | disney | settled | model_wrong | computation, value_grounding | high | Ours casts '$'-text gross to 0 so the order is arbitrary (David Hand); the lowest gross is Winnie the Pooh ($0), directed by Wolfgang Reitherman. |
| `train_design:2490` | disney | settled | both_wrong | computation, value_grounding | high | Ours casts '$'-text gross to 0 and returns 0.0 (true average is about 166.4M over 19 Action PG-13 films); the key drops the Action filter and gives 81.2M. |
| `train_design:2492` | disney | adjudicated | model_wrong | projection, grain_aggregation | high | Question wants one estimated inflation rate for 1995 (aggregate ratio 1.933 over 32 films, per-film range 1.907-1.938); ours returns 32 titled rows with a x100 value; A and B right. |
| `train_design:2493` | disney | settled | model_wrong | computation | high | Ours subtracts '$'-prefixed text values, giving 0 instead of $110,618,207; its popularity ordering also sorts text. |
| `train_design:2494` | disney | settled | both_acceptable | — | medium | Both give Frozen with its $414,997,174 gross (correct); the key adds a release_date column, and ours returns exactly the requested values though its date sort is text-based. |
| `train_design:2496` | disney | settled | both_wrong | computation, value_grounding | medium | Ours casts '$'-text to 0, giving a wrong top-5 list and NULL percentages; the key uses '>' with the fifth-place value as threshold (top 4 only, 15.95% vs true 17.75%) and lists no titles. |
| `train_design:4185` | works_cycles | settled | gold_wrong | — | high | Key filters on Shift.StartTime (a time of day) instead of EmployeeDepartmentHistory.StartDate and returns 0; ours gives 35 night-shift employees starting in 2009 or later. |
| `train_design:4460` | hockey | settled | model_wrong | projection | high | The question asks to list the goalies and the teams they played for; ours returns only distinct team names and omits the goalie names. |
| `train_design:4472` | hockey | adjudicated | uncertain | — | medium | Hint says deathYear IS NOT NULL although the question says 'still alive' (10 living goalies qualify), and the key's lgID+year Teams join fans out (50 names vs 37 with tmID+year); A right that the hint/question conflict blocks a call. |
| `train_design:4474` | hockey | settled | both_wrong | projection, schema_retrieval | medium | Key joins Teams on lgID only and never excludes players (wrong coach and team); ours finds the right coach (Boon, 1909 Montreal Wanderers) but returns firstName and tmID instead of nameGiven ('Richard R.') and the team name. |
| `train_design:4475` | hockey | settled | both_wrong | projection | medium | Key ignores tmID='DET' and lists an overall top coach's seasons; ours applies DET but returns coachID instead of the requested coach name. |
| `train_design:4477` | hockey | adjudicated | gold_wrong | — | medium | W and L are stored as text so the key's L>W comparison is lexicographic (303 rows differ) and its HAVING COUNT>2 is per team, not two seasons; ours casts and counts seasons (returns tmID for the team); A and B right. |
| `train_design:4478` | hockey | disputed | gold_wrong | — | low | Hint says percentage = W/GP*100 but the key returns the bare fraction; ours applies *100 and returns the same six goalie-seasons keyed by playerID. |
| `train_design:4480` | hockey | settled | gold_wrong | — | high | Key keeps dead goalies (deathYear NOT NULL) and tests SUM(Min)/SUM(GP) > 0.5, which is minutes not wins; ours keeps living goalies and uses SUM(W)/SUM(GP) > 50%. |
| `train_design:4492` | hockey | settled | model_wrong | join, projection | high | The tallest player (Chara, 81) is not in the Hall of Fame, so the answer is 'No'; ours' inner join returns no rows. |
| `train_design:4494` | hockey | settled | model_wrong | grain_aggregation | medium | Ours counts distinct Master.playerID, which is NULL for coaches who never played, giving 14; the key counts 58 coach seasons (21 distinct coaches). |
| `train_design:4515` | hockey | adjudicated | both_wrong | hint_misread, computation | medium | Key does integer division on text (0) and ours averages only the 77 of 90 HOF coaches with weight/height (0.0357) instead of the hint's sum/count(coachID) (~0.0305); B right. |
| `train_design:4523` | hockey | settled | gold_wrong | — | high | Key sums this coach's wins over all seasons (692) instead of 1933; ours filters Coaches.year=1933 and returns 26. |
| `train_design:4530` | hockey | settled | gold_wrong | — | high | Key compares GA > 150 as text, letting Dan Blackburn (GA 93) through; with numeric GA the youngest is Roberto Luongo, as ours returns. |
| `train_design:4533` | hockey | settled | gold_wrong | — | high | Key returns SUM(SHO) of regular-season shutouts over a fan-out join rather than points; ours finds COL (unique top PostSHO) and returns its 104 Pts. |
| `train_design:4534` | hockey | disputed | model_wrong | projection | low | Both find Boudreau ('Gabby'), but the question asks which coach and the nickname; ours returns only the nickname and omits the coach identity. |
| `train_design:4535` | hockey | disputed | gold_wrong | — | medium | NAS has the top PP% and Trotz is its sole 2011 coach; ours returns his full name, while the key returns only coachID and its Coaches join is not restricted to 2011. |
| `train_design:4542` | hockey | settled | gold_wrong | — | high | Key sums Teams.W over a goalie fan-out join (111) and counts all goalies, not postseason ones; STL is the team with three postseason goalies and 49 wins, as ours returns. |
| `train_design:4548` | hockey | settled | both_acceptable | — | medium | Kovalchuk (220) and Heatley (216) tie at 136 PPG since 2000, so either weight is a valid answer depending on tie order. |
| `train_design:4549` | hockey | settled | model_wrong | schema_retrieval | high | Used ScoringSup.SHA (shorthanded assists) as text '7' instead of summing Scoring.SHG per player; returns nothing although two players (L and R) had 7 SHG in 1989. |
| `train_design:4552` | hockey | settled | model_wrong | computation | high | BenchMinor is text, so MAX(BenchMinor) compares as text and picks the wrong team; numerically Minnesota (44) is highest and its coach is Lemaire, as the key says. |
| `train_design:4554` | hockey | settled | both_acceptable | — | medium | Both compute (W/(W+L) 2006 minus 2005)*100 for Vancouver and agree to 14 digits (8.5765765...); the mismatch is only floating-point noise. |
| `train_design:4559` | hockey | adjudicated | both_acceptable | — | medium | L is integer with max 71 (SJS 1992), so ours follows the hint's MAX(L) on a single team-season (16.14); the key totals losses per franchise (CHI). Reviews A and B were right that the hint does not decide. |
| `train_design:4562` | hockey | settled | model_wrong | computation, grain_aggregation | medium | MAX(SHO) is taken over a text column so it returns '9' instead of 22, which selects arbitrary team-seasons and yields 49; key's team-level aggregation is a plausible reading. |
| `train_design:4564` | hockey | adjudicated | both_wrong | predicate | medium | Key uses LIMIT 8 with no offset so it returns 8 rows, not the 9th; ours ranks Master rows with NULL playerID (non-players) so its 9th row has NULL pos, while the 9th real player (cattajo01) is a G. Review A was right; B's uncertain was too cautious. |
| `train_design:4569` | hockey | settled | both_wrong | grain_aggregation, predicate | high | Key queries AwardsPlayers/LW positions and returns NULL; ours restricts Teams.year to each team's overall max year (not the goalie's last year) so returns nothing, and averages only the tallest goalie instead of all 114 (72.5). |
| `train_design:4572` | hockey | settled | both_wrong | join | medium | Key returns Irvin's award (SUM(w) over fan-out, not the top-win coach); ours finds Bowman correctly but joins to all 31 Coaches rows, returning each of his 2 Jack Adams awards 31 times (62 rows). |
| `train_design:4574` | hockey | settled | gold_wrong | — | high | Key sorts text +/- via SUM over an unrelated Teams join and returns NULLs with reversed subtraction; the true minimum is -82 by Mikkelson in 1974 (1974-1971=3), matching ours. |
| `train_design:4579` | hockey | settled | both_wrong | projection | medium | Key returns count 1 with a single opponent (grouped by opponent with LIMIT 1); ours omits the requested count and picks the team by best single-matchup W (a 5-way tie decided by luck) rather than season wins (MOC 16). |
| `train_design:4581` | hockey | settled | both_acceptable | — | high | Both return coach paterri01c with 6 losses; only the column order differs. |
| `train_design:4585` | hockey | adjudicated | both_wrong | grain_aggregation, projection | medium | Key drops the Canada filter (returns Finns) and ours lists 16159 per-season rows for 3831 players instead of a count of players with career goals <=5 (1686 by career total). Both reviews were right. |
| `train_design:4586` | hockey | settled | gold_wrong | — | high | Key arbitrarily halves the total; Teams has 44 distinct seasons for St. Louis Blues (no duplicate rows) and the sum is 686. |
| `train_design:4590` | hockey | settled | model_wrong | schema_retrieval | high | Used TeamsPost (playoff stats) instead of Teams regular-season BenchMinor; Pittsburgh Penguins leads with 38 in Teams for 2006. |
| `train_design:4597` | hockey | adjudicated | both_wrong | grain_aggregation | medium | Ours picks an arbitrary series row with max W (many series have W=4, Boston first) instead of totalling wins; the key's TeamsSC sum ties Ottawa and Montreal at 11 and LIMIT 1 picks Ottawa arbitrarily, while full SCF data gives Montreal (103). Review A was closer than B. |
| `train_design:4615` | hockey | settled | model_wrong | computation | high | Divided TeamVsTeam.W (wins against one opponent) by Teams.G, giving 0.019; winning rate per hint is Teams W/G (about 0.561), as in the key. |
| `train_design:4616` | hockey | settled | model_wrong | schema_retrieval, value_grounding | high | Filters SeriesPost.round = 'SC', a value that does not exist (finals are 'SCF'), so the average is NULL; key averages PIM from the Stanley Cup finals table TeamsSC (30.33). |
| `train_design:4618` | hockey | settled | both_wrong | grain_aggregation | high | Key computes an unrelated TeamsSC W/G expression; ours counts coach-season rows (6) in the numerator over 29 distinct coaches (20.7%), whereas 1 of 29 distinct coaches is American (3.45%). |
| `train_design:4630` | hockey | settled | gold_wrong | — | high | Key filters pos='D' (a defenseman, Mummery) although the question and hint ask for goalies; Paddy Moran leads with 7595 minutes. |
| `train_design:4649` | hockey | settled | gold_wrong | — | high | Key sums Teams.L across a join to every Scoring row, giving 775; BOS lost 25 games in 2010 and players made 413 assists, matching ours. |
| `train_design:4653` | hockey | settled | model_wrong | computation, projection | high | Returns raw W and G as two columns instead of the requested wins-per-game ratio (34/82=0.4146); top scorer primeke02 is right. |
| `train_design:5124` | chicago_crime | settled | gold_wrong | — | medium | Key sorts comma-formatted population text so '10,185' (New City) sorts first; numerically West Pullman (2,876) is smallest, matching ours (correct despite CAST lacking REPLACE). |
| `train_design:5129` | chicago_crime | settled | gold_wrong | — | high | Key's join condition compares T2.community_area_no to itself, so it returns one arbitrary neighborhood; Hyde Park (98,514) has two neighborhoods, Hyde Park and East Hyde Park, as ours returns. |
| `train_design:5160` | chicago_crime | settled | both_wrong | computation | medium | Population is comma-formatted text; key's SUM(text) and our CAST without REPLACE both read only leading digits (166, 278), so neither is a real sum (e.g. Northwest side is 168,031). |
| `train_design:5168` | chicago_crime | settled | gold_wrong | — | high | Key never restricts to the most populated ward (67 is the citywide count); ward 40 has 2 domestic bar/tavern incidents, as ours returns. |
| `train_design:5178` | chicago_crime | settled | both_acceptable | — | high | Both return Andre Vasquez Jr. for ward 40; only the order of the name columns differs. |
| `train_design:5187` | chicago_crime | settled | gold_wrong | — | high | Key orders by COUNT ascending and so uses the least-crime area, not the most populous; Hyde Park has 1965 crimes, so 1965/12 = 163.75, as ours returns. |
| `train_design:5196` | chicago_crime | adjudicated | both_wrong | value_grounding, computation | medium | Stored side is 'West ' (trailing space) so ours matches nothing and returns NULL, and population is comma text ('13,393') so a plain CAST fails too; the key averages the comma text (27.6 vs true 28074). Review A was right. |
| `train_design:5197` | chicago_crime | settled | both_wrong | predicate | medium | Key ignores the population condition (its crime is in Garfield Ridge, not the largest area); ours uses citywide max population (Hyde Park, no Burke-ward crimes) and returns nothing. |
| `train_design:5203` | chicago_crime | adjudicated | both_wrong | value_grounding, computation | medium | A list of 3536 report_nos exists (side is 'Far North ' with trailing space, population is comma text like '71,942'); ours returns nothing and the key returns a count instead of the list. Review A was right. |
| `train_design:5209` | chicago_crime | settled | gold_wrong | — | high | Key orders by COUNT(population) and lands on the wrong area (21.57%); Hyde Park, the most populated, has 182 domestic of 1965 crimes (9.26%), as ours returns. |
| `train_design:5210` | chicago_crime | disputed | uncertain | — | low | Question says average beat of all crimes (ours: 12743 cases) but hint restricts the average to population<52000 (25265 cases); the key also returns a count rather than the requested case numbers. |
| `train_design:5245` | chicago_crime | settled | gold_wrong | — | medium | Key averages ward population over crime rows, weighting each ward by its crime count; the question asks for the average of the wards themselves, which is 53868.82 over 50 distinct wards. |
| `train_design:5251` | chicago_crime | settled | gold_wrong | — | high | Key joins Crime.report_no to IUCR.iucr_no (wrong key) and uses latitude 41.64820251 (not the asked 41.64820151), returning NULL; the correct join gives 1 severe incident. |
| `train_design:5257` | chicago_crime | settled | gold_wrong | — | high | Key lists all 74 locations with no counting or limit; the least populated area (West Pullman) has RESIDENCE as its most common location (1529). |
| `train_design:5259` | chicago_crime | settled | gold_wrong | — | high | Key orders by latitude/longitude instead of incident count; the most frequent Chatham simple-assault coordinate is 41.74621174, -87.63540603 (9 incidents), as ours returns. |
| `train_design:5297` | chicago_crime | settled | gold_wrong | — | high | Key counts domestic crimes in all wards (ORDER BY is not a filter); ward 40, the most populated, has 332. |
| `train_design:5307` | chicago_crime | settled | gold_wrong | — | high | Key uses integer division (2946/12 = 245); the true average is 245.5, as ours returns. |
| `train_dev:13` | movie | adjudicated | both_wrong | value_grounding, computation | medium | screentime is text like '0:32:30' so both answers return NULL; the key uses only the minutes digits (1500) while the true value with seconds is about 1082. Review A was right. |
| `train_dev:44` | movie | settled | both_wrong | computation, value_grounding | high | NetWorth is text like '$95,000,000.00'; text comparison counts 86 actors (18.4%) instead of the 2 numerically over 400M (~0.43%), and the key returns a count difference, not a percentage. |
| `train_dev:56` | restaurant | settled | gold_wrong | — | medium | Key lists regions having any non-African restaurant (nearly all regions incl. bay area); ours correctly returns the 8 regions with no African restaurant. |
| `train_dev:61` | restaurant | settled | gold_wrong | — | high | Key returns counties with any other restaurant (20 of 20) rather than counties lacking Bakers Square; ours returns the correct 19. |
| `train_dev:67` | restaurant | settled | model_wrong | value_grounding | high | Used 'San Francisco' but the data stores lowercase 'san francisco', so the result is empty. |
| `train_dev:72` | restaurant | settled | both_wrong | grain_aggregation | high | Correct answer is the 3 regions with no pizza (los angeles area, yosemite and mono lake area, sacramento area); key returns regions that do have pizza, ours checks per city so returns 9 regions. |
| `train_dev:82` | restaurant | settled | gold_wrong | — | high | Key filters on 'San Francisco' (capitalized) and returns nothing; three restaurants tie at 4.5, so LIMIT 1 is incomplete while the tie-inclusive answer is right. |
| `train_dev:117` | restaurant | settled | gold_wrong | — | high | Key filters city = 'Danville' (case mismatch) and returns nothing; the stored value is 'danville' with 69 rows, which ours returns. |
| `train_dev:119` | restaurant | adjudicated | model_wrong | grain_aggregation | medium | There are 180 restaurants/labels in unknown-county cities; ours' COUNT(DISTINCT label) collapses chain names to 165. Both reviews were right. |
| `train_dev:125` | restaurant | settled | gold_wrong | — | high | Key filters 'Napa Valley' (wrong case) over geographic rows and returns 0; the correct restaurant share is 192/9590 = 2.00%, matching both answers. |
| `train_dev:157` | restaurant | settled | gold_wrong | — | high | Key joins location and generalinfo on city, a fan-out producing 114,912 rows; ours joins on id_restaurant and returns the 89 distinct streets. |
| `train_dev:158` | restaurant | settled | gold_wrong | — | high | Question asks for the number of types (3 distinct food types); the key counts restaurant rows (4); ours[1] filters on nonexistent region values and returns 0. |
| `train_dev:159` | restaurant | settled | both_acceptable | — | medium | Same restaurant and values as the key (4 restaurants tie at 4.5, LIMIT 1 in both); ours only orders columns as the hint lists them (num, name, city). |
| `train_dev:160` | restaurant | settled | gold_wrong | — | medium | Key returns the county with the most restaurants overall; the question asks for counties of the chain with most branches (round table pizza, 10 counties), which ours returns. |
| `train_dev:177` | soccer_2016 | disputed | model_wrong | hint_misread, projection | low | Hint defines role as Role_Id (key returns 1); ours returns Role_Desc 'Captain' instead. |
| `train_dev:179` | soccer_2016 | settled | model_wrong | computation, hint_misread | medium | Hint divides sum(Win_Margin) by count(Match_Id) over all 59 matches (16.66); ours averages only the 57 non-NULL margins (17.25). |
| `train_dev:180` | soccer_2016 | settled | gold_wrong | — | high | Key compares a text SUBSTR to integer 1985, which is true for all 469 players; ours correctly filters to 203 players (72.41%). |
| `train_dev:209` | soccer_2016 | settled | gold_wrong | — | high | Key's UNION with ORDER BY/LIMIT 1 is broken and returns KKR; actual most losses is Delhi Daredevils (75), which ours returns. |
| `train_dev:256` | soccer_2016 | settled | model_wrong | hint_misread | high | Key is right (Pune as Team_1, list Team_2); ours[0] swaps the direction, listing Team_1 opponents; ours[1] is correct. |
| `train_dev:263` | soccer_2016 | settled | gold_wrong | — | high | Key SQL is about St George/Port Elizabeth, unrelated to SuperSport Park; ours returns the row showing SuperSport Park is in Centurion. |
| `train_dev:267` | soccer_2016 | disputed | gold_wrong | — | low | Key returns a percentage of ball count over all innings-1 runs, not an average; average runs per ball in overs 2-24 of innings 1 is 1.2806 (ours[1]); ours[0] divides by sum of over ids. |
| `train_dev:268` | soccer_2016 | adjudicated | both_wrong | hint_misread, grain_aggregation | medium | Key is AVG(Innings_No)=2.0 (meaningless); the hint's formula sum(Extra_Runs)/count(rows) gives 1.2747 over 3596 rows, but ours averages per-match totals (8.04). Both reviews were right. |
| `train_dev:273` | soccer_2016 | settled | gold_wrong | — | medium | Key divides by TOTAL(Player_Id) (sum of ids), giving 0.012; ours follows the hint, 249 of 12,694 rows = 1.96%. |
| `train_dev:275` | soccer_2016 | settled | both_wrong | grain_aggregation, projection | medium | Question wants one average (~343 right-hand batters / 11 countries); key returns a percentage (73.1), ours returns per-country counts with a useless denominator of 1. |
| `train_dev:276` | soccer_2016 | adjudicated | gold_wrong | — | medium | Key matches ' Legbreak' (stored value is 'Legbreak', id 10, 24 players) and divides by TOTAL(Player_Id), so its 0.0 is broken; ours[0] is a sound joined-players percentage (5.63, vs 5.12 over all 469) while ours[1] only gets 0 by comparing an integer to text. Review B was right; A was too harsh on ours[0]. |
| `train_dev:283` | soccer_2016 | settled | gold_wrong | — | medium | Key lists every fielder with no above-average filter; ours[1] correctly returns the 122 players above the average number of catches; ours[0] adds an unrequested catches column. |
| `train_dev:285` | soccer_2016 | settled | gold_wrong | — | high | Hint asks for avg(Player_Out) lbw minus run out; ours computes the difference (-7.40) while the key returns only the lbw average. |
| `train_dev:294` | soccer_2016 | settled | gold_wrong | — | medium | Key returns team/cap ids for every combination with no purple-and-orange condition; ours returns Chennai Super Kings, confirmed as the only team with both cap winners in the same season. |
| `train_dev:300` | soccer_2016 | settled | gold_wrong | — | medium | Key lists the two venues where Kochi was Team_1 with no ranking; Nehru Stadium (5 matches) is the clear most-played venue, which ours returns. |
| `train_dev:301` | soccer_2016 | disputed | uncertain | — | low | Question is unanswerable as worded (no game has zero runs); key is broken (3.7M rows), ours counts games with any dot ball, which equals all 133 Delhi matches. |
| `train_dev:304` | soccer_2016 | disputed | uncertain | — | low | Ranking by bowling skill is not well defined; key orders by the numeric skill id, ours[1] matches that (with ties at ids 14/13) and ours[0] orders alphabetically by skill name. |
| `train_dev:307` | soccer_2016 | settled | gold_wrong | — | high | Key's chained comparison 2011 < Season_Year < 2015 is always true (returns all 9 seasons); ours applies the hint's exclusive bounds and returns 3. |
| `train_dev:310` | soccer_2016 | settled | both_wrong | advanced_sql | high | Only 2009-04-23, 04-24, 04-25 are consecutive days, so the answer is 392194, 392196 and 392197; key returns all 15 matches, ours return a single match each. |
| `train_dev:314` | soccer_2016 | adjudicated | gold_wrong | — | medium | Key compares DOB text with unpadded '1980-4-11', letting KP Pietersen (1980-06-27) in for 12; ours with a proper date gives 11. Review A was right; B's uncertain over-weights the format mismatch. |
| `train_dev:318` | soccer_2016 | settled | gold_wrong | — | high | Key's BETWEEN '2011%' AND '2012%' only matches 2011 dates (13); the correct 2011-2012 total is 13+13=26, which ours returns. |
| `train_dev:322` | soccer_2016 | disputed | uncertain | — | low | Key is empty (broken); question does not say which innings or whether extras count; ours[0] adds both innings' runs over 17 overs, ours[1] picks innings 1 with extras (172/17=10.1). |
| `train_dev:323` | soccer_2016 | disputed | uncertain | — | low | Key is empty (uses wrong match id); innings and extras are unspecified, ours[0] combines both innings, ours[1] uses innings 1 only. |
| `train_dev:325` | soccer_2016 | settled | gold_wrong | — | high | Key returns the most common full birth date (1987-04-30), not a year; ours returns 1984 (41 players), the most common birth year. |
| `train_dev:327` | soccer_2016 | settled | both_acceptable | — | medium | Key returns Season_Id (2) and ours returns the matching Season_Year (2009); both identify the season with the fewest matches (57, no tie). |
| `train_dev:351` | soccer_2016 | disputed | both_acceptable | — | low | Question order suggests left/right (key) but the garbled hint puts right-hand bat in the numerator (ours); the hint does not settle the direction. |
| `train_dev:359` | soccer_2016 | settled | both_wrong | projection | medium | Key's average is count/count of the same rows (1.0) while real average is 3215 wickets/565 matches; ours omits the requested average entirely and returns only the lbw count. |
| `train_dev:363` | soccer_2016 | disputed | uncertain | — | medium | Hint defines Superover as win_type='wickets' (307 matches) which contradicts the question and the Outcome table's real 'Superover' value (6 matches). |
| `train_dev:373` | soccer_2016 | adjudicated | gold_wrong | — | medium | Key's ORDER BY win_margin LIMIT 1 takes a NULL-margin match (9 NULLs sort first); the true minimum margin is 1, shared by several matches, and ours returns their second teams. Review B was right. |
| `train_dev:394` | soccer_2016 | settled | gold_wrong | — | high | Key joins Player_Match without a season filter so it returns Pune Warriors (2011-12); Ganguly played only for Kolkata Knight Riders in 2008. |
| `train_dev:399` | soccer_2016 | adjudicated | uncertain | — | medium | Player links only to a country, not a city; the hint's MIN(DOB) is the oldest (Jayasuriya, country 7 with no cities) while the youngest is Ishan Kishan, so the key's city is arbitrary and ours gives nothing or all 20 Indian cities. |
| `train_dev:420` | soccer_2016 | disputed | both_wrong | predicate | medium | Key drops the 2009 filter (56 matches all years); ours counts wickets-wins by either team among DD's 15 matches (11/15) instead of DD's own wins by wickets (7 of 15). |
| `train_dev:428` | sales_in_weather | settled | gold_wrong | — | medium | Key has no date join between sales and weather (214 is an arbitrary row); the true max-tmax days for store 3's station are 2012-08-01 and 08-03 (169+42=211), matching answer 1, while answer 0 uses a global max and returns NULL. |
| `train_dev:430` | sales_in_weather | settled | both_wrong | join | high | Key sums a CASE over an undated cross join (12566); ours joins weather by station only with no date match (112), while the correct date-matched count is 19 (16 in 2012). |
| `train_dev:431` | sales_in_weather | settled | both_wrong | join | high | Correct day is 2014-02-13 (range 51 at store 3's station 7, 24 units); key has no date join (214) and ours use the global max range from another station so return NULL. |
| `train_dev:432` | sales_in_weather | settled | gold_wrong | — | high | Key has no date join so 2012-01-01 is arbitrary; date-matched result is 2012-11-11 (range 41), which is answer 0, while answer 1 also lacks the date join. |
| `train_dev:435` | sales_in_weather | settled | gold_wrong | — | medium | Key has no date join and groups by tmax (114622); the two tied hottest days for store 3 (2012-08-01, 08-03) total 275+141=416, matching both answers. |
| `train_dev:436` | sales_in_weather | settled | both_wrong | join | high | Key subtracts store 6 instead of store 10 and has no date join; ours filter weather to the hottest date but never restrict sales to that date, so they return whole-history totals (22867) instead of the tied-day units (65 vs 0). |
| `train_dev:440` | sales_in_weather | disputed | uncertain | — | low | Key has no date join (yearly ratio) and answer 0 lacks the sales-date filter; the hottest day is tied (08-01 gives 61.45%, 08-03 gives 29.79%, combined 50.7%) so answer 1's single-day pick cannot be confirmed. |
| `train_dev:450` | sales_in_weather | settled | gold_wrong | — | high | Key filters store_nbr=14 although the question and hint say store 6; store 6 maps to station 14 whose wetbulb on 2012-02-15 is 47. |
| `train_dev:466` | sales_in_weather | settled | model_wrong | projection | high | Stations 15 and 19 tie at 23 days; ours LIMIT 1 returns only station 15 and adds an unrequested count column. |
| `train_dev:467` | sales_in_weather | settled | gold_wrong | — | medium | Question asks for the station of the single store selling most of item 9 (store 17, station 20); key groups by station instead of store and returns station 13. |
| `train_dev:475` | sales_in_weather | disputed | both_acceptable | — | low | Key and answer 0 rank individual store-day-item records (station 13 twice), a plausible reading; answer 1 uses distinct stations (13, 2, 20) but adds an unrequested max_units column. |
| `train_dev:479` | sales_in_weather | settled | both_acceptable | — | medium | Station 17 (6 stores, no tie) and its 56.24 average match the key; ours also returns the station the question first asks for while the key omits it. |
| `train_dev:489` | sales_in_weather | disputed | both_acceptable | — | low | Hint's item_nbr suggests counting items (key: 111, though only 3 items had units>0) while 'how many items sold' also reads as total units (answer 1: 122 date-matched); answer 0 lacks the date join. |
| `train_dev:491` | sales_in_weather | settled | gold_wrong | — | high | Key's malformed LIKE ... OR 'HZ' OR '%' returns all 852 dates; store 35's station 5 has no HZ in codesum, so the correct result is empty. |
| `train_dev:496` | sales_in_weather | settled | uncertain | — | medium | Hint date 2022-09-16 does not exist in the data (weather covers 2012-2014); the key silently uses 2012-09-16. |
| `train_dev:497` | sales_in_weather | settled | both_wrong | join | high | Correct join needs both station and date (37 units); key joins weather by date only (424) and ours joins by station only with no date match (28008). |
| `train_dev:498` | sales_in_weather | settled | gold_wrong | — | medium | Key uses item 5 although the question and hint say item 1; with item 1 and a proper station+date join both sunset extremes sum to 0, so ours (0) is right. |
| `train_dev:499` | sales_in_weather | settled | both_wrong | join | high | Proper station+date join gives 363; key joins by date only (6161) and ours joins by station only without a date match (346425). |
| `jev_live_pilot_questions:12` | ice_hockey_draft | settled | model_wrong | temporal | high | Draft-year season is stored as (draftyear-1)-draftyear, but ours builds draftyear-(draftyear+1) so it returns no rows; the right filter gives Sidney Crosby. |
| `jev_live_pilot_questions:13` | ice_hockey_draft | settled | uncertain | — | medium | Hint lists 'Czech Republic' but the data stores 'Czech Rep.' (10 of 66 Toronto picks), and that mismatch decides 9.09% versus 24.24%. |
| `jev_live_pilot_questions:22` | ice_hockey_draft | settled | gold_wrong | — | medium | Key queries Pavel Patera instead of Per Mars; Per Mars has no 1997-1998 rows, so ours (NULL, no games) is right. |
| `jev_live_pilot_questions:24` | ice_hockey_draft | settled | gold_wrong | — | medium | Key ignores the Playoffs filter and returns three per-season rows; ours applies GAMETYPE='Playoffs' over the three seasons combined per the hint (36/396 = 9.09%). |
| `jev_live_pilot_questions:25` | movielens | settled | gold_wrong | — | medium | Question asks how many users are male; key counts rating rows (166871) while distinct male users who gave a 5 number 4309. |
| `jev_live_pilot_questions:26` | movielens | settled | gold_wrong | — | high | Key filters country='france' (lowercase), which matches nothing, so it returns NULL; the stored value is 'France' and ours returns the correct 3.62. |
| `jev_live_pilot_questions:31` | movielens | adjudicated | uncertain | — | medium | 568 actors tie at a_quality=5 so 'top 5 actors' is arbitrary and the key also picks one arbitrary movie per actor; A and B both right. |
| `jev_live_pilot_questions:35` | movielens | settled | gold_wrong | — | high | Key filters T2.userid = 2462959 instead of movieid, so it returns 0; movie 2462959 has 948 distinct raters and ours counts the female ones (223). |
| `jev_live_pilot_questions:36` | movielens | settled | model_wrong | projection | high | Director 61069 is the unique top (2 films) as in the key, but ours adds an unrequested film_count column. |
| `jev_live_pilot_questions:38` | movielens | settled | model_wrong | schema_retrieval | medium | Actor rating is actors.a_quality (key ~97.7%, distinct-actor ~97.2%), but ours uses user ratings from u2base, which fans out and gives 99.1%. |
| `jev_live_pilot_questions:40` | movielens | settled | gold_wrong | — | high | Question says at least 2 French films but key uses HAVING COUNT > 2 (117 actors); ours >= 2 gives 483. |
| `jev_live_pilot_questions:41` | movielens | disputed | uncertain | — | low | 'both US or UK' is ambiguous (intersection 2812 vs union 68440 actors) and the key counts actor-movie rows (114976) without DISTINCT. |
| `jev_live_pilot_questions:42` | movielens | settled | gold_wrong | — | high | Key counts director-genre join rows (456) instead of distinct directors (238), double-counting directors with both Action and Adventure films. |
| `jev_live_pilot_questions:43` | movielens | settled | both_wrong | grain_aggregation | high | Key filters genre='comedy' (stored as 'Comedy') so returns 0; ours counts join rows (955) rather than distinct movies (905), double-counting movies with several directors. |
| `jev_live_pilot_questions:46` | movielens | settled | model_wrong | other | high | Our answer produced no SQL (repair exhausted) so nothing was returned; the key follows the hint (rating = 5). |
| `jev_live_pilot_questions:47` | movielens | settled | model_wrong | computation, projection | medium | Question asks for the male:female ratio; ours returns two raw counts instead of a ratio. |
| `jev_live_pilot_questions:49` | movielens | disputed | gold_wrong | — | low | Key takes one arbitrary row among 9 movies tied at the minimum single rating (1754754 averages 3.9); ours picks the lowest-rated movie by average, a reasonable reading. |
| `jev_live_pilot_questions:50` | professional_basketball | disputed | both_acceptable | — | low | Key gives an unlabelled per-team-season ratio (1536 rows) while ours gives one overall home-win percentage; question wording and hint formula support either. |
| `jev_live_pilot_questions:51` | professional_basketball | settled | gold_wrong | — | high | Key ignores the playoff-not-null condition and divides over all teams (18.55%); ours restricts to playoff teams (280/901 = 31.08%) as asked. |
| `jev_live_pilot_questions:52` | professional_basketball | settled | both_wrong | grain_aggregation | medium | Key orders by stint, which does not measure years served; ours groups by coach+team so it misses coaches (e.g. fitchbi01, mottadi01, shuege01) who tie at 11 seasons across teams. |
| `jev_live_pilot_questions:53` | professional_basketball | settled | gold_wrong | — | high | Question asks for games won at home; key returns total wins (T2.won) while ours returns homeWon; the coach set is identical (8 rows). |
| `jev_live_pilot_questions:54` | professional_basketball | adjudicated | both_acceptable | — | medium | Same two 1947 teams and coaches; key shows team name, ours the tmID code with a correct year join (A and B right). |
| `jev_live_pilot_questions:56` | professional_basketball | settled | model_wrong | projection | high | Question asks only which teams; ours adds an unrequested tmID column. |
| `jev_live_pilot_questions:57` | professional_basketball | settled | model_wrong | grain_aggregation | high | Ours puts COUNT(DISTINCT) inside a per-team GROUP BY, returning 37 rows of 1 instead of a single count of 37. |
| `jev_live_pilot_questions:60` | professional_basketball | adjudicated | model_wrong | grain_aggregation | medium | Hint defines qualifying teams by tmID (84 tmIDs, 80 names) but ours groups by tmID+name giving 79 names and missing 'Fort Wayne Zollner Pistons'; A right on the mechanism, though the key returning codes instead of names is a lesser flaw. |
| `jev_live_pilot_questions:61` | professional_basketball | settled | gold_wrong | — | high | Key omits the hint's multiplication by 703 (max 0.045 instead of a realistic BMI); ours follows the hint's formula. |
| `jev_live_pilot_questions:62` | professional_basketball | settled | gold_wrong | — | high | Key omits the hint's *703 factor (0.034); ours applies the formula and gives a realistic BMI of about 23.8. |
| `jev_live_pilot_questions:64` | professional_basketball | adjudicated | both_wrong | grain_aggregation | medium | Key's AVG(DISTINCT height)=78.62 is meaningless while ours averages over appearances (78.107) rather than the 258 distinct East all-stars (77.95); B right. |
| `jev_live_pilot_questions:66` | professional_basketball | adjudicated | both_wrong | grain_aggregation | medium | Ours uses the hint's players_teams columns but lacks DISTINCT (533 rows for 488 players); key wrongly restricts to all-star rows from another table; B right. |
| `jev_live_pilot_questions:68` | professional_basketball | settled | both_acceptable | — | high | Same formula; results differ only by floating-point noise (8.571428571428573 vs 8.57142857142857). |
| `jev_live_pilot_questions:69` | professional_basketball | disputed | both_acceptable | — | low | Key counts any coach who coached STL and ever won an award; ours requires the award year to match the STL season; 'from STL team' allows either. |
| `jev_live_pilot_questions:70` | professional_basketball | settled | gold_wrong | — | medium | Same player (chrisdo01 = Douglas Dale Christie) but key returns only playerID while question and hint ask for the name; ours returns the name. |
| `jev_live_pilot_questions:71` | professional_basketball | settled | gold_wrong | — | medium | Key ranks by an individual player's points and returns VAN; hint says max(o_pts) at team level, where non-playoff Seattle (4743) leads; PostGP is 0 for both teams. |
| `jev_live_pilot_questions:74` | professional_basketball | settled | both_acceptable | — | high | Same player (Glenn Robinson); key adds the middle name, ours returns first and last name exactly as the hint defines full name. |
| `jev_live_pilot_questions:75` | regional_sales | settled | gold_wrong | — | high | Question asks for order numbers with product names; key returns distinct ProductID/product name and no order numbers; ours lists all 277 orders. |
| `jev_live_pilot_questions:76` | regional_sales | settled | both_wrong | computation | high | Unit Cost is text with thousands commas; key sorts it as text and ours casts without removing commas; true max is SO - 0008074 (Trigen, 12/28/20), not Amylin Group. |
| `jev_live_pilot_questions:77` | regional_sales | disputed | model_wrong | projection | low | Hint says cities means City Name; ours adds an unrequested Region column (key returns only distinct city names). |
| `jev_live_pilot_questions:80` | regional_sales | settled | model_wrong | computation | high | Unit Price/Cost carry thousands commas and ours casts without removing them, so the profit ranking is wrong; correct top is Photo Frames. |
| `jev_live_pilot_questions:83` | regional_sales | adjudicated | uncertain | — | medium | Question says 6 June 2018 ('6/6/18', 4 rows, used by key) but hint says '6/5/18' (7 rows, used by ours), and the mismatch decides the result; A and B right. |
| `jev_live_pilot_questions:85` | regional_sales | adjudicated | both_wrong | computation | high | Ours casts comma-formatted prices without stripping commas so ranks are wrong; key lists Carl Nguyen twice (4 distinct teams); true top 5 is Carl Nguyen, Samuel Fowler, Roger Alexander, Adam Hernandez, Frank Brown; A right. |
| `jev_live_pilot_questions:89` | regional_sales | settled | uncertain | — | medium | Question says state of New York (key uses State, 16.7%) but hint says City Name = 'New York', a city that does not exist in the data (only Manhattan, Huntington), so ours gives 0%. |
| `jev_live_pilot_questions:91` | regional_sales | settled | model_wrong | temporal | high | Ours builds non-zero-padded date strings that date() cannot parse, so it returns no rows; all 7991 orders are after 1/1/2018, which the key returns. |
| `jev_live_pilot_questions:93` | regional_sales | settled | gold_wrong | — | medium | Max online discount (0.4) is tied across 115 orders in all 4 regions; key's LIMIT 1 returns one arbitrary region while the question asks for regions; ours returns all 4. |
| `jev_live_pilot_questions:99` | regional_sales | disputed | both_acceptable | — | low | Same team (Todd Roberts); key counts orders both placed and shipped in 2019 (128), ours counts orders shipped in 2019 (134); the hint's separate definitions support either. |

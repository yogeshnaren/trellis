# Paired comparison: `bird_raw_20260926T211555Z.jsonl` → `bird_raw_20260927T083717Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- declared variable(s): ['code', 'config', 'prompt']

## ⚠️ PILOT comparison: partial overlap allowed, NOT acceptance evidence

500 shared questions; repeats old/new = 3/3 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | -1.13 | [-2.73, +0.40] |
| Database macro | -1.35 | [-3.03, +0.31] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000205 | 0.000661 | 1.36 |
| new | 0.000170 | 0.000665 | 1.58 |

**Track: submission.** **Required minimum: +1.50 pts** (declared base; cost and latency are ceilings: mean uncached ≤ $0.01/answer, any answer ≤ $0.05, P90 ≤ 30s; new run mean $0.000665, max $0.0029, P90 2.96s: **within**). Meets it: row-weighted **no**, macro **no** (point estimate ≥ minimum and CI lower bound > 0).
Non-inferiority (CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one strictly better): **no**.
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `california_schools` | 30 | 47.8% | 45.6% | -2.2 | 3 | 1 | 0.625 |
| `card_games` | 52 | 56.4% | 52.6% | -3.8 | 7 | 1 | 0.070 |
| `codebase_community` | 49 | 61.2% | 61.9% | +0.7 | 3 | 3 | 1.000 |
| `debit_card_specializing` | 30 | 55.6% | 58.9% | +3.3 | 1 | 4 | 0.375 |
| `european_football_2` | 51 | 68.6% | 66.7% | -2.0 | 4 | 3 | 1.000 |
| `financial` | 32 | 57.3% | 45.8% | -11.5 | 7 | 1 | 0.070 |
| `formula_1` | 66 | 62.1% | 61.6% | -0.5 | 2 | 2 | 1.000 |
| `student_club` | 48 | 88.9% | 88.2% | -0.7 | 1 | 0 | 1.000 |
| `superhero` | 52 | 85.9% | 86.5% | +0.6 | 0 | 1 | 1.000 |
| `thrombosis_prediction` | 50 | 54.7% | 56.7% | +2.0 | 0 | 3 | 0.250 |
| `toxicology` | 40 | 67.5% | 66.7% | -0.8 | 2 | 1 | 1.000 |

| Difficulty | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| challenging | 102 | 54.6% | 53.6% | -1.0 | 6 | 5 | 1.000 |
| moderate | 250 | 62.9% | 61.7% | -1.2 | 16 | 12 | 0.572 |
| simple | 148 | 76.6% | 75.5% | -1.1 | 8 | 3 | 0.227 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 204 | 72.9% | 73.2% | +0.3 | 7 | 8 | 1.000 |
| medium | 233 | 62.8% | 60.2% | -2.6 | 20 | 10 | 0.099 |
| high | 63 | 49.7% | 49.2% | -0.5 | 3 | 2 | 1.000 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- REGRESSION: `european_football_2` question 1136 (row 171)
- REGRESSION: `formula_1` question 978 (row 234)
- fix: `codebase_community` question 581 (row 316)
- REGRESSION: `codebase_community` question 716 (row 345)
- fix: `card_games` question 440 (row 376)
- REGRESSION: `financial` question 137 (row 484)
- REGRESSION: `financial` question 137 (row 487)


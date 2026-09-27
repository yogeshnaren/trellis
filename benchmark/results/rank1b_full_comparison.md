# Paired comparison: `bird_raw_20260926T212754Z.jsonl` → `bird_raw_20260927T060549Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- declared variable(s): ['code', 'config', 'prompt']

## Acceptance evidence (official EX): full comparison, coverage verified

501 shared questions; repeats old/new = 2/2 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | +0.80 | [-0.30, +2.00] |
| Database macro | +1.59 | [+0.05, +3.51] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000141 | 0.000696 | 1.50 |
| new | 0.000153 | 0.000700 | 1.71 |

**Track: submission.** **Required minimum: +1.50 pts** (declared base; cost and latency are ceilings: mean uncached ≤ $0.01/answer, any answer ≤ $0.05, P90 ≤ 30s; new run mean $0.000700, max $0.0027, P90 3.17s: **within**). Meets it: row-weighted **no**, macro **yes** (point estimate ≥ minimum and CI lower bound > 0).
Non-inferiority (CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one strictly better): **no**.
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `movie` | 46 | 83.7% | 87.0% | +3.3 | 0 | 2 | 0.500 |
| `restaurant` | 117 | 70.1% | 69.2% | -0.9 | 3 | 2 | 1.000 |
| `sales_in_weather` | 80 | 60.0% | 63.7% | +3.8 | 0 | 4 | 0.125 |
| `soccer_2016` | 258 | 69.4% | 69.6% | +0.2 | 2 | 3 | 1.000 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 243 | 79.4% | 79.6% | +0.2 | 3 | 4 | 1.000 |
| medium | 207 | 63.8% | 64.7% | +1.0 | 1 | 5 | 0.219 |
| high | 51 | 44.1% | 47.1% | +2.9 | 1 | 2 | 1.000 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- fix: `movie` question 748 (row 18)
- REGRESSION: `restaurant` question 1680 (row 56)
- REGRESSION: `restaurant` question 1706 (row 82)
- fix: `restaurant` question 1711 (row 87)
- fix: `sales_in_weather` question 8149 (row 433)
- fix: `sales_in_weather` question 8186 (row 470)


# Paired comparison: `bird_raw_20260926T212754Z.jsonl` → `bird_raw_20260927T034045Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- `code` differs (`code_state_sha256_16`)
- declared variable(s): ['code', 'config']

## ⚠️ PILOT comparison: partial overlap allowed, NOT acceptance evidence

100 shared questions; repeats old/new = 2/2 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | -1.50 | [-5.50, +2.50] |
| Database macro | -1.50 | [-5.50, +2.50] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000143 | 0.000583 | 1.42 |
| new | 0.000202 | 0.000629 | 2.26 |

**Track: product.** **Required minimum: +2.50 pts** (base +1.50, plus 1 pt per +50% uncached cost and per +1s P50). Meets it: row-weighted **no**, macro **no** (point estimate ≥ minimum and CI lower bound > 0).
Non-inferiority (CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one strictly better): **no**.
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `movie` | 25 | 84.0% | 88.0% | +2.0 | 0 | 1 | 1.000 |
| `restaurant` | 25 | 76.0% | 72.0% | -6.0 | 2 | 0 | 0.500 |
| `sales_in_weather` | 25 | 64.0% | 64.0% | +4.0 | 1 | 2 | 1.000 |
| `soccer_2016` | 25 | 64.0% | 56.0% | -6.0 | 2 | 0 | 0.500 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 47 | 85.1% | 80.9% | -3.2 | 2 | 0 | 0.500 |
| medium | 43 | 60.5% | 60.5% | -1.2 | 3 | 2 | 1.000 |
| high | 10 | 50.0% | 60.0% | +5.0 | 0 | 1 | 1.000 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- REGRESSION: `restaurant` question 1753 (row 129)
- REGRESSION: `soccer_2016` question 1895 (row 271)
- fix: `sales_in_weather` question 8186 (row 470)


# Paired comparison: `bird_raw_20260924T175733Z.jsonl` → `bird_raw_20260925T005017Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- `code` differs (`code_state_sha256_16`)
- declared variable(s): ['code', 'config']

## ⚠️ PILOT comparison: partial overlap allowed, NOT acceptance evidence

100 shared questions; repeats old/new = 2/2 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | -0.50 | [-4.00, +3.00] |
| Database macro | -0.50 | [-4.00, +3.00] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000274 | 0.000419 | 1.16 |
| new | 0.001360 | 0.002425 | 3.78 |

**Required minimum: +13.69 pts** (base +1.50, plus 1 pt per +50% uncached cost and per +1s P50). Meets it: row-weighted **no**, macro **no** (point estimate ≥ minimum and CI lower bound > 0).
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `movie` | 25 | 84.0% | 84.0% | +0.0 | 0 | 0 | 1.000 |
| `restaurant` | 25 | 72.0% | 72.0% | +0.0 | 1 | 1 | 1.000 |
| `sales_in_weather` | 25 | 56.0% | 52.0% | -2.0 | 1 | 1 | 1.000 |
| `soccer_2016` | 25 | 64.0% | 64.0% | +0.0 | 0 | 0 | 1.000 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 47 | 80.9% | 80.9% | +0.0 | 1 | 1 | 1.000 |
| medium | 43 | 60.5% | 58.1% | -2.3 | 1 | 0 | 1.000 |
| high | 10 | 40.0% | 50.0% | +5.0 | 0 | 1 | 1.000 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- REGRESSION: `restaurant` question 1740 (row 116)
- fix: `restaurant` question 1753 (row 129)
- REGRESSION: `sales_in_weather` question 8186 (row 470)


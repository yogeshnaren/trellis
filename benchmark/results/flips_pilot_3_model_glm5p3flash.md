# Paired comparison: `bird_raw_20260924T175733Z.jsonl` → `bird_raw_20260925T004347Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- `code` differs (`code_state_sha256_16`)
- declared variable(s): ['code', 'config']

## ⚠️ PILOT comparison: partial overlap allowed, NOT acceptance evidence

100 shared questions; repeats old/new = 2/2 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | -13.50 | [-21.00, -6.50] |
| Database macro | -13.50 | [-21.00, -6.50] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000274 | 0.000419 | 1.16 |
| new | 0.000326 | 0.000358 | 4.27 |

**Required minimum: +4.61 pts** (base +1.50, plus 1 pt per +50% uncached cost and per +1s P50). Meets it: row-weighted **no**, macro **no** (point estimate ≥ minimum and CI lower bound > 0).
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `movie` | 25 | 84.0% | 68.0% | -16.0 | 4 | 0 | 0.125 |
| `restaurant` | 25 | 72.0% | 48.0% | -24.0 | 9 | 1 | 0.021 |
| `sales_in_weather` | 25 | 56.0% | 48.0% | -6.0 | 4 | 1 | 0.375 |
| `soccer_2016` | 25 | 64.0% | 56.0% | -8.0 | 2 | 0 | 0.500 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 47 | 80.9% | 74.5% | -6.4 | 7 | 2 | 0.180 |
| medium | 43 | 60.5% | 44.2% | -16.3 | 8 | 0 | 0.008 |
| high | 10 | 40.0% | 10.0% | -35.0 | 4 | 0 | 0.125 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- REGRESSION: `movie` question 757 (row 27)
- REGRESSION: `movie` question 758 (row 28)
- REGRESSION: `movie` question 762 (row 32)
- REGRESSION: `movie` question 770 (row 40)
- REGRESSION: `restaurant` question 1697 (row 73)
- REGRESSION: `restaurant` question 1698 (row 74)
- REGRESSION: `restaurant` question 1699 (row 75)
- REGRESSION: `restaurant` question 1718 (row 94)
- fix: `restaurant` question 1753 (row 129)
- REGRESSION: `restaurant` question 1757 (row 133)
- REGRESSION: `soccer_2016` question 1872 (row 248)
- REGRESSION: `soccer_2016` question 2022 (row 398)
- REGRESSION: `sales_in_weather` question 8186 (row 470)
- fix: `sales_in_weather` question 8198 (row 482)


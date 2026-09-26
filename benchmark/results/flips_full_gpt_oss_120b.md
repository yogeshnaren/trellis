# Paired comparison: `bird_raw_20260924T175733Z.jsonl` → `bird_raw_20260925T014638Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- `code` differs (`code_state_sha256_16`)
- declared variable(s): ['code', 'config']

## Acceptance evidence (official EX): full comparison, coverage verified

501 shared questions; repeats old/new = 2/2 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | -1.40 | [-3.89, +1.10] |
| Database macro | -1.04 | [-3.51, +1.37] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000398 | 0.000497 | 1.05 |
| new | 0.000166 | 0.000398 | 0.97 |

**Required minimum: +1.50 pts** (base +1.50, plus 1 pt per +50% uncached cost and per +1s P50). Meets it: row-weighted **no**, macro **no** (point estimate ≥ minimum and CI lower bound > 0).
Non-inferiority (CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one strictly better): **no**.
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `movie` | 46 | 84.8% | 84.8% | +0.0 | 0 | 0 | 1.000 |
| `restaurant` | 117 | 70.1% | 66.7% | -3.4 | 10 | 7 | 0.629 |
| `sales_in_weather` | 80 | 52.5% | 52.5% | +0.6 | 4 | 5 | 1.000 |
| `soccer_2016` | 258 | 70.5% | 69.0% | -1.4 | 12 | 10 | 0.832 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 243 | 79.0% | 76.5% | -2.3 | 13 | 9 | 0.523 |
| medium | 207 | 62.8% | 62.3% | -0.5 | 11 | 11 | 1.000 |
| high | 51 | 43.1% | 43.1% | -1.0 | 2 | 2 | 1.000 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- fix: `restaurant` question 1679 (row 55)
- fix: `restaurant` question 1686 (row 62)
- REGRESSION: `restaurant` question 1687 (row 63)
- fix: `restaurant` question 1691 (row 67)
- REGRESSION: `restaurant` question 1695 (row 71)
- REGRESSION: `restaurant` question 1704 (row 80)
- REGRESSION: `restaurant` question 1706 (row 82)
- fix: `restaurant` question 1711 (row 87)
- fix: `restaurant` question 1743 (row 119)
- REGRESSION: `restaurant` question 1744 (row 120)
- REGRESSION: `restaurant` question 1746 (row 122)
- REGRESSION: `restaurant` question 1747 (row 123)
- REGRESSION: `restaurant` question 1748 (row 124)
- REGRESSION: `restaurant` question 1759 (row 135)
- REGRESSION: `restaurant` question 1772 (row 148)
- REGRESSION: `soccer_2016` question 1787 (row 163)
- REGRESSION: `soccer_2016` question 1794 (row 170)
- REGRESSION: `soccer_2016` question 1804 (row 180)
- REGRESSION: `soccer_2016` question 1845 (row 221)
- fix: `soccer_2016` question 1852 (row 228)
- REGRESSION: `soccer_2016` question 1854 (row 230)
- REGRESSION: `soccer_2016` question 1895 (row 271)
- fix: `soccer_2016` question 1901 (row 277)
- fix: `soccer_2016` question 1905 (row 281)
- fix: `soccer_2016` question 1927 (row 303)
- REGRESSION: `soccer_2016` question 1938 (row 314)
- REGRESSION: `soccer_2016` question 1942 (row 318)
- REGRESSION: `soccer_2016` question 1945 (row 321)
- REGRESSION: `soccer_2016` question 1974 (row 350)
- REGRESSION: `soccer_2016` question 1997 (row 373)
- fix: `soccer_2016` question 2005 (row 381)
- REGRESSION: `soccer_2016` question 2022 (row 398)
- fix: `soccer_2016` question 2033 (row 409)
- fix: `soccer_2016` question 2034 (row 410)
- REGRESSION: `sales_in_weather` question 8158 (row 442)
- fix: `sales_in_weather` question 8160 (row 444)
- REGRESSION: `sales_in_weather` question 8196 (row 480)
- fix: `sales_in_weather` question 8198 (row 482)
- fix: `sales_in_weather` question 8203 (row 487)
- REGRESSION: `sales_in_weather` question 8209 (row 493)


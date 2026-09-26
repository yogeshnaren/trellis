# Paired comparison: `bird_raw_20260924T175733Z.jsonl` → `bird_raw_20260926T203859Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- `code` differs (`code_state_sha256_16`)
- declared variable(s): ['code', 'config']

## Acceptance evidence (official EX): full comparison, coverage verified

501 shared questions; repeats old/new = 2/2 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | +0.40 | [-1.90, +2.69] |
| Database macro | +1.53 | [-0.69, +3.94] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000398 | 0.000497 | 1.05 |
| new | 0.000185 | 0.000696 | 1.61 |

**Required minimum: +2.86 pts** (base +1.50, plus 1 pt per +50% uncached cost and per +1s P50). Meets it: row-weighted **no**, macro **no** (point estimate ≥ minimum and CI lower bound > 0).
Non-inferiority (CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one strictly better): **no**.
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `movie` | 46 | 84.8% | 84.8% | +0.0 | 0 | 0 | 1.000 |
| `restaurant` | 117 | 70.1% | 68.4% | -1.3 | 8 | 6 | 0.791 |
| `sales_in_weather` | 80 | 52.5% | 60.0% | +8.8 | 3 | 10 | 0.092 |
| `soccer_2016` | 258 | 70.5% | 69.0% | -1.4 | 12 | 8 | 0.503 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 243 | 79.0% | 78.2% | -0.4 | 13 | 11 | 0.839 |
| medium | 207 | 62.8% | 63.8% | +1.2 | 9 | 10 | 1.000 |
| high | 51 | 43.1% | 45.1% | +1.0 | 1 | 3 | 0.625 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- fix: `restaurant` question 1672 (row 48)
- fix: `restaurant` question 1675 (row 51)
- fix: `restaurant` question 1679 (row 55)
- fix: `restaurant` question 1686 (row 62)
- REGRESSION: `restaurant` question 1692 (row 68)
- REGRESSION: `restaurant` question 1706 (row 82)
- REGRESSION: `restaurant` question 1740 (row 116)
- REGRESSION: `restaurant` question 1741 (row 117)
- REGRESSION: `restaurant` question 1745 (row 121)
- REGRESSION: `restaurant` question 1749 (row 125)
- fix: `restaurant` question 1753 (row 129)
- REGRESSION: `soccer_2016` question 1787 (row 163)
- REGRESSION: `soccer_2016` question 1794 (row 170)
- REGRESSION: `soccer_2016` question 1803 (row 179)
- REGRESSION: `soccer_2016` question 1804 (row 180)
- fix: `soccer_2016` question 1852 (row 228)
- fix: `soccer_2016` question 1901 (row 277)
- fix: `soccer_2016` question 1927 (row 303)
- REGRESSION: `soccer_2016` question 1938 (row 314)
- REGRESSION: `soccer_2016` question 1942 (row 318)
- REGRESSION: `soccer_2016` question 1945 (row 321)
- REGRESSION: `soccer_2016` question 1997 (row 373)
- fix: `soccer_2016` question 2005 (row 381)
- fix: `soccer_2016` question 2034 (row 410)
- fix: `sales_in_weather` question 8160 (row 444)
- fix: `sales_in_weather` question 8175 (row 459)
- fix: `sales_in_weather` question 8198 (row 482)
- fix: `sales_in_weather` question 8199 (row 483)
- fix: `sales_in_weather` question 8203 (row 487)
- fix: `sales_in_weather` question 8204 (row 488)
- fix: `sales_in_weather` question 8206 (row 490)


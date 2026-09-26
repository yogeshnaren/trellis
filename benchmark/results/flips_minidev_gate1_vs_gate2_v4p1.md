# Paired comparison: `bird_raw_20260924T232302Z.jsonl` → `bird_raw_20260926T211555Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- declared variable(s): ['code', 'config']

## ⚠️ PILOT comparison: partial overlap allowed, NOT acceptance evidence

500 shared questions; repeats old/new = 3/3 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | +5.93 | [+3.20, +8.73] |
| Database macro | +5.88 | [+2.94, +8.79] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000205 | 0.000491 | 0.97 |
| new | 0.000205 | 0.000661 | 1.36 |

**Required minimum: +2.58 pts** (base +1.50, plus 1 pt per +50% uncached cost and per +1s P50). Meets it: row-weighted **yes**, macro **yes** (point estimate ≥ minimum and CI lower bound > 0).
Non-inferiority (CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one strictly better): **no**.
No borderline audit required.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `california_schools` | 30 | 43.3% | 46.7% | +4.4 | 2 | 4 | 0.688 |
| `card_games` | 52 | 50.0% | 55.8% | +5.8 | 5 | 8 | 0.581 |
| `codebase_community` | 49 | 61.2% | 61.2% | -0.7 | 4 | 3 | 1.000 |
| `debit_card_specializing` | 30 | 53.3% | 56.7% | +3.3 | 3 | 3 | 1.000 |
| `european_football_2` | 51 | 70.6% | 68.6% | -1.3 | 6 | 5 | 1.000 |
| `financial` | 32 | 50.0% | 56.2% | +7.3 | 3 | 6 | 0.508 |
| `formula_1` | 66 | 48.5% | 62.1% | +13.6 | 1 | 11 | 0.006 |
| `student_club` | 48 | 81.2% | 89.6% | +8.3 | 0 | 5 | 0.062 |
| `superhero` | 52 | 86.5% | 86.5% | +0.0 | 3 | 3 | 1.000 |
| `thrombosis_prediction` | 50 | 50.0% | 54.0% | +4.7 | 1 | 4 | 0.375 |
| `toxicology` | 40 | 47.5% | 67.5% | +19.2 | 0 | 10 | 0.002 |

| Difficulty | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| challenging | 102 | 48.0% | 54.9% | +6.5 | 5 | 12 | 0.143 |
| moderate | 250 | 54.0% | 62.8% | +8.9 | 14 | 39 | 0.001 |
| simple | 148 | 76.4% | 76.4% | +0.5 | 9 | 11 | 0.824 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 204 | 70.1% | 73.0% | +2.6 | 13 | 19 | 0.377 |
| medium | 233 | 54.1% | 62.7% | +8.6 | 15 | 37 | 0.003 |
| high | 63 | 42.9% | 49.2% | +6.9 | 0 | 6 | 0.031 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- fix: `debit_card_specializing` question 1472 (row 1)
- fix: `debit_card_specializing` question 1500 (row 14)
- fix: `student_club` question 1359 (row 46)
- fix: `student_club` question 1381 (row 55)
- fix: `student_club` question 1410 (row 68)
- fix: `thrombosis_prediction` question 1227 (row 105)
- fix: `european_football_2` question 1037 (row 136)
- fix: `european_football_2` question 1040 (row 138)
- REGRESSION: `european_football_2` question 1078 (row 146)
- REGRESSION: `european_football_2` question 1134 (row 169)
- fix: `european_football_2` question 1136 (row 171)
- REGRESSION: `european_football_2` question 1146 (row 176)
- fix: `formula_1` question 846 (row 179)
- fix: `formula_1` question 865 (row 187)
- fix: `formula_1` question 877 (row 193)
- fix: `formula_1` question 897 (row 202)
- fix: `formula_1` question 950 (row 221)
- fix: `formula_1` question 972 (row 232)
- fix: `formula_1` question 978 (row 234)
- fix: `formula_1` question 1002 (row 242)
- fix: `superhero` question 736 (row 254)
- fix: `superhero` question 758 (row 266)
- REGRESSION: `superhero` question 798 (row 288)
- REGRESSION: `superhero` question 801 (row 290)
- REGRESSION: `codebase_community` question 531 (row 297)
- fix: `codebase_community` question 571 (row 311)
- REGRESSION: `codebase_community` question 581 (row 316)
- fix: `codebase_community` question 604 (row 323)
- fix: `card_games` question 346 (row 350)
- fix: `card_games` question 415 (row 371)
- REGRESSION: `card_games` question 440 (row 376)
- fix: `card_games` question 487 (row 392)
- fix: `toxicology` question 220 (row 411)
- fix: `toxicology` question 226 (row 412)
- fix: `toxicology` question 228 (row 414)
- fix: `toxicology` question 239 (row 420)
- fix: `toxicology` question 243 (row 423)
- fix: `toxicology` question 282 (row 436)
- fix: `california_schools` question 31 (row 448)
- REGRESSION: `financial` question 115 (row 477)
- fix: `financial` question 137 (row 484)
- fix: `financial` question 137 (row 487)
- fix: `financial` question 168 (row 493)


# Paired comparison: `bird_raw_20260924T170715Z.jsonl` → `bird_raw_20260924T175733Z.jsonl`

## Comparability

- `prompt` differs (`effective_prompt_sha256_16`)
- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- `code` differs (`code_state_sha256_16`)
- declared variable(s): ['code', 'config', 'prompt']

## Acceptance evidence (official EX): full comparison, coverage verified

501 shared questions; repeats old/new = 2/2 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | +1.60 | [+0.20, +2.99] |
| Database macro | +3.90 | [+1.13, +7.05] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000278 | 0.000467 | 1.22 |
| new | 0.000398 | 0.000497 | 1.05 |

**Required minimum: +1.63 pts** (base +1.50, plus 1 pt per +50% uncached cost and per +1s P50). Meets it: row-weighted **no**, macro **yes** (point estimate ≥ minimum and CI lower bound > 0).
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `movie` | 46 | 69.6% | 84.8% | +15.2 | 0 | 7 | 0.016 |
| `restaurant` | 117 | 70.1% | 70.1% | +0.0 | 2 | 2 | 1.000 |
| `sales_in_weather` | 80 | 52.5% | 52.5% | +0.0 | 1 | 1 | 1.000 |
| `soccer_2016` | 258 | 69.8% | 70.5% | +0.4 | 2 | 4 | 0.688 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 243 | 78.2% | 79.0% | +0.8 | 3 | 6 | 0.508 |
| medium | 207 | 59.9% | 62.8% | +2.9 | 2 | 8 | 0.109 |
| high | 51 | 43.1% | 43.1% | +0.0 | 0 | 0 | 1.000 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- fix: `movie` question 732 (row 2)
- fix: `movie` question 734 (row 4)
- fix: `movie` question 752 (row 22)
- fix: `movie` question 756 (row 26)
- fix: `movie` question 767 (row 37)
- fix: `movie` question 768 (row 38)
- fix: `movie` question 771 (row 41)
- REGRESSION: `restaurant` question 1679 (row 55)
- fix: `restaurant` question 1748 (row 124)
- fix: `sales_in_weather` question 8179 (row 463)
- REGRESSION: `sales_in_weather` question 8208 (row 492)


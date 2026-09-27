# Paired comparison: `bird_raw_20260927T095517Z.jsonl` → `bird_raw_20260927T095825Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- declared variable(s): ['config']

## ⚠️ PILOT comparison: partial overlap allowed, NOT acceptance evidence

100 shared questions; repeats old/new = 1/1 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | +0.00 | [+0.00, +0.00] |
| Database macro | +0.00 | [+0.00, +0.00] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000348 | 0.000618 | 1.66 |
| new | 0.000151 | 0.000615 | 1.53 |

**Track: submission.** **Required minimum: +1.50 pts** (declared base; cost and latency are ceilings: mean uncached ≤ $0.01/answer, any answer ≤ $0.05, P90 ≤ 30s; new run mean $0.000615, max $0.0011, P90 2.65s: **within**). Meets it: row-weighted **no**, macro **no** (point estimate ≥ minimum and CI lower bound > 0).
Non-inferiority (CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one strictly better): **yes**.
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ice_hockey_draft` | 25 | 84.0% | 84.0% | +0.0 | 0 | 0 | 1.000 |
| `movielens` | 25 | 48.0% | 48.0% | +0.0 | 0 | 0 | 1.000 |
| `professional_basketball` | 25 | 32.0% | 32.0% | +0.0 | 0 | 0 | 1.000 |
| `regional_sales` | 25 | 60.0% | 60.0% | +0.0 | 0 | 0 | 1.000 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 44 | 59.1% | 59.1% | +0.0 | 0 | 0 | 1.000 |
| medium | 45 | 48.9% | 48.9% | +0.0 | 0 | 0 | 1.000 |
| high | 11 | 72.7% | 72.7% | +0.0 | 0 | 0 | 1.000 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- none

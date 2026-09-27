# Paired comparison: `bird_raw_20260927T062743Z.jsonl` → `bird_raw_20260927T063407Z.jsonl`

## Comparability

- `config` differs (`config_sha256_16`)
- declared variable(s): ['code', 'config', 'prompt']

## Acceptance evidence (official EX): full comparison, coverage verified

175 shared questions; repeats old/new = 3/3 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | +1.90 | [-0.19, +4.19] |
| Database macro | +1.90 | [-0.19, +4.19] |

| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |
|---|---:|---:|---:|
| old | 0.000190 | 0.000574 | 1.72 |
| new | 0.000156 | 0.000580 | 1.67 |

**Track: submission.** **Required minimum: +1.50 pts** (declared base; cost and latency are ceilings: mean uncached ≤ $0.01/answer, any answer ≤ $0.05, P90 ≤ 30s; new run mean $0.000580, max $0.0016, P90 3.02s: **within**). Meets it: row-weighted **no**, macro **no** (point estimate ≥ minimum and CI lower bound > 0).
Non-inferiority (CI lower bounds ≥ −1.5 pts, cost and P50 no worse, one strictly better): **no**.
Audit required: a CI lower bound is within 1 pt of 0.
Subgroup tables below are for investigating regressions, not for voting.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `european_football_1` | 25 | 76.0% | 80.0% | +4.0 | 0 | 1 | 1.000 |
| `food_inspection_2` | 25 | 80.0% | 80.0% | +0.0 | 0 | 0 | 1.000 |
| `olympics` | 25 | 97.3% | 97.3% | -0.0 | 1 | 1 | 1.000 |
| `retail_complains` | 25 | 68.0% | 72.0% | +4.0 | 0 | 1 | 1.000 |
| `shipping` | 25 | 80.0% | 84.0% | +4.0 | 0 | 1 | 1.000 |
| `synthea` | 25 | 65.3% | 66.7% | +1.3 | 2 | 1 | 1.000 |
| `university` | 25 | 88.0% | 88.0% | +0.0 | 0 | 0 | 1.000 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 76 | 81.6% | 82.9% | +1.3 | 0 | 1 | 1.000 |
| medium | 92 | 77.5% | 80.1% | +2.5 | 2 | 3 | 1.000 |
| high | 7 | 76.2% | 76.2% | -0.0 | 1 | 1 | 1.000 |

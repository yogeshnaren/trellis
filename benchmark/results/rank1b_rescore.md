# Official re-score: `bird_raw_20260927T060549Z.jsonl`

Scoring unit: dataset rows (duplicates included, as in BIRD's official evaluator). The last column is an **oracle ceiling**: presentational rewrites chosen using the gold result, so it bounds what output-contract work could recover; it is not a gain.

| Difficulty | N | Official EX | Oracle contract ceiling |
|---|---:|---:|---:|
| unknown | 501 | 70.1% | 72.3% |
| overall | 501 | 70.1% | 72.3% |

## Per database

| db_id | N | Official EX |
|---|---:|---:|
| `sales_in_weather` | 80 | 65.0% |
| `soccer_2016` | 258 | 69.0% |
| `restaurant` | 117 | 69.2% |
| `movie` | 46 | 87.0% |
| **macro (mean over databases)** | 4 DBs | 72.5% |

## Failure buckets (150 failures)

- values-differ: 84
- row-count-differs: 43
- extra-columns: 9
- empty-result: 8
- missing-columns: 5
- gold-exec-error: 1

## Oracle output-contract rewrites (first rewrite that matches gold)

- count-without-distinct: 7
- drop-extra-columns: 4

Per-row results: benchmark/results/analysis_bird_raw_20260927T060549Z.json

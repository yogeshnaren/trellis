# BIRD-SQL Report: `train_dev.json`

Local execution-accuracy (EX) run against 100 questions from `data/bird/splits/train_dev.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4p1-flash` | unknown | 100 | 74.0% | 1.58 | 2.93 | 1.0% | $0.000306 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | overall | 100 | 74.0% | 1.58 | 2.93 | 1.0% | $0.000306 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `soccer_2016` | 25 | 64.0% |
| `sales_in_weather` | 25 | 68.0% |
| `restaurant` | 25 | 80.0% |
| `movie` | 25 | 84.0% |
| **macro (mean over databases)** | 4 DBs | 74.0% |

## Failure analysis
- `movie` #743 (unknown): Result sets differ (category: wrong-result)
- `movie` #748 (unknown): Result sets differ (category: wrong-result)
- `movie` #766 (unknown): Result sets differ (category: wrong-result)
- `movie` #775 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1671 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1739 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1767 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1781 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1783 (unknown): Result sets match (category: wrong-result)
- `sales_in_weather` #8143 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8147 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8148 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8170 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8183 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8188 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8190 (unknown): Gold execution failed: interrupted (category: wrong-result)
- `sales_in_weather` #8212 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1812 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1893 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1899 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1915 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1948 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1951 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1969 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1971 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2023 (unknown): Result sets differ (category: wrong-result)

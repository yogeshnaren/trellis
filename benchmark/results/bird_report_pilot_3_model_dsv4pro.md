# BIRD-SQL Report: `train_dev.json`

Local execution-accuracy (EX) run against 100 questions from `data/bird/splits/train_dev.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4-pro-0813` | unknown | 200 | 68.0% | 3.78 | 14.28 | 1.0% | $0.001360 |
| `accounts/fireworks/models/deepseek-v4-pro-0813` | overall | 200 | 68.0% | 3.78 | 14.28 | 1.0% | $0.001360 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `sales_in_weather` | 50 | 52.0% |
| `soccer_2016` | 50 | 64.0% |
| `restaurant` | 50 | 72.0% |
| `movie` | 50 | 84.0% |
| **macro (mean over databases)** | 4 DBs | 68.0% |

## Failure analysis
- `movie` #743 (unknown): Result sets differ (category: wrong-result)
- `movie` #743 (unknown): Result sets differ (category: wrong-result)
- `movie` #748 (unknown): Result sets differ (category: wrong-result)
- `movie` #748 (unknown): Result sets differ (category: wrong-result)
- `movie` #766 (unknown): Result sets differ (category: wrong-result)
- `movie` #766 (unknown): Result sets differ (category: wrong-result)
- `movie` #775 (unknown): Result sets differ (category: wrong-result)
- `movie` #775 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1671 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1671 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1672 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1672 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1739 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1739 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1740 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1740 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1767 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1767 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1781 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1781 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1783 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1783 (unknown): Result sets match (category: wrong-result)
- `sales_in_weather` #8143 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8143 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8147 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8147 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8148 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8148 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8170 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8170 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8175 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8175 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8183 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8183 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8186 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `sales_in_weather` #8186 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `sales_in_weather` #8188 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8188 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8190 (unknown): Gold execution failed: interrupted (category: wrong-result)
- `sales_in_weather` #8190 (unknown): Gold execution failed: interrupted (category: wrong-result)
- `sales_in_weather` #8198 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8198 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8204 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8204 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8212 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8212 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1812 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1812 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1893 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1893 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1899 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1899 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1915 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1915 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1948 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1948 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1951 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1951 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1969 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1969 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1971 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1971 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2023 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2023 (unknown): Result sets differ (category: wrong-result)

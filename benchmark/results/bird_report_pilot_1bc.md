# BIRD-SQL Report: `train_dev.json`

Local execution-accuracy (EX) run against 115 questions from `data/bird/splits/train_dev.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4-flash-0731` | unknown | 230 | 68.7% | 1.51 | 14.87 | 2.6% | $0.000360 |
| `accounts/fireworks/models/deepseek-v4-flash-0731` | overall | 230 | 68.7% | 1.51 | 14.87 | 2.6% | $0.000360 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `sales_in_weather` | 54 | 46.3% |
| `soccer_2016` | 50 | 62.0% |
| `restaurant` | 74 | 75.7% |
| `movie` | 52 | 88.5% |
| **macro (mean over databases)** | 4 DBs | 68.1% |

## Failure analysis
- `movie` #743 (unknown): Result sets differ (category: wrong-result)
- `movie` #743 (unknown): Result sets differ (category: wrong-result)
- `movie` #766 (unknown): Result sets differ (category: wrong-result)
- `movie` #766 (unknown): Result sets differ (category: wrong-result)
- `movie` #775 (unknown): Result sets differ (category: wrong-result)
- `movie` #775 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1671 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1671 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1672 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1672 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1675 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1675 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1684 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1684 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1691 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1691 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1727 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1727 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1739 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1739 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1753 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1753 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1782 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1782 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8148 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8148 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8150 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8150 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8153 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8153 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8160 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8160 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8170 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `sales_in_weather` #8170 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `sales_in_weather` #8183 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8183 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8188 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8188 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8190 (unknown): Gold execution failed: interrupted (category: wrong-result)
- `sales_in_weather` #8190 (unknown): Gold execution failed: interrupted (category: wrong-result)
- `sales_in_weather` #8191 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8191 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8198 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8198 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8203 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8203 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8207 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8207 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8212 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8212 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8213 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8213 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8216 (unknown): Result sets differ (category: repair-exhausted)
- `soccer_2016` #1833 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1833 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1838 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1899 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1899 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1900 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1900 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1905 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1905 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1906 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1906 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1917 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1917 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1946 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1946 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1957 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1957 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2032 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2032 (unknown): Result sets differ (category: wrong-result)

# BIRD-SQL Report: `train_dev.json`

Local execution-accuracy (EX) run against 94 questions from `data/bird/splits/train_dev.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4-flash-0731` | unknown | 188 | 63.3% | 0.96 | 5.78 | 2.7% | $0.000245 |
| `accounts/fireworks/models/deepseek-v4-flash-0731` | overall | 188 | 63.3% | 0.96 | 5.78 | 2.7% | $0.000245 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `sales_in_weather` | 40 | 47.5% |
| `soccer_2016` | 40 | 60.0% |
| `restaurant` | 40 | 65.0% |
| `movie` | 68 | 73.5% |
| **macro (mean over databases)** | 4 DBs | 61.5% |

## Failure analysis
- `movie` #731 (unknown): Result sets differ (category: wrong-result)
- `movie` #731 (unknown): Result sets differ (category: wrong-result)
- `movie` #737 (unknown): Result sets differ (category: wrong-result)
- `movie` #737 (unknown): Result sets differ (category: wrong-result)
- `movie` #740 (unknown): Result sets differ (category: wrong-result)
- `movie` #740 (unknown): Result sets differ (category: wrong-result)
- `movie` #743 (unknown): Result sets differ (category: wrong-result)
- `movie` #743 (unknown): Result sets differ (category: wrong-result)
- `movie` #766 (unknown): Result sets differ (category: wrong-result)
- `movie` #766 (unknown): Result sets differ (category: wrong-result)
- `movie` #768 (unknown): Result sets differ (category: wrong-result)
- `movie` #768 (unknown): Result sets differ (category: wrong-result)
- `movie` #769 (unknown): Result sets differ (category: wrong-result)
- `movie` #769 (unknown): Result sets differ (category: wrong-result)
- `movie` #770 (unknown): Result sets differ (category: wrong-result)
- `movie` #770 (unknown): Result sets differ (category: wrong-result)
- `movie` #775 (unknown): Result sets differ (category: wrong-result)
- `movie` #775 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1671 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1671 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1672 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1672 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1727 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1727 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1739 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1739 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1753 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1753 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1782 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1782 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1785 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1785 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8148 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8148 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8150 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8150 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8170 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `sales_in_weather` #8170 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `sales_in_weather` #8183 (unknown): Result sets differ (category: repair-exhausted)
- `sales_in_weather` #8183 (unknown): Result sets differ (category: repair-exhausted)
- `sales_in_weather` #8187 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8187 (unknown): Result sets differ (category: repair-exhausted)
- `sales_in_weather` #8188 (unknown): Execution failed: no such column: r.date (category: safety-rejected)
- `sales_in_weather` #8188 (unknown): Execution failed: no such column: r.date (category: safety-rejected)
- `sales_in_weather` #8190 (unknown): Gold execution failed: interrupted (category: wrong-result)
- `sales_in_weather` #8190 (unknown): Gold execution failed: interrupted (category: wrong-result)
- `sales_in_weather` #8193 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8198 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8198 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8207 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8207 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8212 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8212 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1798 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1798 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1838 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1838 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1899 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1899 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1900 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1900 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1905 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1905 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1906 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1906 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1957 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1957 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1963 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1963 (unknown): Result sets differ (category: wrong-result)

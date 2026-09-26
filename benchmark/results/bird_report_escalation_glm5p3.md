# BIRD-SQL Report: `train_dev.json`

Local execution-accuracy (EX) run against 92 questions from `data/bird/splits/train_dev.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/glm-5p3` | unknown | 92 | 35.9% | 1.64 | 3.41 | 0.0% | $0.001929 |
| `accounts/fireworks/models/glm-5p3` | overall | 92 | 35.9% | 1.64 | 3.41 | 0.0% | $0.001929 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `movie` | 1 | 0.0% |
| `soccer_2016` | 39 | 30.8% |
| `sales_in_weather` | 26 | 38.5% |
| `restaurant` | 26 | 42.3% |
| **macro (mean over databases)** | 4 DBs | 27.9% |

## Failure analysis
- `movie` #743 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1684 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1687 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1689 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1704 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1706 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1739 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1744 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1746 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1747 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1748 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1769 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1781 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1782 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1783 (unknown): Result sets differ (category: wrong-result)
- `restaurant` #1784 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8144 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8147 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8151 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8153 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8154 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8156 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8170 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8175 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8188 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8191 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8198 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8205 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8208 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8213 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8214 (unknown): Result sets differ (category: wrong-result)
- `sales_in_weather` #8215 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1787 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1794 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1804 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1854 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1891 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1892 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1897 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1899 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1901 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1907 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1909 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1918 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1923 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1925 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1934 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1938 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1946 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1947 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1949 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1982 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1983 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1987 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #1997 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2022 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2023 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2033 (unknown): Result sets differ (category: wrong-result)
- `soccer_2016` #2044 (unknown): Result sets differ (category: wrong-result)

# BIRD-SQL Report: `dev_20251106.json`

Local execution-accuracy (EX) run against 99 questions from `data/bird/dev_cleaned/dev_20251106.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4p1-flash` | simple | 53 | 71.7% | 1.45 | 3.50 | 1.9% | $0.000259 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | moderate | 22 | 63.6% | 1.74 | 3.84 | 0.0% | $0.000438 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | challenging | 24 | 29.2% | 2.46 | 5.39 | 0.0% | $0.000485 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | overall | 99 | 59.6% | 1.58 | 3.85 | 1.0% | $0.000354 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `financial` | 9 | 11.1% |
| `california_schools` | 9 | 33.3% |
| `thrombosis_prediction` | 9 | 33.3% |
| `toxicology` | 9 | 33.3% |
| `card_games` | 9 | 55.6% |
| `codebase_community` | 9 | 66.7% |
| `formula_1` | 9 | 66.7% |
| `european_football_2` | 9 | 77.8% |
| `debit_card_specializing` | 9 | 88.9% |
| `superhero` | 9 | 88.9% |
| `student_club` | 9 | 100.0% |
| **macro (mean over databases)** | 11 DBs | 59.6% |

## Failure analysis
- `california_schools` #8 (challenging): Result sets differ (category: wrong-result)
- `california_schools` #15 (simple): Result sets differ (category: wrong-result)
- `california_schools` #17 (simple): Result sets differ (category: wrong-result)
- `california_schools` #32 (challenging): Result sets differ (category: wrong-result)
- `california_schools` #60 (challenging): Result sets differ (category: wrong-result)
- `california_schools` #63 (simple): Result sets differ (category: wrong-result)
- `card_games` #342 (simple): Result sets differ (category: wrong-result)
- `card_games` #437 (simple): Result sets differ (category: wrong-result)
- `card_games` #448 (simple): Result sets differ (category: wrong-result)
- `card_games` #515 (moderate): Result sets differ (category: wrong-result)
- `codebase_community` #587 (moderate): Result sets differ (category: wrong-result)
- `codebase_community` #590 (simple): Result sets differ (category: wrong-result)
- `codebase_community` #672 (moderate): Result sets differ (category: wrong-result)
- `debit_card_specializing` #1482 (challenging): Result sets differ (category: wrong-result)
- `european_football_2` #1064 (simple): Result sets differ (category: wrong-result)
- `european_football_2` #1115 (challenging): Result sets differ (category: wrong-result)
- `financial` #92 (challenging): Result sets differ (category: wrong-result)
- `financial` #115 (challenging): Result sets differ (category: wrong-result)
- `financial` #137 (challenging): Result sets differ (category: wrong-result)
- `financial` #138 (challenging): No generated SQL (category: structured-output-failed)
- `financial` #144 (challenging): Result sets differ (category: wrong-result)
- `financial` #151 (challenging): Result sets differ (category: wrong-result)
- `financial` #166 (challenging): Result sets differ (category: wrong-result)
- `financial` #189 (moderate): Result sets differ (category: wrong-result)
- `formula_1` #894 (moderate): Result sets differ (category: wrong-result)
- `formula_1` #973 (moderate): Result sets differ (category: wrong-result)
- `formula_1` #975 (simple): Result sets differ (category: wrong-result)
- `superhero` #791 (simple): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1190 (challenging): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1243 (challenging): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1249 (simple): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1261 (simple): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1279 (moderate): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1282 (simple): Result sets differ (category: wrong-result)
- `toxicology` #195 (challenging): No generated SQL (category: structured-output-failed)
- `toxicology` #200 (challenging): No generated SQL (category: structured-output-failed)
- `toxicology` #201 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #221 (simple): Result sets differ (category: wrong-result)
- `toxicology` #263 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #309 (simple): Result sets differ (category: wrong-result)

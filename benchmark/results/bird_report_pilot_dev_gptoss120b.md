# BIRD-SQL Report: `dev_untouched.json`

Local execution-accuracy (EX) run against 55 questions from `data/bird/splits/dev_untouched.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/gpt-oss-120b` | simple | 42 | 52.4% | 1.03 | 3.50 | 4.8% | $0.000318 |
| `accounts/fireworks/models/gpt-oss-120b` | moderate | 13 | 30.8% | 1.29 | 3.35 | 0.0% | $0.000417 |
| `accounts/fireworks/models/gpt-oss-120b` | overall | 55 | 47.3% | 1.14 | 3.50 | 3.6% | $0.000341 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `california_schools` | 5 | 0.0% |
| `european_football_2` | 5 | 0.0% |
| `formula_1` | 5 | 20.0% |
| `student_club` | 5 | 40.0% |
| `thrombosis_prediction` | 5 | 40.0% |
| `toxicology` | 5 | 40.0% |
| `card_games` | 5 | 60.0% |
| `codebase_community` | 5 | 60.0% |
| `financial` | 5 | 80.0% |
| `superhero` | 5 | 80.0% |
| `debit_card_specializing` | 5 | 100.0% |
| **macro (mean over databases)** | 11 DBs | 47.3% |

## Failure analysis
- `california_schools` #9 (simple): Result sets differ (category: wrong-result)
- `california_schools` #58 (simple): Result sets match (category: wrong-result)
- `california_schools` #71 (simple): Result sets differ (category: wrong-result)
- `california_schools` #75 (simple): No generated SQL (category: wrong-result)
- `california_schools` #80 (simple): Result sets differ (category: wrong-result)
- `card_games` #482 (simple): Result sets differ (category: wrong-result)
- `card_games` #511 (moderate): Result sets differ (category: wrong-result)
- `codebase_community` #616 (simple): Result sets differ (category: wrong-result)
- `codebase_community` #686 (simple): Result sets differ (category: wrong-result)
- `european_football_2` #1023 (moderate): Result sets differ (category: wrong-result)
- `european_football_2` #1064 (simple): Result sets differ (category: wrong-result)
- `european_football_2` #1108 (moderate): Result sets differ (category: wrong-result)
- `european_football_2` #1120 (moderate): No generated SQL (category: structured-output-failed)
- `european_football_2` #1126 (simple): No generated SQL (category: wrong-result)
- `financial` #171 (moderate): Result sets differ (category: wrong-result)
- `formula_1` #893 (simple): Result sets differ (category: wrong-result)
- `formula_1` #927 (simple): Result sets differ (category: wrong-result)
- `formula_1` #938 (moderate): Result sets differ (category: wrong-result)
- `formula_1` #993 (simple): Result sets differ (category: wrong-result)
- `student_club` #1315 (simple): Execution failed: near "s": syntax error (category: safety-rejected)
- `student_club` #1407 (simple): Result sets differ (category: wrong-result)
- `student_club` #1454 (moderate): Result sets differ (category: wrong-result)
- `superhero` #720 (simple): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1197 (simple): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1199 (simple): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1284 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #252 (simple): Result sets differ (category: wrong-result)
- `toxicology` #317 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #335 (simple): Result sets differ (category: wrong-result)

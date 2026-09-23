# BIRD-SQL Mini-Dev Report

Local execution-accuracy (EX) run against 60 Mini-Dev questions (public dev-labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4-flash-0731` | simple | 16 | 81.2% | 1.56 | 3.22 | 6.2% | $0.000444 |
| `accounts/fireworks/models/deepseek-v4-flash-0731` | moderate | 31 | 41.9% | 1.18 | 3.45 | 0.0% | $0.000499 |
| `accounts/fireworks/models/deepseek-v4-flash-0731` | challenging | 13 | 30.8% | 1.20 | 3.18 | 0.0% | $0.000438 |
| `accounts/fireworks/models/deepseek-v4-flash-0731` | overall | 60 | 50.0% | 1.22 | 3.25 | 1.7% | $0.000471 |

## Failure analysis
- `california_schools` #23 (moderate): Result sets differ (category: wrong-result)
- `california_schools` #40 (moderate): Result sets differ (category: wrong-result)
- `card_games` #465 (moderate): Result sets differ (category: wrong-result)
- `card_games` #474 (moderate): Result sets differ (category: wrong-result)
- `codebase_community` #563 (moderate): Result sets differ (category: wrong-result)
- `codebase_community` #565 (moderate): Result sets differ (category: wrong-result)
- `codebase_community` #586 (challenging): Result sets differ (category: wrong-result)
- `codebase_community` #694 (moderate): Result sets differ (category: wrong-result)
- `debit_card_specializing` #1500 (simple): Result sets differ (category: wrong-result)
- `debit_card_specializing` #1505 (simple): Execution failed: interrupted (category: repair-exhausted)
- `debit_card_specializing` #1531 (moderate): Result sets differ (category: wrong-result)
- `european_football_2` #1030 (moderate): Result sets differ (category: wrong-result)
- `european_football_2` #1141 (moderate): Result sets differ (category: wrong-result)
- `financial` #94 (challenging): Result sets differ (category: wrong-result)
- `financial` #137 (moderate): Result sets differ (category: wrong-result)
- `financial` #149 (challenging): Result sets differ (category: wrong-result)
- `financial` #159 (simple): Result sets differ (category: wrong-result)
- `formula_1` #881 (moderate): Result sets differ (category: wrong-result)
- `formula_1` #954 (challenging): Result sets differ (category: wrong-result)
- `formula_1` #955 (challenging): Result sets differ (category: wrong-result)
- `formula_1` #1003 (moderate): Result sets differ (category: wrong-result)
- `student_club` #1381 (moderate): Result sets differ (category: wrong-result)
- `student_club` #1427 (moderate): Result sets differ (category: wrong-result)
- `superhero` #751 (moderate): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1187 (moderate): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1189 (challenging): Result sets differ (category: wrong-result)
- `thrombosis_prediction` #1232 (challenging): Execution failed: no such column: l.T (category: safety-rejected)
- `toxicology` #201 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #220 (challenging): No generated SQL (category: wrong-result)
- `toxicology` #230 (challenging): Result sets differ (category: wrong-result)

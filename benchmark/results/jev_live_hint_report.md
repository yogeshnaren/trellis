# BIRD-SQL Report: `jev_live_pilot_questions.json`

Local execution-accuracy (EX) run against 100 questions from `benchmark/results/jev_live_pilot_questions.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4p1-flash` | unknown | 100 | 56.0% | 1.53 | 2.59 | 1.0% | $0.000151 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | overall | 100 | 56.0% | 1.53 | 2.59 | 1.0% | $0.000151 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `professional_basketball` | 25 | 32.0% |
| `movielens` | 25 | 48.0% |
| `regional_sales` | 25 | 60.0% |
| `ice_hockey_draft` | 25 | 84.0% |
| **macro (mean over databases)** | 4 DBs | 56.0% |

## Failure analysis
- `ice_hockey_draft` #6948 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6949 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6985 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6997 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2248 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2257 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2272 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2291 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2294 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2302 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2306 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2309 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2310 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2312 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2325 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `movielens` #2332 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2336 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2796 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2800 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2802 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2803 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2806 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2835 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2838 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2851 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2860 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2866 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2869 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2887 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2908 (unknown): Result sets match (category: wrong-result)
- `professional_basketball` #2915 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2932 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2935 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2947 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2579 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2582 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2600 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2628 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2671 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2687 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2697 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2701 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2704 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2725 (unknown): Result sets differ (category: wrong-result)

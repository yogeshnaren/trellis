# BIRD-SQL Report: `dev_20251106.json`

Local execution-accuracy (EX) run against 148 questions from `data/bird/dev_cleaned/dev_20251106.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4p1-flash` | simple | 68 | 69.1% | 1.47 | 2.77 | 0.0% | $0.000135 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | moderate | 38 | 68.4% | 1.65 | 2.69 | 0.0% | $0.000162 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | challenging | 42 | 40.5% | 2.02 | 4.99 | 4.8% | $0.000276 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | overall | 148 | 60.8% | 1.66 | 3.37 | 1.4% | $0.000182 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `toxicology` | 145 | 60.0% |
| `thrombosis_prediction` | 3 | 100.0% |
| **macro (mean over databases)** | 2 DBs | 80.0% |

## Failure analysis
- `toxicology` #195 (challenging): No generated SQL (category: structured-output-failed)
- `toxicology` #196 (challenging): No generated SQL (category: structured-output-failed)
- `toxicology` #197 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #198 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #199 (simple): Result sets differ (category: wrong-result)
- `toxicology` #200 (challenging): No generated SQL (category: structured-output-failed)
- `toxicology` #201 (moderate): Result sets match (category: wrong-result)
- `toxicology` #203 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #204 (challenging): No generated SQL (category: structured-output-failed)
- `toxicology` #205 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #207 (challenging): Result sets differ (category: repair-exhausted)
- `toxicology` #208 (challenging): No generated SQL (category: structured-output-failed)
- `toxicology` #209 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #211 (simple): Result sets differ (category: wrong-result)
- `toxicology` #215 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #217 (simple): Result sets differ (category: wrong-result)
- `toxicology` #218 (challenging): No generated SQL (category: structured-output-failed)
- `toxicology` #219 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #220 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #221 (simple): Result sets differ (category: wrong-result)
- `toxicology` #223 (simple): Result sets differ (category: wrong-result)
- `toxicology` #224 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #225 (simple): Result sets differ (category: wrong-result)
- `toxicology` #229 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #231 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #234 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #237 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #239 (simple): Result sets differ (category: wrong-result)
- `toxicology` #247 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #248 (simple): Result sets differ (category: wrong-result)
- `toxicology` #251 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #252 (simple): Result sets differ (category: wrong-result)
- `toxicology` #254 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #258 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #259 (simple): Result sets differ (category: wrong-result)
- `toxicology` #263 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #267 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #269 (simple): Result sets differ (category: wrong-result)
- `toxicology` #270 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #271 (simple): Result sets differ (category: wrong-result)
- `toxicology` #281 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #286 (simple): Result sets differ (category: wrong-result)
- `toxicology` #289 (simple): Result sets differ (category: wrong-result)
- `toxicology` #290 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #296 (simple): Result sets differ (category: wrong-result)
- `toxicology` #298 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #300 (simple): Result sets differ (category: wrong-result)
- `toxicology` #305 (simple): Result sets differ (category: wrong-result)
- `toxicology` #306 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #308 (simple): Result sets differ (category: wrong-result)
- `toxicology` #317 (moderate): Result sets differ (category: wrong-result)
- `toxicology` #319 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #326 (simple): Result sets differ (category: wrong-result)
- `toxicology` #328 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #330 (challenging): Result sets differ (category: wrong-result)
- `toxicology` #332 (simple): Result sets differ (category: wrong-result)
- `toxicology` #335 (simple): Result sets differ (category: wrong-result)
- `toxicology` #338 (moderate): Result sets differ (category: wrong-result)

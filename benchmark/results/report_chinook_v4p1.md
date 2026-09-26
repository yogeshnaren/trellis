# Model Bake-off Report

This compares the schema-grounded agent with a same-model raw-prompt control on DeepSeek-V4-Flash. It is **not** a head-to-head run against a proprietary frontier model; any such comparison elsewhere in this repo is directional context, not a benchmark run here.

Concurrency 1 is authoritative for the interactive P50 < 3s SLO. Concurrency 5 is reported separately as throughput/load evidence.

| Model | Arm | Concurrency | SQL Eq | E2E Acc | P50 (s) | P90 (s) | Repair % | Out tok (med) | $/query | $/day @30k |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4p1-flash` | agent | 1 | 53.3% | 53.3% | 1.59 | 2.65 | 0.0% | 78 | $0.000292 | $8.76 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | baseline | 1 | 0.0% | 0.0% | 2.72 | 3.75 | 0.0% | 188 | $0.000246 | $7.37 |

## Cache-reuse diagnostic
- `('accounts/fireworks/models/deepseek-v4p1-flash', 'agent', 'q_002')`: 2651ms, 1548ms, 743ms
- `('accounts/fireworks/models/deepseek-v4p1-flash', 'agent', 'q_003')`: 2021ms, 998ms, 1253ms
- `('accounts/fireworks/models/deepseek-v4p1-flash', 'agent', 'q_005')`: 2244ms, 1284ms, 2689ms
- `('accounts/fireworks/models/deepseek-v4p1-flash', 'agent', 'q_008')`: 2270ms, 949ms, 1516ms
- `('accounts/fireworks/models/deepseek-v4p1-flash', 'baseline', 'q_003')`: 1631ms, 700ms, 1925ms

## Failure analysis
- q_001 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed) (x3)
- q_002 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: Execution failed: no such table: albums (category: safety-rejected) (x2)
- q_002 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed)
- q_003 / `accounts/fireworks/models/deepseek-v4p1-flash` / agent: Result sets differ (category: wrong-result) (x3)
- q_003 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: Execution failed: no such table: customers (category: safety-rejected) (x2)
- q_003 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed)
- q_004 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed) (x3)
- q_005 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed) (x3)
- q_006 / `accounts/fireworks/models/deepseek-v4p1-flash` / agent: Result sets differ (category: wrong-result) (x3)
- q_006 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed) (x3)
- q_007 / `accounts/fireworks/models/deepseek-v4p1-flash` / agent: Result sets differ (category: wrong-result) (x2)
- q_007 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed) (x3)
- q_008 / `accounts/fireworks/models/deepseek-v4p1-flash` / agent: Result sets differ (category: wrong-result) (x3)
- q_008 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed) (x3)
- q_009 / `accounts/fireworks/models/deepseek-v4p1-flash` / agent: Result sets differ (category: wrong-result) (x3)
- q_009 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed) (x3)
- q_010 / `accounts/fireworks/models/deepseek-v4p1-flash` / baseline: No generated SQL (category: baseline-parse-failed) (x3)

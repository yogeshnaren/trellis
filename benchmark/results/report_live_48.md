# Model Bake-off Report

This compares the schema-grounded agent with a same-model raw-prompt control on DeepSeek-V4-Flash. It is **not** a head-to-head run against GPT-5.4; the customer's reported GPT-5.4 behavior is context only.

Concurrency 1 is authoritative for the interactive P50 < 3s SLO. Concurrency 5 is reported separately as throughput/load evidence.

| Model | Arm | Concurrency | SQL Eq | E2E Acc | P50 (s) | P90 (s) | Repair % | Out tok (med) | $/query | $/day @30k |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4-flash` | agent | 1 | 100.0% | 100.0% | 1.92 | 3.97 | 0.0% | 98 | $0.000080 | $2.40 |

## Cache-reuse diagnostic
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_001')`: 1012ms, 1924ms, 954ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_007')`: 3578ms, 2194ms, 1424ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_008')`: 1210ms, 1931ms, 2819ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_009')`: 6057ms, 1820ms, 4931ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_011')`: 2216ms, 3481ms, 1660ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_015')`: 1925ms, 3998ms, 1217ms

## Failure analysis
No SQL-equivalence failures in the recorded run.

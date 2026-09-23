# Model Bake-off Report

This compares the schema-grounded agent with a same-model raw-prompt control on DeepSeek-V4-Flash. It is **not** a head-to-head run against GPT-5.4; the customer's reported GPT-5.4 behavior is context only.

Concurrency 1 is authoritative for the interactive P50 < 3s SLO. Concurrency 5 is reported separately as throughput/load evidence.

| Model | Arm | Concurrency | SQL Eq | E2E Acc | P50 (s) | P90 (s) | Repair % | Out tok (med) | $/query | $/day @30k |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4-flash` | agent | 1 | 81.2% | 81.2% | 2.32 | 4.27 | 0.0% | 88 | $0.000076 | $2.28 |

## Cache-reuse diagnostic
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_004')`: 4391ms, 3327ms, 1750ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_006')`: 1638ms, 1360ms, 4839ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_009')`: 2322ms, 2727ms, 6853ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_010')`: 4273ms, 2609ms, 7177ms
- `('accounts/fireworks/models/deepseek-v4-flash', 'agent', 'live_011')`: 7925ms, 1715ms, 2237ms

## Failure analysis
- live_011 / `accounts/fireworks/models/deepseek-v4-flash` / agent: Result sets differ (category: wrong-result) (x3)
- live_014 / `accounts/fireworks/models/deepseek-v4-flash` / agent: Result sets differ (category: wrong-result) (x3)
- live_016 / `accounts/fireworks/models/deepseek-v4-flash` / agent: Result sets differ (category: wrong-result) (x3)

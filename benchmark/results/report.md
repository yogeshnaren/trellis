# Model Bake-off Report

This compares the schema-grounded agent with a same-model raw-prompt control on DeepSeek-V4-Flash. It is **not** a head-to-head run against a proprietary frontier model; any such comparison elsewhere in this repo is directional context, not a benchmark run here.

Concurrency 1 is authoritative for the interactive P50 < 3s SLO. Concurrency 5 is reported separately as throughput/load evidence.

| Model | Arm | Concurrency | SQL Eq | E2E Acc | P50 (s) | P90 (s) | Repair % | Out tok (med) | $/query | $/day @30k |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4-flash-0731` | agent | 1 | 60.0% | 60.0% | 0.84 | 0.96 | 0.0% | 76 | $0.000502 | $15.05 |

## Cache-reuse diagnostic
No repeat showed a >2× latency spread attributable to possible cache reuse.

## Failure analysis
- q_003 / `accounts/fireworks/models/deepseek-v4-flash-0731` / agent: Result sets differ (category: wrong-result)
- q_006 / `accounts/fireworks/models/deepseek-v4-flash-0731` / agent: Result sets differ (category: wrong-result)
- q_008 / `accounts/fireworks/models/deepseek-v4-flash-0731` / agent: Result sets differ (category: wrong-result)
- q_009 / `accounts/fireworks/models/deepseek-v4-flash-0731` / agent: Result sets differ (category: wrong-result)

## Full train_dev runs

| Configuration | Official EX | P50 | P90 | $/query measured | $/query no cache | $ per 1k (no cache) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Baseline, product prompt (`deepseek-v4-flash-0731`) | 60.1% | n/v | n/v | $0.000293 | $0.000511 | $0.51 | starting point |
| + benchmark prompt profile | 67.1% | 1.22s | 8.46s | $0.000278 | $0.000467 | $0.47 | adopted |
| + quoting + pipeline repairs (the frozen config) | 68.7% | 1.05s | 8.46s | $0.000398 | $0.000497 | $0.50 | adopted |
| **same config on `deepseek-v4p1-flash` (default)** | 69.4% | 1.50s | 3.03s | $0.000141 | $0.000696 | $0.70 | **default**: ties here, +5.9 on Mini-Dev |
| `gpt-oss-120b`, low effort, same config | 67.3% | 0.97s | 1.93s | $0.000166 | $0.000398 | $0.40 | cheaper and faster; misses the non-inferiority margin |

## Pilots

| Variant (100-question pilot x 2) | Official EX | vs control (95% CI) | P50 | P90 | $/query uncached |
|---|---:|---|---:|---:|---:|
| Current configuration (control) | 68.5% | n/a | 1.16s | n/a | $0.000419 |
| deepseek-v4p1-flash | 72.0% | +3.5 [-1.5, +8.5] | 1.56s | 13.30s | $0.000590 |
| deepseek-v4-pro-0813 | 68.0% | -0.5 [-4.0, +3.0] | 3.78s | 14.28s | $0.002425 |
| glm-5p3-flash, low effort | 68.5% | +0.0 [-4.5, +4.5] | 1.93s | 9.18s | $0.000248 |
| glm-5p3-flash, default | 55.0% | -13.5 [-21.0, -6.5] | 4.27s | 13.88s | $0.000358 |
| + few-shot (BM25, k=3) | 68.5% | +0.0 [-4.0, +4.0] | 2.01s | 14.31s | $0.000503 |

## Provenance

| Run (UTC) | Set | Model | Answers | Official EX | Commit | Tree | Config | Data |
|---|---|---|---:|---:|---|---|---|---|
| 2026-09-24 00:53 | train_dev baseline (product prompt) | `deepseek-v4-flash-0731` | 1,002 | 60.1% | `5a69af6` | clean | `76ed4867` | `e5503cce` |
| 2026-09-24 17:07 | train_dev + benchmark profile | `deepseek-v4-flash-0731` | 1,002 | 67.1% | `6d18d06` | dirty `18243ce1` | `e7fc10c4` | `e5503cce` |
| 2026-09-24 17:57 | train_dev + quoting and repairs | `deepseek-v4-flash-0731` | 1,002 | 68.7% | `1694580` | dirty `47a379b8` | `a5a42bc0` | `e5503cce` |
| 2026-09-24 23:23 | Mini-Dev, gate 1 | `deepseek-v4-flash-0731` | 1,500 | 59.3% | `285272c` | clean | `92e1c3cb` | `4ba5fa8d` |
| 2026-09-25 01:52 | dev_untouched | `deepseek-v4-flash-0731` | 1,036 | 63.6% | `a9ab833` | dirty `9e2f8c8c` | `e0ecfba5` | `b0aed7f6` |
| 2026-09-26 20:38 | train_dev, v4p1-flash | `deepseek-v4p1-flash` | 1,002 | 69.1% | `a9ab833` | dirty `48db653b` | `baff9689` | `e5503cce` |
| 2026-09-26 21:15 | Mini-Dev, gate 2 | `deepseek-v4p1-flash` | 1,500 | 65.3% | `eafe2ba` | clean | `baff9689` | `4ba5fa8d` |
| 2026-09-26 21:21 | dev_untouched | `deepseek-v4p1-flash` | 1,036 | 67.6% | `eafe2ba` | clean | `baff9689` | `b0aed7f6` |
| 2026-09-26 21:27 | train_dev, v4p1-flash, clean reproduction | `deepseek-v4p1-flash` | 1,002 | 69.4% | `eafe2ba` | clean | `baff9689` | `e5503cce` |

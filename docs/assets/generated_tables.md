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

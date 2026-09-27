# Candidate bank: 501 questions, candidates direct, decompose, plan, glm

Stored runs: direct 20260926T212754Z (first repeat), decompose 20260927T045254Z, plan 20260927T045227Z, glm 20260927T044613Z. This is one diagnostic pass; oracle pass@4 uses gold only to measure headroom, never to choose SQL.

| Candidate | EX | Macro |
|---|---:|---:|
| `direct` | 69.5% | 71.1% |
| `decompose` | 67.1% | 68.2% |
| `plan` | 66.9% | 68.2% |
| `glm` | 66.9% | 67.3% |

| Selector over the bank | EX | Macro |
|---|---:|---:|
| oracle pass@4 (perfect selector) | 73.5% | 75.0% |
| majority vote by result | 68.9% | 70.1% |

| k | mean oracle pass@k over subsets |
|---:|---:|
| 1 | 67.6% |
| 2 | 71.0% |
| 3 | 72.6% |
| 4 | 73.5% |

- All candidates return the same result on 399 questions (79.6%); **93 of those are wrong** (18.6% of all): no selector can fix them.
- No candidate is correct on 133 questions (26.5%).
- Disagreement (≥ 2 distinct results) on 102 questions: the only place a selector acts.


## Headroom by database

| Database | N | Direct correct | At least one of four correct | Perfect-selector gain |
|---|---:|---:|---:|---:|
| movie | 46 | 39 | 40 | +1 |
| restaurant | 117 | 82 | 88 | +6 |
| sales_in_weather | 80 | 48 | 52 | +4 |
| soccer_2016 | 258 | 179 | 188 | +9 |
| **Total** | **501** | **348** | **368** | **+20** |

Even perfect selection from this bank reaches 73.5% on train_dev; exceeding
75% there requires at least 376 correct. A separate repeat is needed before
using this diagnostic to authorize paid fine-tuning or a selector.

# Candidate bank: 501 questions, candidates direct, decompose, plan, glm

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


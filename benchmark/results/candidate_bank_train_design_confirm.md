# Candidate bank on 350 questions (train_design_confirm.json)

## Official keys (350 questions scored)

| Route | EX | Adds over incumbent | $ / answer (uncached) |
|---|---:|---:|---:|
| `direct` | 64.3% (225) | — | 0.00132 |
| `gptoss` | 62.9% (220) | 10 | 0.00075 |
| `qwen` | 66.6% (233) | 18 | 0.00069 |
| `arctic` | 62.6% (219) | 24 | 0.00000 |

| Fixed route set | Oracle coverage | Majority vote | $ / question |
|---|---:|---:|---:|
| direct | 64.3% | 64.3% | 0.00132 |
| direct + gptoss | 67.1% | 64.3% | 0.00207 |
| direct + qwen | 69.4% | 64.3% | 0.00201 |
| direct + arctic | 71.1% | 64.3% | 0.00132 |
| direct + gptoss + qwen | 70.0% | 66.6% | 0.00276 |
| direct + gptoss + arctic | 72.0% | 65.1% | 0.00207 |
| direct + qwen + arctic | 72.9% | 67.4% | 0.00201 |
| direct + gptoss + qwen + arctic | 72.9% | 66.0% | 0.00276 |

## Corrected keys (339 questions scored)

| Route | EX | Adds over incumbent | $ / answer (uncached) |
|---|---:|---:|---:|
| `direct` | 79.9% (271) | — | 0.00125 |
| `gptoss` | 77.3% (262) | 11 | 0.00073 |
| `qwen` | 78.2% (265) | 16 | 0.00066 |
| `arctic` | 71.7% (243) | 17 | 0.00000 |

| Fixed route set | Oracle coverage | Majority vote | $ / question |
|---|---:|---:|---:|
| direct | 79.9% | 79.9% | 0.00125 |
| direct + gptoss | 83.2% | 79.9% | 0.00198 |
| direct + qwen | 84.7% | 79.9% | 0.00192 |
| direct + arctic | 85.0% | 80.2% | 0.00125 |
| direct + gptoss + qwen | 85.5% | 81.7% | 0.00265 |
| direct + gptoss + arctic | 86.4% | 80.2% | 0.00198 |
| direct + qwen + arctic | 87.0% | 80.5% | 0.00192 |
| direct + gptoss + qwen + arctic | 87.3% | 81.1% | 0.00265 |

## Pre-registered selection rules (Experiment C)

| Rule | Official EX | Corrected EX | Corrected Δ, 95% CI | Switched away from incumbent | Switches: fix / break (corrected) |
|---|---:|---:|---:|---:|---:|
| S0 incumbent | 64.3% | 79.9% | — | 0 | 0 / 0 |
| S1 family majority | 66.9% | 82.0% | [+0.3, +4.1] | 21 | 10 / 3 |
| S2 fallback on empty/error | 65.4% | 81.4% | [+0.3, +2.7] | 11 | 5 / 0 |
| S3 detector switch | 64.3% | 79.9% | [+0.0, +0.0] | 2 | 0 / 0 |
| S4 other families agree | 65.7% | 80.8% | [-0.3, +2.1] | 7 | 4 / 1 |

## Diversity

Distinct non-empty result signatures per question: 1: 235, 2: 95, 3: 16, 4: 4



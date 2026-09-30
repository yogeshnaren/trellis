# Candidate bank on 353 questions (train_dev2_bank.json)

## Official keys (353 questions scored)

| Route | EX | Adds over incumbent | $ / answer (uncached) |
|---|---:|---:|---:|
| `direct` | 58.9% (208) | — | 0.00065 |
| `gptoss` | 55.8% (197) | 10 | 0.00042 |
| `qwen` | 59.2% (209) | 26 | 0.00033 |
| `arctic` | 59.2% (209) | 34 | 0.00000 |

| Fixed route set | Oracle coverage | Majority vote | $ / question |
|---|---:|---:|---:|
| direct | 58.9% | 58.9% | 0.00065 |
| direct + gptoss | 61.8% | 58.9% | 0.00107 |
| direct + qwen | 66.3% | 58.9% | 0.00098 |
| direct + arctic | 68.6% | 59.2% | 0.00065 |
| direct + gptoss + qwen | 67.7% | 58.6% | 0.00141 |
| direct + gptoss + arctic | 69.7% | 59.5% | 0.00107 |
| direct + qwen + arctic | 71.1% | 61.5% | 0.00098 |
| direct + gptoss + qwen + arctic | 72.0% | 60.3% | 0.00141 |

## Corrected keys (350 questions scored)

| Route | EX | Adds over incumbent | $ / answer (uncached) |
|---|---:|---:|---:|
| `direct` | 72.0% (252) | — | 0.00065 |
| `gptoss` | 69.4% (243) | 18 | 0.00043 |
| `qwen` | 66.0% (231) | 21 | 0.00033 |
| `arctic` | 65.4% (229) | 33 | 0.00000 |

| Fixed route set | Oracle coverage | Majority vote | $ / question |
|---|---:|---:|---:|
| direct | 72.0% | 72.0% | 0.00065 |
| direct + gptoss | 77.1% | 72.0% | 0.00108 |
| direct + qwen | 78.0% | 72.0% | 0.00098 |
| direct + arctic | 81.4% | 72.0% | 0.00065 |
| direct + gptoss + qwen | 81.4% | 71.4% | 0.00141 |
| direct + gptoss + arctic | 84.6% | 72.6% | 0.00108 |
| direct + qwen + arctic | 83.4% | 69.7% | 0.00098 |
| direct + gptoss + qwen + arctic | 86.0% | 73.1% | 0.00141 |

## Pre-registered selection rules (Experiment C)

| Rule | Official EX | Corrected EX | Corrected Δ, 95% CI | Switched away from incumbent | Switches: fix / break (corrected) |
|---|---:|---:|---:|---:|---:|
| S0 incumbent | 58.9% | 72.0% | — | 0 | 0 / 0 |
| S1 family majority | 61.2% | 74.3% | [+0.3, +4.3] | 23 | 11 / 3 |
| S2 fallback on empty/error | 59.2% | 72.6% | [+0.0, +1.4] | 4 | 2 / 0 |
| S3 detector switch | 59.5% | 72.6% | [+0.0, +1.4] | 6 | 2 / 0 |
| S4 other families agree | 59.8% | 72.9% | [-0.3, +2.3] | 6 | 4 / 1 |

## Diversity

Distinct non-empty result signatures per question: 1: 192, 2: 110, 3: 43, 4: 8



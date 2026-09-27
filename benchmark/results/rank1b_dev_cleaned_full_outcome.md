# Rank 1b on the full cleaned BIRD dev set

**Result (2026-09-27): 1,020/1,534 = 66.49% official EX** with bounded database facts, versus 1,012/1,534 = 65.97% in the earlier no-facts baseline. The paired difference is **+8 rows, +0.52 percentage points**. This is above 66%, but does not establish a reliable improvement: 33 rows flipped wrong-to-right and 25 right-to-wrong (exact McNemar p = 0.358). A question bootstrap stratified within the 11 databases gives a 95% row-weighted difference interval of **−0.46 to +1.50 points** and a database-macro difference interval of **−0.81 to +1.40 points**. Both include zero. Each configuration has only one answer per question, so this is descriptive gate evidence, not the two-repeat development acceptance test.

| Metric | No facts | Bounded facts | Difference |
|---|---:|---:|---:|
| Row-weighted EX | 65.97% (1,012/1,534) | 66.49% (1,020/1,534) | +0.52 pts |
| Database-macro EX | 64.08% | 64.38% | +0.30 pts |
| Measured model calls | $0.298395 | $0.347516 | +$0.049121 (16.5%) |
| Measured cost per answer | $0.000195 | $0.000227 | +16.5% |

| Difficulty | N | No facts | Bounded facts | Difference |
|---|---:|---:|---:|---:|
| Simple | 860 | 75.35% | 76.05% | +0.70 pts |
| Moderate | 443 | 65.01% | 65.01% | 0.00 pts |
| Challenging | 231 | 32.90% | 33.77% | +0.87 pts |

| Database | N | No facts | Bounded facts | Difference |
|---|---:|---:|---:|---:|
| california_schools | 89 | 32.58% | 29.21% | −3.37 pts |
| card_games | 191 | 65.97% | 66.49% | +0.52 pts |
| codebase_community | 186 | 76.88% | 79.03% | +2.15 pts |
| debit_card_specializing | 64 | 71.88% | 70.31% | −1.56 pts |
| european_football_2 | 129 | 75.97% | 75.97% | 0.00 pts |
| financial | 106 | 24.53% | 27.36% | +2.83 pts |
| formula_1 | 174 | 61.49% | 62.64% | +1.15 pts |
| student_club | 158 | 87.97% | 86.71% | −1.27 pts |
| superhero | 129 | 87.60% | 89.15% | +1.55 pts |
| thrombosis_prediction | 163 | 60.74% | 61.35% | +0.61 pts |
| toxicology | 145 | 59.31% | 60.00% | +0.69 pts |

## Coverage and provenance

The first bounded-facts run stopped at the approved $7 shared-ledger limit. It had 1,386 usable answers, one budget-error record, and 147 unanswered rows. After approval raised the total cap to $7.15, only the exact 148 affected original rows were run. The two result files were merged after validating the question-set fingerprint, configuration fingerprint, code state, overlapping database and effective-prompt fingerprints, row identities, and unique `(model, row_index, repeat)` keys. The merged artifact has exactly one non-budget answer for each of the 1,534 expected rows. Its metadata records the SHA-256 of both source files and the continuation manifest. The no-facts baseline also contains exactly one non-budget answer for all 1,534 rows; its metadata `complete` flag is false despite full record coverage, so coverage was checked from the records directly.

Both runs use `deepseek-v4p1-flash`, temperature 0, 400 max tokens, no reasoning, the benchmark prompt, identifier quoting, and pipeline repairs on the same cleaned Nov 2025 question and database package. Their recorded generation configurations differ only in `profile_facts`. The code-state hashes also differ because the baseline preceded the rank 1b implementation, so the paired result should not be read as a perfectly isolated causal experiment. It is the third of four permitted cleaned-dev looks. No individual cleaned-dev errors were inspected to revise the feature. The first, sampled `train_lockbox` look remains the only unseen-database safety screen; the remaining 799 lockbox questions stay sealed.

The shared project ledger now totals **$7.024033** with no open reservations, below the approved **$7.15** total cap. This public dev score is not a hidden-test result and does not predict a test score.

Artifacts: `bird_raw_rank1b_cleaned_dev_full.jsonl`, `bird_meta_rank1b_cleaned_dev_full.json`, `bird_report_dev_cleaned_rank1b_merged.md`, `rank1b_dev_cleaned_resume_manifest.json`, and their two source raw/meta files.

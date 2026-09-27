# Rank 1b database-facts experiment

Source: `train_dev.json`, four databases, BIRD official execution accuracy. The control is `bird_raw_20260926T212754Z.jsonl` (501 questions, two repeats). All variants used the same model and benchmark profile. Facts were built from the database, with no gold SQL at inference.

| Run | Questions × repeats | EX | Paired row Δ (95% CI) | Macro Δ (95% CI) | Decision |
|---|---:|---:|---:|---:|---|
| Control on the 100-row pilot selection | 100 × 2 | 71.5% | — | — | Reference |
| Initial facts pilot `20260927T054448Z` | 100 × 2 | 72.0% | +0.5 [−3.5, +4.5] pts | +0.5 [−3.5, +4.5] pts | Corrected misleading facts |
| Exact-case, unique-location pilot `20260927T055053Z` | 100 × 2 | 74.5% | +3.0 [+0.5, +6.5] pts | +3.0 [+0.5, +6.5] pts | Qualified for full comparison only |
| Corrected full `20260927T060549Z` | 501 × 2 | 70.2% | +0.80 [−0.30, +2.00] pts | +1.59 [+0.05, +3.51] pts | Missed predeclared rule; owner subsequently adopted for benchmark |

The full control was 69.4% EX on 1,002 outputs. Coverage checks passed for all 501 questions and both repeats in both full runs. The prespecified acceptance rule requires the row-weighted **and** four-database macro gains to each reach +1.5 pts, with both intervals above zero. The row-weighted result does neither. The pilot therefore overestimated the full-set gain. The owner subsequently chose to adopt the bounded facts for the **benchmark** profile as an explicit exception. The product profile is unchanged; `--no-profile-facts` provides a control. This adoption is a preference decision, not a statistically validated transfer claim. A prespecified unseen-database holdout check follows.

The first pilot surfaced a real fact-quality bug: a case-folded FTS match caused `19th st` to be presented beside evidence specifying `19th St`, and a `sunnyvale` fact listed three possible city columns without resolving which table mattered. Fact rendering now requires an exact-case quoted value and a unique location. A focused regression test covers both errors. The feature is on by default for the benchmark profile by owner direction. It remains off for the product profile.

The borderline full-run flips were read against the original question, evidence and gold SQL. Repeat-consistent fixes: movie #748 (money stored as text), restaurant #1711, sales_in_weather #8149 and #8186. Repeat-consistent regressions: restaurant #1680 and #1706. #1706 regressed and #8149 improved with **no profile fact in either prompt**, demonstrating run-to-run variation even at temperature zero; those flips cannot be attributed to this feature. No database fell by 10 pts, but restaurant lost 0.9 pts. This is not enough evidence to add the prompt cost and latency.

The two pilots and full variant added about **$0.220** to the shared ledger, which ended at **$6.495 of the approved $7 total** (including pre-existing provisional charges). No lockbox or Mini-Dev gate was used. The three saved candidate-bank arms were analyzed offline with no new calls for that diagnostic; see `candidate_bank_diagnostic.md`.

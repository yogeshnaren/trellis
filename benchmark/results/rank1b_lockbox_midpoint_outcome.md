# Rank 1b first lockbox look: aggregate only

This is the preregistered midpoint screen in `rank1b_lockbox_midpoint_prereg.md` on **seven train databases never used for prompt tuning**. The exact 175 original rows (25 per database; seed 260926) were frozen before calls. Control `bird_raw_20260927T062743Z.jsonl` and facts `bird_raw_20260927T063407Z.jsonl` each cover every selected row **three times** with the same code commit, database hashes, model and settings; only `profile_facts` differs. The result was opened only after both arms completed. No individual lockbox SQL, gold answers or flips were inspected for this analysis.

| Metric | No facts | Facts | Paired difference |
|---|---:|---:|---:|
| Official EX, 525 outputs | 79.24% (416 correct) | 81.14% (426 correct) | **+1.90 pts** |
| Row-weighted Δ, question bootstrap | — | — | +1.90 pts, 95% CI **[−0.19, +4.19]** |
| Seven-database macro Δ | — | — | +1.90 pts, 95% within-database CI **[−0.19, +4.19]** |
| Exploratory hierarchical bootstrap (database then question) | — | — | 95% CI **[−0.38, +4.95]** |
| Measured spend for this arm | $0.0995 | $0.0818 | $0.1813 combined |

The macro and row-weighted values coincide because the sample has exactly 25 questions from every database. Four databases improved, three were flat to displayed precision; none had a ≥10-point drop. The prespecified **safety screen passed**: both point estimates were positive, neither interval was wholly negative, and no database collapsed. The prespecified **strong transfer criterion did not pass** because both intervals include zero. The owner-adopted benchmark default therefore remains active, but the gain on unseen databases is **not statistically established**. Do not extrapolate the 81.14% sample EX to the 974-row lockbox, cleaned dev or hidden test.

This consumed **one of two** lockbox looks. The other **799 original rows** are sealed in `rank1b_lockbox_final_manifest.json` for a final frozen-configuration gate. No prompt or routing change should be chosen from the midpoint rows. The seven databases are diverse, but public BIRD train material could also have appeared in the base model's pretraining; hidden test is the final transfer check.

Shared ledger after both arms: **$6.6765 of the approved $7 total**, with no open reservations. The comparison details without question-level flips are in `rank1b_lockbox_midpoint_aggregate.md`.

# Preregistration: first database-lockbox look for rank 1b

**Frozen comparison, before opening predictions:** exact-case, unique-location database facts versus no database facts, with the same benchmark profile, model (`deepseek-v4p1-flash`), quoted identifiers, pipeline repairs, 400 max tokens, reasoning off, and 60s LLM timeout. `--profile-value-facts` remains at its default in the candidate; the exploratory value-hint ablation is **not** part of this gate.

Dataset: `data/bird/splits/train_lockbox.json`, 974 questions in seven databases/domains. First look is a stratified **25 questions per database**, seed **260926**, 175 questions total. Exact original row indices and the source fingerprint are frozen in `rank1b_lockbox_midpoint_manifest.json`. Each arm gets **three repeats** on identical rows (525 answers each). Results are compared with official EX, question-mean paired flips, within-database question bootstrap, row-weighted and seven-database macro deltas. No question IDs were selected for their contents or labels. The remaining 799 questions are reserved for the final lockbox gate.

This is a **holdout screen**, not a hidden-test estimate. It uses one of two planned lockbox looks. Do not inspect individual lockbox flips, gold SQL, or generated SQL to adjust the feature. Publish only aggregate and per-database results. The small sample cannot reliably confirm the +0.8-point development effect; a full final gate and the hidden test remain necessary.

Prespecified interpretation:
- Strong transfer support: row and macro Δ both positive, both 95% intervals above zero, and no database drop ≥10 points.
- Safety screen passed but transfer unproven: both point estimates nonnegative, neither interval wholly below zero, and no database drop ≥10 points. Owner adoption can remain active, explicitly labeled as unproven.
- Roll back the benchmark default to opt-in if either point estimate is negative or any database drops ≥10 points. A statistically clear loss reinforces that decision. Do not tune on this lockbox sample.

Budget: shared ledger starts near $6.495 of the owner's $7 total cap. The control uses a stricter $6.75 ledger ceiling, leaving at least $0.25 for the candidate; candidate cap is $7.00. The 1,050 calls are estimated at ~$0.16 using measured prompt caching; uncached upper estimate ~$0.74 would exceed the remaining budget, so the ledger may stop an arm. **Incomplete coverage is no result**. Before launching the candidate, check only control cost and coverage, not its accuracy.

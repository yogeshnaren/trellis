# Database-facts failure analysis (before holdout)

All findings below use the four `train_dev` databases. They are development findings, **not evidence of transfer** to an unseen database. Control: `bird_raw_20260926T212754Z.jsonl`. Candidate: `bird_raw_20260927T060549Z.jsonl`. Each has 501 questions × 2 repeats. BIRD official EX rose 69.4% → 70.2%: +0.80 pts, 95% within-database question-bootstrap interval [−0.30, +2.00]. Macro gain was +1.59 [+0.05, +3.51] across only four databases. The owner chose to adopt the bounded facts for the benchmark path despite the predeclared +1.5-point row-gain rule. A separate lockbox check is required before claiming transfer.

## Where facts helped and where they failed

| Injected fact type | Questions | Control EX | Facts EX | Paired Δ | Changed questions: better / worse |
|---|---:|---:|---:|---:|---:|
| Format only | 39 | 74.4% | 76.9% | +2.6 pts | 1 / 0 |
| Format + join | 26 | 73.1% | 76.9% | +3.8 pts | 1 / 0 |
| Format + value | 25 | 54.0% | 56.0% | +2.0 pts | 1 / 0 |
| Value location only | 194 | 76.5% | 77.1% | +0.5 pts | 5 / 3 |
| No fact | 217 | 63.4% | 63.6% | +0.2 pts | 3 / 2 |

The four groups with facts total 284 questions. Format and join hints are the strongest signal in this run. Value-only hints reach many questions but add little net EX and account for all three regressions among questions with facts. The 217 no-fact questions are the lowest-scoring group; three gains and two losses there are temperature-zero variation, not a causal effect of facts. The current bootstrap resamples questions *within* each database; it does not estimate transfer uncertainty to new databases.

The initial pilot also exposed unsafe value rendering: case-folded FTS results could suggest `19th st` where evidence specified `19th St`, and one literal could be listed under three city columns. The adopted renderer now requires exact-case value matching and one unique location. Tests cover both. More retrieval coverage must preserve this precision.

## Consistent flips audited against question, evidence and gold

- **Likely format benefit:** movie row 18 / #748 stored `NetWorth` as money text; both new repeats converted it numerically and matched gold. sales_in_weather row 470 / #8186 switched the month filter from `weather.date` to `sales_in_weather.date` in both new repeats, matching gold.
- **Value hint with plausible benefit:** restaurant row 87 / #1711 included both the street number and the located street-name literal after seeing its unique `location.street_name` value.
- **Value hint regressions:** restaurant row 56 / #1680 changed the scope of a negative `NOT EXISTS`, turning a previously matching result into a mismatch. Row 61 / #1685 shows the same regional-negation pattern in one repeat. Soccer row 256 / #1880 swapped first and second team roles in one repeat.
- **Variation independent of facts:** restaurant row 82 / #1706 regressed on a question that received no fact; sales_in_weather row 433 / #8149 improved without a fact. Both changes held across repeats, so repeat consistency alone is not proof of causation.

## Remaining errors in the adopted run

A local re-score of the first repeat found **150 wrong of 501**: 84 values differ, 43 row counts differ, 9 extra columns, 8 empty results, 5 missing columns and 1 gold execution error. The 84 + 43 result/value errors are the main remaining work. Eleven first-repeat failures have an *oracle* presentation rewrite (7 `COUNT(DISTINCT)` removals and 4 column drops); that is a ceiling found with gold, never an automatic fix.

| Database | First-repeat failures | Values differ | Row count differs |
|---|---:|---:|---:|
| soccer_2016 | 80 | 45 | 25 |
| restaurant | 36 | 13 | 16 |
| sales_in_weather | 28 | 23 | 0 |
| movie | 6 | 3 | 2 |

Of the 150 failures, 78 received no fact, 46 a value-only fact, and 26 a format or join fact. In soccer, date storage/conversion and role-specific joins recur. In sales_in_weather, the prediction often joins weather by date while BIRD gold sometimes joins only by station, changing aggregates. Restaurant errors frequently change the requested output field, filter casing, or grouping scope. These are better targets for a cheap SQL-constraint check and selective repair than for more generic value snippets.

**Gold-label caution:** Some inspected failures are apparent question/gold disagreements. Soccer row 219 asks for player names but gold returns team name; row 285 asks for a difference of two averages but gold returns one average; row 320 asks for a first match but gold returns all match dates. Restaurant row 54 asks for street numbers but gold returns restaurant IDs. Do not encode those label conventions as product rules or infer hidden-test performance from them. Adjudicate a fixed sample and keep it separate from model failures.

## Next checks, cheapest first

1. **One preregistered lockbox look, aggregate only.** Freeze the current candidate and control before evaluating seven unseen database domains. Do not inspect lockbox SQL flips or tune on its questions. Keep the unused rows for a final gate.
2. **Value-hint ablation on development databases.** The `--no-profile-value-facts` switch retains format and join facts. Compare it against the owner-adopted default on a stratified pilot that includes negation and role-sensitive questions, then a full two-repeat run only if promising. Treat selected target rows as diagnostic, not acceptance evidence.
3. **Offline constraint audit before new API calls.** On a preselected sample of the 127 values/row-count failures, record whether the delivered SQL preserves explicit evidence operators, date columns, join paths, output columns and aggregation. A cheap deterministic check can then be piloted on violations only. Keep apparent gold disagreements in a separate bucket.
4. **Coverage audit for 217 no-fact questions.** Measure retrieval recall and false hints before widening to unquoted literals or descriptions. The first pilot showed why broad value recall without exactness can lower EX.
5. **Recheck generator headroom.** The saved candidate bank was built before this adoption and has oracle pass@4 of 73.5% on `train_dev`; do not claim a selector or Jev can close the >75% gap until a new bank on the frozen configuration shows enough correct candidates.

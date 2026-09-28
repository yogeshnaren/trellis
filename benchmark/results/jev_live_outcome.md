# Jev live advisory pilot — 2026-09-27

**Decision:** neither advisory qualifies for a full comparison or adoption. This was a frozen, one-repeat pilot on 100 `train_dev2` questions (25 per database), not a holdout gate. No Mini-Dev, cleaned-dev, or train-lockbox look was used. The predeclared screen in `jev_live_protocol.md` required at least four net official-EX fixes per 100 and no net loss of three or more questions within a database.

| Arm | Official EX | Paired fixes / regressions | SQL changed vs control | Fireworks cost | Jev cost | Generator P50 |
|---|---:|---:|---:|---:|---:|---:|
| Current v4p1 control | 56/100 | — | — | $0.034772 | — | 1.66 s |
| Jev starting-table advisory | 57/100 | 1 / 0 | 43/100 | $0.026406 | $0.005077 | 1.62 s |
| Jev evidence-role advisory | 56/100 | 0 / 0 | 30/100 | $0.015146 | $0.000544 | 1.53 s |

The hint arm matched the control on all 27 eligible questions (14/27 correct). Every database has 25 questions. Table-arm scores by database were ice_hockey_draft 21/25 unchanged, movielens 13/25 vs 12/25, professional_basketball 8/25 unchanged, regional_sales 15/25 unchanged. The hint arm was unchanged in every database. Paired reports contain 95% question-level bootstrap intervals; the table gain was +1.0 point [0.0, +3.0], and the hint gain was 0.0 [0.0, 0.0]. Those intervals describe this single-run paired sample and do not establish a generalization gain.

The table arm's sole fix was movielens question 2325. The control produced a correlated `EXISTS` query that the local evaluator interrupted; the table arm produced an `IN` query that completed. Both queries appear to implement the same actor count, so this is an execution-behavior improvement, not evidence that Jev chose a more accurate interpretation. The model was run at T=0 but is not perfectly deterministic, making attribution from one flip especially weak.

Jev used `typesafe/jev-1.13-20260917` for all 127 decisions. Its median latency was 180 ms for table choice and 196 ms for hint role; P90 was 277 ms and 297 ms. Jev received only the question, evidence, and verified schema-derived state; it did not receive gold SQL or results. The full schema remained visible to the generator. Fireworks spend for all three arms was $0.076324; Jev spend was $0.005622. The shared ledger's Fireworks committed total after the pilot was $7.442104 of the approved $8 ceiling (including $0.032246 provisional), leaving $0.557896. The OpenRouter ledger total was $0.027703 of its separate $5 cap. Fireworks cost differences between arms reflect prompt-cache behavior and must not be credited to Jev.

**Next:** retain the accepted v4p1 configuration. Use free deterministic grounding and failure analysis first. Reconsider Jev only for a narrow decision that shows a stronger frozen shadow signal and has a causal path to an EX change; then run a new predeclared paired pilot on questions outside this development sample. Do not tune table probability thresholds or hint wording against these 100 results. No full train-dev, Mini-Dev, or lockbox run is justified by these advisory pilots.

Artifacts: `jev_live_pilot_manifest.json`, `jev_live_protocol.md`, `jev_live_*_annotations.json`, three `bird_raw_20260927T095*.jsonl` with metadata, and `jev_live_{table,hint}_comparison.md`.

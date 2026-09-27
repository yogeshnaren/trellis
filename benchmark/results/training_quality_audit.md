# Filtered training-pool quality preflight

- BIRD filtered source: 6,601 rows; excluded evaluation-database rows: 1,486; candidate pool: **5,115** across 54 databases.
- Locally checkable: **4,146** rows / 43 databases. Database unavailable: **969** rows.
- Mechanical SQL checks: `{'database_missing': 969, 'explain_ok': 4146}`. An EXPLAIN success verifies compilation against the local schema, **not** that the SQL answers the question.
- Exact question-text overlap with evaluation sets after database exclusion: 0. Filtered rows with multiple identical original-train matches: 3 (all original indices retained).
- Frozen semantic-review sample: 100 rows, one or more from every local database (43), deterministic within-database hash selection. `row_weight` permits database-stratified row-level estimates after labels are assigned. This coverage-oriented sample must not be treated as having a measured semantic error rate while `review_label` is pending.

The generated candidate pool is gitignored under `data/bird/training_quality/`; the checked manifest and 100-row review sample are in `benchmark/results/`. **Do not train on this pool yet.** Inspect question, evidence, SQL and relevant database contents, then label each sample `sound`, `defect`, or `uncertain`. The predeclared training gate is a weighted defect rate no greater than 15% among reviewed local-database rows; uncertain cases are reported separately. The missing-database tier requires another download before execution checks.

## Single-reviewer semantic screen

I read all 100 frozen question/evidence/SQL triples and recorded **18 clear defects across 14 databases** in `training_quality_review_labels.csv` (8 low, 7 medium and 3 high complexity). The other 82 remain `unresolved`, not certified sound. With each database's planned sampling weight, clear defects are **17.52% of this sample's row-weighted mass even if every unresolved item is treated as sound**. This is a conservative sample point estimate, not a population confidence bound. It crosses the predeclared 15% stop threshold: **re-filter and independently review before SFT**.

Clear failures include a missing episode filter, `SUM(film_id)` instead of counting films, `UNION` in place of AND, counting survey responses instead of questions, returning category IDs for requested subcategory IDs, and `PayFrequency * Rate > 50` instead of the two requested predicates. All passed SQLite `EXPLAIN`; compilation is not semantic verification. This is one-rater triage. A second reviewer and further source checks are required before estimating the final label error rate or admitting training rows.

Source: BIRD's `birdsql/bird23-train-filtered` release (CC BY-SA 4.0; provenance and license in `data/bird/train_filtered/README.md`). The 100-row review packet and reasoned label overlay are pinned by `training_quality_triage.json`.

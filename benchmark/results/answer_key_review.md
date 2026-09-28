# Answer-key review: 252 practice-set disagreements (2026-09-27)

Human review of the cases built by `benchmark/review_packet.py`: questions where a
rejected experiment flipped the official result, where all four rank 4 candidates agreed
but were marked wrong, and the 194 "numbers stored as text" design questions. For each
case the reviewer read the question, hint, gold SQL and result, and our SQL and result,
and recorded one verdict. Verdicts are stored on the private review page; this file holds
only the aggregates. No question text, SQL or result is reproduced here.

- **Reviewers:** the owner judged 166 cases. Two Sonnet 5 agents judged the remaining 86,
  following the owner's recorded choices and notes; their notes are marked
  `[Sonnet review]`, and 8 are marked low confidence. Three agent verdicts were
  spot-checked against the databases and held.
- **Verdicts:** `key_wrong` (the gold answer is wrong; ours is right), `ours_wrong`,
  `both_ok` (both readings are defensible), `ambiguous` (the question does not decide).
  When both answers were wrong, the verdict is `ours_wrong`.
- **Scope:** the cases were *selected* for disagreement, so these shares describe that
  selection, not BIRD as a whole. Official EX remains the only acceptance metric.

## Verdicts

| Reviewer | Cases | Key wrong | Ours wrong | Both OK | Ambiguous |
|---|---:|---:|---:|---:|---:|
| Owner | 166 | 106 | 41 | 14 | 5 |
| Sonnet agents | 86 | 47 | 33 | 6 | 0 |
| **All** | **252** | **153 (61%)** | **74 (29%)** | **20 (8%)** | **5 (2%)** |

| BIRD quality filter (`bird23-train-filtered`) | Cases | Key wrong | Ours wrong | Both OK | Ambiguous |
|---|---:|---:|---:|---:|---:|
| Kept by the filter | 134 | 62 (46%) | 51 (38%) | 17 (13%) | 4 (3%) |
| Removed by the filter | 118 | 91 (77%) | 23 (19%) | 3 (3%) | 1 (1%) |

The filter removes mostly bad keys, but almost half of the reviewed cases it keeps
still have a wrong key.

## By source

A case can belong to more than one source.

| Source | Cases | Key wrong | Ours wrong | Both OK | Ambiguous |
|---|---:|---:|---:|---:|---:|
| Reasoning low: flipped rows | 11 | 0 | 9 | 2 | 0 |
| Reasoning high: flipped rows | 12 | 0 | 10 | 1 | 1 |
| Few-shot: flipped rows | 6 | 0 | 6 | 0 | 0 |
| Data dictionary: flipped rows | 3 | 0 | 3 | 0 | 0 |
| Column notes (rank 1c): flipped rows | 8 | 0 | 7 | 1 | 0 |
| Rank 4 bank: unanimous but marked wrong | 93 | 77 | 8 | 5 | 3 |
| Numbers stored as text (`train_design`) | 194 | 76 | 44 | 13 | 2 |

## Should the rejected experiments have been adopted?

Each flipped row is re-scored by the verdict: `key_wrong` and `both_ok` count as correct
for our answer, `ours_wrong` and `ambiguous` as wrong.

| Experiment | Official paired change | After review | Decision |
|---|---:|---:|---|
| Reasoning low | −1.5 | −1.0 | Rejection stands |
| Reasoning high | −1.5 | −2.5 | Rejection stands |
| Few-shot | +0.0 | +0.0 | Rejection stands |
| Data dictionary | +0.9 | +0.9 | Rejection stands |
| Column notes (rank 1c) | −1.5 | −0.5 | Rejection stands |

None of the 40 flipped rows had a wrong key: 35 were real errors on the side that
disagreed with the key, and 5 were both acceptable or ambiguous. Label noise did not
hide a real improvement. The bad keys sit mostly where every approach
agrees, so they lower the score without steering the paired decisions.

## Effect on practice scores

- **Rank 4 bank:** on 82 of the 93 unanimous-but-wrong questions, our answer is correct
  (77 wrong key + 5 both acceptable). Re-scoring only those rows moves `direct` on
  `train_dev` from 69.5% (348/501) to **85.8%** (430/501). This is not an official score
  and not a strict floor: rows where `direct` matched a wrong key were not reviewed.
- **Numbers stored as text:** 59/194 (30.4%) officially; **145/194 (74.7%)** after
  review. Most "misses" were the gold ordering or averaging text such as `'$4.99'` as
  a string while our SQL converted it.
- The agents noted that many numbers-as-text keys have other defects too: wrong join
  keys, join fan-out, missing filters and integer division.

## What follows

- Practice-set EX on BIRD train databases understates the system substantially. The
  cleaned Nov 2025 dev (66.0%) already fixes many keys, so this does not transfer to a
  dev estimate.
- The hidden test is graded with several gold-SQL pools and human review, so the test
  number is the cheapest way to learn the real standing. Get it before paid training
  (rank G).
- Training on BIRD-style labels (rank G) would learn these key conventions: better dev
  EX, but a transfer risk for test and product. Filter training rows by
  `bird23-train-filtered` at minimum.

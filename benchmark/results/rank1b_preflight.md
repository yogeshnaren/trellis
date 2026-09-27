# Rank 1b profile-facts pilot: prepared, not run

Clean worktree branch: codex/rank1b-bank, based on master 483a106.
Variant: bounded database-derived facts in the user message, with no gold at inference.
Control: bird_raw_20260926T212754Z.jsonl, 501 train_dev questions x 2 repeats.
Pilot selection: 25 rows per train_dev database, seed 1; 100 questions x 2 repeats.
Of those 100 questions, 60 receive at least one fact (movie 19, restaurant 17,
sales_in_weather 10, soccer_2016 14). Added text averages 97.5 characters
per answer across all 100; the other 40 prompts are unchanged.
Control accuracy on these selected rows: 71.5% across repeats (affected 75.0%,
unaffected 66.2%).

Estimated variant cost: about $0.14-$0.16 uncached for 200 answers, based on the
measured v4p1 train_dev price and a small allowance for repairs. This is an
estimate, not a charge. The shared Fireworks ledger was $6.275 spent against its previous $6 cap.
The owner approved a new $7 total cap. This pilot uses a tighter $6.55
per-run ledger ceiling (at most $0.275 above that starting balance), and
loads the existing credential only inside the process. No persistent
credential link or copy is created.

The original checkout was not modified. Its three completed candidate-bank
arms were copied into this worktree and analysed offline.

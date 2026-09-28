# Jev live advisory pilot protocol

Frozen before Fireworks generation. The 100 questions are 25 per `train_dev2` database, with atomic formula/comparison hints included using only question and evidence text. The 50 basketball questions used in the earlier Jev table shadow are excluded. The selection and database fingerprints are in `jev_live_pilot_manifest.json`.

Control: current accepted `deepseek-v4p1-flash` benchmark configuration. Arms: (1) Jev selected starting-table advisory; (2) Jev classified evidence-role advisory on the 27 eligible questions. Each arm generates one SQL answer per question. The database schema is always complete. No gold SQL or gold result is passed to Jev or the generator.

Screen rule: an arm is worth a full paired comparison only if it has at least four more official-EX fixes than regressions per 100 questions and no database loses at least three of its 25 questions net. Report all row and database results, dollar costs, and latency. This 100-question screen cannot justify adoption. A promoted arm needs two-repeat paired full `train_dev2` confirmation, then the preplanned sealed gate. Do not tune thresholds or question selection on this pilot's results.

Both Fireworks and OpenRouter costs are recorded in the shared SQLite ledger. Fireworks ceiling: $8. OpenRouter ceiling: $5 total and $1 session, independently enforced.

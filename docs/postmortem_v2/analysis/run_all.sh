#!/usr/bin/env bash
# Regenerates every table in docs/POSTMORTEM_V2.md from recorded runs. Zero API cost.
# Run from the repo root. pm2 (official re-score of every failure) takes ~10 minutes.
set -euo pipefail
export PYTHONPATH=docs/postmortem_v2/analysis
LOGS=docs/postmortem_v2/data/logs
mkdir -p "$LOGS"
for step in pm1_scoreboard pm3_features pm7_levers pm9_final pm10_snapshots pm11_dev_consensus pm12_dev_cleaned pm4_v1_tracking pm6_labelnoise pm8_goldbugs pm5_cases pm2_buckets; do
  echo "== $step"
  uv run python "docs/postmortem_v2/analysis/$step.py" > "$LOGS/$step.txt" 2>&1
done
echo "done"

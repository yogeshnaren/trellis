#!/usr/bin/env bash
set -euo pipefail

for command in uv curl sqlite3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing prerequisite: $command" >&2
    exit 1
  fi
done

mkdir -p data
curl -fsSL \
  https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sql \
  | sqlite3 data/Chinook.db
echo "Created data/Chinook.db"

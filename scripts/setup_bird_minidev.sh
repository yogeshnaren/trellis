#!/usr/bin/env bash
# Downloads BIRD-SQL Mini-Dev (500 questions / 11 SQLite databases, officially maintained at
# https://github.com/bird-bench/mini_dev) into data/bird/. ~800MB download, ~1.4GB on disk;
# data/bird/ is gitignored and never committed.
set -euo pipefail

for command in curl unzip; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing prerequisite: $command" >&2
    exit 1
  fi
done

if [ -f data/bird/mini_dev_sqlite.json ] && [ -d data/bird/dev_databases ]; then
  echo "data/bird/ already populated; nothing to do."
  exit 0
fi

mkdir -p data/bird
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

echo "Downloading BIRD Mini-Dev (~800MB)..."
curl -fSL -o "$workdir/minidev.zip" \
  "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"

echo "Extracting SQLite databases and question set..."
unzip -q "$workdir/minidev.zip" \
  "minidev/MINIDEV/dev_databases/*" \
  "minidev/MINIDEV/mini_dev_sqlite.json" \
  -d "$workdir/extracted"

mv "$workdir/extracted/minidev/MINIDEV/dev_databases" data/bird/
mv "$workdir/extracted/minidev/MINIDEV/mini_dev_sqlite.json" data/bird/

echo "Done: data/bird/mini_dev_sqlite.json + $(ls data/bird/dev_databases | wc -l) databases."

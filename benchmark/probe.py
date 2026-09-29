"""Bounded, read-only probe of a *training* database, for reviewers (accuracy review).

Runs one query through the same safety gate and read-only connection the agent uses and
prints at most ``--max-rows`` rows as JSON. Only databases under the train directory are
reachable, so evaluation sets (Mini-Dev, dev, cleaned dev) cannot be probed.

    uv run python -m benchmark.probe soccer_2016 "SELECT COUNT(*) FROM Player"
"""

from __future__ import annotations

import argparse
import json
import re

from benchmark.bird import db_path_for
from src.db import connect_readonly, execute_candidate

TRAIN_DB_DIR = "data/bird/train/train_databases"
_DB_ID = re.compile(r"^[A-Za-z0-9_]+$")


def probe(db_id: str, sql: str, max_rows: int = 20) -> dict[str, object]:
    if not _DB_ID.match(db_id):
        return {"error": "invalid database id"}
    path = db_path_for(db_id, db_dir=TRAIN_DB_DIR)
    if not path.exists():
        return {"error": f"no training database named {db_id}"}
    conn = connect_readonly(path, timeout_seconds=15)
    try:
        result = execute_candidate(conn, sql, db_path=path)
    finally:
        conn.close()
    return {
        "error": result.error,
        "columns": result.columns,
        "row_count": result.row_count,
        "rows": [list(row) for row in result.rows[:max_rows]],
        "truncated": result.row_count > max_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("db_id")
    parser.add_argument("sql")
    parser.add_argument("--max-rows", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(probe(args.db_id, args.sql, min(args.max_rows, 50)), default=str))


if __name__ == "__main__":
    main()

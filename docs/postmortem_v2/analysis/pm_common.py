"""Shared loaders for the v2 postmortem analysis. Read-only; makes no API calls.

Run each script from the repo root, e.g.
    PYTHONPATH=docs/postmortem_v2/analysis uv run python docs/postmortem_v2/analysis/pm1_scoreboard.py
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

from benchmark.analyze import load_runs, official_correct, sql_complexity  # noqa: E402
from benchmark.bird import BirdQuestion, load_questions  # noqa: E402

RES = ROOT / "benchmark/results"
SPLITS = ROOT / "data/bird/splits"

QSETS = {
    "mini_dev": (ROOT / "data/bird/mini_dev_sqlite.json", ROOT / "data/bird/dev_databases"),
    "train_dev": (SPLITS / "train_dev.json", ROOT / "data/bird/train/train_databases"),
    "dev_untouched": (SPLITS / "dev_untouched.json", ROOT / "data/bird/dev_databases"),
}

# Runs used in the postmortem: label -> (question set, raw file stem)
RUNS = {
    "mini_dev/baseline(1x)": ("mini_dev", "bird_raw_20260923T061413Z"),
    "mini_dev/gate1(3x)": ("mini_dev", "bird_raw_20260924T232302Z"),
    "train_dev/baseline(2x)": ("train_dev", "bird_raw_20260924T005317Z"),
    "train_dev/1a(2x)": ("train_dev", "bird_raw_20260924T170715Z"),
    "train_dev/1abc(2x)": ("train_dev", "bird_raw_20260924T175733Z"),
    "train_dev/gptoss120b(2x)": ("train_dev", "bird_raw_20260925T014638Z"),
    "train_dev/v4p1flash(2x)": ("train_dev", "bird_raw_20260926T203859Z"),
    "dev_untouched(1x)": ("dev_untouched", "bird_raw_20260925T015202Z"),
    "dev_untouched/gptoss120b(1x)": ("dev_untouched", "bird_raw_20260926T215536Z"),
}


def questions_for(qset: str) -> list[BirdQuestion]:
    return load_questions(QSETS[qset][0])


def load(label: str):
    qset, stem = RUNS[label]
    qs = questions_for(qset)
    runs = load_runs(RES / f"{stem}.jsonl", qs)
    return qs, runs, QSETS[qset][1]


def correct_flags(qs, runs, db_dir) -> dict[int, list[bool]]:
    by_row = {q.row_index: q for q in qs}
    out = {}
    for row, recs in runs.items():
        out[row] = [official_correct(r, by_row[row], db_dir) for r in recs]
    return out


def bootstrap_ci(per_q: dict[int, float], db_of: dict[int, str], n=2000, seed=0, macro=False):
    rng = random.Random(seed)
    by_db: dict[str, list[float]] = defaultdict(list)
    for row, v in per_q.items():
        by_db[db_of[row]].append(v)
    stats = []
    for _ in range(n):
        accs = []
        tot = cnt = 0.0
        for db, vals in by_db.items():
            s = [vals[rng.randrange(len(vals))] for _ in vals]
            accs.append(sum(s) / len(s))
            tot += sum(s)
            cnt += len(s)
        stats.append(sum(accs) / len(accs) if macro else tot / cnt)
    stats.sort()
    return stats[int(0.025 * n)], stats[int(0.975 * n)]

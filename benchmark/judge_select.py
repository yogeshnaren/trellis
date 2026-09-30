"""LLM-judge selection over a frozen candidate bank (Experiment C).

For each question whose candidates return different results, the judge sees the question,
the evidence and each *distinct* candidate (SQL plus a result preview) and picks one. When
all candidates agree, or the judge fails, the incumbent's answer is kept. The prompt is fixed
before scoring; nothing is tuned on the bank's labels. Scored with ``benchmark.bank_report``'s
official and corrected views.

    uv run python -m benchmark.judge_select --judge accounts/fireworks/models/gpt-oss-120b \\
        --reasoning high ... direct=RUN gptoss=RUN qwen=RUN arctic=RUN
"""

from __future__ import annotations

import argparse
import asyncio
import json
import string
from pathlib import Path

from dotenv import load_dotenv

import benchmark.bank_report as br
from benchmark.analyze import NON_INFERIORITY_MARGIN_PTS, _bootstrap, delivered_sql, easy_slice
from benchmark.bird import db_path_for, load_questions
from src.costs import get_shared_budget
from src.db import connect_readonly, execute_candidate, timeout_for_database
from src.llm import complete

JUDGE_PROMPT = """You are checking candidate SQL answers to a question about a SQLite database.

Question: {question}
Evidence (definitions from the question author): {evidence}

Candidates (each with its SQL and the first rows it returns):
{candidates}

Pick the candidate whose result correctly and exactly answers the question: the requested
columns only, the right entities and grain, the right filters, and correct handling of numbers
stored as text. Prefer following the evidence's definitions. Reply as JSON:
{{"choice": "<letter>", "reason": "<one sentence>"}}"""


def preview(db_path: Path, sql: str) -> str:
    conn = connect_readonly(db_path, timeout_seconds=timeout_for_database(db_path, default=30.0))
    try:
        res = execute_candidate(conn, sql, db_path=db_path)
    finally:
        conn.close()
    if not res.ok:
        return f"error: {res.error}"
    head = [list(r) for r in res.rows[:5]]
    return f"columns {res.columns}; {res.row_count} rows; first rows {head}"


async def main_async(args: argparse.Namespace) -> None:
    questions = load_questions(args.questions)
    by_row = {q.row_index: q for q in questions}
    routes = dict(br.load_route(s, questions) for s in args.routes)
    names = list(routes)
    rows = sorted(set.intersection(*(set(r) for r in routes.values())))
    sigs = br.candidate_signatures(routes, questions, args.db_dir)
    labels = json.loads(Path(args.labels).read_text())
    lrows = json.loads(Path(args.label_rows).read_text())["source_rows"]
    refs = br.reference_signatures([by_row[r] for r in rows], args.db_dir, labels, lrows, args.label_prefix)
    guard = get_shared_budget(args.budget)
    options = {"reasoning_effort": args.reasoning} if args.reasoning else None
    sem = asyncio.Semaphore(args.concurrency)
    picks: dict[int, str] = {}
    log = []

    async def judge(r: int) -> None:
        distinct: dict[str, str] = {}
        for n in names:
            s = sigs[n][r]
            if s is not None and s not in distinct.values():
                distinct[n] = s
        if len(distinct) < 2:
            picks[r] = names[0]
            return
        q = by_row[r]
        db = db_path_for(q.db_id, db_dir=args.db_dir)
        letters = dict(zip(string.ascii_uppercase, distinct, strict=False))
        text = "\n\n".join(f"{L}. SQL: {delivered_sql(routes[n][r])}\n   Result: {preview(db, delivered_sql(routes[n][r]) or '')}"
                           for L, n in letters.items())
        prompt = JUDGE_PROMPT.format(question=q.question, evidence=q.evidence or "none", candidates=text)
        async with sem:
            try:
                res = await complete([{"role": "user", "content": prompt}], args.judge,
                                     response_format={"type": "json_object"}, max_tokens=args.max_tokens,
                                     budget=guard, request_options=options, timeout_s=120)
                choice = json.loads(res.text).get("choice", "").strip().upper()[:1]
                picks[r] = letters.get(choice, names[0])
                log.append({"row": r, "choice": choice, "route": picks[r], "reason": json.loads(res.text).get("reason"),
                            "cost": res.cost_usd})
            except Exception as exc:  # noqa: BLE001 - keep the incumbent on any failure
                picks[r] = names[0]
                log.append({"row": r, "error": type(exc).__name__})

    await asyncio.gather(*(judge(r) for r in rows))
    scored = [r for r in rows if refs.get(r) is not None]
    judged = [e for e in log if "route" in e]

    def ok(route: str, r: int, view: str) -> bool:
        return bool(routes[route][r].get("official_ex")) if view == "official" else sigs[route][r] in (refs[r] or set())

    out = {"judge": args.judge, "reasoning": args.reasoning, "judged": len(judged),
           "failures": sum(1 for e in log if "error" in e), "cost_usd": round(sum(e.get("cost", 0) for e in log), 4)}
    for view, pool in (("official", rows), ("corrected", scored)):
        base = sum(ok(names[0], r, view) for r in pool)
        sel = sum(ok(picks[r], r, view) for r in pool)
        fix = sum(1 for r in pool if ok(picks[r], r, view) and not ok(names[0], r, view))
        brk = sum(1 for r in pool if not ok(picks[r], r, view) and ok(names[0], r, view))
        per_db: dict[str, list[float]] = {}
        easy: dict[str, list[float]] = {}
        for r in pool:
            d = float(ok(picks[r], r, view)) - float(ok(names[0], r, view))
            per_db.setdefault(by_row[r].db_id, []).append(d)
            if easy_slice(by_row[r]):
                easy.setdefault(by_row[r].db_id, []).append(d)
        (lo, hi), _ = _bootstrap(per_db, 2000, 0)
        gates: dict[str, object] = {"ci": [round(100 * lo, 2), round(100 * hi, 2)]}
        if easy:
            (elo, _), _ = _bootstrap(easy, 2000, 0)
            gates["easy_questions"] = sum(len(v) for v in easy.values())
            gates["easy_ci_low"] = round(100 * elo, 2)
            gates["easy_non_inferior"] = elo * 100 >= -NON_INFERIORITY_MARGIN_PTS
        gates["protected_lost"] = brk
        out[view] = {"questions": len(pool), "incumbent": round(100 * base / len(pool), 1),
                     "judge": round(100 * sel / len(pool), 1), "fixes": fix, "breaks": brk, **gates}
    print(json.dumps(out))
    Path(args.log).write_text(json.dumps(log, indent=1, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--label-rows", type=Path, required=True)
    parser.add_argument("--label-prefix", default="train_dev2")
    parser.add_argument("--judge", required=True)
    parser.add_argument("--reasoning", default=None)
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--budget", type=float, default=10.0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--log", type=Path, default=Path("/tmp/judge_log.json"))
    parser.add_argument("routes", nargs="+", help="label=RUN; the first is the incumbent")
    load_dotenv()
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()

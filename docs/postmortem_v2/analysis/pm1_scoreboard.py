from pm_common import *  # noqa
import statistics

summary = {}
for label in RUNS:
    qs, runs, db_dir = load(label)
    flags = correct_flags(qs, runs, db_dir)
    by_row = {q.row_index: q for q in qs}
    db_of = {r: by_row[r].db_id for r in flags}
    per_q = {r: sum(f) / len(f) for r, f in flags.items()}
    n = len(per_q)
    reps = Counter(len(f) for f in flags.values())
    row_acc = sum(per_q.values()) / n
    dbs = defaultdict(list)
    for r, v in per_q.items():
        dbs[db_of[r]].append(v)
    macro = sum(sum(v) / len(v) for v in dbs.values()) / len(dbs)
    lo, hi = bootstrap_ci(per_q, db_of, n=1000)
    mlo, mhi = bootstrap_ci(per_q, db_of, n=1000, macro=True)
    # stability
    allc = sum(all(f) for f in flags.values())
    allw = sum(not any(f) for f in flags.values())
    flaky = n - allc - allw
    passk = sum(any(f) for f in flags.values()) / n
    # cost/latency
    lat, cost, unc = [], [], []
    from src.costs import cost_usd
    for recs in runs.values():
        for r in recs:
            lat.append(r["t_total_ms"] / 1000)
            cost.append(sum(c["cost_usd"] for c in r["llm_calls"]))
            unc.append(sum(cost_usd(c["model"], c["input_tokens"], 0, c["output_tokens"]) for c in r["llm_calls"]))
    lat.sort()
    p = lambda a, q: a[min(len(a) - 1, int(q * len(a)))]
    summary[label] = dict(
        rows=n, repeats=dict(reps), row_acc=row_acc, ci=(lo, hi), macro=macro, macro_ci=(mlo, mhi),
        all_correct=allc, all_wrong=allw, flaky=flaky, pass_any=passk,
        p50=p(lat, .5), p90=p(lat, .9), cost=statistics.mean(cost), uncached=statistics.mean(unc),
        per_db={d: (sum(v) / len(v), len(v)) for d, v in dbs.items()},
    )
    s = summary[label]
    print(f"\n### {label}: rows={n} repeats={s['repeats']}")
    print(f"row-weighted {row_acc:.1%} [{lo:.1%},{hi:.1%}]  macro {macro:.1%} [{mlo:.1%},{mhi:.1%}]")
    print(f"stable-correct {allc} ({allc/n:.1%}) | stable-wrong {allw} ({allw/n:.1%}) | flaky {flaky} ({flaky/n:.1%}) | pass@any {passk:.1%}")
    print(f"P50 {s['p50']:.2f}s P90 {s['p90']:.2f}s  $/answer {s['cost']:.6f}  uncached-eq {s['uncached']:.6f}")
    for d, (a, k) in sorted(s["per_db"].items(), key=lambda kv: kv[1][0]):
        print(f"   {d:26s} {a:6.1%}  n={k}")

json.dump(summary, open(str(OUT / "scoreboard.json"), "w"), indent=1, default=str)

from pm_common import *  # noqa
from benchmark.analyze import rescore, load_corrected_gold

targets = {
    "mini_dev/baseline(1x)": ROOT / "data/bird/arcwise_plat_sql.json",
    "mini_dev/gate1(3x)": ROOT / "data/bird/arcwise_plat_sql.json",
    "train_dev/baseline(2x)": SPLITS / "verified_gold_same_inputs.json",
    "train_dev/1abc(2x)": SPLITS / "verified_gold_same_inputs.json",
    "dev_untouched(1x)": None,
}
out = {}
for label, cg in targets.items():
    qs, runs, db_dir = load(label)
    qset, stem = RUNS[label]
    corrected = load_corrected_gold(cg) if cg else None
    res = rescore(RES / f"{stem}.jsonl", qs, db_dir, corrected)
    out[label] = res
    n = len(res)
    b = Counter(r["bucket"] for r in res)
    fails = n - b["correct"]
    print(f"\n### {label}  rows={n}  official={b['correct']/n:.1%}  failing={fails}")
    for k, v in b.most_common():
        if k == "correct":
            continue
        print(f"   {k:34s} {v:4d}  {v/fails:5.1%} of failures  {v/n:5.1%} of all rows")
    fx = Counter(r["contract_fix_oracle"] for r in res if r["contract_fix_oracle"])
    print("   oracle presentational fixes (upper bound, NOT a gain):", dict(fx), "-> +", f"{sum(fx.values())/n:.1%}")
    if corrected is not None:
        cc = [r for r in res if r["official_ex_corrected"] is not None]
        if cc:
            print(f"   rows with corrected gold: {len(cc)}; official {sum(r['official_ex'] for r in cc)/len(cc):.1%} -> corrected {sum(bool(r['official_ex_corrected']) for r in cc)/len(cc):.1%}")
json.dump(out, open(str(OUT / "failure_buckets.json"), "w"), default=str)

"""Snapshot churn and three-run consensus on train_dev (deepseek-0731, deepseek-v4p1-flash, gpt-oss-120b)."""
from pm_common import *  # noqa

qs = questions_for("train_dev")
db_dir = QSETS["train_dev"][1]


def flags(stem):
    runs = load_runs(RES / f"{stem}.jsonl", qs)
    return correct_flags(qs, runs, db_dir), runs


f_old, r_old = flags("bird_raw_20260924T175733Z")   # deepseek-v4-flash-0731, current configuration
f_new, r_new = flags("bird_raw_20260926T203859Z")   # deepseek-v4p1-flash, same configuration
f_gpt, r_gpt = flags("bird_raw_20260925T014638Z")   # gpt-oss-120b, same configuration
n = len(qs)
mean = lambda f: sum(sum(v) / len(v) for v in f.values()) / n
print(f"0731 {mean(f_old):.1%} | v4p1 {mean(f_new):.1%} | gpt-oss {mean(f_gpt):.1%}")
verdict = lambda f: {x: sum(f[x]) / len(f[x]) >= 0.5 for x in f}
a, b, c = verdict(f_old), verdict(f_new), verdict(f_gpt)
fix = sum((not a[x]) and b[x] for x in range(n)); reg = sum(a[x] and not b[x] for x in range(n))
print(f"0731 -> v4p1: verdict changes on {fix + reg} rows ({(fix + reg) / n:.1%}): fixes {fix}, regressions {reg}, net {fix - reg:+d}")
anyc = sum(a[x] or b[x] or c[x] for x in range(n)); allw = n - anyc
print(f"any of 3 runs correct: {anyc / n:.1%}; wrong in all three: {allw} ({allw / n:.1%})")
sigs = lambda r, x: {s.get("result_signature") for s in r[x] if s.get("result_signature")}
agree = sum(1 for x in range(n) if not (a[x] or b[x] or c[x]) and (sigs(r_old, x) & sigs(r_new, x) & sigs(r_gpt, x)))
print(f"of those, all three return the same result set: {agree} ({agree / allw:.0%}) = {agree / n:.1%} of rows")

from pm_common import *  # noqa
from benchmark.analyze import run_query, load_corrected_gold, delivered_sql
from benchmark.bird import db_path_for

# ---- (1) Mechanical label-change rate: how often does the corrected gold change the result set?
def label_change(qset, corrected_path, label):
    qs = questions_for(qset); db_dir = QSETS[qset][1]
    cg = load_corrected_gold(corrected_path)
    changed = tot = err = 0
    per_db = defaultdict(lambda: [0, 0])
    for q in qs:
        if q.question_id not in cg: continue
        dbp = db_path_for(q.db_id, db_dir=db_dir)
        g0 = run_query(dbp, q.gold_sql); g1 = run_query(dbp, cg[q.question_id])
        tot += 1; per_db[q.db_id][1] += 1
        if g0 is None or g1 is None:
            err += 1
            if (g0 is None) != (g1 is None): changed += 1; per_db[q.db_id][0] += 1
            continue
        if set(g0) != set(g1):
            changed += 1; per_db[q.db_id][0] += 1
    print(f"\n[{label}] rows with corrected gold: {tot}; result set changed: {changed} ({changed/tot:.1%}); exec errors {err}")
    for d, (c, n) in sorted(per_db.items(), key=lambda kv: -kv[1][0] / kv[1][1]):
        print(f"    {d:26s} {c:3d}/{n:3d} = {c/n:.0%}")
    return cg

label_change("mini_dev", ROOT / "data/bird/arcwise_plat_sql.json", "Mini-Dev vs Arcwise-Plat-SQL")
cg_tr = label_change("train_dev", SPLITS / "verified_gold_same_inputs.json", "train_dev (Verified same-input subset)")

# ---- (2) Cross-check the manual sample: do stable-wrong rows with a Verified label match it?
qs, runs, db_dir = load("train_dev/1abc(2x)")
flags = correct_flags(qs, runs, db_dir)
by_row = {q.row_index: q for q in qs}
sw = [r for r, f in flags.items() if not any(f)]
hit = conf = 0
for r in sw:
    q = by_row[r]
    if q.question_id not in cg_tr: continue
    hit += 1
    dbp = db_path_for(q.db_id, db_dir=db_dir)
    g1 = run_query(dbp, cg_tr[q.question_id]); sql = delivered_sql(runs[r][0])
    p = run_query(dbp, sql) if sql else None
    if g1 is not None and p is not None and set(p) == set(g1): conf += 1
print(f"\nstable-wrong train_dev rows with a Verified same-input label: {hit}; of which the agent matches the CORRECTED gold: {conf} ({conf/max(hit,1):.0%})")

# ---- (3) Cross-model consensus against gold (train_dev, DeepSeek 1abc vs gpt-oss-120b)
q2, runs2, _ = load("train_dev/gptoss120b(2x)")
flags2 = correct_flags(q2, runs2, db_dir)
both_wrong = agree = only_ds = only_gpt = 0
for r in range(len(qs)):
    a = any(flags[r]); b = any(flags2[r])
    if a and not b: only_ds += 1
    if b and not a: only_gpt += 1
    if not a and not b:
        both_wrong += 1
        s1 = {x.get("result_signature") for x in runs[r] if x.get("result_signature")}
        s2 = {x.get("result_signature") for x in runs2[r] if x.get("result_signature")}
        if s1 & s2: agree += 1
n = len(qs)
print(f"\ntrain_dev both model families wrong on {both_wrong}/{n} ({both_wrong/n:.1%}); of those they return the SAME result set: {agree} ({agree/both_wrong:.0%}) -> {agree/n:.1%} of all rows")
print(f"only DeepSeek right {only_ds}; only gpt-oss right {only_gpt}; union-correct {(n-both_wrong)/n:.1%} vs DeepSeek alone {sum(any(f) for f in flags.values())/n:.1%}")

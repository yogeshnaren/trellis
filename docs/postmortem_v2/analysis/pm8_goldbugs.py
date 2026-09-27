from pm_common import *  # noqa
import re
from sqlglot import exp, parse_one

CMP = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Like, exp.In, exp.Is, exp.Between)

def bugs(sql):
    found = set()
    lo = sql.lower()
    if re.search(r"\btotal\s*\(", lo): found.add("TOTAL()-of-id/odd-agg")
    if re.search(r"like\s+'[^']*'\s+or\s+'", lo): found.add("LIKE ... OR '...' (always true)")
    try:
        t = parse_one(sql, read="sqlite")
    except Exception:
        return found
    for c in t.find_all(exp.Count):
        inner = c.this
        if isinstance(inner, exp.Distinct): continue
        if isinstance(inner, CMP): found.add("COUNT(<comparison>) counts every row")
        if isinstance(inner, exp.Case):
            ifs = inner.args.get("ifs") or []
            default = inner.args.get("default")
            if ifs and default is not None and default.sql() not in ("NULL",):
                found.add("COUNT(CASE..THEN 1 ELSE 0) counts every row")
    return found

print(f"{'dataset':16} {'rows':>5} {'gold w/ >=1 unambiguous bug idiom':>36}   breakdown")
for qset in ("mini_dev", "train_dev", "dev_untouched"):
    qs = questions_for(qset)
    c = Counter(); any_bug = 0
    for q in qs:
        b = bugs(q.gold_sql)
        if b: any_bug += 1
        for x in b: c[x] += 1
    print(f"{qset:16} {len(qs):5d} {any_bug:5d} ({any_bug/len(qs):.1%})   {dict(c)}")

# does the agent 'fail' on those rows more? (train_dev + mini gate1 + dev)
for label in ("mini_dev/gate1(3x)", "train_dev/1abc(2x)", "dev_untouched(1x)"):
    qs, runs, db_dir = load(label); fl = correct_flags(qs, runs, db_dir)
    byr = {q.row_index: q for q in qs}
    bug_rows = [r for r in fl if bugs(byr[r].gold_sql)]
    ok = [r for r in fl if r not in set(bug_rows)]
    a = lambda rs: sum(sum(fl[r]) / len(fl[r]) for r in rs) / max(len(rs), 1)
    print(f"{label:22s} rows with gold-bug idiom: {len(bug_rows):3d} agent acc {a(bug_rows):.1%} | other rows {len(ok)} acc {a(ok):.1%}")

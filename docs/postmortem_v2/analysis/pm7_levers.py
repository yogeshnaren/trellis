from pm_common import *  # noqa
import re
from benchmark.analyze import delivered_sql
sys.path.insert(0, str(RES.parent.parent))

rows_feat = {(r["dataset"], r["row"]): r for r in json.load(open(str(OUT / "question_features.json")))}

# (A) Shipped answers whose result is a single all-NULL row — an un-retried "silent empty".
print("### (A) all-NULL / empty shipped answers")
for label in ["mini_dev/gate1(3x)", "train_dev/1abc(2x)", "dev_untouched(1x)"]:
    qs, runs, db_dir = load(label); flags = correct_flags(qs, runs, db_dir)
    nul = emp = 0; nul_ok = emp_ok = 0; tot = 0
    for r, recs in runs.items():
        rec = recs[0]; tot += 1
        rows = rec.get("rows"); ok = flags[r][0]
        if rec.get("error") is None and rec.get("response_type") == "query":
            if rows is not None and len(rows) == 0: emp += 1; emp_ok += ok
            elif rows is not None and len(rows) == 1 and all(v is None for v in rows[0]): nul += 1; nul_ok += ok
    print(f"{label:22s} answers={tot}  empty={emp} (correct {emp_ok})  single-all-NULL={nul} (correct {nul_ok})")

# (B) COUNT(DISTINCT ...) used by the agent: precision of DISTINCT vs gold
print("\n### (B) agent uses COUNT(DISTINCT ..): correctness, and whether gold also uses DISTINCT")
def has_cd(sql): return bool(re.search(r"count\s*\(\s*distinct", sql or "", re.I))
for label in ["mini_dev/gate1(3x)", "train_dev/1abc(2x)", "dev_untouched(1x)"]:
    qs, runs, db_dir = load(label); flags = correct_flags(qs, runs, db_dir); byr = {q.row_index: q for q in qs}
    agent_cd = [r for r, recs in runs.items() if has_cd(delivered_sql(recs[0]))]
    both = [r for r in agent_cd if has_cd(byr[r].gold_sql)]
    only_agent = [r for r in agent_cd if not has_cd(byr[r].gold_sql)]
    only_gold = [r for r, recs in runs.items() if has_cd(byr[r].gold_sql) and not has_cd(delivered_sql(recs[0]))]
    f = lambda rs: f"{sum(flags[r][0] for r in rs)}/{len(rs)} = {sum(flags[r][0] for r in rs)/max(len(rs),1):.0%}"
    print(f"{label:22s} agent uses COUNT(DISTINCT): {len(agent_cd)}; both-distinct correct {f(both)}; agent-only distinct correct {f(only_agent)}; gold-only distinct correct {f(only_gold)}")

# (C) Is the feature<->failure link confounded by label noise? cross-model consensus by feature (train_dev)
print("\n### (C) train_dev: among rows wrong for BOTH model families, share where the two agree (= consensus vs gold), by feature")
qs, runs, db_dir = load("train_dev/1abc(2x)"); fl = correct_flags(qs, runs, db_dir)
q2, runs2, _ = load("train_dev/gptoss120b(2x)"); fl2 = correct_flags(q2, runs2, db_dir)
def cons(r):
    s1 = {x.get("result_signature") for x in runs[r] if x.get("result_signature")}
    s2 = {x.get("result_signature") for x in runs2[r] if x.get("result_signature")}
    return bool(s1 & s2)
groups = {"all": lambda f: True, "q_ratio": lambda f: f.get("q_ratio"), "division|cast": lambda f: f.get("division") or f.get("cast"),
          "group_by": lambda f: f.get("group_by"), "subquery": lambda f: f.get("subquery"), "joins>=2": lambda f: f.get("nj", 0) >= 2,
          "q_superlative": lambda f: f.get("q_superlative"), "q_count": lambda f: f.get("q_count"), "no feature (simple)": lambda f: not any(f.get(k) for k in ("q_ratio","division","cast","group_by","subquery","q_superlative")) and f.get("nj",0) < 2}
print(f"{'group':22s} {'n':>4} {'DS acc':>7} {'both-wrong':>10} {'consensus':>10} {'genuine-ish (both wrong, disagree)':>36}")
for g, fn in groups.items():
    rs = [r for r in range(len(qs)) if fn(rows_feat[("train_dev/1abc(2x)", r)])]
    bw = [r for r in rs if not any(fl[r]) and not any(fl2[r])]
    c = [r for r in bw if cons(r)]
    acc = sum(any(fl[r]) for r in rs) / len(rs)
    print(f"{g:22s} {len(rs):4d} {acc:7.1%} {len(bw):10d} {len(c):5d} ({len(c)/max(len(bw),1):.0%}) {len(bw)-len(c):20d} ({(len(bw)-len(c))/len(rs):.1%} of rows)")

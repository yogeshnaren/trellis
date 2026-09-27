from pm_common import *  # noqa
import re
from sqlglot import exp, parse_one

def feats(q: BirdQuestion) -> dict[str, bool | int]:
    try:
        t = parse_one(q.gold_sql, read="sqlite")
    except Exception:
        t = None
    f: dict[str, Any] = {}
    sql = q.gold_sql
    lo = sql.lower()
    if t is not None:
        f["n_joins"] = len(list(t.find_all(exp.Join)))
        f["n_tables"] = len({x.name.lower() for x in t.find_all(exp.Table)})
        f["subquery"] = len(list(t.find_all(exp.Select))) > 1
        f["group_by"] = t.find(exp.Group) is not None
        f["having"] = t.find(exp.Having) is not None
        f["order_limit"] = t.find(exp.Limit) is not None
        f["window"] = t.find(exp.Window) is not None
        f["case_iif"] = t.find(exp.Case) is not None or "iif(" in lo
        f["cast"] = t.find(exp.Cast) is not None
        f["distinct"] = t.find(exp.Distinct) is not None
        f["agg"] = t.find(exp.AggFunc) is not None
        f["like"] = t.find(exp.Like) is not None
        f["set_op"] = t.find(exp.Union, exp.Intersect, exp.Except) is not None
        f["date_fn"] = bool(re.search(r"strftime|substr\(|julianday|date\(|year\(", lo))
        f["division"] = t.find(exp.Div) is not None
    ev = q.evidence or ""
    ql = q.question.lower()
    f["no_evidence"] = not ev.strip()
    f["ev_formula"] = bool(re.search(r"divide|/|\*|sum\(|count\(|avg\(|max\(|min\(|percent|ratio", ev.lower()))
    f["q_superlative"] = bool(re.search(r"\b(highest|lowest|most|least|top|maximum|minimum|best|worst|oldest|youngest|largest|smallest|longest|shortest|first|latest|earliest)\b", ql))
    f["q_count"] = "how many" in ql or "number of" in ql
    f["q_ratio"] = bool(re.search(r"percent|ratio|proportion|rate\b|average|avg", ql))
    f["q_temporal"] = bool(re.search(r"\b(year|month|date|between|before|after|since|during|in 19|in 20|from 19|from 20)\b", ql))
    f["q_multi_ask"] = bool(re.search(r"\band\b.*\b(also|list|give|show|indicate|provide)\b|\bhow (much|many).*\band\b|,.*\band\b", ql))
    f["gold_cols>1"] = None  # filled later if needed
    f["evidence_long"] = len(ev) > 150
    return f

FEATS = ["subquery", "group_by", "having", "order_limit", "window", "case_iif", "cast", "distinct", "agg", "like", "set_op",
         "date_fn", "division", "no_evidence", "ev_formula", "evidence_long", "q_superlative", "q_count", "q_ratio", "q_temporal", "q_multi_ask"]

datasets = {"mini_dev/gate1(3x)": None, "train_dev/1abc(2x)": None, "dev_untouched(1x)": None}
allrows = []
for label in datasets:
    qs, runs, db_dir = load(label)
    flags = correct_flags(qs, runs, db_dir)
    by_row = {q.row_index: q for q in qs}
    for r, f in flags.items():
        q = by_row[r]
        d = feats(q)
        d.update(dataset=label, acc=sum(f) / len(f), db=q.db_id, row=r, difficulty=q.difficulty,
                 nj=d.get("n_joins", 0), gold=q.gold_sql)
        allrows.append(d)

def table(rows, title):
    base = sum(r["acc"] for r in rows) / len(rows)
    print(f"\n#### {title}  (n={len(rows)}, base acc {base:.1%})")
    print(f"{'feature':16} {'n_with':>6} {'acc_with':>9} {'acc_without':>12} {'delta':>7}")
    out = []
    for ft in FEATS:
        w = [r for r in rows if r.get(ft)]
        wo = [r for r in rows if not r.get(ft)]
        if len(w) < 15 or len(wo) < 15:
            continue
        aw = sum(r["acc"] for r in w) / len(w); ao = sum(r["acc"] for r in wo) / len(wo)
        out.append((aw - ao, ft, len(w), aw, ao))
    for d, ft, n, aw, ao in sorted(out):
        print(f"{ft:16} {n:6d} {aw:9.1%} {ao:12.1%} {d*100:+6.1f}")
    # joins
    for k in (0, 1, 2, 3):
        s = [r for r in rows if (r["nj"] == k if k < 3 else r["nj"] >= 3)]
        if s: print(f"joins={'3+' if k==3 else k}: n={len(s)} acc {sum(r['acc'] for r in s)/len(s):.1%}")

for label in datasets:
    table([r for r in allrows if r["dataset"] == label], label)
table(allrows, "POOLED")

# schema stats vs DB accuracy (rank correlation) for Mini-Dev DBs
from src.schema import _metadata, _db_key
import os, statistics
def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0]*len(v)
    for k, i in enumerate(o): r[i] = k
    return r
def spearman(a, b):
    ra, rb = rank(a), rank(b); n = len(a)
    ma, mb = sum(ra)/n, sum(rb)/n
    num = sum((x-ma)*(y-mb) for x, y in zip(ra, rb)); den = (sum((x-ma)**2 for x in ra)*sum((y-mb)**2 for y in rb))**.5
    return num/den
dbdir = ROOT/"data/bird/dev_databases"
stats = {}
for db in os.listdir(dbdir):
    md = _metadata(_db_key(dbdir/db/f"{db}.sqlite"))
    ncols = [len(c) for c in md.values()]
    special = sum(1 for c in md.values() for n, k, p in c if re.search(r"[^A-Za-z0-9_]", n))
    stats[db] = dict(tables=len(md), max_cols=max(ncols), total_cols=sum(ncols), special=special,
                     mb=(dbdir/db/f"{db}.sqlite").stat().st_size/1e6)
dbacc = defaultdict(list)
for r in allrows:
    if r["dataset"] in ("mini_dev/gate1(3x)", "dev_untouched(1x)"):
        dbacc[r["db"]].append(r["acc"])
dbs = sorted(stats)
acc = [sum(dbacc[d])/len(dbacc[d]) for d in dbs]
print("\n#### Schema stats vs pooled (Mini-Dev gate1 + dev_untouched) DB accuracy — Spearman rho (n=11 DBs)")
for k in ("tables", "max_cols", "total_cols", "special", "mb"):
    print(f"  {k:10s} rho={spearman([stats[d][k] for d in dbs], acc):+.2f}")
print(f"{'db':26} {'acc':>6} {'tables':>6} {'maxcol':>6} {'totcol':>6} {'special':>7} {'MB':>7}")
for d in sorted(dbs, key=lambda d: sum(dbacc[d])/len(dbacc[d])):
    s = stats[d]; print(f"{d:26} {sum(dbacc[d])/len(dbacc[d]):6.1%} {s['tables']:6d} {s['max_cols']:6d} {s['total_cols']:6d} {s['special']:7d} {s['mb']:7.1f}")
json.dump([{k: v for k, v in r.items() if k != 'gold'} for r in allrows], open(str(OUT / "question_features.json"), "w"), default=str)

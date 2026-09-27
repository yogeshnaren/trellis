from pm_common import *  # noqa
import sqlite3
S = json.load(open(str(OUT / "scoreboard.json")))
mini = S["mini_dev/gate1(3x)"]["per_db"]; du = S["dev_untouched(1x)"]["per_db"]
dbs = sorted(mini)
def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r=[0]*len(v)
    for k,i in enumerate(o): r[i]=k
    return r
a=[mini[d][0] for d in dbs]; b=[du[d][0] for d in dbs]
ra, rb = rank(a), rank(b); n=len(a); ma=sum(ra)/n; mb=sum(rb)/n
rho = sum((x-ma)*(y-mb) for x,y in zip(ra,rb))/((sum((x-ma)**2 for x in ra)*sum((y-mb)**2 for y in rb))**.5)
print(f"Spearman(per-DB acc: Mini-Dev gate1 vs dev_untouched) = {rho:.2f}")
print(f"{'db':26}{'Mini(3x)':>9}{'n':>4}{'DevUnt':>8}{'n':>5}{'delta':>7}")
for d in sorted(dbs, key=lambda d: mini[d][0]):
    print(f"{d:26}{mini[d][0]:9.1%}{mini[d][1]:4d}{du[d][0]:8.1%}{du[d][1]:5d}{(du[d][0]-mini[d][0])*100:+7.1f}")

# majority vote at T=0 across repeats (by result signature)
for label in ("mini_dev/gate1(3x)", "train_dev/1abc(2x)"):
    qs, runs, db_dir = load(label); fl = correct_flags(qs, runs, db_dir)
    maj = 0
    for r, recs in runs.items():
        sig = Counter(x.get("result_signature") or f"u{i}" for i, x in enumerate(recs))
        top = sig.most_common(1)[0][0]
        idx = next(i for i, x in enumerate(recs) if (x.get("result_signature") or f"u{i}") == top)
        maj += fl[r][idx]
    n = len(runs); mean = sum(sum(f)/len(f) for f in fl.values())/n
    print(f"{label}: mean {mean:.1%}  majority-by-signature {maj/n:.1%}  pass@any {sum(any(f) for f in fl.values())/n:.1%}")

# spend ledger
try:
    con = sqlite3.connect(f"file:{RES}/.spend.sqlite?mode=ro", uri=True)
    tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    print("ledger tables:", tabs)
    for t in tabs:
        cols = [c[1] for c in con.execute(f"pragma table_info({t})")]
        print(t, cols)
    if "charges" in tabs:
        print(con.execute("select source, round(sum(amount_usd),4) from charges group by source").fetchall())
except Exception as e:
    print("ledger read failed:", e)

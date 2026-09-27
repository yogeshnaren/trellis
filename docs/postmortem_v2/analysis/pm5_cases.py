from pm_common import *  # noqa
from benchmark.analyze import run_query, delivered_sql, bucket
from benchmark.bird import db_path_for

label = "train_dev/1abc(2x)"
qs, runs, db_dir = load(label)
flags = correct_flags(qs, runs, db_dir)
by_row = {q.row_index: q for q in qs}
stable_wrong = [r for r, f in flags.items() if not any(f)]
rng = random.Random(11)
quota = {"soccer_2016": 16, "sales_in_weather": 12, "restaurant": 12, "movie": 6}
picked = []
for db, k in quota.items():
    pool = [r for r in stable_wrong if by_row[r].db_id == db]
    rng.shuffle(pool)
    picked += pool[:k]
print("stable-wrong rows:", len(stable_wrong), "by db:", Counter(by_row[r].db_id for r in stable_wrong))

def shortrows(rows, n=3):
    if rows is None: return "ERR"
    return f"{len(rows)} rows; first={[tuple(str(x)[:24] for x in r) for r in rows[:n]]}"

out = []
for r in picked:
    q = by_row[r]; rec = runs[r][0]
    dbp = db_path_for(q.db_id, db_dir=db_dir)
    gold = run_query(dbp, q.gold_sql)
    sql = delivered_sql(rec)
    pred = run_query(dbp, sql) if sql else None
    b = bucket(rec, gold, pred)
    out.append(f"""=== row {r} | {q.db_id} | qid {q.question_id} | {b}
Q: {q.question}
EV: {q.evidence[:260]}
GOLD: {' '.join(q.gold_sql.split())[:420]}
PRED: {' '.join((sql or 'NONE').split())[:420]}
G-> {shortrows(gold)}
P-> {shortrows(pred)}
""")
open(str(ROOT / "data/bird/postmortem_v2_train_dev_cases.txt"), "w").write("\n".join(out))
print(len(out), "cases written")

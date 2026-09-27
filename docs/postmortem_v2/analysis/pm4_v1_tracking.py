from pm_common import *  # noqa

qs, runs, db_dir = load("mini_dev/gate1(3x)")
bq, bruns, _ = load("mini_dev/baseline(1x)")
by_qid = defaultdict(list)
for q in qs:
    by_qid[q.question_id].append(q.row_index)

groups = {
    "6.1 unquoted special-char identifiers": [1192, 1225, 1232, 1189],
    "6.3 wide-table false 'unsupported' / wrong-table": [1169, 1267],
    "6.5 over-projection (Chinook-era rule)": [881, 954, 955, 1003],
    "6.7 fan-out COUNT vs COUNT DISTINCT": [201],
    "6.2 dictionary-related (yearmonth text date; rtype)": [1500, 40],
    "6.4/evidence literal traps (date slash; label inversion)": [563, 565],
    "6.6 outer-join implied": [23, 24],
    "timeouts (v1 6.8)": [1505, 1031, 595, 604, 409, 247, 346, 518, 701],
    "hallucinated identifiers (not quoting)": [1356, 639, 473, 243],
}
def status(rec):
    ok = "OK " if rec["official_ex"] else "bad"
    tag = rec.get("error_category") or rec.get("response_type") if (rec.get("error_category") or rec.get("response_type") != "query") else ""
    return f"{ok}{('/'+str(tag)) if tag else ''}"
tot = Counter()
for g, ids in groups.items():
    print(f"\n{g}")
    for qid in ids:
        for row in by_qid[qid][:1]:
            recs = runs[row]
            b = bruns[row][0]
            bok = "OK " if (b.get("official_ex") if "official_ex" in b else None) else "bad"
            print(f"  #{qid:5d} {qs[row].db_id:24s} baseline={'?' if 'official_ex' not in b else bok}  gate1(3x)= " + " | ".join(status(r) for r in recs) + f"   err={recs[0].get('error')}")
            tot[g] += sum(r["official_ex"] for r in recs) / len(recs)
print()
for g, ids in groups.items():
    print(f"{g:60s} gate1 accuracy on these {len(ids)} ids: {tot[g]/len(ids):.0%}")

# pipeline outcome census at gate 1 (all 1500 answers)
c = Counter()
for recs in runs.values():
    for r in recs:
        if r.get("error_category"): c["err:" + r["error_category"]] += 1
        elif r.get("response_type") not in (None, "query"): c["resp:" + r["response_type"]] += 1
        if r.get("repaired"): c["repaired"] += 1
        if r.get("refusal_retried"): c["refusal_retried"] += 1
        if r.get("empty_retried"): c["empty_retried"] += 1
        if r.get("truncated"): c["result_truncated"] += 1
print("\nGate-1 pipeline census over", sum(len(v) for v in runs.values()), "answers:", dict(c))
# flips between repeats
fl = [r for r, recs in runs.items() if len({x['official_ex'] for x in recs}) > 1]
print("flaky rows:", len(fl), [(qs[r].db_id, qs[r].question_id) for r in fl][:20])

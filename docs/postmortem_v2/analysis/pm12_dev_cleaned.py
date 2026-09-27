"""Dev label noise, measured mechanically with BIRD's own Nov-2025 cleaned dev SQL.

The cleaned release also rewrites some questions and evidence, so its SQL only grades our answers
where the question AND evidence are unchanged. We score both model runs on that subset against the
original and the cleaned gold. No dev question is read by hand.
Data: data/bird/dev_cleaned/dev_20251106.json (BIRD, CC-BY-SA-4.0; fetched from Hugging Face, gitignored).
"""
import re
import sys

from pm_common import *  # noqa
from benchmark.analyze import delivered_sql, run_query
from benchmark.bird import db_path_for

RAW_DEEPSEEK = "bird_raw_20260925T015202Z"
RAW_GPTOSS = sys.argv[1] if len(sys.argv) > 1 else "bird_raw_20260926T215536Z"
norm = lambda s: re.sub(r"\s+", " ", (s or "").strip()).lower()

cleaned = {r["question_id"]: r for r in json.load(open(ROOT / "data/bird/dev_cleaned/dev_20251106.json"))}
qs = questions_for("dev_untouched")
db_dir = QSETS["dev_untouched"][1]
runs = {"deepseek-0731": load_runs(RES / f"{RAW_DEEPSEEK}.jsonl", qs), "gpt-oss-120b": load_runs(RES / f"{RAW_GPTOSS}.jsonl", qs)}

same = [q for q in qs
        if (c := cleaned.get(q.question_id)) and c["db_id"] == q.db_id
        and norm(c["question"]) == norm(q.question) and norm(c["evidence"]) == norm(q.evidence)]
print(f"dev_untouched rows {len(qs)}; question+evidence unchanged in cleaned release: {len(same)} ({len(same)/len(qs):.1%})")

# per-row verdicts against original and cleaned gold (re-execute only where the SQL text differs)
res = {}
for q in same:
    dbp = db_path_for(q.db_id, db_dir=db_dir)
    c_sql = cleaned[q.question_id]["SQL"]
    changed_text = norm(c_sql) != norm(q.gold_sql)
    g0 = run_query(dbp, q.gold_sql)
    g1 = g0 if not changed_text else run_query(dbp, c_sql)
    row = {"changed_text": changed_text, "changed_result": (g0 is None) != (g1 is None) or (g0 is not None and set(g0) != set(g1))}
    for name, rr in runs.items():
        rec = rr[q.row_index][0]
        orig_ok = bool(rec["official_ex"])                       # recorded in-run verdict vs original gold
        if changed_text:
            sql = delivered_sql(rec)
            pred = run_query(dbp, sql) if sql else None
            clean_ok = g1 is not None and pred is not None and set(pred) == set(g1)
        else:
            clean_ok = orig_ok
        row[name] = (orig_ok, clean_ok)
    res[q.row_index] = row

n = len(res)
sc = sum(r["changed_text"] for r in res.values()); rc = sum(r["changed_result"] for r in res.values())
print(f"\ncleaned SQL text differs on {sc} of {n} same-input rows ({sc/n:.1%}); the gold RESULT SET changes on {rc} ({rc/n:.1%})")
print(f"\n{'model':16} {'original gold':>14} {'cleaned gold':>13} {'delta':>7}   (rows: {n})")
for name in runs:
    o = sum(r[name][0] for r in res.values()) / n; c = sum(r[name][1] for r in res.values()) / n
    print(f"{name:16} {o:14.1%} {c:13.1%} {(c-o)*100:+7.1f}")

# consensus against ORIGINAL vs CLEANED gold on the same subset
def consensus(idx):
    bw = [r for r, v in res.items() if not v["deepseek-0731"][idx] and not v["gpt-oss-120b"][idx]]
    sig = lambda name, r: {x.get("result_signature") for x in runs[name][r] if x.get("result_signature")}
    ag = [r for r in bw if sig("deepseek-0731", r) & sig("gpt-oss-120b", r)]
    return len(bw), len(ag)
for label, idx in (("original", 0), ("cleaned", 1)):
    bw, ag = consensus(idx)
    print(f"\nagainst {label} gold: both wrong {bw} ({bw/n:.1%}); same answer {ag} = {ag/bw:.1%} of jointly-wrong, {ag/n:.1%} of rows; disagree {bw-ag} ({(bw-ag)/n:.1%} of rows)")
o_bw, o_ag = consensus(0); c_bw, c_ag = consensus(1)
print(f"\nconsensus-against-gold rows explained by label cleaning: {o_ag - c_ag} of {o_ag} ({(o_ag - c_ag)/max(o_ag,1):.0%})")
fixed_any = sum(1 for v in res.values() if (not v['deepseek-0731'][0] and v['deepseek-0731'][1]) or (not v['gpt-oss-120b'][0] and v['gpt-oss-120b'][1]))
broke_any = sum(1 for v in res.values() if (v['deepseek-0731'][0] and not v['deepseek-0731'][1]) or (v['gpt-oss-120b'][0] and not v['gpt-oss-120b'][1]))
print(f"rows that flip wrong->right under cleaned gold (either model): {fixed_any}; right->wrong: {broke_any}")

# composition of DeepSeek's errors on the same-input subset, original vs cleaned labels
print("\nComposition of deepseek-0731's wrong rows on the same-input subset (share of ALL rows)")
for label, idx in (("original", 0), ("cleaned", 1)):
    ds_wrong = [r for r, v in res.items() if not v["deepseek-0731"][idx]]
    both = [r for r in ds_wrong if not res[r]["gpt-oss-120b"][idx]]
    sig = lambda name, r: {x.get("result_signature") for x in runs[name][r] if x.get("result_signature")}
    shared = [r for r in both if sig("deepseek-0731", r) & sig("gpt-oss-120b", r)]
    print(f"  {label:9}: deepseek wrong {len(ds_wrong)/n:.1%} = shared-with-gpt-oss {len(shared)/n:.1%} + both-wrong-but-differ {(len(both)-len(shared))/n:.1%} + deepseek-only {(len(ds_wrong)-len(both))/n:.1%}")

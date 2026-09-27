"""Consensus-against-gold on a dev-like set: DeepSeek-0731 vs gpt-oss-120b on dev_untouched.

Decision rule declared in docs/POSTMORTEM_V2.md section 10.1 step 1, before the run:
  consensus >= 60% of jointly-wrong rows  -> prioritize training (conventions / labels)
  consensus <= 35%                        -> prioritize value grounding / computation / disambiguation
"""
import sys

from pm_common import *  # noqa

RAW_DEEPSEEK = "bird_raw_20260925T015202Z"
RAW_GPTOSS = sys.argv[1] if len(sys.argv) > 1 else "bird_raw_20260926T215536Z"

qs = questions_for("dev_untouched")
db_dir = QSETS["dev_untouched"][1]
byrow = {q.row_index: q for q in qs}
rows_feat = {r["row"]: r for r in json.load(open(OUT / "question_features.json")) if r["dataset"] == "dev_untouched(1x)"}


def load_flags(stem):
    runs = load_runs(RES / f"{stem}.jsonl", qs)
    return correct_flags(qs, runs, db_dir), runs


f_a, r_a = load_flags(RAW_DEEPSEEK)
f_b, r_b = load_flags(RAW_GPTOSS)
common = sorted(set(f_a) & set(f_b))
n = len(common)
a = {r: any(f_a[r]) for r in common}
b = {r: any(f_b[r]) for r in common}
sig = lambda runs, r: {x.get("result_signature") for x in runs[r] if x.get("result_signature")}
empty = lambda runs, r: all((x.get("rows") == [] or x.get("result_row_count") == 0) for x in runs[r])

print(f"rows compared: {n} (deepseek {len(f_a)}, gpt-oss {len(f_b)})")
print(f"deepseek-0731 {sum(a.values()) / n:.1%} | gpt-oss-120b {sum(b.values()) / n:.1%} | any-correct {sum(a[r] or b[r] for r in common) / n:.1%}")
both_wrong = [r for r in common if not a[r] and not b[r]]
agree = [r for r in both_wrong if sig(r_a, r) & sig(r_b, r)]
disagree = [r for r in both_wrong if r not in set(agree)]
print(f"\nboth wrong: {len(both_wrong)} ({len(both_wrong) / n:.1%})")
print(f"  same result set (consensus against gold): {len(agree)} = {len(agree) / len(both_wrong):.1%} of jointly-wrong, {len(agree) / n:.1%} of all rows")
print(f"  disagree (genuine-ish): {len(disagree)} = {len(disagree) / len(both_wrong):.1%} of jointly-wrong, {len(disagree) / n:.1%} of all rows")
print(f"  only deepseek right: {sum(a[r] and not b[r] for r in common)}, only gpt-oss right: {sum(b[r] and not a[r] for r in common)}")
rule = "PRIORITIZE TRAINING (>=60%)" if len(agree) / len(both_wrong) >= 0.60 else "PRIORITIZE VALUE/COMPUTATION/DISAMBIGUATION (<=35%)" if len(agree) / len(both_wrong) <= 0.35 else "INCONCLUSIVE (35-60%)"
print("\nDECISION RULE ->", rule)

# what the agreeing-wrong answers look like
emp = [r for r in agree if empty(r_a, r) and empty(r_b, r)]
print(f"\nconsensus rows where both return EMPTY: {len(emp)} ({len(emp) / max(len(agree), 1):.0%} of consensus rows)")

# per database and difficulty
print(f"\n{'database':26} {'n':>4} {'DS':>6} {'GPT':>6} {'both wrong':>10} {'consensus':>10} {'genuine-ish % rows':>19}")
by = defaultdict(list)
for r in common:
    by[byrow[r].db_id].append(r)
for d, rs in sorted(by.items(), key=lambda kv: sum(a[r] for r in kv[1]) / len(kv[1])):
    bw = [r for r in rs if not a[r] and not b[r]]
    ag = [r for r in bw if r in set(agree)]
    print(f"{d:26} {len(rs):4d} {sum(a[r] for r in rs)/len(rs):6.1%} {sum(b[r] for r in rs)/len(rs):6.1%} {len(bw):10d} {len(ag):5d} ({len(ag)/max(len(bw),1):.0%}) {(len(bw)-len(ag))/len(rs):18.1%}")
print()
for diff in ("simple", "moderate", "challenging"):
    rs = [r for r in common if byrow[r].difficulty == diff]
    bw = [r for r in rs if not a[r] and not b[r]]
    ag = [r for r in bw if r in set(agree)]
    print(f"{diff:12} n={len(rs):4d} DS {sum(a[r] for r in rs)/len(rs):.1%} GPT {sum(b[r] for r in rs)/len(rs):.1%} both-wrong {len(bw)} consensus {len(ag)} ({len(ag)/max(len(bw),1):.0%}) genuine-ish {(len(bw)-len(ag))/len(rs):.1%} of rows")

# by feature
groups = {"ratio question": lambda f: f.get("q_ratio"), "division|cast": lambda f: f.get("division") or f.get("cast"),
          "group_by": lambda f: f.get("group_by"), "subquery": lambda f: f.get("subquery"), "joins>=2": lambda f: f.get("nj", 0) >= 2,
          "superlative": lambda f: f.get("q_superlative"), "count question": lambda f: f.get("q_count"),
          "simple (no feature)": lambda f: not any(f.get(k) for k in ("q_ratio", "division", "cast", "group_by", "subquery", "q_superlative")) and f.get("nj", 0) < 2}
print(f"\n{'group':22} {'n':>4} {'DS acc':>7} {'both wrong':>10} {'consensus':>10} {'genuine-ish % rows':>19}")
for g, fn in groups.items():
    rs = [r for r in common if r in rows_feat and fn(rows_feat[r])]
    if not rs:
        continue
    bw = [r for r in rs if not a[r] and not b[r]]
    ag = [r for r in bw if r in set(agree)]
    print(f"{g:22} {len(rs):4d} {sum(a[r] for r in rs)/len(rs):7.1%} {len(bw):10d} {len(ag):5d} ({len(ag)/max(len(bw),1):.0%}) {(len(bw)-len(ag))/len(rs):18.1%}")

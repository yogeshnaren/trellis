"""Build the README's visual assets from the committed benchmark reports.

    uv run python scripts/render_readme_assets.py            # render SVGs + tables (offline, free)
    uv run python scripts/render_readme_assets.py --capture  # re-record CLI fixtures (live, ~$0.002)

Everything the README shows is regenerated from two sources, so no number is retyped by hand:

* ``benchmark/results/*.md``: accuracy, latency and cost are parsed from the run reports and
  the paired-comparison ("flips") reports. A handful of figures that only exist in
  ``docs/SOTA_PLAN.md`` are constants below, each annotated with its section.
* ``docs/assets/fixtures/cli_captures.json``: real ``AgentResult`` snapshots recorded from live
  Chinook questions. The CLI SVGs are drawn by the product's own ``src.cli._render``, so the
  screenshots cannot drift from what the tool prints.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.terminal_theme import TerminalTheme

RESULTS = ROOT / "benchmark" / "results"
ASSETS = ROOT / "docs" / "assets"
FIXTURES = ASSETS / "fixtures" / "cli_captures.json"
LEADERBOARD = ASSETS / "fixtures" / "bird_leaderboard_2026-09-26.json"

# --- palette: every asset is a self-contained dark card, so it reads on light and dark pages ---
BG, PANEL, GRID = "#0d1117", "#161b22", "#30363d"
FG, MUTED = "#e6edf3", "#8b949e"
GREEN, AMBER, RED, BLUE, GREY = "#3fb950", "#d29922", "#f85149", "#58a6ff", "#6e7681"
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace"

GITHUB_DARK = TerminalTheme(
    (13, 17, 23),
    (201, 209, 217),
    [(72, 79, 88), (255, 123, 114), (63, 185, 80), (210, 153, 34),
     (88, 166, 255), (188, 140, 255), (57, 197, 207), (177, 186, 196)],
    [(110, 118, 129), (255, 161, 152), (86, 211, 100), (227, 179, 65),
     (121, 192, 255), (210, 168, 255), (86, 212, 221), (240, 246, 252)],
)

# --- figures that exist only in docs/SOTA_PLAN.md (section in the trailing comment) ---
BASELINE_MINIDEV = {  # official EX on 500 Mini-Dev rows, 2026-09-23 run, section 0.1
    "overall": 47.6, "simple": 66.2, "moderate": 42.8, "challenging": 32.4,
}
DB_DELTA_VS_BASELINE = {  # gate-1 log, "Every database improved"
    "student_club": 24.4, "european_football_2": 20.9, "superhero": 16.7, "financial": 12.5,
    "thrombosis_prediction": 12.0, "california_schools": 10.0, "codebase_community": 8.8,
    "formula_1": 7.6, "debit_card_specializing": 5.5, "card_games": 4.4, "toxicology": 3.3,
}
MINIDEV_COMMIT = "285272c"
REASONING_LOW = (2.03, -1.5, -6.5, 3.5)  # ratio (+103%), delta, CI: Phase 3a table
REASONING_HIGH = (3.01, -1.5, -6.5, 3.0)  # +201%
DICTIONARY = (1.32, 1.2, -1.2, 4.4)  # +32%: Phase 1 step 2 table
ESCALATION = (2.77, 0.8)  # 0.001379 / 0.000497 uncached: "Cheap-model Pareto round" table


# ------------------------------------------------------------------------------ parsing
def _read(name: str) -> str:
    return (RESULTS / name).read_text(encoding="utf-8")


@dataclass(frozen=True)
class Overall:
    n: int
    ex: float
    p50: float
    p90: float
    repair: float
    cost: float


def overall(report: str) -> Overall:
    m = re.search(
        r"\| overall \| (\d+) \| ([\d.]+)% \| ([\d.]+) \| ([\d.]+) \| ([\d.]+)% \| \$([\d.]+) \|",
        _read(report),
    )
    if not m:
        raise ValueError(f"no overall row in {report}")
    n, ex, p50, p90, rep, cost = m.groups()
    return Overall(int(n), float(ex), float(p50), float(p90), float(rep), float(cost))


@dataclass(frozen=True)
class Flips:
    delta: float
    lo: float
    hi: float
    old_unc: float
    new_unc: float
    old_p50: float
    new_p50: float

    @property
    def ratio(self) -> float:
        return self.new_unc / self.old_unc


def flips(report: str) -> Flips:
    text = _read(report)
    row = re.search(r"\| Row-weighted \| ([+-][\d.]+) \| \[([+-][\d.]+), ([+-][\d.]+)\]", text)
    old = re.search(r"\| old \| [\d.]+ \| ([\d.]+) \| ([\d.]+) \|", text)
    new = re.search(r"\| new \| [\d.]+ \| ([\d.]+) \| ([\d.]+) \|", text)
    if not (row and old and new):
        raise ValueError(f"cannot parse {report}")
    return Flips(*map(float, row.groups()), float(old[1]), float(new[1]), float(old[2]), float(new[2]))


def minidev_breakdown() -> tuple[dict[str, float], list[tuple[str, int, float]]]:
    text = _read("bird_report_minidev_gate1.md")
    by_diff = {
        m[1]: float(m[2])
        for m in re.finditer(r"\| (simple|moderate|challenging|overall) \| \d+ \| ([\d.]+)% \|", text)
    }
    by_db = [
        (m[1], int(m[2]) // 3, float(m[3]))
        for m in re.finditer(r"\| `(\w+)` \| (\d+) \| ([\d.]+)% \|", text)
    ]
    return by_diff, sorted(by_db, key=lambda r: -r[2])


# ------------------------------------------------------------------------------ provenance
@dataclass(frozen=True)
class Run:
    label: str
    run_id: str  # timestamp in benchmark/results/bird_{raw,meta}_<run_id>.*
    report: str  # the committed report whose overall row is this run's headline


# Every number the README headlines comes from one of these runs. Add new runs here.
RUNS: list[Run] = [
    Run("train_dev baseline (product prompt)", "20260924T005317Z", "bird_report_train_dev_baseline.md"),
    Run("train_dev + benchmark profile", "20260924T170715Z", "bird_report_train_dev_1a_full.md"),
    Run("train_dev + quoting and repairs", "20260924T175733Z", "bird_report_train_dev_1abc_full.md"),
    Run("Mini-Dev, gate 1", "20260924T232302Z", "bird_report_minidev_gate1.md"),
    Run("dev_untouched", "20260925T015202Z", "bird_report_dev_untouched_1.md"),
    Run("train_dev, v4p1-flash", "20260926T203859Z", "bird_report_full_v4p1_flash_rerun.md"),
    Run("Mini-Dev, gate 2", "20260926T211555Z", "bird_report_minidev_gate2_v4p1.md"),
    Run("dev_untouched", "20260926T212111Z", "bird_report_dev_untouched_v4p1.md"),
    Run("train_dev, v4p1-flash, clean reproduction", "20260926T212754Z", "bird_report_train_dev_v4p1_clean.md"),
]
GATE1, GATE2, DEV_OLD, DEV_NEW = "20260924T232302Z", "20260926T211555Z", "20260925T015202Z", "20260926T212111Z"
TRAIN_DEV_CLEAN = "20260926T212754Z"  # clean-commit reproduction of the train_dev x2 run


def _meta(run_id: str) -> dict[str, Any]:
    return json.loads((RESULTS / f"bird_meta_{run_id}.json").read_text(encoding="utf-8"))


def provenance_table(runs: list[Run] | None = None) -> str:
    """One row per headline run: when it ran, on which code, data and config."""
    header = ("| Run (UTC) | Set | Model | Answers | Official EX | Commit | Tree | Config | Data |\n"
              "|---|---|---|---:|---:|---|---|---|---|")
    rows = []
    for run in sorted(runs or RUNS, key=lambda r: r.run_id):
        meta, o = _meta(run.run_id), overall(run.report)
        stamp = f"{run.run_id[:4]}-{run.run_id[4:6]}-{run.run_id[6:8]} {run.run_id[9:11]}:{run.run_id[11:13]}"
        tree = "clean" if not meta["git_dirty"] else f"dirty `{meta['code_state_sha256_16'][:8]}`"
        model = meta["config"]["models"][0].rsplit("/", 1)[-1]
        rows.append(
            f"| {stamp} | {run.label} | `{model}` | {o.n:,} | {o.ex:.1f}% | "
            f"`{meta['git_commit'][:7]}` | {tree} | `{meta['config_sha256_16'][:8]}` | "
            f"`{meta['dataset_sha256_16'][:8]}` |"
        )
    return header + "\n" + "\n".join(rows)


def uncached_per_answer(run_id: str) -> float:
    """Mean $/answer if no prompt token were served from cache (the fair cost axis)."""
    from src.costs import cost_usd

    total, n = 0.0, 0
    for line in (RESULTS / f"bird_raw_{run_id}.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        n += 1
        total += sum(cost_usd(c["model"], c["input_tokens"], 0, c["output_tokens"])
                     for c in record.get("llm_calls", []))
    return total / n


def _by_difficulty(report: str) -> dict[str, float]:
    return {m[1]: float(m[2]) for m in re.finditer(
        r"\| (simple|moderate|challenging|overall) \| \d+ \| ([\d.]+)% \|", _read(report))}


def dev_estimate() -> float:
    """Row-weighted EX over Mini-Dev (500 rows) and dev_untouched, ~ BIRD's 1,534-row dev set."""
    mini, dev = overall("bird_report_minidev_gate2_v4p1.md"), overall("bird_report_dev_untouched_v4p1.md")
    return (mini.ex * 500 + dev.ex * dev.n) / (500 + dev.n)


def headline_table() -> str:
    mini, dev = overall("bird_report_minidev_gate2_v4p1.md"), overall("bird_report_dev_untouched_v4p1.md")
    md_d, dv_d = _by_difficulty("bird_report_minidev_gate2_v4p1.md"), _by_difficulty("bird_report_dev_untouched_v4p1.md")
    rows_mini, rows_dev = 500, dev.n
    est = (mini.ex * rows_mini + dev.ex * rows_dev) / (rows_mini + rows_dev)
    um, ud = uncached_per_answer(GATE2), uncached_per_answer(DEV_NEW)
    ue = (um * rows_mini * 3 + ud * rows_dev) / (rows_mini * 3 + rows_dev)
    return "\n".join([
        "| | BIRD Mini-Dev | BIRD dev, untouched | Both, row-weighted |",
        "|---|---:|---:|---:|",
        f"| **Official execution accuracy** | **{mini.ex:.1f}%** | **{dev.ex:.1f}%** | **≈ {est:.1f}%** |",
        f"| Questions × repeats | 500 × 3 | {dev.n:,} × 1 | {rows_mini + rows_dev:,} rows |",
        (f"| Simple / moderate / challenging | {md_d['simple']:.1f} / {md_d['moderate']:.1f} / "
         f"{md_d['challenging']:.1f} | {dv_d['simple']:.1f} / {dv_d['moderate']:.1f} / "
         f"{dv_d['challenging']:.1f} | n/a |"),
        f"| P50 / P90 latency | {mini.p50:.2f}s / {mini.p90:.2f}s | {dev.p50:.2f}s / {dev.p90:.2f}s | n/a |",
        f"| Cost per query, as measured | ${mini.cost:.6f} | ${dev.cost:.6f} | n/a |",
        f"| Cost per query, no prompt cache | ${um:.6f} | ${ud:.6f} | ${ue:.6f} |",
        (f"| Per 1,000 queries: measured / no cache | ${mini.cost * 1000:.2f} / ${um * 1000:.2f} | "
         f"${dev.cost * 1000:.2f} / ${ud * 1000:.2f} | n/a |"),
    ])


def inject(readme: str, name: str, content: str) -> str:
    """Replace the block between <!-- BEGIN generated:name --> and its END marker."""
    pattern = re.compile(rf"(<!-- BEGIN generated:{name} -->\n).*?(<!-- END generated:{name} -->)", re.DOTALL)
    if not pattern.search(readme):
        raise ValueError(f"README has no generated:{name} block")
    return pattern.sub(lambda m: m.group(1) + content + "\n" + m.group(2), readme)


# ------------------------------------------------------------------------------ leaderboard
SHORT = {
    "DataGallery-Text2SQL": "DataGallery-Text2SQL", "Gemini-SQL2": "Gemini-SQL2",
    "Databricks RLVR 32B": "Databricks RLVR 32B", "SQLWeaver-32B": "SQLWeaver-32B",
    "Claude Opus 4.6": "Claude Opus 4.6 (baseline)", "Claude 4.5 Sonnet": "Claude 4.5 Sonnet (baseline)",
    "Arctic-ExCoT-70B": "Arctic-ExCoT-70B", "Arctic-ExCoT-32B": "Arctic-ExCoT-32B",
    "Command A": "Command A", "SFT CodeS-15B": "SFT CodeS-15B", "SFT CodeS-7B": "SFT CodeS-7B",
    "Qwen3-Coder-480B": "Qwen3-Coder-480B (baseline)", "OneSQL-v0.1-Qwen-32B": "OneSQL-v0.1-Qwen-32B",
}


def _label(name: str, size: str) -> str:
    short = _short(name)
    return short if size in ("", "UNK") or size in short else f"{short} ({size})"


def _short(name: str) -> str:
    return next((v for k, v in SHORT.items() if name.startswith(k)), name.split(" ")[0])


def _leaderboard() -> dict[str, Any]:
    return json.loads(LEADERBOARD.read_text(encoding="utf-8"))


def _peers() -> list[tuple[str, list[dict[str, Any]]]]:
    lb = _leaderboard()

    def scored(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in rows if r["dev"] is not None and "Human" not in r["name"]]

    overall_rows, single = scored(lb["overall"]), scored(lb["single_model"])
    return [
        ("All submissions", overall_rows),
        ("Single model, any self-consistency", single),
        ("Single model, no self-consistency", [r for r in single if r["self_consistency"] in ("", "-")]),
    ]


# Estimated serving cost and latency for leaderboard peers (nothing is run; see docs/PEER_ESTIMATES.md).
# Every assumption is a named constant so it can be challenged and changed in one place.
FIREWORKS_TIERS = ((4, 0.10), (16, 0.20), (float("inf"), 0.90))  # $/M tokens by dense params (B), docs.fireworks.ai/serverless/pricing
H100_BW_GBPS, H100_FP8_TFLOPS = 3350.0, 989.0  # SXM5 spec sheet
DECODE_EFFICIENCY = (0.5, 0.9)  # share of memory bandwidth reached while decoding one stream (low, high)
PREFILL_EFFICIENCY = 0.4  # share of peak FP8 FLOPs reached while prefilling
TP_SCALING = 0.85  # bandwidth scaling per extra GPU under tensor parallelism
NETWORK_QUEUE_S = 0.3  # request routing, queueing and network for a hosted call
CLOSED_TTFT_S = (0.5, 1.0)  # assumed time to first token for a hosted frontier API (the published page charts it but gives no value)
# name prefix -> (kind, params in B or (in $/M, out $/M, published output tokens/s)); prices and speeds read 2026-09-26
PEER_SPECS: list[tuple[str, str, Any]] = [
    ("Databricks RLVR 32B", "open", 32),
    ("SQLWeaver-32B", "open", 32),
    ("Claude Opus 4.6", "closed", (5.0, 25.0, 39.0)),  # platform.claude.com pricing; artificialanalysis.ai speed
    ("Arctic-ExCoT-70B", "open", 70),
    ("Arctic-ExCoT-32B", "open", 32),
    ("Claude 4.5 Sonnet", "closed", (3.0, 15.0, 41.0)),
    ("OneSQL-v0.1-Qwen-32B", "open", 32),
    ("Command A", "open", 111),
    ("SFT CodeS-15B", "open", 15),
]
NOT_ESTIMATED = {
    "Qwen3-Coder-480B": "no list price for a 480B MoE on the pricing page used",
    "GLM-4.7": "reasoning model: hidden thinking tokens are undisclosed",
    "DeepSeek-R1": "reasoning model: hidden thinking tokens are undisclosed",
    "Kimi-K2-Thinking": "reasoning model: hidden thinking tokens are undisclosed",
    "SuperSQL": "pipeline and model size are not disclosed",
}


def token_profile() -> tuple[float, float]:
    """Mean input and output tokens per answer, measured on Mini-Dev gate 2 (includes repair calls)."""
    n = tin = tout = 0
    for line in (RESULTS / f"bird_raw_{GATE2}.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        n += 1
        tin += sum(c["input_tokens"] for c in record["llm_calls"])
        tout += sum(c["output_tokens"] for c in record["llm_calls"])
    return tin / n, tout / n


def estimate_peer(spec: tuple[str, str, Any]) -> dict[str, Any]:
    tin, tout = token_profile()
    name, kind, detail = spec
    if kind == "closed":
        p_in, p_out, speed = detail
        cost = (tin * p_in + tout * p_out) / 1e6
        decode = tout / speed
        return {"name": name, "cost": cost, "lat": (CLOSED_TTFT_S[0] + decode, CLOSED_TTFT_S[1] + decode),
                "basis": f"list price ${p_in:g}/${p_out:g} per M; published {speed:g} tok/s"}
    params = float(detail)
    price = next(v for limit, v in FIREWORKS_TIERS if params <= limit)
    cost = (tin + tout) * price / 1e6
    weights_gb = params  # FP8: one byte per parameter
    gpus = max(1, math.ceil(weights_gb * 1.25 / 80))  # leave 25% of an 80 GB GPU for KV cache
    bandwidth = H100_BW_GBPS * gpus * (TP_SCALING if gpus > 1 else 1.0)
    prefill = 2 * params * 1e9 * tin / (PREFILL_EFFICIENCY * H100_FP8_TFLOPS * 1e12 * gpus)
    lat = tuple(NETWORK_QUEUE_S + prefill + tout / (eff * bandwidth / weights_gb) for eff in reversed(DECODE_EFFICIENCY))
    return {"name": name, "cost": cost, "lat": lat,
            "basis": f"{params:g}B dense at ${price:.2f}/M (Fireworks size tier); {gpus} x H100 FP8 roofline"}


def peer_estimates() -> list[dict[str, Any]]:
    out = []
    for spec in PEER_SPECS:
        e = estimate_peer(spec)
        row = next(r for _, rows in _peers()[2:] for r in rows if r["name"].startswith(spec[0]))
        out.append({**e, "dev": row["dev"], "test": row["test"], "size": row["size"]})
    return out


def leaderboard_table() -> str:
    est = dev_estimate()
    mini = overall("bird_report_minidev_gate2_v4p1.md")
    ours_nc = uncached_per_answer(GATE2)
    out = ["| Peer group | Entries with a dev score | Trellis would rank | Best entry (dev / test) |",
           "|---|---:|---:|---|"]
    for label, rows in _peers():
        rank = sum(r["dev"] > est for r in rows) + 1
        best = max(rows, key=lambda r: r["dev"])
        out.append(f"| {label} | {len(rows)} | **#{rank}** of {len(rows) + 1} | "
                   f"{_short(best['name'])} ({best['dev']:.1f} / {best['test']:.1f}) |")
    peers = sorted(peer_estimates(), key=lambda r: -r["dev"])
    out += ["", ("Estimated cost and latency for the identifiable systems in that group. **These are estimates, not runs**: "
            "one call with our measured prompt (about 1,900 input and 75 output tokens), list prices, no prompt cache "
            "on either side, and a roofline model for latency (method and sources in "
            "[`docs/PEER_ESTIMATES.md`](docs/PEER_ESTIMATES.md)). Submitted pipelines often make several calls with longer "
            "prompts, so their real cost is higher."), "",
            "| System | Dev EX | Test EX | Est. cost / query | vs Trellis | Est. latency | vs Trellis |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    trellis = (f"| **Trellis** (measured, not submitted) | **≈ {est:.1f}** | not submitted | **${ours_nc:.5f}** "
               f"(${mini.cost:.5f} cached) | 1× | **{mini.p50:.2f}s** | 1× |")
    inserted = False
    for r in peers:
        if not inserted and r["dev"] < est:
            out.append(trellis)
            inserted = True
        lo, hi = r["lat"]
        out.append(f"| {_label(r['name'], r['size'])} | {r['dev']:.1f} | {r['test']:.1f} | ${r['cost']:.5f} | "
                   f"{r['cost'] / ours_nc:.1f}× | {lo:.1f}–{hi:.1f}s | {lo / mini.p50:.1f}–{hi / mini.p50:.1f}× |")
    if not inserted:
        out.append(trellis)
    return "\n".join(out)


def peer_estimates_doc() -> str:
    est = dev_estimate()
    tin, tout = token_profile()
    ours = uncached_per_answer(GATE2)
    lines = ["# Peer cost and latency estimates", "",
             ("Nothing here was run. Every figure is derived from public information and named assumptions, "
             "regenerated by `scripts/render_readme_assets.py`. Treat latency as roughly ±50% and cost as a "
             "**lower bound**: leaderboard pipelines often make several calls with longer prompts, and the "
             "leaderboard publishes neither cost nor latency."), "",
             "## Method", "",
             (f"- **Token profile:** Trellis's measured mean per answer on Mini-Dev gate 2: {tin:,.0f} input and "
             f"{tout:,.0f} output tokens (includes repair calls). Every peer is priced as one call with that profile."),
             ("- **Cost, closed models:** list price per million tokens (Anthropic pricing page, read 2026-09-26): "
             "Claude Opus 4.6 $5 in / $25 out, Claude Sonnet 4.5 $3 / $15. No prompt cache, matching the "
             "no-cache figure we report for Trellis."),
             ("- **Cost, open models:** Fireworks serverless size tiers (docs.fireworks.ai/serverless/pricing, read "
             "2026-09-26): 4-16B $0.20, over 16B dense $0.90 per million tokens, input and output alike. A "
             "fine-tuned model would normally need a dedicated deployment; the tier price is a same-provider proxy."),
             (f"- **Latency, open models:** `network/queue {NETWORK_QUEUE_S}s + prefill + decode`. Prefill is "
             f"compute-bound: `2 x params x input_tokens / ({PREFILL_EFFICIENCY} x {H100_FP8_TFLOPS:.0f} TFLOPs x GPUs)`. "
             f"Decode is bandwidth-bound: `tokens/s = efficiency x {H100_BW_GBPS:.0f} GB/s x GPUs x scaling / weight GB`, "
             f"efficiency {DECODE_EFFICIENCY[0]}-{DECODE_EFFICIENCY[1]}, FP8 weights, GPUs = enough H100 80 GB to leave "
             f"25% free for KV cache, {TP_SCALING} bandwidth scaling per extra GPU."),
             (f"- **Latency, closed models:** assumed {CLOSED_TTFT_S[0]}-{CLOSED_TTFT_S[1]}s to first token, plus output tokens "
             "divided by the published output speed (Artificial Analysis, read 2026-09-26: Opus 4.6 39 tok/s, "
             "Sonnet 4.5 41 tok/s)."),
             ("- **Sanity check:** the same style of model lands near what we measured for Trellis "
             "(P50 1.36s on Mini-Dev), and we have not tuned any constant to make peers look worse."),
             ("- **Not estimated:** entries whose serving is undisclosed, priced without a public list price, or that "
             "bill hidden reasoning tokens."), "",
             "## The group: single model, no self-consistency", "",
             "| Dev | Test | System | Size | Status |", "|---:|---:|---|---|---|"]
    estimated = {e["name"]: e for e in peer_estimates()}
    for r in sorted(_peers()[2][1], key=lambda r: -r["dev"]):
        key = next((k for k in estimated if r["name"].startswith(k)), None)
        if key:
            e = estimated[key]
            status = f"est. ${e['cost']:.5f}/query ({e['cost'] / ours:.1f}x Trellis), {e['lat'][0]:.1f}-{e['lat'][1]:.1f}s; {e['basis']}"
        else:
            reason = next((v for k, v in NOT_ESTIMATED.items() if r["name"].startswith(k)), "below the comparison range (dev under 58) or size not disclosed")
            status = f"not estimated: {reason}"
        lines.append(f"| {r['dev']:.1f} | {r['test']:.1f} | {_short(r['name'])} | {r['size']} | {status} |")
    lines += ["", (f"Trellis for comparison: ${ours:.5f}/query with no cache (${overall('bird_report_minidev_gate2_v4p1.md').cost:.5f} measured), "
              f"P50 {overall('bird_report_minidev_gate2_v4p1.md').p50:.2f}s, dev estimate about {est:.1f}%.")]
    return "\n".join(lines) + "\n"


def rank_strip_svg() -> str:
    est = dev_estimate()
    peers = _peers()
    w, h, left, right = 760, 300, 210, 30
    lo, hi = 55.0, 80.0

    def px(v: float) -> float:
        return left + (v - lo) / (hi - lo) * (w - left - right)

    body = header("Where Trellis sits on the BIRD dev leaderboard",
                  f"each dot is one submission's dev EX; line = Trellis ≈ {est:.1f}% (local run, not submitted)")
    for v in range(55, 81, 5):
        body += (f'<line x1="{px(v):.1f}" y1="72" x2="{px(v):.1f}" y2="{h - 44}" stroke="{GRID}" stroke-width="1"/>'
                 + t(px(v), h - 28, f"{v}%", 11, MUTED, "middle"))
    for i, (label, rows) in enumerate(peers):
        cy = 108 + i * 68
        above = sum(r["dev"] > est for r in rows)
        body += (t(left - 14, cy - 2, label, 12, FG, "end") + t(left - 14, cy + 14, f"#{above + 1} of {len(rows) + 1}", 12, GREEN, "end", "700"))
        for j, r in enumerate(sorted(rows, key=lambda r: r["dev"])):
            jitter = ((j * 7) % 5 - 2) * 6
            color = GREEN if r["dev"] > est else GREY
            body += f'<circle cx="{px(min(max(r["dev"], lo), hi)):.1f}" cy="{cy + jitter}" r="3.6" fill="{color}" opacity="0.75"/>'
    body += (f'<line x1="{px(est):.1f}" y1="70" x2="{px(est):.1f}" y2="{h - 44}" stroke="{AMBER}" stroke-width="2"/>'
             + t(px(est) + 6, 82, f"Trellis ≈ {est:.1f}%", 12, AMBER, "start", "700"))
    body += (f'<circle cx="{left}" cy="{h - 10}" r="4" fill="{GREEN}"/>' + t(left + 10, h - 6, "above Trellis", 11, MUTED)
             + f'<circle cx="{left + 110}" cy="{h - 10}" r="4" fill="{GREY}"/>' + t(left + 120, h - 6, "at or below", 11, MUTED))
    return svg_doc(w, h, "BIRD dev leaderboard position", f"Trellis at about {est:.1f}% dev EX.", body)


# ------------------------------------------------------------------------------ svg helpers
def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def t(x: float, y: float, s: str, size: int = 13, fill: str = FG, anchor: str = "start",
      weight: str = "400", mono: bool = False) -> str:
    fam = MONO if mono else FONT
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')


def svg_doc(w: int, h: int, title: str, desc: str, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" '
            f'height="{h}" role="img" aria-labelledby="t d"><title id="t">{esc(title)}</title>'
            f'<desc id="d">{esc(desc)}</desc><rect width="{w}" height="{h}" rx="12" fill="{BG}" '
            f'stroke="{GRID}"/>{body}</svg>\n')


def header(title: str, subtitle: str) -> str:
    return t(24, 34, title, 16, weight="600") + t(24, 54, subtitle, 12, MUTED)


# ------------------------------------------------------------------------------ charts
def progress_svg() -> str:
    g1, g2 = _by_difficulty("bird_report_minidev_gate1.md"), _by_difficulty("bird_report_minidev_gate2_v4p1.md")
    counts = {"overall": 500, "simple": 148, "moderate": 250, "challenging": 102}
    w, h, left, right = 760, 430, 150, 100
    span = w - left - right
    body = header("BIRD Mini-Dev: official execution accuracy",
                  "500 questions x 3 repeats per stage; same prompt and data hashes at both gates")
    for i in range(0, 101, 25):
        x = left + span * i / 100
        body += (f'<line x1="{x}" y1="76" x2="{x}" y2="356" stroke="{GRID}" stroke-width="1"/>'
                 + t(x, 372, f"{i}%", 11, MUTED, "middle"))
    y = 84
    for key in ("overall", "simple", "moderate", "challenging"):
        vals = ((BASELINE_MINIDEV[key], GREY, 11), (g1[key], BLUE, 13), (g2[key], GREEN, 17))
        weight = "700" if key == "overall" else "400"
        body += t(left - 12, y + 34, key.capitalize() + ("" if key == "overall" else f" ({counts[key]})"),
                  13, FG, "end", weight)
        yy = y
        for value, color, bar_h in vals:
            body += (f'<rect x="{left}" y="{yy}" width="{span * value / 100:.1f}" height="{bar_h}" rx="3" '
                     f'fill="{color}"/>' + t(left + span * value / 100 + 8, yy + bar_h - 2, f"{value:.1f}%", 11 if bar_h < 17 else 13,
                                             FG if color == GREEN else MUTED, weight="700" if color == GREEN else "400"))
            yy += bar_h + 3
        body += t(w - 24, y + 34, f"+{g2[key] - BASELINE_MINIDEV[key]:.1f} pts", 13, GREEN, "end", "700")
        y += 68
    body += (f'<rect x="{left}" y="398" width="10" height="10" rx="2" fill="{GREY}"/>' + t(left + 16, 407, "2026-09-23 baseline", 11, MUTED)
             + f'<rect x="{left + 150}" y="398" width="10" height="10" rx="2" fill="{BLUE}"/>' + t(left + 166, 407, "gate 1: Phase 1 config, deepseek-v4-flash-0731", 11, MUTED)
             + f'<rect x="{left + 420}" y="398" width="10" height="10" rx="2" fill="{GREEN}"/>' + t(left + 436, 407, "gate 2: deepseek-v4p1-flash", 11, MUTED))
    return svg_doc(w, h, "Mini-Dev accuracy by difficulty",
                   f"Overall {BASELINE_MINIDEV['overall']}% to {g1['overall']}% to {g2['overall']}%.", body)


def _by_db(report: str) -> dict[str, tuple[int, float]]:
    return {m[1]: (int(m[2]) // 3, float(m[3])) for m in re.finditer(r"\| `(\w+)` \| (\d+) \| ([\d.]+)% \|", _read(report))}


def perdb_svg() -> str:
    new, old = _by_db("bird_report_minidev_gate2_v4p1.md"), _by_db("bird_report_minidev_gate1.md")
    order = sorted(new, key=lambda d: -new[d][1])
    w, left = 760, 190
    span = w - left - 190
    h = 100 + 26 * len(order)
    macro = sum(v[1] for v in new.values()) / len(new)
    body = header("Accuracy by database (BIRD Mini-Dev, gate 2)",
                  f"official EX, 3 repeats; database macro {macro:.1f}%; tick = gate 1 (deepseek-v4-flash-0731)")
    y = 82
    for db in order:
        n, ex = new[db]
        delta = ex - old[db][1]
        color = GREEN if delta >= 0 else RED
        body += (t(left - 10, y + 13, db, 12, FG, "end", mono=True)
                 + f'<rect x="{left}" y="{y}" width="{span * ex / 100:.1f}" height="16" rx="3" fill="{BLUE}"/>'
                 + f'<rect x="{left + span * old[db][1] / 100 - 1:.1f}" y="{y - 3}" width="2.5" height="22" fill="{FG}"/>'
                 + t(left + span * max(ex, old[db][1]) / 100 + 10, y + 13, f"{ex:.1f}%", 12, FG, weight="600")
                 + t(w - 24, y + 13, f"{delta:+.1f} vs gate 1  (n={n})", 12, color, "end"))
        y += 26
    return svg_doc(w, h, "Mini-Dev accuracy by database", "Bars sorted by accuracy; tick marks the previous gate.", body)


# ------------------------------------------------------------------------------ tables
def pareto_table() -> str:
    """Full train_dev runs (1,002 answers): the config progression, then the current default."""
    base = overall("bird_report_train_dev_baseline.md")
    f1a = overall("bird_report_train_dev_1a_full.md")
    acc = overall("bird_report_train_dev_1abc_full.md")
    gpt = overall("bird_report_full_gpt_oss_120b.md")
    clean = TRAIN_DEV_CLEAN or "20260926T203859Z"
    cur = overall("bird_report_train_dev_v4p1_clean.md" if TRAIN_DEV_CLEAN else "bird_report_full_v4p1_flash_rerun.md")
    unc = {
        "base": flips("flips_train_dev_baseline_vs_1a.md").old_unc,
        "1a": flips("flips_train_dev_baseline_vs_1a.md").new_unc,
        "acc": flips("flips_train_dev_1a_vs_1abc.md").new_unc,
        "gpt": flips("flips_full_gpt_oss_120b.md").new_unc,
        "cur": uncached_per_answer(clean),
    }
    rows = [
        ("Baseline, product prompt (`deepseek-v4-flash-0731`)", base, unc["base"], "starting point"),
        ("+ benchmark prompt profile", f1a, unc["1a"], "adopted"),
        ("+ quoting + pipeline repairs (the frozen config)", acc, unc["acc"], "adopted"),
        ("**same config on `deepseek-v4p1-flash` (default)**", cur, unc["cur"],
         "**default**: ties here, +5.9 on Mini-Dev"),
        ("`gpt-oss-120b`, low effort, same config", gpt, unc["gpt"], "cheaper and faster; misses the non-inferiority margin"),
    ]
    out = ["| Configuration | Official EX | P50 | P90 | $/query measured | $/query no cache | $ per 1k (no cache) | Verdict |",
           "|---|---:|---:|---:|---:|---:|---:|---|"]
    for name, o, u, verdict in rows:
        first = name.startswith("Baseline")
        p50, p90 = ("n/v", "n/v") if first else (f"{o.p50:.2f}s", f"{o.p90:.2f}s")
        out.append(f"| {name} | {o.ex:.1f}% | {p50} | {p90} | ${o.cost:.6f} | ${u:.6f} | ${u * 1000:.2f} | {verdict} |")
    return "\n".join(out)


def pilot_table() -> str:
    pro_report, pro_flips = overall("bird_report_pilot_3_model_dsv4pro.md"), flips("flips_pilot_3_model_dsv4pro.md")
    control_ex = pro_report.ex - pro_flips.delta  # the control rows are shared by every pilot
    spec = [
        ("deepseek-v4p1-flash", "bird_report_pilot_3_model_dsv4p1flash.md", "flips_pilot_3_model_dsv4p1flash.md"),
        ("deepseek-v4-pro-0813", "bird_report_pilot_3_model_dsv4pro.md", "flips_pilot_3_model_dsv4pro.md"),
        ("glm-5p3-flash, low effort", "bird_report_pilot_glm5p3_flash_low.md", "flips_pilot_glm5p3_flash_low.md"),
        ("glm-5p3-flash, default", "bird_report_pilot_3_model_glm5p3flash.md", "flips_pilot_3_model_glm5p3flash.md"),
        ("+ few-shot (BM25, k=3)", "bird_report_pilot_fewshot3.md", "flips_pilot_fewshot3.md"),
    ]
    out = ["| Variant (100-question pilot x 2) | Official EX | vs control (95% CI) | P50 | P90 | $/query uncached |",
           "|---|---:|---|---:|---:|---:|",
           f"| Current configuration (control) | {control_ex:.1f}% | n/a | {pro_flips.old_p50:.2f}s | n/a | ${pro_flips.old_unc:.6f} |"]
    for name, rep, fl in spec:
        o, f = overall(rep), flips(fl)
        out.append(f"| {name} | {o.ex:.1f}% | {f.delta:+.1f} [{f.lo:+.1f}, {f.hi:+.1f}] | {o.p50:.2f}s | {o.p90:.2f}s | ${f.new_unc:.6f} |")
    return "\n".join(out)


# ------------------------------------------------------------------------------ frontier + ledger
@dataclass(frozen=True)
class Point:
    name: str
    ex: float
    cost: float  # $/query with no prompt cache
    p50: float
    dx: int = 12
    dy: int = 4
    anchor: str = "start"


def frontier_points() -> list[Point]:
    """The same 100 stratified train_dev questions x 2 repeats for every variant, so they are comparable."""
    control = flips("flips_pilot_3_model_dsv4pro.md")
    control_ex = overall("bird_report_pilot_3_model_dsv4pro.md").ex - control.delta

    def pt(name: str, report: str, flip: str, **kw: Any) -> Point:
        return Point(name, overall(report).ex, flips(flip).new_unc, overall(report).p50, **kw)

    return [
        Point("Previous snapshot (frozen config)", control_ex, control.old_unc, control.old_p50, 0, -46, "middle"),
        pt("deepseek-v4p1-flash (default)", "bird_report_pilot_3_model_dsv4p1flash.md", "flips_pilot_3_model_dsv4p1flash.md", dx=18, dy=4, anchor="start"),
        pt("gpt-oss-120b", "bird_report_pilot_3_model_gptoss120b.md", "flips_pilot_3_model_gptoss120b.md", dx=0, dy=34, anchor="middle"),
        pt("glm-5p3-flash, low effort", "bird_report_pilot_glm5p3_flash_low.md", "flips_pilot_glm5p3_flash_low.md", dx=0, dy=-24, anchor="middle"),
        pt("+ few-shot", "bird_report_pilot_fewshot3.md", "flips_pilot_fewshot3.md", dx=16, dy=4, anchor="start"),
        pt("deepseek-v4-pro", "bird_report_pilot_3_model_dsv4pro.md", "flips_pilot_3_model_dsv4pro.md", dx=0, dy=-24, anchor="middle"),
        pt("glm-5p3-flash, default", "bird_report_pilot_3_model_glm5p3flash.md", "flips_pilot_3_model_glm5p3flash.md", dx=0, dy=0, anchor="middle"),
        Point("reasoning: low", overall("bird_report_pilot_3a_low.md").ex, control.old_unc * REASONING_LOW[0], overall("bird_report_pilot_3a_low.md").p50, 0, 34, "middle"),
        Point("reasoning: high", overall("bird_report_pilot_3a_high.md").ex, control.old_unc * REASONING_HIGH[0], overall("bird_report_pilot_3a_high.md").p50, 0, 56, "middle"),
    ]


def pareto_optimal(points: list[Point]) -> set[str]:
    """Not beaten on all of quality (up), cost (down) and P50 (down) by any other point."""
    keep = set()
    for a in points:
        beaten = any(b is not a and b.ex >= a.ex and b.cost <= a.cost and b.p50 <= a.p50
                     and (b.ex > a.ex or b.cost < a.cost or b.p50 < a.p50) for b in points)
        if not beaten:
            keep.add(a.name)
    return keep


def frontier_svg() -> str:
    pts = frontier_points()
    best = pareto_optimal(pts)
    w, h, x0, x1, y0, y1 = 900, 520, 80, 860, 84, 430
    lo_c, hi_c, lo_y, hi_y = 0.00018, 0.0035, 64.0, 74.0

    def px(c: float) -> float:
        return x0 + (math.log(c) - math.log(lo_c)) / (math.log(hi_c) - math.log(lo_c)) * (x1 - x0)

    def py(v: float) -> float:
        return y1 - (v - lo_y) / (hi_y - lo_y) * (y1 - y0)

    body = header("Quality, cost and latency: the same 100 questions, every variant",
                  "official EX (y, +/-4 pts at 95%) vs cost per query with no prompt cache (x, log); bubble area = P50 latency")
    for v in range(64, 75, 2):
        body += (f'<line x1="{x0}" y1="{py(v):.1f}" x2="{x1}" y2="{py(v):.1f}" stroke="{GRID}" stroke-width="0.7"/>'
                 + t(x0 - 10, py(v) + 4, f"{v}%", 11, MUTED, "end"))
    for c, label in ((0.0002, "$0.0002"), (0.0005, "$0.0005"), (0.001, "$0.001"), (0.002, "$0.002"), (0.003, "$0.003")):
        body += (f'<line x1="{px(c):.1f}" y1="{y0}" x2="{px(c):.1f}" y2="{y1}" stroke="{GRID}" stroke-width="0.7"/>'
                 + t(px(c), y1 + 18, label, 11, MUTED, "middle"))
    for p in pts:
        cx = px(p.cost)
        if p.ex < lo_y:  # off the scale: pin to the floor and say so
            body += (f'<path d="M{cx - 6:.1f},{y1 - 16} L{cx + 6:.1f},{y1 - 16} L{cx:.1f},{y1 - 4} Z" fill="{GREY}"/>'
                     + t(cx + 12, y1 - 6, f"{p.name}: {p.ex:.1f}% ({p.p50:.2f}s), off scale", 11, MUTED))
            continue
        r = 5 + 3.2 * math.sqrt(p.p50)
        col = GREEN if p.name in best else GREY
        body += (f'<circle cx="{cx:.1f}" cy="{py(p.ex):.1f}" r="{r:.1f}" fill="{col}" fill-opacity="{0.35 if p.name in best else 0.18}" '
                 f'stroke="{col}" stroke-width="1.8"/>'
                 + t(cx + p.dx, py(p.ex) + p.dy, f"{p.name}  ({p.p50:.2f}s)", 11, FG if p.name in best else MUTED, p.anchor))
    body += t((x0 + x1) / 2, y1 + 42, "cost per query, no prompt cache (log scale)", 12, MUTED, "middle")
    body += (f'<circle cx="80" cy="{h - 22}" r="5" fill="{GREEN}" fill-opacity="0.35" stroke="{GREEN}" stroke-width="1.8"/>'
             + t(92, h - 18, "not beaten on quality, cost and latency together", 11, MUTED)
             + f'<circle cx="420" cy="{h - 22}" r="5" fill="{GREY}" fill-opacity="0.18" stroke="{GREY}" stroke-width="1.8"/>'
             + t(432, h - 18, "beaten by another variant on all three", 11, MUTED))
    return svg_doc(w, h, "Quality, cost and latency of every variant tested",
                   "Pareto view over the same 100 stratified questions.", body)


def ledger_table() -> str:
    f1a, f1bc = flips("flips_train_dev_baseline_vs_1a.md"), flips("flips_train_dev_1a_vs_1abc.md")
    v_train, v_mini = flips("flips_full_v4p1_flash.md"), flips("flips_minidev_gate1_vs_gate2_v4p1.md")
    few, gpt = flips("flips_pilot_fewshot3.md"), flips("flips_full_gpt_oss_120b.md")
    pro, glm = flips("flips_pilot_3_model_dsv4pro.md"), flips("flips_pilot_glm5p3_flash_low.md")

    def d(f: Flips) -> str:
        return f"{f.delta:+.1f} [{f.lo:+.1f}, {f.hi:+.1f}]"

    def cost(f: Flips) -> str:
        return f"{(f.ratio - 1) * 100:+.0f}% cost, P50 {f.old_p50:.2f} → {f.new_p50:.2f}s"

    return "\n".join([
        "| Change | Δ official EX (95% CI) | Cost, latency | Verdict |",
        "|---|---|---|---|",
        f"| Benchmark prompt profile | **{d(f1a)}** | {cost(f1a)} | ✅ adopted |",
        f"| Quoting + pipeline repairs | {d(f1bc)}; macro **+3.9** | {cost(f1bc)} | ⚠️ borderline, adopted after audit |",
        f"| `deepseek-v4p1-flash` | train_dev {d(v_train)}; **Mini-Dev {d(v_mini)}** | {cost(v_mini)} on Mini-Dev | ✅ default: ties on train_dev, wins on the harder set |",
        f"| Reasoning, low / high | {REASONING_LOW[1]:+.1f} / {REASONING_HIGH[1]:+.1f} | +103% / +201% cost, P50 4.9s / 5.9s | ❌ overthinks BIRD's literal gold |",
        f"| More context: dictionary CSVs / retrieved few-shot | {DICTIONARY[1]:+.1f} / {few.delta:+.1f} | +32% / {(few.ratio - 1) * 100:+.0f}% cost, P50 to 1.5s / {few.new_p50:.1f}s | ❌ below the bar |",
        f"| Other models: `gpt-oss-120b` / `deepseek-v4-pro` / `glm-5p3-flash` | {gpt.delta:+.1f} / {pro.delta:+.1f} / {glm.delta:+.1f} | {(gpt.ratio - 1) * 100:+.0f}% / {(pro.ratio - 1) * 100:+.0f}% / {(glm.ratio - 1) * 100:+.0f}% cost | ❌ none clears the bar; `gpt-oss-120b` is the cheaper, faster alternative |",
    ])


# ------------------------------------------------------------------------------ CLI captures
QUESTIONS = [
    ("hero", "What are the top 5 best-selling genres by total sales?"),
    ("unsupported", "What's the weather in Paris today?"),
    ("destructive", "Delete all customers from Brazil"),
]


async def capture(model_override: str | None, effort: str | None) -> None:
    from dotenv import load_dotenv

    from src.agent import Agent
    from src.conversation import ConversationContext
    from src.costs import DEFAULT_MODEL, get_shared_budget
    from src.db import connect_readonly
    from src.schema import get_schema

    load_dotenv(ROOT / ".env")
    db_path = ROOT / "data" / "Chinook.db"
    model = model_override or os.getenv("FIREWORKS_MODEL", DEFAULT_MODEL)
    guard = get_shared_budget(float(os.getenv("FIREWORKS_BUDGET_USD", "6.00")))
    conn = connect_readonly(db_path)
    options = {"reasoning_effort": effort} if effort else None
    agent = Agent(model, conn, guard, db_path=db_path, request_options=options)
    out: dict[str, Any] = {"captured": datetime.now(UTC).date().isoformat(), "model": model, "cases": {}}
    await agent.ask(QUESTIONS[0][1], ConversationContext(get_schema(db_path)))  # warm-up, discarded
    for key, question in QUESTIONS:
        ctx = ConversationContext(get_schema(db_path))
        r = await agent.ask(question, ctx)
        out["cases"][key] = {
            "question": question, "response_type": r.response_type, "message": r.message,
            "sql": r.sql, "columns": r.columns, "rows": [list(x) for x in (r.rows or [])],
            "error": r.error, "error_category": r.error_category, "repaired": r.repaired,
            "input_tokens": r.input_tokens, "cached_tokens": r.cached_tokens,
            "output_tokens": r.output_tokens, "cost_usd": r.cost_usd,
            "t_total_ms": r.t_total_ms, "shared_remaining": guard.remaining,
        }
        print(f"captured {key}: {r.response_type} ${r.cost_usd:.6f}")
    conn.close()
    FIXTURES.parent.mkdir(parents=True, exist_ok=True)
    FIXTURES.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def _result(case: dict[str, Any]) -> Any:
    from src.agent import AgentResult
    from src.llm import LLMResult

    call = LLMResult("", case["input_tokens"], case["cached_tokens"], case["output_tokens"],
                     case["t_total_ms"], 0.0, "", case["cost_usd"])
    return AgentResult(
        question=case["question"], response_type=case["response_type"], message=case["message"],
        sql=case["sql"], columns=case["columns"], rows=[tuple(x) for x in case["rows"]] or None,
        error=case["error"], error_category=case["error_category"], repaired=case["repaired"],
        llm_calls=[call], t_total_ms=case["t_total_ms"],
    )


def cli_capture(name: str, cases: list[dict[str, Any]], banner: bool, model: str) -> None:
    from src import cli
    from src.schema import table_count

    console = Console(record=True, width=100, file=io.StringIO(), force_terminal=True,
                      color_system="truecolor", legacy_windows=False)
    cli.console = console  # draw with the product's own renderer
    if banner:
        console.print(Panel(  # mirrors the banner printed by src.cli._run
            f"Model: {model}\nDatabase: data/Chinook.db\n"
            f"Tables: {table_count(ROOT / 'data' / 'Chinook.db')}\n"
            f"Shared remaining: ${cases[0]['shared_remaining']:.4f}", title="Trellis"))
    for case in cases:
        console.print(f"[bold cyan]Question:> [/bold cyan]{case['question']}")
        cli._render(_result(case), case["shared_remaining"])
    (ASSETS / f"{name}.svg").write_text(
        console.export_svg(title="uv run trellis", theme=GITHUB_DARK), encoding="utf-8")


def render_captures() -> None:
    from src.db import is_safe

    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    cases, model = data["cases"], data["model"].rsplit("/", 1)[-1]
    cli_capture("cli-hero", [cases["hero"]], True, model)
    cli_capture("cli-refusals", [cases["unsupported"], cases["destructive"]], False, model)
    # The model refuses destructive requests before any SQL exists. To show the second,
    # independent layer, feed the AST guard the statement a misbehaving model could emit.
    sql = "DELETE FROM Customer WHERE Country = 'Brazil';"
    safe, reason = is_safe(sql, db_path=ROOT / "data" / "Chinook.db")
    assert not safe
    simulated = {**cases["destructive"], "response_type": "query", "sql": sql, "message": None,
                 "error": reason, "error_category": "safety-rejected", "rows": [],
                 "cost_usd": 0.0, "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0,
                 "t_total_ms": 0.4}
    cli_capture("cli-safety", [simulated], False, model)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--capture", action="store_true", help="re-record CLI fixtures (live API)")
    parser.add_argument("--model", help="model for --capture (default: FIREWORKS_MODEL or the project default)")
    parser.add_argument("--reasoning-effort", help="reasoning_effort for --capture, e.g. none")
    args = parser.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    if args.capture:
        asyncio.run(capture(args.model, args.reasoning_effort))
    render_captures()
    for name, svg in (("progress", progress_svg()), ("per-database", perdb_svg()),
                      ("frontier", frontier_svg()), ("leaderboard", rank_strip_svg())):
        (ASSETS / f"{name}.svg").write_text(svg, encoding="utf-8")
    (ROOT / "docs" / "PROVENANCE.md").write_text(
        "# Provenance\n\nEvery headline number in the README comes from one run below. "
        "Generated by `scripts/render_readme_assets.py` from the run sidecars in `benchmark/results/`.\n\n"
        "- **Run (UTC)** is when the run finished, and is the id in `bird_raw_<id>.jsonl` and `bird_meta_<id>.json`.\n"
        "- **Tree** `clean` means the run used exactly that commit; `dirty <hash>` means uncommitted edits, "
        "pinned by the hash but not recreatable from the commit alone.\n"
        "- **Config** hashes the model, prompt profile, quoting, repairs, temperature, token limit, reasoning "
        "effort and timeout; **Data** hashes the question file.\n\n" + provenance_table() + "\n", encoding="utf-8")
    (ROOT / "docs" / "PEER_ESTIMATES.md").write_text(peer_estimates_doc(), encoding="utf-8")
    (ASSETS / "generated_tables.md").write_text(
        "## Full train_dev runs\n\n" + pareto_table() + "\n\n## Pilots\n\n" + pilot_table() + "\n", encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name, content in (("headline", headline_table()), ("leaderboard", leaderboard_table()),
                          ("pareto", pareto_table()), ("ledger", ledger_table())):
        readme = inject(readme, name, content)
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    print(f"wrote assets to {ASSETS.relative_to(ROOT)} and refreshed README tables")


if __name__ == "__main__":
    main()

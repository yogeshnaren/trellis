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


@dataclass(frozen=True)
class Change:
    name: str
    ratio: float
    delta: float
    lo: float | None
    hi: float | None
    status: str  # adopted | borderline | pending | rejected
    dx: int = 10
    dy: int = 4
    anchor: str = "start"


def changes() -> list[Change]:
    f1a = flips("flips_train_dev_baseline_vs_1a.md")
    f1bc = flips("flips_train_dev_1a_vs_1abc.md")
    gpt = flips("flips_full_gpt_oss_120b.md")
    pro = flips("flips_pilot_3_model_dsv4pro.md")
    v4p1 = flips("flips_full_v4p1_flash.md")
    glm_low = flips("flips_pilot_glm5p3_flash_low.md")
    glm_def = flips("flips_pilot_3_model_glm5p3flash.md")
    few = flips("flips_pilot_fewshot3.md")
    return [
        Change("Benchmark prompt profile", f1a.ratio, f1a.delta, f1a.lo, f1a.hi, "adopted", -12, 4, "end"),
        Change("Quoting + pipeline repairs", f1bc.ratio, f1bc.delta, f1bc.lo, f1bc.hi, "borderline", -10, -11, "end"),
        Change("v4p1-flash (full run)", v4p1.ratio, v4p1.delta, v4p1.lo, v4p1.hi, "tie", 14, 26, "start"),
        Change("Dictionary CSVs", DICTIONARY[0], DICTIONARY[1], DICTIONARY[2], DICTIONARY[3], "rejected", 14, -30, "start"),
        Change("Few-shot (BM25, k=3)", few.ratio, few.delta, few.lo, few.hi, "rejected", -9, 81, "start"),
        Change("gpt-oss-120b (full run)", gpt.ratio, gpt.delta, gpt.lo, gpt.hi, "rejected", 0, 59, "middle"),
        Change("glm-5p3-flash, low", glm_low.ratio, glm_low.delta, glm_low.lo, glm_low.hi, "rejected", -37, -79, "start"),
        Change("glm-5p3-flash, default", glm_def.ratio, glm_def.delta, glm_def.lo, glm_def.hi, "rejected", 12, 4, "start"),
        Change("Reasoning: low", REASONING_LOW[0], REASONING_LOW[1], REASONING_LOW[2], REASONING_LOW[3], "rejected", 0, 98, "middle"),
        Change("Reasoning: high", REASONING_HIGH[0], REASONING_HIGH[1], REASONING_HIGH[2], REASONING_HIGH[3], "rejected", 0, 98, "middle"),
        Change("Escalate on disagreement", ESCALATION[0], ESCALATION[1], None, None, "rejected", 0, -64, "middle"),
        Change("v4-pro", pro.ratio, pro.delta, pro.lo, pro.hi, "rejected", 0, -65, "middle"),
    ]


def pareto_svg() -> str:
    w, h = 900, 540
    x0, x1, y0, y1 = 80, 860, 84, 450
    lo_r, hi_r, lo_y, hi_y = 0.5, 7.0, -9.0, 14.0

    def px(r: float) -> float:
        return x0 + (math.log(r) - math.log(lo_r)) / (math.log(hi_r) - math.log(lo_r)) * (x1 - x0)

    def py(v: float) -> float:
        return y1 - (v - lo_y) / (hi_y - lo_y) * (y1 - y0)

    body = header("Every change tested: quality gain vs. cost",
                  "change in official EX (points, 95% CI) against cost multiple at uncached prices; y-axis clipped at -9")
    for v in range(-5, 15, 5):
        body += (f'<line x1="{x0}" y1="{py(v):.1f}" x2="{x1}" y2="{py(v):.1f}" stroke="{GRID}" '
                 f'stroke-width="{1.6 if v == 0 else 0.6}"/>' + t(x0 - 10, py(v) + 4, f"{v:+d}" if v else "0", 11, MUTED, "end"))
    for r in (0.5, 1, 2, 4, 6):
        body += (f'<line x1="{px(r):.1f}" y1="{y0}" x2="{px(r):.1f}" y2="{y1}" stroke="{GRID}" stroke-width="0.6"/>'
                 + t(px(r), y1 + 18, f"{r:g}x", 11, MUTED, "middle"))
    # the acceptance bar: 1.5 pts plus 1 pt per +50% cost (latency term omitted, so a floor)
    need = lambda r: 1.5 + max(0.0, (r - 1) * 2)
    grid = [lo_r * (hi_r / lo_r) ** (i / 120) for i in range(121)]
    pts = " ".join(f"{px(r):.1f},{py(need(r)):.1f}" for r in grid if need(r) <= hi_y)
    body += (f'<polyline points="{pts}" fill="none" stroke="{AMBER}" stroke-width="1.4" stroke-dasharray="5 4"/>'
             + t(px(5.0) - 10, py(need(5.0)) - 6, "minimum required gain (cost term)", 11, AMBER, "end"))
    colors = {"adopted": GREEN, "borderline": AMBER, "tie": BLUE, "rejected": RED}
    for c in changes():
        col, cx, cy = colors[c.status], px(c.ratio), py(c.delta)
        if c.delta < lo_y:  # off the scale: pin to the floor and say so in the label
            body += (f'<path d="M{cx - 6:.1f},{y1 - 14} L{cx + 6:.1f},{y1 - 14} L{cx:.1f},{y1 - 3} Z" fill="{col}"/>'
                     + f'<line x1="{cx:.1f}" y1="{y1 - 14}" x2="{cx:.1f}" y2="{py(c.hi or lo_y):.1f}" stroke="{col}" stroke-width="1.5" opacity="0.55"/>'
                     + t(cx + 12, y1 - 6, f"{c.name}: {c.delta:+.1f} (off scale)", 11, FG))
            continue
        if c.lo is not None and c.hi is not None:
            body += (f'<line x1="{cx:.1f}" y1="{py(c.lo):.1f}" x2="{cx:.1f}" y2="{py(c.hi):.1f}" '
                     f'stroke="{col}" stroke-width="1.5" opacity="0.55"/>')
        fill = col if c.status in {"adopted", "borderline"} else BG
        body += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="{fill}" stroke="{col}" stroke-width="2"/>'
                 + t(cx + c.dx, cy + c.dy, c.name, 11, FG, c.anchor))
    body += t((x0 + x1) / 2, y1 + 42, "cost per answer relative to the configuration it was compared with (log scale)", 12, MUTED, "middle")
    for i, (label, col) in enumerate((("adopted", GREEN), ("borderline, audited", AMBER),
                                      ("tied on train_dev, better on Mini-Dev: default", BLUE), ("rejected", RED))):
        lx = 80 + i * 150 + (i > 2) * 130
        body += f'<circle cx="{lx}" cy="{h - 22}" r="5" fill="{col}"/>' + t(lx + 12, h - 18, label, 11, MUTED)
    return svg_doc(w, h, "Quality gain versus cost for every tested change",
                   "Only changes above the dashed line were adopted.", body)


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
    for name, svg in (("progress", progress_svg()), ("per-database", perdb_svg()), ("pareto", pareto_svg())):
        (ASSETS / f"{name}.svg").write_text(svg, encoding="utf-8")
    (ASSETS / "generated_tables.md").write_text(
        "## Full train_dev runs\n\n" + pareto_table() + "\n\n## Pilots\n\n" + pilot_table()
        + "\n\n## Provenance\n\n" + provenance_table() + "\n", encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name, content in (("headline", headline_table()), ("pareto", pareto_table()),
                          ("provenance", provenance_table())):
        readme = inject(readme, name, content)
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    print(f"wrote assets to {ASSETS.relative_to(ROOT)} and refreshed README tables")


if __name__ == "__main__":
    main()

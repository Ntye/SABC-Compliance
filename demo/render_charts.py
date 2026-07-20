#!/usr/bin/env python3
"""Render the results-chapter figures in the CRICLO dashboard's palette.

Produces:
  • posture_chart.png  — compliance posture before vs after enforcement
  • latency_chart.png   — remediation-latency distributions, closed loop vs
                          scheduled sweep at the same tier

Data:
  • Latency: a CSV with columns `path,detection_s,remediation_s` where `path`
    is `closed_loop` or `scheduled_sweep` (the header measure_latency.py writes).
    `--demo-data` writes a seeded sample criclo_latency.csv so the figures render
    before you have real trials.
  • Posture: two numbers, `--before` / `--after` (defaults 49 → 88).

Palette is taken from the app: brand crimson #C0281F, blue #1D4ED8, and the
score bands (red <70, amber <90, green ≥90) — validated for colour-vision
separation with the dataviz palette checker.

Usage:
  python3 render_charts.py --demo-data          # write sample CSV + both PNGs
  python3 render_charts.py --latency-csv criclo_latency.csv --before 49 --after 88
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ── Dashboard palette ─────────────────────────────────────────────────────────
BRAND   = "#C0281F"   # closed loop (the platform's own fast path)
SWEEP   = "#1D4ED8"   # scheduled sweep (distinct cool hue; CVD-validated pair)
RED     = "#DC2626"   # score band < 70
AMBER   = "#F59E0B"   # score band 70–89
GREEN   = "#16A34A"   # score band ≥ 90 / target
INK     = "#111827"   # primary text
SUB     = "#4B5563"   # secondary text
MUTED   = "#9CA3AF"   # de-emphasised text
GRID    = "#E5E7EB"   # recessive grid
SURFACE = "#FFFFFF"

plt.rcParams.update({
    "font.family": ["DM Sans", "DejaVu Sans", "sans-serif"],
    "font.size": 11,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.linewidth": 1.0,
    "text.color": INK,
    "axes.labelcolor": SUB,
    "xtick.color": SUB,
    "ytick.color": SUB,
    "svg.fonttype": "none",
})


def _band(v: float) -> str:
    return GREEN if v >= 90 else AMBER if v >= 70 else RED


def _despine(ax, keep=("left", "bottom")):
    for side, sp in ax.spines.items():
        sp.set_visible(side in keep)


# ── Posture: before vs after ──────────────────────────────────────────────────
def posture_chart(before: float, after: float, out: str, title: str) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 4.4), dpi=200)
    xs = [0, 1]
    vals = [before, after]
    colors = [_band(before), _band(after)]

    ax.bar(xs, vals, width=0.56, color=colors, zorder=3, edgecolor=SURFACE, linewidth=1.5)
    # Rounded caps on the data-ends (4px feel), same colour as the bar.
    for x, v, c in zip(xs, vals, colors):
        ax.add_patch(FancyBboxPatch((x - 0.28, v - 1.2), 0.56, 2.4,
                     boxstyle="round,pad=0,rounding_size=0.12", mutation_aspect=0.5,
                     linewidth=0, facecolor=c, zorder=4, clip_on=False))
        ax.text(x, v + 2.5, f"{v:.0f}%", ha="center", va="bottom",
                fontsize=15, fontweight="bold", color=c, zorder=5)

    # Target line.
    ax.axhline(90, color=GREEN, lw=1.4, ls=(0, (4, 3)), zorder=2, alpha=0.8)
    ax.text(1.46, 90, "Target ≥ 90%", va="center", ha="left",
            fontsize=9, color=GREEN, alpha=0.9)

    # Delta annotation.
    delta = after - before
    ax.annotate("", xy=(1, after - 3), xytext=(0, before + 3),
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.4,
                                connectionstyle="arc3,rad=-0.25"), zorder=2)
    ax.text(0.5, max(before, after) + 9, f"+{delta:.0f} pts",
            ha="center", va="bottom", fontsize=12, fontweight="bold", color=INK)

    ax.set_xticks(xs)
    ax.set_xticklabels(["Before enforcement", "After enforcement"], fontsize=11, color=INK)
    ax.set_ylabel("Applicable controls passing (%)", fontsize=10)
    ax.set_ylim(0, 108)
    ax.set_xlim(-0.6, 1.9)
    ax.set_yticks(range(0, 101, 20))
    ax.grid(axis="y", color=GRID, lw=0.9, zorder=0)
    _despine(ax)
    ax.set_title(title, fontsize=13, fontweight="bold", color=INK, loc="left", pad=12)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"  wrote {out}")


# ── Latency: closed loop vs scheduled sweep ───────────────────────────────────
def latency_chart(groups: dict[str, list[float]], out: str, title: str) -> None:
    order = [("closed_loop", "Closed loop", BRAND), ("scheduled_sweep", "Scheduled sweep", SWEEP)]
    order = [g for g in order if groups.get(g[0])]
    fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
    positions = list(range(len(order), 0, -1))   # first group on top

    for pos, (key, label, color) in zip(positions, order):
        data = groups[key]
        bp = ax.boxplot(data, positions=[pos], vert=False, widths=0.5,
                        patch_artist=True, showfliers=False, zorder=3,
                        medianprops=dict(color=color, lw=2.2),
                        boxprops=dict(facecolor=color + "22", edgecolor=color, lw=1.6),
                        whiskerprops=dict(color=color, lw=1.4),
                        capprops=dict(color=color, lw=1.4))
        # Jittered raw points for honesty (small N).
        jit = [pos + random.uniform(-0.13, 0.13) for _ in data]
        ax.scatter(data, jit, s=22, color=color, alpha=0.45,
                   edgecolor=SURFACE, linewidth=0.6, zorder=4)
        med = statistics.median(data)
        ax.text(med, pos + 0.32, f"median {med:.1f} s", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=color)

    ax.set_yticks(positions)
    ax.set_yticklabels([lbl for _, lbl, _ in order], fontsize=11, color=INK)
    ax.set_xscale("log")
    ax.set_xlabel("Remediation latency — seconds (log scale)", fontsize=10)
    ax.set_ylim(0.4, len(order) + 0.7)
    ax.grid(axis="x", which="both", color=GRID, lw=0.8, zorder=0)
    _despine(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)
    ax.set_title(title, fontsize=13, fontweight="bold", color=INK, loc="left", pad=12)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"  wrote {out}")


# ── Data ──────────────────────────────────────────────────────────────────────
def read_latency(path: str) -> dict[str, list[float]]:
    groups: dict[str, list[float]] = {"closed_loop": [], "scheduled_sweep": []}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            g = (row.get("path") or "").strip()
            v = row.get("remediation_s")
            if g in groups and v not in (None, ""):
                groups[g].append(float(v))
    return groups


def write_demo_csv(path: str, sweep_interval: float = 900.0, n: int = 20) -> None:
    """Seeded sample: closed-loop measured-like, scheduled-sweep = uniform over
    the sweep interval (a change lands anywhere within one sweep window)."""
    random.seed(42)
    rows = []
    for i in range(1, n + 1):
        det = round(random.uniform(0.8, 2.6), 3)
        rem = round(random.gauss(11.5, 2.6), 3)             # closed loop: seconds
        rows.append(("closed_loop", i, det, max(6.0, rem)))
    for i in range(1, n + 1):
        det = round(random.uniform(0.8, 2.6), 3)
        rem = round(random.uniform(0.06 * sweep_interval, sweep_interval), 3)  # waits for the sweep
        rows.append(("scheduled_sweep", i, det, rem))
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "trial", "detection_s", "remediation_s", "violation"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], "True"])
    print(f"  wrote {path}  (seeded sample — replace with measure_latency.py output)")


def summarise(groups):
    def p95(xs):
        s = sorted(xs); k = (len(s) - 1) * 0.95; lo = int(k)
        return s[lo] + (s[min(lo + 1, len(s) - 1)] - s[lo]) * (k - lo)
    print("\nLatency summary (for Table 5.3):")
    for key, label in [("closed_loop", "Closed loop"), ("scheduled_sweep", "Scheduled sweep")]:
        xs = groups.get(key) or []
        if xs:
            print(f"  {label:16s} remediation median={statistics.median(xs):.1f}s  p95={p95(xs):.1f}s  n={len(xs)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency-csv", default="criclo_latency.csv")
    ap.add_argument("--before", type=float, default=49)
    ap.add_argument("--after", type=float, default=88)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--sweep-interval", type=float, default=900.0,
                    help="sweep window (s) used only when --demo-data synthesises the sweep path")
    ap.add_argument("--demo-data", action="store_true",
                    help="write a seeded sample criclo_latency.csv first")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    if args.demo_data or not os.path.exists(args.latency_csv):
        write_demo_csv(args.latency_csv, args.sweep_interval)

    groups = read_latency(args.latency_csv)
    posture_chart(args.before, args.after,
                  os.path.join(args.out_dir, "posture_chart.png"),
                  "Compliance posture — before and after enforcement")
    latency_chart(groups,
                  os.path.join(args.out_dir, "latency_chart.png"),
                  "Remediation latency — closed loop vs scheduled sweep (same tier)")
    summarise(groups)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Charts + summary for the blog post.

  scripts/plots.py [--sweep results/smoke] [--timed results/timed-go1.23-go1.27.json]

Writes results/plots/*.png|svg and results/summary.md.
  *-by-version   small multiples, one panel per program, go1.2 -> go1.27
                 (sweep data: one full-size run per version)
  go1.23-vs-go1.27  % change in median elapsed, interleaved timed runs
"""
import argparse
import glob
import json
import math
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# reference palette (light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e6e5e1"
SERIES = "#2a78d6"   # categorical slot 1 / sequential blue
FASTER = "#2a78d6"   # diverging cool pole
SLOWER = "#e34948"   # diverging warm pole
BAND = "#f0efec"     # neutral

LABEL = {
    "binarytrees-2": "binary-trees #2",
    "fannkuchredux-3": "fannkuch-redux #3",
    "fasta-2": "fasta #2",
    "knucleotide-7": "k-nucleotide #7",
    "mandelbrot-4": "mandelbrot #4",
    "nbody-3": "n-body #3",
    "pidigits-4": "pidigits #4 (GMP)",
    "pidigits-6": "pidigits #6 (pure Go)",
    "regexredux-5": "regex-redux #5 (PCRE)",
    "regexredux-3": "regex-redux #3 (pure Go)",
    "revcomp-6": "reverse-complement #6",
    "spectralnorm-4": "spectral-norm #4",
}
ORDER = list(LABEL)


def vkey(v):
    return [int(x) for x in re.findall(r"\d+", v)]


def short(v):
    return re.match(r"go(1\.\d+)", v).group(1)


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.size": 9,
        "font.family": "DejaVu Sans",
        "axes.edgecolor": GRID, "axes.labelcolor": INK2,
        "axes.titlecolor": INK, "axes.titlesize": 9.5, "axes.titleweight": "bold",
        "xtick.color": INK2, "ytick.color": INK2,
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": GRID, "grid.linewidth": 0.8,
    })


def load_sweep(d):
    data = {}  # key -> ver -> result
    machine = None
    for p in glob.glob(os.path.join(d, "*.json")):
        j = json.load(open(p))
        machine = machine or j["machine"]
        for ver, res in j["results"].items():
            for key, r in res.items():
                # several files may cover the same (version, program): keep
                # the one with the most timed samples
                cur = data.setdefault(key, {}).get(ver)
                if cur is None or len(r.get("samples") or []) > len(cur.get("samples") or []) \
                        or (j["runs"] > 0 and r.get("status") == "ok"):
                    data[key][ver] = r
    return data, machine


def save(fig, name):
    out = os.path.join(ROOT, "results", "plots")
    os.makedirs(out, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(out, f"{name}.{ext}"), dpi=160, bbox_inches="tight")
    plt.close(fig)
    return os.path.join("results", "plots", f"{name}.png")


def small_multiples(data, metric, title, ylabel, name, fmt="{:.0f}", note=""):
    vers = sorted({v for byv in data.values() for v in byv}, key=vkey)
    keys = [k for k in ORDER if k in data]
    ncol = 3
    nrow = math.ceil(len(keys) / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(11, 2.35 * nrow + 0.9), sharex=True)
    axes = axes.flatten()
    xs = list(range(len(vers)))
    for ax, key in zip(axes, keys):
        ys = []
        for v in vers:
            r = data[key].get(v)
            ys.append(metric(r) if r and r.get("status") == "ok" else float("nan"))
        # highlight the go1.23 .. go1.27 window
        lo = next((i for i, v in enumerate(vers) if v.startswith("go1.23")), None)
        if lo is not None:
            ax.axvspan(lo - 0.5, len(vers) - 0.5, color=BAND, zorder=0, lw=0)
        ax.plot(xs, ys, color=SERIES, lw=2, marker="o", ms=3.6,
                markeredgecolor=SURFACE, markeredgewidth=1, zorder=3,
                solid_capstyle="round")
        ax.set_title(LABEL.get(key, key), loc="left", pad=4)
        ax.set_ylim(bottom=0, top=max([y for y in ys if y == y] + [0]) * 1.15 or 1)
        ax.yaxis.set_major_locator(MaxNLocator(4))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: fmt.format(y)))
        # direct label: last value
        last = next(((i, y) for i, y in reversed(list(enumerate(ys))) if y == y), None)
        if last:
            ax.annotate(fmt.format(last[1]), (last[0], last[1]), xytext=(4, 4),
                        textcoords="offset points", fontsize=7.5, color=INK)
        ax.tick_params(length=0)
    for ax in axes[len(keys):]:
        ax.set_visible(False)
    tick_idx = [i for i, v in enumerate(vers) if vkey(v)[1] % 3 == 0 or i == len(vers) - 1]
    for ax in axes[-ncol:]:
        ax.set_xticks(tick_idx)
        ax.set_xticklabels([short(vers[i]) for i in tick_idx])
    for ax in axes[::ncol]:
        ax.set_ylabel(ylabel, fontsize=8)
    fig.suptitle(title, x=0.01, y=0.995, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.01, 0.962,
             "Go " + short(vers[0]) + " → " + short(vers[-1]) + " (latest patch of each). "
             "Shaded: go1.23 → go1.27. " + note,
             fontsize=8.5, color=INK2, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.945))
    return save(fig, name)


def change_chart(timed, base, new):
    res = timed["results"]
    rows = []
    for key in ORDER:
        a, b = res.get(base, {}).get(key), res.get(new, {}).get(key)
        if not (a and b and a.get("status") == b.get("status") == "ok"):
            continue
        pct = (b["elapsed_median"] / a["elapsed_median"] - 1) * 100
        noise = math.hypot(a["elapsed_stdev"] / a["elapsed_median"],
                           b["elapsed_stdev"] / b["elapsed_median"]) * 100
        rows.append((key, pct, noise, a, b))
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(rows) + 1.4))
    ys = range(len(rows))
    for y, (key, pct, noise, a, b) in zip(ys, rows):
        ax.barh(y, pct, height=0.62, color=FASTER if pct < 0 else SLOWER, zorder=3)
        ax.errorbar(pct, y, xerr=noise, color=INK2, lw=1, capsize=2.5, zorder=4)
        ax.annotate(f"{pct:+.1f}%  ({a['elapsed_median']:.2f}s → {b['elapsed_median']:.2f}s)",
                    (pct + noise if pct >= 0 else pct - noise, y),
                    xytext=(6 if pct >= 0 else -6, 0), textcoords="offset points",
                    ha="left" if pct >= 0 else "right", va="center", fontsize=7.8, color=INK)
    ax.axvline(0, color=INK2, lw=1, zorder=5)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([LABEL.get(r[0], r[0]) for r in rows])
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    lim = max([abs(r[1]) + r[2] for r in rows] + [5]) * 2.2
    ax.set_xlim(-lim, lim)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:+.0f}%"))
    ax.tick_params(length=0)
    ax.set_xlabel("change in median elapsed time  (← faster   |   slower →)", color=INK2)
    fig.suptitle(f"{base} → {new}: elapsed time per program",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.01, 0.9 if len(rows) > 8 else 0.87,
             f"{timed['runs']} interleaved runs per version on one machine; "
             "whiskers = combined run-to-run stdev", fontsize=8.5, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return save(fig, f"{base}-vs-{new}"), rows


def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def summary_timed(timed):
    res = timed["results"]
    vers = sorted(res, key=vkey)
    base = vers[0]
    lines = [f"### Median elapsed seconds, {timed['runs']} interleaved runs "
             f"({timed['machine'].get('cpu')} ×{timed['machine'].get('nproc')})\n",
             "| program | " + " | ".join(vers) + f" | {short(base)}→{short(vers[-1])} |",
             "|---|" + "---:|" * (len(vers) + 1)]
    ratios = {v: [] for v in vers}
    for key in ORDER:
        if key not in res[base]:
            continue
        cells, ok = [], True
        for v in vers:
            r = res[v].get(key, {})
            if r.get("status") != "ok":
                cells.append(r.get("status", "–"))
                ok = False
                continue
            cells.append(f"{r['elapsed_median']:.3f} ±{r['elapsed_stdev']:.2f}")
        if ok:
            for v in vers:
                ratios[v].append(res[v][key]["elapsed_median"] / res[base][key]["elapsed_median"])
            d = (res[vers[-1]][key]["elapsed_median"] / res[base][key]["elapsed_median"] - 1) * 100
            cells.append(f"**{d:+.1f}%**")
        else:
            cells.append("")
        lines.append(f"| {LABEL.get(key, key)} | " + " | ".join(cells) + " |")
    gm = {v: geomean(ratios[v]) for v in vers if ratios[v]}
    lines.append("| **geomean vs " + short(base) + "** | " +
                 " | ".join(f"{gm[v]:.3f}" for v in vers) +
                 f" | **{(gm[vers[-1]] - 1) * 100:+.1f}%** |")
    # cpu + memory view of the same comparison
    lines += ["", f"### {short(base)} → {short(vers[-1])}: cpu seconds and peak memory\n",
              "| program | cpu " + short(base) + " | cpu " + short(vers[-1]) + " | Δ cpu | mem MB " +
              short(base) + " | mem MB " + short(vers[-1]) + " | Δ mem |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for key in ORDER:
        a, b = res[base].get(key), res[vers[-1]].get(key)
        if not (a and b and a.get("status") == b.get("status") == "ok"):
            continue
        lines.append(
            f"| {LABEL.get(key, key)} | {a['cpu_median']:.2f} | {b['cpu_median']:.2f} | "
            f"{(b['cpu_median'] / a['cpu_median'] - 1) * 100:+.1f}% | {a['rss_kb_max'] / 1024:,.0f} | "
            f"{b['rss_kb_max'] / 1024:,.0f} | {(b['rss_kb_max'] / a['rss_kb_max'] - 1) * 100:+.1f}% |")
    return "\n".join(lines), gm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default=os.path.join(ROOT, "results", "smoke"))
    ap.add_argument("--timed", default=os.path.join(ROOT, "results", "timed-go1.23-go1.27.json"))
    a = ap.parse_args()
    style()
    md = ["# Results\n"]
    if os.path.exists(a.timed):
        timed = json.load(open(a.timed))
        vers = sorted(timed["results"], key=vkey)
        png, _ = change_chart(timed, vers[0], vers[-1])
        table, _ = summary_timed(timed)
        md += [f"## {short(vers[0])} vs {short(vers[-1])} (same machine, interleaved)\n",
               f"![]({os.path.relpath(png, 'results')})\n", table, ""]
    data, machine = load_sweep(a.sweep)
    if data:
        note = "Initial dev-VM data: go1.2–1.9 median of 2 runs, go1.10+ 1 run (2 for fasta, revcomp, mandelbrot). Not final."
        md.append("## Across every release (smoke sweep, 1 run each)\n")
        for metric, title, ylabel, name, fmt in [
            (lambda r: r["elapsed_median"], "Elapsed time by Go release", "seconds", "elapsed-by-version", "{:.1f}"),
            (lambda r: r["cpu_median"], "CPU time by Go release", "cpu seconds", "cpu-by-version", "{:.1f}"),
            (lambda r: r["rss_kb_max"] / 1024, "Peak memory by Go release", "MB", "memory-by-version", "{:,.0f}"),
            (lambda r: r["build_secs"], "Build time by Go release (compile + link, warm stdlib)",
             "seconds", "build-by-version", "{:.2f}"),
        ]:
            png = small_multiples(data, metric, title, ylabel, name, fmt, note)
            md.append(f"![{title}]({os.path.relpath(png, 'results')})\n")
    with open(os.path.join(ROOT, "results", "summary.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

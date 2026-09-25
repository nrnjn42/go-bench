#!/usr/bin/env python3
"""Project the Go numbers of Pereira et al. (SLE 2017 / SCP 2021) onto a newer Go.

Runs their exact Go programs (benchmarks-pereira2017.json) on the old and new
toolchains, then scales the paper's figures by the measured ratios.

Energy isn't measured here, so it is bracketed by two models:
  cpu-bound    energy ∝ cpu-seconds  (dynamic power dominates)
  time-bound   energy ∝ elapsed      (static/baseline power dominates, as on the
                                      van Kempen et al. server: 287 W baseline vs ~2 W per busy core)
A desktop i5 like the paper's sits between the two.

  scripts/pereira_compare.py results/pereira2017-programs.json --old go1.8.7 --new go1.27.1
"""
import argparse
import json
import math
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
# Table 4, normalized global results (1.00 = best language)
PAPER_GO = {"energy": 3.23, "time": 2.83, "memory": 1.05}


def gm(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def pct(x):
    return f"{(x - 1) * 100:+.0f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", default="go1.27.1")
    ap.add_argument("--arena", default=os.path.join(ROOT, "results", "binarytrees-arena.json"),
                    help="results with binarytrees-p2017 and binarytrees-arena on --new")
    a = ap.parse_args()
    full = json.load(open(os.path.join(ROOT, "benchmarks-pereira2017.json")))
    cfg = {f"{b['name']}-{b['id']}": b for b in full["benchmarks"]}
    res = json.load(open(a.results))["results"]
    old, new = res[a.old], res[a.new]
    print(f"### Pereira et al. Go programs: {a.old} → {a.new}\n")
    print("| benchmark | elapsed | cpu | peak mem | paper (J / ms) | projected on the paper's machine: time | energy range |")
    print("|---|---:|---:|---:|---|---:|---|")
    rt, rc, rm = [], [], []
    for key, b in cfg.items():
        o, n = old.get(key), new.get(key)
        if not (o and n and o.get("status") == n.get("status") == "ok"):
            print(f"| {key} | {(n or o or {}).get('status', 'missing')} | | | | | |")
            continue
        t = n["elapsed_median"] / o["elapsed_median"]
        c = n["cpu_median"] / o["cpu_median"]
        m = n["rss_kb_max"] / o["rss_kb_max"]
        rt.append(t), rc.append(c), rm.append(m)
        paper = proj_t = proj_e = ""
        if b.get("paper_ms"):
            paper = f"{b['paper_joules']:.1f} J / {b['paper_ms']:,} ms"
            proj_t = f"{b['paper_ms'] * t:,.0f} ms"
            lo, hi = sorted((b["paper_joules"] * c, b["paper_joules"] * t))
            proj_e = f"{lo:.0f}–{hi:.0f} J"
        print(f"| {b['name']} | {pct(t)} | {pct(c)} | {pct(m)} | {paper} | {proj_t} | {proj_e} |")
    T, C, M = gm(rt), gm(rc), gm(rm)
    print(f"| **geomean ({len(rt)} programs)** | **{pct(T)}** | **{pct(C)}** | **{pct(M)}** | | | |\n")
    elo, ehi = sorted((C, T))
    print("### Go's row in the paper's Table 4 (normalized; 1.00 = best language), "
          "assuming the other languages stood still\n")
    print("| | paper (2017) | with " + a.new + " |")
    print("|---|---:|---:|")
    print(f"| energy | {PAPER_GO['energy']:.2f} | {PAPER_GO['energy'] * elo:.2f}–{PAPER_GO['energy'] * ehi:.2f} |")
    print(f"| time | {PAPER_GO['time']:.2f} | {PAPER_GO['time'] * T:.2f} |")
    print(f"| memory | {PAPER_GO['memory']:.2f} | {PAPER_GO['memory'] * M:.2f} |")

    # Combined score recomputed the paper's way: arithmetic mean of per-benchmark
    # energy (and time) over the benchmarks in its global table, divided by C's mean.
    base = full["paper_base"]
    excl = set(base["excluded_from_global"])
    ratios = {}
    for key, b in cfg.items():
        o, n = old.get(key), new.get(key)
        if b["name"] in excl or "paper_joules" not in b or not (o and n):
            continue
        ratios[key] = (n["cpu_median"] / o["cpu_median"], n["elapsed_median"] / o["elapsed_median"])
    arena = None
    if os.path.exists(a.arena):
        ar = json.load(open(a.arena))["results"].get(a.new, {})
        if "binarytrees-arena" in ar and "binarytrees-p2017" in ar:
            # arena@new relative to the 2017 program@new, chained to the 2017 program@old
            c0, t0 = ratios["binarytrees-2"]
            arena = (c0 * ar["binarytrees-arena"]["cpu_median"] / ar["binarytrees-p2017"]["cpu_median"],
                     t0 * ar["binarytrees-arena"]["elapsed_median"] / ar["binarytrees-p2017"]["elapsed_median"])

    def combined(rs):
        n = len(rs)
        e = [sum(cfg[k]["paper_joules"] * r[i] for k, r in rs.items()) / n / base["c_energy_mean_j"] for i in (0, 1)]
        t = sum(cfg[k]["paper_ms"] * r[1] for k, r in rs.items()) / n / base["c_time_mean_ms"]
        return min(e), max(e), t

    one = {k: (1.0, 1.0) for k in ratios}
    rows = [("paper, 2017 (recomputed from raw data)", combined(one)),
            (f"same 2017 programs on {a.new}", combined(ratios))]
    if arena:
        rows.append((f"{a.new} + pre-allocated arena binary-trees", combined(dict(ratios, **{"binarytrees-2": arena}))))
        bt = cfg["binarytrees-2"]
        print(f"\nbinary-trees energy: paper {bt['paper_joules']:.0f} J → {a.new} "
              f"{bt['paper_joules'] * min(ratios['binarytrees-2']):.0f}–{bt['paper_joules'] * max(ratios['binarytrees-2']):.0f} J"
              f" → arena {bt['paper_joules'] * min(arena):.0f}–{bt['paper_joules'] * max(arena):.0f} J")
    print(f"\n### Go combined score, paper method (mean of {len(ratios)} benchmarks ÷ C mean; 1.00 = C)\n")
    print("| scenario | energy | time |\n|---|---:|---:|")
    for name, (elo, ehi, t) in rows:
        e = f"{elo:.2f}" if abs(ehi - elo) < 0.005 else f"{elo:.2f}–{ehi:.2f}"
        print(f"| {name} | {e} | {t:.2f} |")


if __name__ == "__main__":
    main()

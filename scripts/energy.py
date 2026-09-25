#!/usr/bin/env python3
"""Estimate energy change between Go releases from measured time and CPU.

No power meter is needed: energy is modelled from the measurements with the
linear model fitted to the raw RAPL data of van Kempen et al., "It's Not Easy
Being Green: On the Energy Efficiency of Programming Languages" (2024,
arXiv:2410.05460, github.com/nicovank/energy-languages, which used go1.23.1):

    energy_J ~= A * cpu_seconds + B * elapsed_seconds

refit from data/osmium/docker-default (3192 runs, 13 languages, package energy):
A = 1.99 J per cpu-second, B = 286.6 J per elapsed second, R^2 = 0.968.
A CPU-time-only model (E ~ cpu) explains ~none of that data (R^2 ~ 0).

  scripts/energy.py results/timed-go1.23-go1.27.json [--base go1.23.12 --new go1.27.1]
  scripts/energy.py --refit /path/to/energy-languages   # recompute A, B
"""
import argparse
import glob
import json
import math
import os

A, B = 1.99, 286.6
LANGS = "C C++ Rust Go Java C# JavaScript TypeScript PHP Python PyPy Lua LuaJIT".split()


def refit(repo):
    import numpy as np
    xs, ys = [], []
    files = [f for lang in LANGS for f in
             glob.glob(os.path.join(repo, "data", "osmium", "docker-default", lang, "*.json"))]
    for f in files:
        for line in open(f):
            r = json.loads(line)
            xs.append((r["counters"]["PERF_COUNT_SW_TASK_CLOCK"] / 1e9, r["runtime_ms"] / 1e3))
            ys.append(sum(sum(e["pkg"] for e in s["energy"]) for s in r["energy_samples"]))
    X, y = np.array(xs), np.array(ys)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    r2 = 1 - ((y - X @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"A = {coef[0]:.2f} J/cpu-s, B = {coef[1]:.1f} J/s, R^2 = {r2:.3f}, n = {len(y)}")


def gm(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def energy(r):
    return A * r["cpu_median"] + B * r["elapsed_median"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?")
    ap.add_argument("--base")
    ap.add_argument("--new")
    ap.add_argument("--refit")
    a = ap.parse_args()
    if a.refit:
        return refit(a.refit)
    res = json.load(open(a.results))["results"]
    vers = sorted(res, key=lambda v: [int(x) for x in v[2:].split(".")])
    base, new = a.base or vers[0], a.new or vers[-1]
    rows = []
    print(f"| program | cpu Δ | elapsed Δ | modelled energy Δ |\n|---|---:|---:|---:|")
    for k, rb in res[base].items():
        rn = res[new].get(k)
        if not (rn and rb.get("status") == rn.get("status") == "ok"):
            continue
        c = rn["cpu_median"] / rb["cpu_median"]
        t = rn["elapsed_median"] / rb["elapsed_median"]
        e = energy(rn) / energy(rb)
        rows.append((c, t, e))
        print(f"| {k} | {(c - 1) * 100:+.1f}% | {(t - 1) * 100:+.1f}% | {(e - 1) * 100:+.1f}% |")
    c, t, e = (gm([r[i] for r in rows]) for i in range(3))
    print(f"| **geomean {base} → {new}** | **{(c - 1) * 100:+.1f}%** | **{(t - 1) * 100:+.1f}%** "
          f"| **{(e - 1) * 100:+.1f}%** |")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build-only matrix: does every program compile (and pass the small reference
check) on every Go release? Fast way to find source-compat gaps."""
import concurrent.futures as cf
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bench  # noqa: E402

cfg = json.load(open(os.path.join(bench.ROOT, "benchmarks.json")))
vers = sys.argv[1:] or subprocess.run([bench.GOVM, "list-remote"], capture_output=True,
                                      text=True, check=True).stdout.split()


def one(ver):
    row = {}
    for b in cfg["benchmarks"]:
        key = f"{b['name']}-{b['id']}"
        exe, _, err = bench.build(ver, b, cfg["goamd64"])
        if not exe:
            lines = [l for l in err.splitlines() if l and not l.startswith("#")]
            row[key] = "BUILD: " + (lines[0] if lines else err)[:140]
        elif not bench.check(exe, b):
            row[key] = "BAD OUTPUT"
        else:
            row[key] = "ok"
    return ver, row


with cf.ThreadPoolExecutor(4) as ex:
    res = dict(ex.map(one, vers))
bad = 0
for ver in sorted(res, key=lambda v: [int(x) for x in v[2:].split(".")]):
    fails = {k: v for k, v in res[ver].items() if v != "ok"}
    bad += len(fails)
    print(f"{ver:>10}: {len(res[ver]) - len(fails)}/{len(res[ver])} ok")
    for k, v in fails.items():
        print(f"{'':>12}{k}: {v}")
sys.exit(1 if bad else 0)

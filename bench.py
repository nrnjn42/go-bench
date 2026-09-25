#!/usr/bin/env python3
"""Re-run the Benchmarks Game Go programs across Go releases.

    ./bench.py run --go go1.27.1 [--go go1.26.8 ...] [--runs 5] [--only nbody,fasta]
    ./bench.py report results/<file>.json [...]

For every requested Go version (installed on demand with bin/govm) each program
in benchmarks.json is built, checked against the Benchmarks Game reference
output, checksummed at full size, then timed --runs times. Rounds interleave
versions and programs so machine noise is spread evenly across them.
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PROGRAMS = os.path.join(ROOT, "programs")
TESTDATA = os.path.join(ROOT, "testdata")
WORK = os.environ.get("GOBENCH_WORK", os.path.join(ROOT, "work"))
GOVM = os.path.join(ROOT, "bin", "govm")
GOVM_ROOT = os.environ.get("GOVM_ROOT", os.path.expanduser("~/.govm"))
TIMEOUT = 900


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def minor(ver):
    m = re.match(r"go1\.(\d+)", ver)
    return int(m.group(1))


def goroot(ver):
    r = os.path.join(GOVM_ROOT, ver)
    if not os.path.exists(os.path.join(r, "bin", "go")):
        subprocess.run([GOVM, "install", ver], check=True,
                       env=dict(os.environ, GOVM_ROOT=GOVM_ROOT))
    return r


def go_env(ver, goamd64):
    r = goroot(ver)
    env = dict(os.environ)
    env.update(
        GOROOT=r,
        PATH=os.path.join(r, "bin") + os.pathsep + env["PATH"],
        GOTOOLCHAIN="local",
        GOAMD64=goamd64,
        CGO_ENABLED="1",
        GOPATH=os.path.join(WORK, "gopath"),
        GOCACHE=os.path.join(WORK, "gocache", ver),
    )
    env.pop("GOBIN", None)
    env.pop("GOFLAGS", None)
    m = minor(ver)
    if m < 8:
        # old cgo links with `ld -r`, which modern PIE-default gcc rejects
        env["CGO_LDFLAGS"] = (env.get("CGO_LDFLAGS", "") + " -no-pie").strip()
    if m < 11:
        # no module support: plain GOPATH build
        env["GOPATH"] = os.path.join(WORK, "gopath-legacy")
        env.pop("GO111MODULE", None)
    else:
        env["GO111MODULE"] = "on"
        # comma-separated GOPROXY lists arrived in 1.13
        env["GOPROXY"] = "https://proxy.golang.org" if m < 13 else "https://proxy.golang.org,direct"
        if m >= 14:
            env["GOFLAGS"] = "-mod=mod"
    return env


def legacy_deps(b, env):
    """GOPATH mode: place required modules under GOPATH/src (fetched with a
    modern toolchain's module cache is not needed; the proxy zip is enough)."""
    for path, v in b.get("require", {}).items():
        dst = os.path.join(env["GOPATH"], "src", path)
        if os.path.isdir(dst):
            continue
        esc = re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), path)
        tmp = os.path.join(WORK, "dl")
        os.makedirs(tmp, exist_ok=True)
        z = os.path.join(tmp, esc.replace("/", "_") + f"@{v}.zip")
        subprocess.run(["curl", "-fsSL", "-o", z,
                        f"https://proxy.golang.org/{esc}/@v/{v}.zip"], check=True)
        ex = z + ".d"
        shutil.rmtree(ex, ignore_errors=True)
        subprocess.run(["unzip", "-q", z, "-d", ex], check=True)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(os.path.join(ex, f"{path}@{v}"), dst)


def build(ver, b, goamd64):
    """Build one program as its own module; the go directive tracks the
    toolchain so each release compiles with its own language semantics."""
    tag = f"{b['name']}-{b['id']}"
    d = os.path.join(WORK, "build", ver, tag)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    shutil.copy(os.path.join(PROGRAMS, b["src"]), os.path.join(d, "main.go"))
    env = go_env(ver, goamd64)
    exe = os.path.join(d, tag + ".run")
    m = minor(ver)
    if m >= 11:
        mod = f"module gobench/{b['name']}\n"
        if m >= 12:  # go directive
            mod += f"\ngo 1.{m}\n"
        for path, v in b.get("require", {}).items():
            mod += f"\nrequire {path} {v}\n"
        with open(os.path.join(d, "go.mod"), "w") as f:
            f.write(mod)
        if b.get("require"):
            p = subprocess.run(["go", "mod", "download"], cwd=d, env=env,
                               capture_output=True, text=True)
            if p.returncode != 0:
                return None, 0.0, "go mod download: " + p.stderr.strip()
        target = "."
    else:
        try:
            legacy_deps(b, env)
        except subprocess.CalledProcessError as e:
            return None, 0.0, f"fetching deps: {e}"
        target = "main.go"
    # First build warms the stdlib cache (go1.10+); then change the source by a
    # comment and time the rebuild, so build secs = compile + link of this
    # program only, comparable across releases.
    p = subprocess.run(["go", "build", "-o", exe, target], cwd=d, env=env,
                       capture_output=True, text=True)
    if p.returncode != 0:
        return None, 0.0, p.stderr.strip()
    with open(os.path.join(d, "main.go"), "a") as f:
        f.write(f"\n// rebuild {time.time_ns()}\n")
    t = time.perf_counter()
    p = subprocess.run(["go", "build", "-o", exe, target], cwd=d, env=env,
                       capture_output=True, text=True)
    secs = time.perf_counter() - t
    if p.returncode != 0:
        return None, secs, p.stderr.strip()
    return exe, secs, ""


def fasta_input(spec, ver, goamd64):
    """'fasta:N' -> path of a file holding the fasta (#1) output for N."""
    n = spec.split(":", 1)[1]
    path = os.path.join(WORK, "inputs", f"fasta-{n}.txt")
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    gen = os.path.join(WORK, "inputs", "fasta-gen")
    if not os.path.exists(gen):
        subprocess.run(["go", "build", "-o", gen,
                        os.path.join(PROGRAMS, "fasta", "fasta.go")],
                       env=dict(go_env(ver, goamd64), GOFLAGS=""), check=True,
                       cwd=os.path.join(WORK, "inputs"))
    log(f"  generating {path}")
    with open(path + ".tmp", "wb") as f:
        subprocess.run([gen, n], stdout=f, check=True)
    os.rename(path + ".tmp", path)
    return path


def steal_secs():
    """Host 'steal' time for this VM (all CPUs), from /proc/stat; a VM being
    throttled or sharing cores shows it growing during a run."""
    try:
        with open("/proc/stat") as f:
            fields = f.readline().split()
        return int(fields[8]) / os.sysconf("SC_CLK_TCK")
    except (OSError, IndexError, ValueError):
        return 0.0


def execute(argv, stdin_path=None, stdout=subprocess.DEVNULL):
    """Run once; returns (status, elapsed s, rusage)."""
    fin = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
    try:
        t = time.perf_counter()
        p = subprocess.Popen(argv, stdin=fin, stdout=stdout,
                             stderr=subprocess.DEVNULL)
        deadline = t + TIMEOUT
        while True:
            pid, status, ru = os.wait4(p.pid, os.WNOHANG)
            if pid:
                break
            if time.perf_counter() > deadline:
                p.kill()
                pid, status, ru = os.wait4(p.pid, 0)
                status = -1
                break
            time.sleep(0.002)
        elapsed = time.perf_counter() - t
        p.returncode = 0  # reaped by wait4
        return (os.waitstatus_to_exitcode(status) if status != -1 else -1,
                elapsed, ru)
    finally:
        if stdin_path:
            fin.close()


def check(exe, b):
    """Small workload vs. the Benchmarks Game reference output."""
    stdin = os.path.join(TESTDATA, b["check_stdin"]) if b.get("check_stdin") else None
    fin = open(stdin, "rb") if stdin else subprocess.DEVNULL
    try:
        p = subprocess.run([exe] + b["check_args"], stdin=fin,
                           capture_output=True, timeout=120)
    finally:
        if stdin:
            fin.close()
    with open(os.path.join(TESTDATA, b["check_out"]), "rb") as f:
        want = f.read()
    return p.returncode == 0 and p.stdout == want


def full_checksum(exe, argv, stdin):
    """Full-size run with stdout hashed; returns (rc, sha256, elapsed, rusage)."""
    h = hashlib.sha256()
    fin = open(stdin, "rb") if stdin else subprocess.DEVNULL
    try:
        t = time.perf_counter()
        p = subprocess.Popen(argv, stdin=fin, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL)
        for chunk in iter(lambda: p.stdout.read(1 << 20), b""):
            h.update(chunk)
        _, status, ru = os.wait4(p.pid, 0)
        elapsed = time.perf_counter() - t
        p.returncode = os.waitstatus_to_exitcode(status)
    finally:
        if stdin:
            fin.close()
    return p.returncode, h.hexdigest(), elapsed, ru


def sample(el, ru, rc):
    return {"elapsed": round(el, 4), "cpu": round(ru.ru_utime + ru.ru_stime, 4),
            "user": round(ru.ru_utime, 4), "sys": round(ru.ru_stime, 4),
            "rss_kb": ru.ru_maxrss, "minflt": ru.ru_minflt, "rc": rc}


def drop_caches(inputs):
    """Free the page cache (needs root) so allocation-heavy programs get fresh
    pages without the kernel reclaiming cache first, then re-read the inputs
    so they are served from RAM, as on the first round."""
    subprocess.run(["sync"], check=False)
    try:
        with open("/proc/sys/vm/drop_caches", "w") as f:
            f.write("1\n")
    except OSError as e:
        log(f"  drop-caches skipped: {e}")
        return
    for p in sorted(set(inputs)):
        with open(p, "rb") as f:
            while f.read(1 << 24):
                pass


def machine_info():
    info = {"python_platform": platform.platform(), "nproc": os.cpu_count()}
    try:
        with open("/proc/cpuinfo") as f:
            m = re.search(r"model name\s*:\s*(.*)", f.read())
            info["cpu"] = m.group(1) if m else None
    except OSError:
        pass
    try:
        with open("/proc/meminfo") as f:
            info["mem_kb"] = int(re.search(r"MemTotal:\s*(\d+)", f.read()).group(1))
    except OSError:
        pass
    try:
        info["loadavg_start"] = os.getloadavg()
    except OSError:
        pass
    return info


def cmd_run(a):
    cfg = json.load(open(a.config or os.path.join(ROOT, "benchmarks.json")))
    if a.with_upstream:
        # add the unmodified site program next to each backport, for A/B checks
        extra = []
        for b in cfg["benchmarks"]:
            if b.get("upstream_src"):
                u = dict(b, src=b["upstream_src"], id=f"{b['id']}u", variant="upstream")
                u.pop("upstream_src")
                extra.append(u)
        cfg["benchmarks"] += extra
    goamd64 = a.goamd64 or cfg.get("goamd64", "v2")
    benches = cfg["benchmarks"]
    if a.only:
        keep = set(a.only.split(","))
        benches = [b for b in benches
                   if b["name"] in keep or f"{b['name']}-{b['id']}" in keep]
    if a.no_cgo:
        benches = [b for b in benches if not b.get("cgo")]
    vers = [v if v.startswith("go") else "go" + v for v in a.go]

    out = {
        "started": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "machine": machine_info(), "label": a.label, "goamd64": goamd64,
        "runs": a.runs, "results": {},
    }

    # build + verify
    ready = []
    for ver in vers:
        env = go_env(ver, goamd64)
        gov = subprocess.run([os.path.join(env["GOROOT"], "bin", "go"), "version"],
                             env=env, capture_output=True, text=True).stdout.strip()
        log(f"== {gov}")
        for b in benches:
            key = f"{b['name']}-{b['id']}"
            r = out["results"].setdefault(ver, {}).setdefault(key, {
                "name": b["name"], "id": b["id"], "variant": b["variant"],
                "site_secs": b.get("site_secs"), "go_version": gov})
            exe, bsecs, err = build(ver, b, goamd64)
            r["build_secs"] = round(bsecs, 2)
            if not exe:
                r["status"] = "build-failed"
                r["error"] = err[-2000:]
                log(f"  {key}: BUILD FAILED\n{err[-600:]}")
                continue
            if not check(exe, b):
                r["status"] = "bad-output"
                log(f"  {key}: BAD OUTPUT (reference check)")
                continue
            stdin = fasta_input(b["stdin"], ver, goamd64) if b.get("stdin") else None
            rc, digest, el, ru = full_checksum(exe, [exe] + b["args"], stdin)
            r["output_sha256"] = digest
            if rc != 0:
                r["status"] = f"exit-{rc}"
                log(f"  {key}: EXIT {rc} at full size")
                continue
            r["status"] = "ok"
            r["samples"] = []
            if a.runs == 0:
                # smoke mode: the checksum run doubles as the only sample
                r["samples"].append(sample(el, ru, rc))
            else:
                ready.append((ver, key, [exe] + b["args"], stdin))
            log(f"  {key}: built in {bsecs:.1f}s, output ok, full run {el:.2f}s")

    # timed rounds, interleaved
    for i in range(a.runs):
        log(f"-- round {i + 1}/{a.runs}")
        if a.drop_caches:
            drop_caches([s for _, _, _, s in ready if s])
        for ver, key, argv, stdin in ready:
            st0 = steal_secs()
            rc, el, ru = execute(argv, stdin)
            r = out["results"][ver][key]
            r["samples"].append(sample(el, ru, rc))
            r["samples"][-1]["steal"] = round(steal_secs() - st0, 3)
            cpu, rss = r["samples"][-1]["cpu"], ru.ru_maxrss
            if rc != 0:
                r["status"] = f"exit-{rc}"
            log(f"   {ver:>10} {key:<16} {el:8.3f}s  cpu {cpu:8.3f}s  {rss // 1024:6d} MB"
                f"  steal {r['samples'][-1]['steal']:.2f}s")

    for ver in out["results"]:
        for r in out["results"][ver].values():
            s = r.get("samples")
            if s:
                el = [x["elapsed"] for x in s]
                r["elapsed_min"] = min(el)
                r["elapsed_median"] = statistics.median(el)
                r["elapsed_stdev"] = statistics.stdev(el) if len(el) > 1 else 0.0
                r["cpu_median"] = statistics.median(x["cpu"] for x in s)
                r["sys_median"] = statistics.median(x["sys"] for x in s)
                r["rss_kb_max"] = max(x["rss_kb"] for x in s)
    out["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    name = a.output or os.path.join(
        ROOT, "results", f"{a.label}-{'_'.join(vers)}.json")
    with open(name, "w") as f:
        json.dump(out, f, indent=1)
    log(f"wrote {name}")
    print(report([out]))


def report(datas):
    lines = []
    vers = []
    rows = {}
    for d in datas:
        for ver, res in d["results"].items():
            if ver not in vers:
                vers.append(ver)
            for key, r in res.items():
                rows.setdefault(key, {})[ver] = r
    vers.sort(key=lambda v: [int(x) for x in re.findall(r"\d+", v)], reverse=True)
    d0 = datas[0]
    m = d0["machine"]
    lines.append(f"Machine: {m.get('cpu')} x{m.get('nproc')}, "
                 f"{(m.get('mem_kb') or 0) // 1048576} GB RAM, GOAMD64={d0['goamd64']}, "
                 + (f"{d0['runs']} timed runs per program" if d0["runs"]
                    else "smoke mode: 1 full-size run per program, stdout hashed")
                 + f" ({d0['started']})\n")
    if len(vers) == 1:
        v = vers[0]
        lines.append("| benchmark | program | variant | median secs | min secs | ± stdev | cpu secs | (of which sys) | peak mem MB | build secs | site secs (go1.23.1) |")
        lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for key, byv in rows.items():
            r = byv.get(v, {})
            prog = f"Go #{r.get('id')}"
            if r.get("status") != "ok":
                lines.append(f"| {r.get('name')} | {prog} | {r.get('variant')} | {r.get('status')} | | | | | | | {r.get('site_secs')} |")
                continue
            lines.append(
                f"| {r['name']} | {prog} | {r['variant']} | {r['elapsed_median']:.3f} | {r['elapsed_min']:.3f} "
                f"| {r['elapsed_stdev']:.3f} | {r['cpu_median']:.2f} | {r['sys_median']:.2f} | {r['rss_kb_max'] / 1024:,.0f} "
                f"| {r['build_secs']:.1f} | {r.get('site_secs')} |")
    else:
        lines.append("Median elapsed seconds (lower is better)\n")
        lines.append("| benchmark | " + " | ".join(vers) + " |")
        lines.append("|---|" + "---:|" * len(vers))
        for key, byv in rows.items():
            cells = []
            for v in vers:
                r = byv.get(v)
                cells.append(f"{r['elapsed_median']:.3f}" if r and r.get("status") == "ok"
                             else (r or {}).get("status", "–"))
            lines.append(f"| {key} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cmd_report(a):
    print(report([json.load(open(p)) for p in a.files]))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--go", action="append", required=True)
    r.add_argument("--runs", type=int, default=5,
                   help="timed runs per program; 0 = smoke mode (the one full-size checksum run is the sample)")
    r.add_argument("--only")
    r.add_argument("--no-cgo", action="store_true")
    r.add_argument("--goamd64")
    r.add_argument("--config", help="alternate benchmarks.json")
    r.add_argument("--drop-caches", action="store_true",
                   help="drop the page cache before every round (root); recommended on the final box")
    r.add_argument("--with-upstream", action="store_true",
                   help="also run the unmodified site program for every backported one")
    r.add_argument("--label", default=platform.node() or "host")
    r.add_argument("--output")
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("files", nargs="+")
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

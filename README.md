# go-bench — Benchmarks Game Go programs, re-run across Go releases

Goal: take the fastest Go programs from the
[Benchmarks Game Go page](https://benchmarksgame-team.pages.debian.net/benchmarksgame/fastest/go.html)
and re-measure them for the latest patch of every Go minor release, newest first
(go1.27.1, go1.26.8, go1.25.14, …), on one machine, with one harness, so the numbers
compare cleanly for a blog post on how Go performance has changed.

## Layout

| path | what |
|---|---|
| `bin/govm` | a small Go version manager. It downloads toolchains from the Go module proxy (`golang.org/toolchain`), the same source `GOTOOLCHAIN` uses, and verifies them against `sum.golang.org`. Every release back to go1.2.2 is there. |
| `programs/` | the chosen Benchmarks Game programs, copied verbatim from the official source zip (BSD-3, see `programs/LICENSE`), plus `*.compat.go` backports |
| `benchmarks.json` | which program represents each task, with its workload, reference check and the site's own time |
| `testdata/` | official reference inputs and outputs, used to check every build |
| `bench.py` | build → check → checksum → timed runs, interleaved across versions; writes JSON and a Markdown table |
| `scripts/setup-ubuntu.sh` | prepares Ubuntu 24.04–26.04 (GMP, PCRE; builds PCRE 8.45 from source on 26.04). `--tune` pins the CPU. |
| `scripts/compat.py` | build + reference check of every program on every release (currently 312/312 ok) |
| `scripts/plots.py` | charts in `results/plots/` and `results/summary.md` |
| `results/` | raw JSON per run set, `summary.md`, `plots/` |

## The programs

For each task, the program is the **fastest Go program by elapsed seconds** on the site (the site measured go1.23.1 with `GOAMD64=v2` on a quad-core machine).
For pidigits and regex-redux the winner calls C (GMP or PCRE), so the fastest **pure-Go** program is tracked too. That's the row that actually measures the Go compiler, runtime and stdlib.

| task | program | variant | notes |
|---|---|---|---|
| binary-trees | Go #2 | fastest | GC / allocation heavy |
| fannkuch-redux | Go #3 | fastest | |
| fasta | Go #2 | fastest | |
| k-nucleotide | Go #7 | fastest | built-in `map` |
| mandelbrot | Go #4 | fastest | |
| n-body | Go #3 | fastest | float64 |
| spectral-norm | Go #4 | fastest | |
| reverse-complement | Go #6 | fastest | input is ~1 GB (fasta n=100M) |
| pidigits | Go #4 | fastest | cgo → libgmp |
| pidigits | Go #6 | pure-go | `math/big` |
| regex-redux | Go #5 | fastest | cgo → libpcre (JIT), `github.com/GRbit/go-pcre v1.0.0` |
| regex-redux | Go #3 | pure-go | `regexp` |

Source: the site's own repository, via a mirror
([gitlab.com/hugefiver/benchmarksgame](https://gitlab.com/hugefiver/benchmarksgame) → `public/download/benchmarksgame-sourcecode.zip`,
measurements in `public/data/data.csv`). The Debian-hosted site itself was unreachable from the build sandbox.

## Same source on every release

Five programs used APIs newer than go1.2 or go1.12. Each has a minimal `.compat.go` backport, and **every Go version runs the backport**:
signed shift count → `uint(...)`, `sort.Slice` → `sort.Sort`, `strings.Builder` → `bytes.Buffer`,
`for range x` → `for _ = range x`, `bufio.Reader.Discard` → `ReadSlice('\n')`. On go1.27.1 the backports match the
originals within noise and produce byte-identical full-size output (`results/backport-ab-go1.27.1.json`).

## Method

* Toolchains: `bin/govm install go1.X.Y` (proxy.golang.org, sumdb-verified). Builds run with `GOTOOLCHAIN=local`.
  go1.2–go1.10 build in GOPATH mode; cgo before go1.8 links with `-no-pie`.
* Each program builds as its own module. The `go` directive equals the toolchain's minor version, so every release compiles with its own language semantics (for example, per-iteration loop variables from 1.22 on).
* `GOAMD64=v2`, same as the site. (v3 would let newer compilers fuse FMA and change n-body/spectral-norm results.)
* Every build is checked byte-for-byte against the official small-workload output. The full-size output is SHA-256'd so any drift between Go versions shows up.
* Timed runs: stdout goes to `/dev/null`. **secs** = wall clock to finish; **cpu secs** = user+sys summed over all threads (`wait4` rusage), the same two columns as the site; memory is peak RSS; `steal` = hypervisor steal time during the run (should be ~0).
* Build secs = rebuild of the program only (compile + link) after the stdlib is warm, so it compares across releases. Rounds interleave versions × programs, so slow periods on the machine hit every version equally. Median and min are both reported.
* Inputs for k-nucleotide (fasta 25M), regex-redux (fasta 5M) and reverse-complement (fasta 100M) are generated once with fasta Go #1.

## Usage

```sh
git clone https://github.com/nrnjn42/go-bench && cd go-bench
sudo scripts/setup-ubuntu.sh --tune
bin/govm list-remote                    # latest patch of every go1.N
scripts/compat.py                       # optional: build/check matrix for every release

# final measurement: every release, 5 interleaved runs, page cache dropped per round (root)
sudo -E ./bench.py run $(bin/govm list-remote | sed 's/^/--go /') --runs 5 --drop-caches --label <machine>

python3 scripts/plots.py --sweep results/<file>.json --timed results/<file>.json
```

Runtime: one round of all 12 programs over all 26 releases is ~45 min, so `--runs 5` is ~4.5 h
(one extra untimed full-size run per program verifies output). Recommended box: 4 dedicated physical cores,
≥16 GB RAM, e.g. GCP `c3-standard-8 --threads-per-core=1`.

## Reproduce on Google Cloud (step by step)

Anyone with a GCP project can re-run the whole study. It takes about 5 hours and costs about $2 (c3-standard-8 is about $0.40/h on demand in us-central1; check current pricing).

**1. Create the VM** (from your laptop, [gcloud CLI](https://cloud.google.com/sdk/docs/install) logged in, billing enabled):

```sh
gcloud config set project <your-project>
gcloud compute instances create go-bench \
  --zone=us-central1-a \
  --machine-type=c3-standard-8 --threads-per-core=1 \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-balanced
```

`--threads-per-core=1` turns off SMT, so Go sees 4 physical cores with no hyperthread sharing, like the Benchmarks Game quad-core box.
Don't use Spot VMs (preemption loses the interleaved run) or shared-core `e2-*` machines (their CPU is time-sliced with other VMs, so timings are unreliable).
Another provider works too if it gives 4 dedicated cores and ≥16 GB RAM.

**2. Set up** (about 3 minutes):

```sh
gcloud compute ssh go-bench --zone=us-central1-a
git clone https://github.com/nrnjn42/go-bench && cd go-bench
sudo scripts/setup-ubuntu.sh --tune
nproc                         # expect 4
scripts/compat.py             # optional, ~10 min: all 12 programs build + pass on all 26 releases
```

**3. Run** (inside tmux so an SSH drop doesn't kill it):

```sh
tmux new -s bench
sudo -E ./bench.py run $(bin/govm list-remote | sed 's/^/--go /') \
  --runs 5 --drop-caches --label gcp-c3-4c --output results/final-gcp-c3-4c.json
# detach: Ctrl-b d      reattach: tmux attach -t bench
```

The per-run output lines include `steal`; it should stay near 0. Consistently more than about 1% of a run's CPU time means the host is taking CPU away from the VM: use another zone or machine type.

**4. Analyse:**

```sh
python3 scripts/plots.py --sweep results/final-gcp-c3-4c.json --timed results/final-gcp-c3-4c.json
scripts/energy.py results/final-gcp-c3-4c.json --base go1.23.12 --new go1.27.1
```

**5. Get the results and delete the VM:**

```sh
# either push from the VM (needs your git credentials there) ...
git add results && git commit -m "final results: gcp c3-standard-8, 4 cores" && git push
# ... or copy them to your laptop
gcloud compute scp --recurse go-bench:~/go-bench/results ./results-gcp --zone=us-central1-a

gcloud compute instances delete go-bench --zone=us-central1-a    # about $290/month if forgotten
```

## Energy

`scripts/energy.py` estimates the energy change between two releases without a power meter. It uses the linear model fitted
to the raw RAPL data of van Kempen et al., [*It's Not Easy Being Green*](https://arxiv.org/abs/2410.05460)
(2024; [data](https://github.com/nicovank/energy-languages); their Go was 1.23.1):

    energy ≈ 1.99 J × cpu-seconds + 286.6 J × elapsed-seconds     (R² = 0.97 over 3,192 runs, 13 languages)

On their dual-socket server the elapsed-time term dominates. CPU time alone does not predict energy there (R² ≈ 0), so the script reports
cpu, elapsed and modelled energy side by side. The constants depend on the machine; `scripts/energy.py --refit <repo>` recomputes them.

## Caveats (worth stating in the post)

* Absolute numbers depend on the machine. Only compare versions measured on the same host, ideally in the same interleaved run.
* Shared cloud VMs are noisy, and page faults are expensive on them. reverse-complement #6 reallocates its buffer in 60 MB steps, so on a Firecracker VM it spends most of its time in the kernel (see the `sys` column). For publication, prefer a dedicated or bare-metal box, fixed CPU frequency, and no other load.
* reverse-complement allocates ~1.6 GB. When the page cache has filled RAM, its page faults get slower (seen on the dev VM: +50% after hours of runs, at identical user time). Use `--drop-caches`.
* The data in `results/` so far comes from a shared 4-vCPU dev VM and is preliminary. Only the 1.23→1.27 comparison used 5 interleaved runs.

# go-bench — Benchmarks Game Go programs, measured on each Go release

This project measures the fastest Go programs from the
[Benchmarks Game Go page](https://benchmarksgame-team.pages.debian.net/benchmarksgame/fastest/go.html).
It measures them on the latest patch of each Go minor release, from go1.2.2 to go1.27.1.
All measurements use one machine and one test harness. Thus, you can compare the results between releases.

## Summary

- **Test setup.** There are 10 tasks. For each task, we use the fastest Go program from the Benchmarks Game.
  For pidigits and regex-redux, we also use a pure-Go program. Thus, there are 12 programs.
  We build each program from the same source code on all 26 releases.
- **Test machine.** We used a GCP virtual machine with 4 dedicated cores. We did 5 runs of each program.
  The hypervisor steal time was 0 s. The output was the same on each release, byte for byte.
- **Go 1.27 against Go 1.23.** Go 1.27.1 is 11.5% faster than go1.23.12 (geometric mean of elapsed time).
  It also uses 12.3% less CPU time.
- **Largest changes.** k-nucleotide is 57.5% faster. binary-trees is 30.7% faster. pidigits (pure Go) is 15.9% faster.
  The numeric programs (n-body, mandelbrot, spectral-norm, fasta) changed by less than 1%.
- **All releases.** Go 1.27.1 is approximately 41% faster than go1.2.2.
  The largest improvements occurred in go1.5 to go1.7 and in go1.24 to go1.27.
  From go1.8 to go1.23, the geometric mean changed by approximately 3%.
- **Go against C.** In 5 of the 10 tasks, the fastest C program uses hand-written SIMD instructions.
  Against the fastest C program without SIMD, Go takes 0.93× to 1.28× the time on the CPU-bound tasks.
  The other 5 fastest C programs use C libraries (khash, APR pools, GMP, PCRE2).
- **Repeat the test.** The full test takes approximately 5 hours on one GCP virtual machine. The cost is approximately $2.
  For the procedure, refer to [Repeat the test on Google Cloud](#repeat-the-test-on-google-cloud).
- **Pre-allocated memory.** A binary-trees program with pre-allocated nodes is approximately 10× faster than Go #2.
  The Benchmarks Game does not accept this type of program.
  For more data, refer to [binary-trees with pre-allocated nodes](#binary-trees-with-pre-allocated-nodes).

## Results (GCP, 2026-09-25)

### Test conditions

| item | value |
|---|---|
| machine | GCP `c3-standard-8 --threads-per-core=1` |
| CPU | 4 physical cores, Xeon Platinum 8481C |
| memory | 32 GB RAM |
| operating system | Ubuntu 24.04 |
| Go releases | 26 (go1.2.2 to go1.27.1) |
| programs | 12 |
| runs | 5 for each program on each release, in alternate sequence |
| total timed runs | 1,560, in 3 hours |
| hypervisor steal time | 0 s |
| median variation between runs | 0.29% |
| settings | `--drop-caches`, `GOAMD64=v2` |

Each program gave the same full-size output on each release, byte for byte.

- Raw data: `results/final/gcp-c3-4c-all-versions.json`.
- Report and charts: [`results/final/summary.md`](results/final/summary.md).

### go1.23.12 compared with go1.27.1

Go 1.27.1 is 11.5% faster than go1.23.12 (geometric mean of elapsed time).
It uses 12.3% less CPU time. The calculated energy is 11.5% less.

| program | change in elapsed time, 1.23 → 1.27 | release of the change |
|---|---:|---|
| k-nucleotide | **−57.5%** | go1.24 |
| binary-trees | **−30.7%** | −14% in go1.27 |
| pidigits (pure Go) | **−15.9%** | go1.25 |
| regex-redux (PCRE) | −7.1% | go1.26 |
| regex-redux (pure Go), fannkuch-redux | −2% | |
| n-body, mandelbrot, fasta, spectral-norm, pidigits (GMP) | ±1% | |
| reverse-complement | +3.1% | peak memory increased by 29% |

### All releases

The table shows the geometric mean of elapsed time for each release.
The value is relative to go1.27.1. A value of 1.00 is the same speed as go1.27.1.
A value of 1.69 is 69% more time than go1.27.1.

| go1.2 | 1.4 | 1.5 | 1.6 | 1.7 | 1.8 | 1.10 | 1.13 | 1.16 | 1.20 | 1.23 | 1.24 | 1.25 | 1.26 | 1.27 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.69 | 1.83 | 1.42 | 1.39 | 1.21 | 1.16 | 1.16 | 1.12 | 1.14 | 1.14 | 1.13 | 1.06 | 1.04 | 1.01 | 1.00 |

The build time (compile and link, with a warm standard library) is approximately 0.15 s for each program.
This time is almost the same on all releases. It increased in go1.5 and go1.6.

![go1.23 compared with go1.27: change in elapsed time for each program](results/final/plots/go1.23.12-vs-go1.27.1.png)

### Charts for each release, go1.2 to go1.27

Each chart has one panel for each program. The shaded band shows go1.23 to go1.27.
Each point is the median of 5 runs on the GCP machine.

**Elapsed time** (wall clock time).

![Elapsed time by Go release](results/final/plots/elapsed-by-version.png)

**CPU time** (user time and system time, added for all threads).

![CPU time by Go release](results/final/plots/cpu-by-version.png)

**Peak memory** (maximum resident set size).

![Peak memory by Go release](results/final/plots/memory-by-version.png)

**Build time** (compile and link of the program only, with a warm standard library).

![Build time by Go release](results/final/plots/build-by-version.png)

## Files

| path | contents |
|---|---|
| `bin/govm` | A small Go version manager. It downloads Go toolchains from the Go module proxy (`golang.org/toolchain`). `GOTOOLCHAIN` uses the same source. It compares each toolchain with `sum.golang.org`. All releases from go1.2.2 are available. |
| `programs/` | The Benchmarks Game programs, copied without changes from the official source zip file (BSD-3 license, refer to `programs/LICENSE`). This folder also has the `*.compat.go` backports. |
| `benchmarks.json` | The program for each task, its workload, its reference output and the time from the Benchmarks Game site. |
| `testdata/` | The official reference inputs and outputs. The harness compares each build with these files. |
| `bench.py` | The test harness. It builds, compares output, calculates checksums and does the timed runs. It writes JSON and a Markdown table. |
| `scripts/setup-ubuntu.sh` | Prepares Ubuntu 24.04 to 26.04 (GMP, PCRE). On 26.04, it builds PCRE 8.45 from source. The `--tune` option sets the CPU to a fixed configuration. |
| `scripts/compat.py` | Builds each program on each release and compares the output with the reference (now 312 of 312 pass). |
| `scripts/plots.py` | Makes the charts in `results/plots/` and the file `results/summary.md`. |
| `results/` | Raw JSON for each set of runs, `summary.md` and `plots/`. |

## Programs

For each task, we use the **fastest Go program by elapsed time** on the Benchmarks Game site.
The site measured go1.23.1 with `GOAMD64=v2` on a computer with 4 cores.

For pidigits and regex-redux, the fastest program calls a C library (GMP or PCRE).
Thus, we also measure the fastest **pure-Go** program for these two tasks.
The pure-Go program measures the Go compiler, runtime and standard library.

| task | program | type | notes |
|---|---|---|---|
| binary-trees | Go #2 | fastest | many allocations, much GC work |
| fannkuch-redux | Go #3 | fastest | |
| fasta | Go #2 | fastest | |
| k-nucleotide | Go #7 | fastest | built-in `map` |
| mandelbrot | Go #4 | fastest | |
| n-body | Go #3 | fastest | float64 |
| spectral-norm | Go #4 | fastest | |
| reverse-complement | Go #6 | fastest | input is approximately 1 GB (fasta n=100M) |
| pidigits | Go #4 | fastest | cgo → libgmp |
| pidigits | Go #6 | pure Go | `math/big` |
| regex-redux | Go #5 | fastest | cgo → libpcre (JIT), `github.com/GRbit/go-pcre v1.0.0` |
| regex-redux | Go #3 | pure Go | `regexp` |

Source of the programs: the repository of the Benchmarks Game site, through a mirror
([gitlab.com/hugefiver/benchmarksgame](https://gitlab.com/hugefiver/benchmarksgame) → `public/download/benchmarksgame-sourcecode.zip`).
The site measurements are in `public/data/data.csv`.

## Same source code on each release

Five programs use APIs that are newer than go1.2 or go1.12.
Each of these programs has a small `.compat.go` backport. **All Go releases use the backport.**

The backports make these changes:

| original | backport |
|---|---|
| signed shift count | `uint(...)` |
| `sort.Slice` | `sort.Sort` |
| `strings.Builder` | `bytes.Buffer` |
| `for range x` | `for _ = range x` |
| `bufio.Reader.Discard` | `ReadSlice('\n')` |

On go1.27.1, the backports have the same speed as the original programs, within the measurement noise.
They give the same full-size output, byte for byte (`results/backport-ab-go1.27.1.json`).

## Method

**Toolchains**

- We install each toolchain with `bin/govm install go1.X.Y`. The source is proxy.golang.org. We compare each toolchain with the checksum database.
- All builds use `GOTOOLCHAIN=local`.
- Releases go1.2 to go1.10 build in GOPATH mode.
- Before go1.8, cgo programs link with `-no-pie`.

**Builds**

- Each program builds as a separate module.
- The `go` directive is the same as the minor version of the toolchain. Thus, each release uses its own language rules.
  For example, from go1.22, each loop iteration has its own loop variable.
- All builds use `GOAMD64=v2`, the same as the Benchmarks Game site.
  With `v3`, newer compilers can use FMA instructions. This changes the results of n-body and spectral-norm.

**Output comparison**

- The harness compares each build with the official small-workload output, byte for byte.
- The harness calculates a SHA-256 checksum of the full-size output. Thus, we can find all output changes between Go releases.

**Timed runs**

- Standard output goes to `/dev/null`.
- **secs** is the wall clock time until the program stops.
- **cpu secs** is the user time and the system time, added for all threads (from the `wait4` rusage data).
  The Benchmarks Game site uses the same two columns.
- **memory** is the peak resident set size.
- **steal** is the hypervisor steal time during the run. It must be approximately 0.
- **build secs** is the time to compile and link the program only, with a warm standard library. Thus, you can compare it between releases.
- Each round runs all versions and all programs in alternate sequence. Thus, a slow period on the machine has the same effect on all versions.
- The results show the median and the minimum.

**Inputs**

- We make the inputs one time with fasta Go #1:
  k-nucleotide uses fasta 25M, regex-redux uses fasta 5M and reverse-complement uses fasta 100M.

## Usage

```sh
git clone https://github.com/nrnjn42/go-bench && cd go-bench
sudo scripts/setup-ubuntu.sh --tune
bin/govm list-remote                    # latest patch of each go1.N
scripts/compat.py                       # optional: build and output test for each release

# final measurement: all releases, 5 runs in alternate sequence, page cache dropped in each round (root)
sudo -E ./bench.py run $(bin/govm list-remote | sed 's/^/--go /') --runs 5 --drop-caches --label <machine>

python3 scripts/plots.py --sweep results/<file>.json --timed results/<file>.json
```

One round of all 12 programs on all 26 releases takes approximately 45 minutes. Thus, `--runs 5` takes approximately 4.5 hours.
The harness also does one full-size run of each program without a timer, to compare the output.

Recommended machine: 4 dedicated physical cores and 16 GB RAM or more.
An example is GCP `c3-standard-8 --threads-per-core=1`.

## Repeat the test on Google Cloud

You can repeat the full test with a GCP project. The test takes approximately 5 hours. The cost is approximately $2.
(On demand, c3-standard-8 costs approximately $0.40 for each hour in us-central1. Look at the current prices before you start.)

### Step 1: Make the virtual machine

Do this step on your computer. You must have the [gcloud CLI](https://cloud.google.com/sdk/docs/install).
You must be logged in and billing must be enabled.

```sh
gcloud config set project <your-project>
gcloud compute instances create go-bench \
  --zone=us-central1-a \
  --machine-type=c3-standard-8 --threads-per-core=1 \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-balanced
```

The option `--threads-per-core=1` disables SMT. Thus, Go has 4 physical cores and no hyperthreads.
The Benchmarks Game computer also has 4 cores.

> **CAUTION:** Do not use Spot VMs. If GCP stops a Spot VM, you lose the full run.
>
> **CAUTION:** Do not use shared-core `e2-*` machines. They share CPU time with other virtual machines. Thus, the times are not reliable.

You can use a different cloud provider. The machine must have 4 dedicated cores and 16 GB RAM or more.

### Step 2: Prepare the machine

This step takes approximately 3 minutes.

```sh
gcloud compute ssh go-bench --zone=us-central1-a
git clone https://github.com/nrnjn42/go-bench && cd go-bench
sudo scripts/setup-ubuntu.sh --tune
nproc                         # the result must be 4
scripts/compat.py             # optional, approximately 10 minutes: all 12 programs build and pass on all 26 releases
```

### Step 3: Do the test

Start the test in tmux. If the SSH connection stops, the test continues.

```sh
tmux new -s bench
sudo -E ./bench.py run $(bin/govm list-remote | sed 's/^/--go /') \
  --runs 5 --drop-caches --label gcp-c3-4c --output results/final-gcp-c3-4c.json
# disconnect: Ctrl-b d      connect again: tmux attach -t bench
```

Each output line shows `steal`. This value must stay near 0.
If it is more than approximately 1% of the CPU time of a run, the host takes CPU time from the virtual machine.
In this condition, use a different zone or a different machine type.

### Step 4: Analyze the results

```sh
python3 scripts/plots.py --sweep results/final-gcp-c3-4c.json --timed results/final-gcp-c3-4c.json
scripts/energy.py results/final-gcp-c3-4c.json --base go1.23.12 --new go1.27.1
```

### Step 5: Get the results and delete the virtual machine

Use one of these two methods to get the results.

Method A: push the results from the virtual machine. You must have your git credentials on the virtual machine.

```sh
git add results && git commit -m "final results: gcp c3-standard-8, 4 cores" && git push
```

Method B: copy the results to your computer.

```sh
gcloud compute scp --recurse go-bench:~/go-bench/results ./results-gcp --zone=us-central1-a
```

Then delete the virtual machine.

```sh
gcloud compute instances delete go-bench --zone=us-central1-a
```

> **CAUTION:** Make sure that you delete the virtual machine. If you do not delete it, it costs approximately $290 each month.

## Why the fastest C programs are faster

The difference on the Benchmarks Game comes mostly from the method used to write the C programs.
The work to set memory to zero is not the main cause. Other runtime work is also not the main cause.
Go sets memory to zero when it allocates the memory, not after use.
The CPU-bound programs do almost no allocations in their hot loops.

**Hand-written SIMD**

- In 5 of the 10 tasks, the fastest C program has a star on the site
  ("possible hand-written vector instructions"). Its source code uses x86 intrinsics:

  | C program | instructions |
  |---|---|
  | n-body #9 | AVX (`__m256d`, 4 doubles for each instruction) |
  | spectral-norm #6 | AVX (`__m256d`) |
  | mandelbrot #6 | SSE2 (`__m128d`) |
  | fannkuch-redux #6 | SSSE3/SSE4.1 byte shuffles (`_mm_shuffle_epi8`) |
  | reverse-complement #7 | SSSE3/SSE4.1 byte shuffles (`_mm_shuffle_epi8`) |

- The Go compiler does not vectorize code automatically. Go does not have a stable SIMD API.

**Go against the fastest C program without SIMD**

The data comes from the Benchmarks Game site (go1.23.1). The values show the Go time divided by the C time.

| task | against C without SIMD | against C with SIMD |
|---|---:|---:|
| n-body | 1.28× | 3.0× |
| spectral-norm | 1.00× | 3.6× |
| mandelbrot | 0.93× | 2.9× |
| fannkuch-redux | 1.15× | 3.9× |

**C libraries and memory management**

The other five fastest C programs do not have a star. But they call C libraries:

- k-nucleotide uses khash.
- binary-trees uses APR memory pools. It frees each full tree in one operation. Thus, it has no GC cost.
- pidigits uses GMP.
- regex-redux uses PCRE2.

**Build settings**

- GCC compiles the C programs with `-O3 -march=<cpu>`. This gives more inline expansion and more loop optimization.
  It also lets the compiler use the newest instructions of the host CPU.
- Go uses its default toolchain, which compiles quickly, with `GOAMD64=v2`.
- Go keeps slice bounds checks when it cannot prove that they are not necessary.

### binary-trees with pre-allocated nodes

The file `programs/binarytrees/binarytrees-arena.go` makes the same trees as Go #2. But it puts the nodes in a pre-allocated slice.
Each worker has its own slice and uses it again for each tree.

- The children are `int32` indexes, not pointers. Thus, the GC does not scan the nodes.
- The program does no allocations after start-up.
- The output is the same as the reference output, byte for byte.

> **NOTE:** The Benchmarks Game does not accept this program. The rules do not permit hand-written memory pools.
> The C program gets the same result with the APR pool library.

We measured this program against Go #2 on go1.27.1, with 5 runs in alternate sequence.
We used a shared virtual machine with 4 vCPUs, not the GCP machine.

| | Go #2 | pre-allocated | ratio |
|---|---:|---:|---:|
| elapsed time | 11.28 s | 1.09 s | 0.097 |
| CPU time | 42.85 s | 3.41 s | 0.079 |
| peak memory | 594 MB | 131 MB | 0.22 |

**Estimate for the GCP results.** We applied these ratios to binary-trees on go1.27.1. The other 11 programs did not change.

- binary-trees: elapsed time 6.08 s → **approximately 0.59 s**. CPU time 23.8 s → approximately 1.9 s.
  Peak memory 642 MB → approximately 140 MB. Calculated energy 1,789 J → approximately 172 J.
- All programs: geometric mean of elapsed time **−17.7%** (2.41 s → 1.99 s). Total CPU time **−15.8%**. Calculated energy **−11.6%**.
- Against C: on the site machine, Go #2 takes 14.21 s and C gcc #2 takes 1.56 s.
  With the same ratio, the pre-allocated Go program takes approximately 1.4 s. This is almost the same as C.

To measure this program on the GCP machine, use this command:

```sh
sudo -E ./bench.py run --config benchmarks-binarytrees-arena.json --go go1.27.1 --runs 5 --drop-caches
```

## Energy

The script `scripts/energy.py` calculates the change in energy between two releases. It does not need a power meter.

The script uses a linear model. The model comes from the raw RAPL data of van Kempen et al.,
[*It's Not Easy Being Green*](https://arxiv.org/abs/2410.05460)
(2024; [data](https://github.com/nicovank/energy-languages)). Their Go release was 1.23.1.

    energy ≈ 1.99 J × cpu-seconds + 286.6 J × elapsed-seconds     (R² = 0.97 over 3,192 runs, 13 languages)

On their server with two CPU sockets, the elapsed time has the largest effect on energy.
CPU time alone does not predict energy on that server (R² ≈ 0).
Thus, the script shows CPU time, elapsed time and calculated energy together.

The constants are different on each machine. To calculate them again, use `scripts/energy.py --refit <repo>`.

The table shows the change from each release to go1.27.1 (geometric mean, GCP data).
To make this table, use `scripts/energy.py results/final/gcp-c3-4c-all-versions.json --base <old> --new go1.27.1`.

| from | CPU time | elapsed time | calculated energy |
|---|---:|---:|---:|
| go1.23.12 | −12.3% | −11.5% | −11.5% |
| go1.20.14 | −12.4% | −12.2% | −12.2% |
| go1.10.8 | −13.4% | −13.9% | −13.9% |
| go1.8.7 | −14.4% | −14.0% | −14.0% |
| go1.6.4 | −27.6% | −28.1% | −28.1% |

## Limits of the results

- The absolute values are different on each machine. Compare only the versions that you measured on the same host.
  It is better to measure them in the same run, in alternate sequence.
- Shared cloud virtual machines give noisy results. Page faults are slow on these machines.
  For example, reverse-complement #6 increases its buffer in steps of 60 MB.
  On a Firecracker virtual machine, it uses most of its time in the kernel (refer to the `sys` column).
- For published results, use a dedicated or bare-metal computer. Set a fixed CPU frequency. Stop all other work on the computer.
- reverse-complement allocates approximately 1.6 GB. If the page cache fills the RAM, its page faults become slower. Use `--drop-caches`.
- The reference data is in `results/final/` (GCP). The other files in `results/` come from test runs on a shared virtual machine.
  Do not compare them with the reference data.

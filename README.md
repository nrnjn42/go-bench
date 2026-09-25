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
| `programs/` | the chosen Benchmarks Game programs, copied verbatim from the official source zip (BSD-3, see `programs/LICENSE`) |
| `benchmarks.json` | which program represents each task, with its workload, reference check and the site's own time |
| `testdata/` | official reference inputs and outputs, used to check every build |
| `bench.py` | build → check → checksum → timed runs, interleaved across versions; writes JSON and a Markdown table |
| `results/` | raw JSON per run set, plus `*.md` summaries |

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

## Method

* Toolchains: `bin/govm install go1.X.Y` (proxy.golang.org, sumdb-verified). Builds run with `GOTOOLCHAIN=local`.
* Each program builds as its own module. The `go` directive equals the toolchain's minor version, so every release compiles with its own language semantics (for example, per-iteration loop variables from 1.22 on).
* `GOAMD64=v2`, same as the site. (v3 would let newer compilers fuse FMA and change n-body/spectral-norm results.)
* Every build is checked byte-for-byte against the official small-workload output. The full-size output is SHA-256'd so any drift between Go versions shows up.
* Timed runs: stdout goes to `/dev/null`. Elapsed is wall clock, cpu/sys come from `wait4` rusage, memory is peak RSS. Rounds interleave versions × programs, so slow periods on the machine hit every version equally. Median and min are both reported.
* Inputs for k-nucleotide (fasta 25M), regex-redux (fasta 5M) and reverse-complement (fasta 100M) are generated once with fasta Go #1.

## Usage

```sh
sudo apt-get install -y libgmp-dev libpcre3-dev    # for the two cgo programs
bin/govm list-remote                               # latest patch of every go1.N
./bench.py run --go go1.27.1 --runs 5 --label my-box
./bench.py run --go go1.27.1 --go go1.26.8 --go go1.25.14 --runs 5   # interleaved comparison
./bench.py report results/*.json
```

## Caveats (worth stating in the post)

* Absolute numbers depend on the machine. Only compare versions measured on the same host, ideally in the same interleaved run.
* Shared cloud VMs are noisy, and page faults are expensive on them. reverse-complement #6 reallocates its buffer in 60 MB steps, so on a Firecracker VM it spends most of its time in the kernel (see the `sys` column). For publication, prefer a dedicated or bare-metal box, fixed CPU frequency, and no other load.
* Toolchains before go1.11 have no module support, so the harness will need a GOPATH build mode for them. Very old releases may not build some programs at all; that is itself a data point.

#!/usr/bin/env bash
# Initial (non-final) sweep completion on the dev VM:
#  - go1.2 .. go1.9: 2 interleaved timed runs of every program
#  - go1.10 .. go1.27: 2 timed runs of the large-output programs, whose
#    single smoke run was slowed by hashing stdout
set -u
cd "$(dirname "$0")/.."
old=(); new=()
for v in $(bin/govm list-remote); do
  m=$(echo "$v" | sed 's/go1\.\([0-9]*\).*/\1/')
  if (( m < 10 )); then old+=(--go "$v"); else new+=(--go "$v"); fi
done
./bench.py run "${old[@]}" --runs 2 --label initial --output results/smoke/go1.2-go1.9-runs2.json \
  > results/smoke/go1.2-go1.9-runs2.log 2>&1; echo "OLD done $?"
./bench.py run "${new[@]}" --runs 2 --only fasta,revcomp,mandelbrot --label initial \
  --output results/smoke/go1.10-go1.27-io-runs2.json > results/smoke/go1.10-go1.27-io-runs2.log 2>&1
echo "IO done $?"

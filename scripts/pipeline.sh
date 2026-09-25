#!/usr/bin/env bash
# 1) backport A/B on go1.27.1  2) timed go1.23..go1.27 comparison  3) smoke sweep
set -u
cd "$(dirname "$0")/.."
./bench.py run --go go1.27.1 --runs 3 --with-upstream \
  --only binarytrees-2,binarytrees-2u,knucleotide-7,knucleotide-7u,pidigits-4,pidigits-4u,regexredux-3,regexredux-3u,revcomp-6,revcomp-6u \
  --label backport-ab --output results/backport-ab-go1.27.1.json > work/ab.log 2>&1
echo "AB done $?"
./bench.py run --go go1.23.12 --go go1.24.13 --go go1.25.14 --go go1.26.8 --go go1.27.1 --runs 5 \
  --label cloud-xeon-4c --output results/timed-go1.23-go1.27.json > work/timed.log 2>&1
echo "TIMED done $?"
scripts/smoke-all.sh
echo "SWEEP done"

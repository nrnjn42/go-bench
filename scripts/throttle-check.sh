#!/usr/bin/env bash
# Re-run go1.27.1 (2 runs) after a long session and compare with the earlier
# go1.27.1 measurements; also logs hypervisor steal time per run.
set -u
cd "$(dirname "$0")/.."
awk '/^cpu /{print "steal-before", $9}' /proc/stat
./bench.py run --go go1.27.1 --runs 2 --label throttle-check \
  --output results/throttle-check-go1.27.1.json > work/throttle.log 2>&1
awk '/^cpu /{print "steal-after", $9}' /proc/stat
echo "THROTTLE done"

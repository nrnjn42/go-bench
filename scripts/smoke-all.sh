#!/usr/bin/env bash
# One full-size, output-checked run of every program on the latest patch of
# every Go minor release, newest first. Verifies the harness, not performance.
set -u
cd "$(dirname "$0")/.."
mkdir -p results/smoke
for v in $(bin/govm list-remote | sort -rV); do
  [[ -f results/smoke/$v.json ]] && continue
  ./bench.py run --go "$v" --runs 0 --label smoke --output "results/smoke/$v.json" \
    > "results/smoke/$v.log" 2>&1 || echo "harness error on $v" >&2
  grep -cE "output ok" "results/smoke/$v.log" | xargs echo "$v ok:"
done

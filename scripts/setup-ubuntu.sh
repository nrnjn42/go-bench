#!/usr/bin/env bash
# Prepare a fresh Ubuntu 24.04 / 25.x / 26.04 (amd64 or arm64) box for go-bench.
#   sudo scripts/setup-ubuntu.sh            # packages (+ PCRE1 from source on 26.04)
#   sudo scripts/setup-ubuntu.sh --tune     # also pin CPU for stable timings (dedicated boxes only)
set -euo pipefail

PCRE_VER=8.45
PCRE_SHA256=4dae6fdcd2bb0bb6c37b5f97c33c2be954da743985369cddac3546e3218bffb8

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a            # never show needrestart's service dialog
export NEEDRESTART_SUSPEND=1
# fresh cloud VMs run unattended-upgrades at first boot; wait for its lock
APT=(apt-get -y -o DPkg::Lock::Timeout=900 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)

step() { echo; echo "==> $*"; }

if pgrep -x unattended-upgr >/dev/null || pgrep -f unattended-upgrade >/dev/null; then
  step "waiting for first-boot unattended-upgrades to finish (can take a few minutes)"
fi
step "apt-get update"
"${APT[@]}" update
step "installing build tools, GMP, python3-matplotlib"
"${APT[@]}" install --no-install-recommends build-essential pkg-config curl unzip \
  python3 python3-matplotlib libgmp-dev ca-certificates

# regex-redux #5 binds PCRE1 (libpcre). Ubuntu 26.04 dropped libpcre3-dev.
step "PCRE1 for regex-redux #5"
if apt-cache show libpcre3-dev >/dev/null 2>&1; then
  "${APT[@]}" install --no-install-recommends libpcre3-dev
  echo "libpcre3-dev installed from apt"
elif ! pkg-config --exists libpcre; then
  echo "libpcre3-dev not packaged here; building PCRE $PCRE_VER from source (~1 min)"
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/pcre.tar.bz2" \
    "https://sourceforge.net/projects/pcre/files/pcre/$PCRE_VER/pcre-$PCRE_VER.tar.bz2/download"
  echo "$PCRE_SHA256  $tmp/pcre.tar.bz2" | sha256sum -c -
  tar -xjf "$tmp/pcre.tar.bz2" -C "$tmp"
  (cd "$tmp/pcre-$PCRE_VER" &&
    ./configure --prefix=/usr/local --enable-jit --enable-utf --enable-unicode-properties \
      --disable-static --disable-cpp >/dev/null &&
    make -j"$(nproc)" >/dev/null && make install >/dev/null)
  ldconfig
  rm -rf "$tmp"
fi
pkg-config --modversion libpcre >/dev/null && echo "libpcre $(pkg-config --modversion libpcre) ok"

if [[ "${1:-}" == --tune ]]; then
  step "CPU tuning"
  # Stable timings: performance governor, no turbo, no THP surprises.
  if compgen -G "/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor" >/dev/null; then
    for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > "$g" || true; done
  else
    echo "no cpufreq in this guest (normal on cloud VMs): the host controls frequency"
  fi
  if [[ -w /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo || true; fi
  if [[ -w /sys/devices/system/cpu/cpufreq/boost ]]; then echo 0 > /sys/devices/system/cpu/cpufreq/boost || true; fi
  echo "CPU tuned (governor=performance, turbo off where supported)"
fi

step "done: $(nproc) CPUs, $(awk '/MemTotal/{printf "%.0f GB", $2/1048576}' /proc/meminfo) RAM"
echo "Throttling check — run the harness only if these look sane:"
echo "  steal time (%st in top) should stay ~0 during a run"
grep -H . /sys/fs/cgroup/cpu.max 2>/dev/null || true
awk '/^cpu /{print "  steal jiffies since boot:", $9}' /proc/stat

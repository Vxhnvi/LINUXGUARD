#!/usr/bin/env bash
# system_info.sh - print a read-only snapshot of this Linux system.
# Usage: ./scripts/system_info.sh
set -uo pipefail

section() { printf '\n===== %s =====\n' "$1"; }
have()    { command -v "$1" >/dev/null 2>&1; }

section "Host"
echo "Hostname : $(hostname)"
if [ -r /etc/os-release ]; then . /etc/os-release; echo "OS       : ${PRETTY_NAME:-unknown}"; fi
echo "Kernel   : $(uname -r)"
echo "Arch     : $(uname -m)"
echo "Uptime   : $(uptime -p 2>/dev/null || cat /proc/uptime)"
echo "Date     : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

section "CPU"
echo "Cores    : $(nproc 2>/dev/null || echo unknown)"
grep -m1 'model name' /proc/cpuinfo 2>/dev/null || echo "model name unavailable"
echo "Load avg : $(cut -d' ' -f1-3 /proc/loadavg)"

section "Memory"
if have free; then free -h; else grep -E 'MemTotal|MemAvailable' /proc/meminfo; fi

section "Disk"
df -h -x tmpfs -x devtmpfs 2>/dev/null || df -h

section "Top 5 processes by CPU"
ps -eo pid,comm,%cpu,%mem --sort=-%cpu 2>/dev/null | head -6 || echo "ps unavailable"

section "Network"
if have ip; then ip -brief address 2>/dev/null; else echo "ip command not found"; fi
echo "--- listening TCP/UDP sockets ---"
if have ss; then ss -tuln 2>/dev/null | head -15; else echo "ss command not found"; fi

section "systemd"
if [ -d /run/systemd/system ] && have systemctl; then
  echo "systemd running; failed units:"; systemctl --failed --no-legend 2>/dev/null | head -10 || true
else
  echo "systemd not running (container or some WSL setups)"
fi
exit 0

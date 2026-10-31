#!/usr/bin/env bash
# health_check.sh - check disk, memory and load. Read-only.
# Exit codes: 0 = OK, 1 = at least one WARNING, 2 = at least one CRITICAL.
# Override limits with env vars, e.g.  DISK_CRIT=95 ./scripts/health_check.sh
set -uo pipefail

DISK_PATH="${DISK_PATH:-/}"
DISK_WARN="${DISK_WARN:-80}"; DISK_CRIT="${DISK_CRIT:-90}"
MEM_WARN="${MEM_WARN:-85}";   MEM_CRIT="${MEM_CRIT:-95}"
LOAD_WARN_PER_CORE="${LOAD_WARN_PER_CORE:-1.0}"
API_URL="${API_URL:-}"        # optional, e.g. http://localhost:5000/api/health

status=0
bump() { [ "$1" -gt "$status" ] && status=$1; }
report() { # level label value limit
  printf '%-9s %-8s %s (limit %s)\n' "[$1]" "$2" "$3" "$4"
}
grade() { # value warn crit label unit
  local v=$1 w=$2 c=$3 label=$4
  if   [ "$v" -ge "$c" ]; then report CRITICAL "$label" "${v}%" "${c}%"; bump 2
  elif [ "$v" -ge "$w" ]; then report WARNING  "$label" "${v}%" "${w}%"; bump 1
  else                         report OK       "$label" "${v}%" "${w}%"; fi
}

# --- disk ---
disk_pct=$(df --output=pcent "$DISK_PATH" 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -z "$disk_pct" ]; then echo "ERROR: cannot read disk usage for $DISK_PATH" >&2; exit 2; fi
grade "$disk_pct" "$DISK_WARN" "$DISK_CRIT" "disk"

# --- memory (used = 100 * (total - available) / total) ---
if [ ! -r /proc/meminfo ]; then echo "ERROR: /proc/meminfo unreadable" >&2; exit 2; fi
mem_total=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
mem_avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
if [ -z "$mem_total" ] || [ -z "$mem_avail" ] || [ "$mem_total" -eq 0 ]; then
  echo "ERROR: could not parse /proc/meminfo" >&2; exit 2
fi
grade $(( 100 * (mem_total - mem_avail) / mem_total )) "$MEM_WARN" "$MEM_CRIT" "memory"

# --- load average per core ---
cores=$(nproc 2>/dev/null || echo 1)
load1=$(cut -d' ' -f1 /proc/loadavg)
if awk -v l="$load1" -v c="$cores" -v t="$LOAD_WARN_PER_CORE" 'BEGIN{exit !(l/c > t)}'; then
  report WARNING load "$load1 on $cores core(s)" "${LOAD_WARN_PER_CORE}/core"; bump 1
else
  report OK load "$load1 on $cores core(s)" "${LOAD_WARN_PER_CORE}/core"
fi

# --- optional: LinuxGuard API ---
if [ -n "$API_URL" ]; then
  if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 5 "$API_URL" >/dev/null 2>&1; then
    report OK api "$API_URL reachable" "-"
  else
    report CRITICAL api "$API_URL unreachable" "-"; bump 2
  fi
fi

case $status in 0) echo "RESULT: healthy";; 1) echo "RESULT: warning";; 2) echo "RESULT: critical";; esac
exit $status

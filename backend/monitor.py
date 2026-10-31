"""System metric collection using psutil and read-only systemd queries.

Nothing here modifies the system. Processes are only *listed*, never signalled.
"""
import os
import platform
import shutil
import socket
import subprocess
import time

import psutil

from .config import SERVICE_NAME_RE
from .models import MetricSample

_SEEN = set()  # (pid, create_time) of processes whose CPU counter has been primed

def get_system_info():
    boot = psutil.boot_time()
    uname = platform.uname()
    os_name = uname.system
    try:  # /etc/os-release gives the pretty distro name on Linux
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    os_name = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return {
        "hostname": socket.gethostname(),
        "os": os_name,
        "kernel": uname.release,
        "architecture": uname.machine,
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "boot_time": boot,
        "uptime_seconds": int(time.time() - boot),
        "timestamp": time.time(),
    }


def compute_rate(prev_value, cur_value, dt):
    """Bytes/second from two cumulative counters.

    Counters only ever grow, so a smaller current value means the counter reset
    (reboot / interface restart): report 0 instead of a huge negative number.
    """
    if prev_value is None or dt <= 0 or cur_value < prev_value:
        return 0.0
    return (cur_value - prev_value) / dt


def collect_metrics(prev=None, disk_path="/", cpu_interval=None):
    """Take one reading from the OS. `prev` is the previous MetricSample (for network rates)."""
    cpu = psutil.cpu_percent(interval=cpu_interval)
    try:
        load1, load5, load15 = os.getloadavg()  # not available on Windows
    except (OSError, AttributeError):
        load1 = load5 = load15 = 0.0
    mem = psutil.virtual_memory()
    try:
        # psutil's percent = used / (used + free-for-users), the same figure `df` prints.
        # (used/total would under-report on filesystems with reserved blocks.)
        disk = psutil.disk_usage(disk_path)
        disk_pct = float(disk.percent)
        disk_total, disk_used, disk_free = disk.total, disk.used, disk.free
    except OSError:
        disk_pct, disk_total, disk_used, disk_free = 0.0, 0, 0, 0
    net = psutil.net_io_counters()
    now = time.time()
    s = MetricSample(
        ts=now, hostname=socket.gethostname(),
        cpu_percent=float(cpu), load1=load1, load5=load5, load15=load15,
        mem_percent=float(mem.percent), mem_total=mem.total, mem_used=mem.used, mem_available=mem.available,
        disk_percent=disk_pct, disk_total=disk_total, disk_used=disk_used, disk_free=disk_free,
        net_bytes_sent=net.bytes_sent, net_bytes_recv=net.bytes_recv,
        net_packets_sent=net.packets_sent, net_packets_recv=net.packets_recv,
    )
    if prev is not None:
        dt = now - prev.ts
        s.net_sent_rate = compute_rate(prev.net_bytes_sent, s.net_bytes_sent, dt)
        s.net_recv_rate = compute_rate(prev.net_bytes_recv, s.net_bytes_recv, dt)
    return s


def list_processes(sort_by="cpu", limit=15):
    """Top processes by CPU or memory. Read-only; never signals or modifies a process.

    - psutil.process_iter() re-uses Process objects between calls, so cpu_percent(None)
      measures CPU since the previous call. The very first reading of a process has no
      baseline, so it is reported as None ("not ready") instead of a misleading 0.0.
    - Processes that exit mid-scan, zombies and permission-denied fields are skipped/None.
    - cpu_percent is % of ONE core (can exceed 100 on multi-core machines, like `top`).
    """
    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    rows, live = [], set()
    for p in psutil.process_iter(["pid", "name", "status", "memory_percent", "username", "create_time"]):
        try:
            info = p.info
            ident = (info["pid"], info.get("create_time"))
            live.add(ident)
            cpu = p.cpu_percent(None)
            if ident not in _SEEN:        # first sighting: counter just primed
                _SEEN.add(ident)
                cpu = None
            mem = info.get("memory_percent")
            rows.append({
                "pid": info["pid"],
                "name": info.get("name") or "?",
                "status": info.get("status"),
                "cpu_percent": None if cpu is None else round(cpu, 1),
                "memory_percent": None if mem is None else round(mem, 2),
                "user": info.get("username"),       # None when access is denied
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue                                # exited or not readable: skip
    _SEEN.intersection_update(live)                 # forget processes that are gone
    rows.sort(key=lambda r: (r[key] if r[key] is not None else -1.0, -r["pid"]), reverse=True)
    return rows[:limit]


def warm_process_counters():
    """Prime per-process CPU counters so the first API call returns real numbers."""
    list_processes("cpu", 1)


def systemd_available():
    """True only if systemd is the running init (WSL/containers often lack it)."""
    return os.path.isdir("/run/systemd/system") and shutil.which("systemctl") is not None


def get_services(names):
    """Read-only `systemctl is-active` for allow-listed service names.

    subprocess gets an argument list (no shell) and names are regex-validated,
    so no user-controlled string can become a command.
    """
    if not systemd_available():
        return {"systemd_available": False,
                "message": "systemd is not running on this host (containers and some WSL setups).",
                "services": []}
    out = []
    for name in names:
        if not SERVICE_NAME_RE.match(name):
            continue
        try:
            r = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=5)
            state = r.stdout.strip() or "unknown"
        except (subprocess.TimeoutExpired, OSError):
            state = "unknown"
        out.append({"name": name, "state": state, "running": state == "active"})
    return {"systemd_available": True, "message": "", "services": out}

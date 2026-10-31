import time

from backend import monitor
from backend.collector import Collector
from backend import database as db
from tests.conftest import make_sample


def test_collect_metrics_reads_real_os_values():
    s = monitor.collect_metrics(None, "/", cpu_interval=0.1)
    assert 0 <= s.cpu_percent <= 100
    assert 0 < s.mem_percent <= 100 and s.mem_total > 0
    assert s.mem_available <= s.mem_total
    assert 0 <= s.disk_percent <= 100 and s.disk_total > 0
    assert s.disk_used + s.disk_free <= s.disk_total
    assert s.net_bytes_recv >= 0 and s.net_packets_sent >= 0


def test_bad_disk_path_does_not_crash():
    s = monitor.collect_metrics(None, "/definitely/not/a/path")
    assert s.disk_total == 0 and s.disk_percent == 0.0


def test_rate_normal_and_counter_reset():
    assert monitor.compute_rate(1000, 3000, 2) == 1000.0
    assert monitor.compute_rate(5000, 100, 2) == 0.0   # counter reset must not go negative
    assert monitor.compute_rate(None, 100, 2) == 0.0
    assert monitor.compute_rate(100, 200, 0) == 0.0    # zero interval


def test_network_rate_computed_from_previous_sample():
    prev = make_sample(ts=time.time() - 2)
    prev.net_bytes_recv = 0
    prev.net_bytes_sent = 0
    cur = monitor.collect_metrics(prev, "/")
    assert cur.net_recv_rate >= 0 and cur.net_sent_rate >= 0


def test_system_info_fields():
    info = monitor.get_system_info()
    for key in ("hostname", "os", "kernel", "uptime_seconds", "cpu_cores_logical"):
        assert key in info
    assert info["uptime_seconds"] > 0


def test_list_processes_sorted_and_limited():
    monitor.list_processes("cpu", 5)  # prime per-process CPU counters
    procs = monitor.list_processes("memory", 5)
    assert 0 < len(procs) <= 5
    mems = [p["memory_percent"] for p in procs]
    assert mems == sorted(mems, reverse=True)
    assert {"pid", "name", "status", "cpu_percent", "memory_percent"} <= set(procs[0])


def test_services_when_systemd_missing(monkeypatch):
    monkeypatch.setattr(monitor, "systemd_available", lambda: False)
    r = monitor.get_services(["ssh"])
    assert r["systemd_available"] is False and r["services"] == []


def test_services_with_fake_systemctl(monkeypatch):
    class R:  # stand-in for subprocess.CompletedProcess
        stdout = "active\n"
    calls = []
    monkeypatch.setattr(monitor, "systemd_available", lambda: True)
    monkeypatch.setattr(monitor.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or R())
    r = monitor.get_services(["ssh", "bad name; rm -rf /"])
    assert [s["name"] for s in r["services"]] == ["ssh"]      # unsafe name skipped
    assert r["services"][0]["running"] is True
    assert calls == [["systemctl", "is-active", "ssh"]]       # list args, no shell


def test_database_insert_and_retrieve(dbpath):
    db.insert_metric(dbpath, make_sample(ts=time.time(), cpu=42.5))
    row = db.latest_metric(dbpath)
    assert row["cpu_percent"] == 42.5 and row["hostname"] == "testhost"
    assert len(db.metric_history(dbpath, time.time() - 60)) == 1


def test_database_persists_across_connections(tmp_path):
    path = str(tmp_path / "p.db")
    db.init_db(path)
    db.insert_metric(path, make_sample(ts=time.time()))
    db.init_db(path)  # re-init (like a restart) must not wipe data
    assert db.latest_metric(path) is not None


def test_prune_and_downsample(dbpath):
    now = time.time()
    db.insert_metric(dbpath, make_sample(ts=now - 10 * 86400))
    for i in range(50):
        db.insert_metric(dbpath, make_sample(ts=now - 50 + i))
    assert db.prune_metrics(dbpath, 7) == 1
    assert len(db.metric_history(dbpath, now - 100, limit=10)) == 10


def test_collector_run_once_writes_row_and_alerts(cfg, dbpath):
    c = Collector(cfg)
    c.run_once()
    c.run_once()
    assert db.latest_metric(dbpath) is not None
    assert c.prev is not None


# ---------------- process edge cases ----------------
import psutil  # noqa: E402


def test_first_sighting_cpu_is_none_then_numeric():
    monitor._SEEN.clear()
    first = monitor.list_processes("memory", 3)
    assert all(p["cpu_percent"] is None for p in first)           # no baseline yet: not a fake 0.0
    second = monitor.list_processes("memory", 3)
    assert all(isinstance(p["cpu_percent"], float) for p in second)


def test_process_that_vanishes_or_denies_access_is_skipped(monkeypatch):
    class Gone:
        info = {"pid": 1, "name": "x", "status": "r", "memory_percent": 1, "username": "u", "create_time": 1}
        def cpu_percent(self, _):
            raise psutil.NoSuchProcess(1)

    class Denied(Gone):
        def cpu_percent(self, _):
            raise psutil.AccessDenied(2)

    class Ok:
        info = {"pid": 3, "name": None, "status": "sleeping", "memory_percent": None, "username": None, "create_time": 3}
        def cpu_percent(self, _):
            return 1.234

    monkeypatch.setattr(monitor.psutil, "process_iter", lambda attrs: iter([Gone(), Denied(), Ok()]))
    monitor._SEEN.clear()
    monitor.list_processes("cpu", 10)
    rows = monitor.list_processes("cpu", 10)
    assert len(rows) == 1
    assert rows[0]["name"] == "?" and rows[0]["user"] is None
    assert rows[0]["memory_percent"] is None and rows[0]["cpu_percent"] == 1.2


def test_sorting_by_cpu_is_descending_with_none_last(monkeypatch):
    def mk(pid, cpu):
        class P:
            info = {"pid": pid, "name": f"p{pid}", "status": "r", "memory_percent": 1.0, "username": "u", "create_time": pid}
            def cpu_percent(self, _):
                return cpu
        return P()
    monkeypatch.setattr(monitor.psutil, "process_iter", lambda attrs: iter([mk(1, 5.0), mk(2, 50.0), mk(3, 20.0)]))
    monitor._SEEN.clear()
    monitor.list_processes("cpu", 10)           # prime
    assert [r["pid"] for r in monitor.list_processes("cpu", 10)] == [2, 3, 1]
    assert len(monitor.list_processes("cpu", 2)) == 2


def test_seen_set_forgets_exited_processes(monkeypatch):
    monitor._SEEN.clear()
    monitor.list_processes("cpu", 1)
    assert len(monitor._SEEN) > 0
    monkeypatch.setattr(monitor.psutil, "process_iter", lambda attrs: iter([]))
    monitor.list_processes("cpu", 1)
    assert len(monitor._SEEN) == 0

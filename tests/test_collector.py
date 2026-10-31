import sqlite3
import time

from backend import collector, database as db, monitor
from backend.collector import Collector
from tests.conftest import make_cfg


def test_singleton_one_collector_per_process(tmp_path):
    cfg = make_cfg(tmp_path)
    db.init_db(cfg.db_path)
    a = collector.start_collector(cfg)
    b = collector.start_collector(cfg)
    try:
        assert a is b
        assert sum(1 for t in __import__("threading").enumerate() if t.name == "linuxguard-collector") == 1
    finally:
        collector.stop_collector()


def test_graceful_shutdown(tmp_path):
    cfg = make_cfg(tmp_path)
    db.init_db(cfg.db_path)
    agent = collector.start_collector(cfg)
    time.sleep(0.3)
    stopped = collector.stop_collector(timeout=5)
    assert stopped is agent and not agent.is_alive()
    assert collector.get_agent() is None


def test_error_in_one_cycle_does_not_stop_collector(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    db.init_db(cfg.db_path)
    real = monitor.collect_metrics
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:            # call 1 is the warm-up reading
            raise RuntimeError("boom")
        return real(*a, **kw)

    monkeypatch.setattr(monitor, "collect_metrics", flaky)
    cfg.poll_seconds = 1
    c = Collector(cfg)
    c.start()
    time.sleep(2.8)
    c.stop_event.set()
    c.join(3)
    assert calls["n"] >= 3 and c.samples >= 1       # kept going after the failure
    assert c.consecutive_failures == 0 and c.last_success_ts is not None


def test_database_error_is_recorded_and_backoff_grows(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    db.init_db(cfg.db_path)
    monkeypatch.setattr(db, "insert_metric", lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
    c = Collector(cfg)
    assert c._wait_time() == cfg.poll_seconds
    try:
        c.run_once()
    except sqlite3.Error as e:
        c._fail(e, "database error")
    assert c.consecutive_failures == 1 and "OperationalError" in c.last_error
    assert c._wait_time() == cfg.poll_seconds * 2
    c.consecutive_failures = 20
    assert c._wait_time() == Collector.MAX_BACKOFF
    assert c.prev is not None          # baseline kept so network rates stay correct


def test_network_rate_survives_failed_write(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    db.init_db(cfg.db_path)
    c = Collector(cfg)
    c.run_once()
    first = c.prev
    monkeypatch.setattr(db, "insert_metric", lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("x")))
    try:
        c.run_once()
    except sqlite3.Error:
        pass
    assert c.prev is not first          # prev advanced despite DB failure


def test_retention_cleanup_runs_from_collector(tmp_path):
    from tests.conftest import make_sample
    cfg = make_cfg(tmp_path)
    db.init_db(cfg.db_path)
    db.insert_metric(cfg.db_path, make_sample(ts=time.time() - 30 * 86400))
    c = Collector(cfg)
    c.run_once()                        # first cycle triggers pruning (_last_prune == 0)
    assert all(r["ts"] > time.time() - 86400 for r in db.metric_history(cfg.db_path, 0))


def test_status_reports_health(tmp_path):
    cfg = make_cfg(tmp_path)
    db.init_db(cfg.db_path)
    c = Collector(cfg)
    c.run_once()
    st = c.status()
    assert st["samples"] == 1 and st["consecutive_failures"] == 0 and "running" in st

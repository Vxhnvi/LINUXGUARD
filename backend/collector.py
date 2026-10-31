"""Background monitoring agent. Runs in its own thread, independent of the dashboard.

DEPLOYMENT ASSUMPTION: run exactly ONE LinuxGuard process per database. The singleton
below prevents two collectors inside one process; it cannot stop a second process
(e.g. gunicorn with several workers) from starting its own collector.
"""
import logging
import sqlite3
import threading
import time

from . import alerts, database as db, monitor

log = logging.getLogger("linuxguard.collector")
_lock = threading.Lock()
_agent = None  # module-level singleton


class Collector(threading.Thread):
    MAX_BACKOFF = 60

    def __init__(self, cfg):
        super().__init__(name="linuxguard-collector", daemon=True)
        self.cfg = cfg
        self.stop_event = threading.Event()
        self.prev = None
        self._last_prune = 0
        # health statistics (read by /api/health)
        self.samples = 0
        self.consecutive_failures = 0
        self.last_error = None
        self.last_success_ts = None

    def run_once(self):
        sample = monitor.collect_metrics(self.prev, self.cfg.disk_path)
        self.prev = sample                 # keep the baseline even if the DB write fails,
        db.insert_metric(self.cfg.db_path, sample)   # so network rates stay correct
        alerts.evaluate_sample(self.cfg.db_path, sample, self.cfg.hysteresis)
        self.samples += 1
        if time.time() - self._last_prune > 3600:    # hourly retention cleanup
            removed = db.prune_metrics(self.cfg.db_path, self.cfg.retention_days)
            self._last_prune = time.time()
            if removed:
                log.info("retention: removed %d old metric rows", removed)
        return sample

    def _wait_time(self):
        if self.consecutive_failures == 0:
            return self.cfg.poll_seconds
        return min(self.cfg.poll_seconds * 2 ** min(self.consecutive_failures, 6), self.MAX_BACKOFF)

    def run(self):
        try:
            monitor.collect_metrics(None, self.cfg.disk_path, cpu_interval=0.5)  # prime CPU counter
            monitor.warm_process_counters()
        except Exception:
            log.exception("collector warm-up failed (continuing)")
        while not self.stop_event.is_set():
            try:
                self.run_once()
                self.consecutive_failures = 0
                self.last_error = None
                self.last_success_ts = time.time()
            except sqlite3.Error as e:      # database trouble: log, back off, retry
                self._fail(e, "database error")
            except Exception as e:          # anything else must not kill the agent
                self._fail(e, "collection error")
            self.stop_event.wait(self._wait_time())
        log.info("collector stopped")

    def _fail(self, exc, kind):
        self.consecutive_failures += 1
        self.last_error = f"{kind}: {exc.__class__.__name__}"
        log.error("%s (failure #%d): %s", kind, self.consecutive_failures, exc)

    def status(self):
        age = None if self.last_success_ts is None else round(time.time() - self.last_success_ts, 1)
        return {"running": self.is_alive(), "samples": self.samples,
                "consecutive_failures": self.consecutive_failures, "last_error": self.last_error,
                "last_success_age_seconds": age}


def get_agent():
    return _agent


def start_collector(cfg):
    """Start the collector once per process; later calls return the same instance."""
    global _agent
    with _lock:
        if _agent is None or not _agent.is_alive():
            _agent = Collector(cfg)
            _agent.start()
        return _agent


def stop_collector(timeout=5):
    """Graceful shutdown: signal the loop and wait for the thread to finish."""
    global _agent
    with _lock:
        agent, _agent = _agent, None
    if agent:
        agent.stop_event.set()
        agent.join(timeout)
    return agent

"""SQLite access layer. All SQL is parameterised (no string-built values)."""
import os
import sqlite3
import time
from contextlib import contextmanager

from .models import SCHEMA, DEFAULT_THRESHOLDS, METRIC_COLUMNS, MetricSample


@contextmanager
def connect(db_path):
    """Open a short-lived connection; commit on success, always close."""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    with connect(db_path) as c:
        c.execute("PRAGMA journal_mode=WAL")  # readers don't block the collector's writes
        c.executescript(SCHEMA)
        for metric, (warn, crit) in DEFAULT_THRESHOLDS.items():
            c.execute("INSERT OR IGNORE INTO thresholds(metric, warning, critical) VALUES (?,?,?)",
                      (metric, warn, crit))


# ---------- metrics ----------
def insert_metric(db_path, s: MetricSample):
    cols = ["ts", "hostname"] + METRIC_COLUMNS
    values = [getattr(s, c) for c in cols]
    sql = f"INSERT INTO metrics({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"  # cols are constants
    with connect(db_path) as c:
        c.execute(sql, values)


def latest_metric(db_path, hostname=None):
    with connect(db_path) as c:
        if hostname:
            row = c.execute("SELECT * FROM metrics WHERE hostname=? ORDER BY ts DESC LIMIT 1", (hostname,)).fetchone()
        else:
            row = c.execute("SELECT * FROM metrics ORDER BY ts DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def metric_history(db_path, since_ts, limit=500, hostname=None):
    """Return up to `limit` rows since `since_ts`, oldest first, evenly down-sampled."""
    with connect(db_path) as c:
        if hostname:
            rows = c.execute("SELECT * FROM metrics WHERE ts>=? AND hostname=? ORDER BY ts ASC",
                             (since_ts, hostname)).fetchall()
        else:
            rows = c.execute("SELECT * FROM metrics WHERE ts>=? ORDER BY ts ASC", (since_ts,)).fetchall()
    rows = [dict(r) for r in rows]
    if len(rows) > limit:
        step = len(rows) / limit
        rows = [rows[int(i * step)] for i in range(limit)]
    return rows


def prune_metrics(db_path, retention_days):
    cutoff = time.time() - retention_days * 86400
    with connect(db_path) as c:
        return c.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,)).rowcount


# ---------- thresholds ----------
def get_thresholds(db_path):
    with connect(db_path) as c:
        rows = c.execute("SELECT metric, warning, critical FROM thresholds ORDER BY metric").fetchall()
    return {r["metric"]: {"warning": r["warning"], "critical": r["critical"]} for r in rows}


def set_threshold(db_path, metric, warning, critical):
    with connect(db_path) as c:
        c.execute("INSERT INTO thresholds(metric, warning, critical) VALUES (?,?,?) "
                  "ON CONFLICT(metric) DO UPDATE SET warning=excluded.warning, critical=excluded.critical",
                  (metric, warning, critical))


# ---------- alerts ----------
def get_active_alert(db_path, hostname, metric):
    with connect(db_path) as c:
        row = c.execute("SELECT * FROM alerts WHERE hostname=? AND metric=? AND status='active' "
                        "ORDER BY id DESC LIMIT 1", (hostname, metric)).fetchone()
    return dict(row) if row else None


def create_alert(db_path, ts, hostname, metric, severity, value, threshold, message):
    with connect(db_path) as c:
        cur = c.execute("INSERT INTO alerts(ts, hostname, metric, severity, value, threshold, message) "
                        "VALUES (?,?,?,?,?,?,?)", (ts, hostname, metric, severity, value, threshold, message))
        return cur.lastrowid


def resolve_alert(db_path, alert_id, ts):
    with connect(db_path) as c:
        c.execute("UPDATE alerts SET status='resolved', resolved_ts=? WHERE id=?", (ts, alert_id))


def list_alerts(db_path, status=None, limit=50):
    with connect(db_path) as c:
        if status:
            rows = c.execute("SELECT * FROM alerts WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

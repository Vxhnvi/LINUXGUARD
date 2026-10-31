"""System overview and metric endpoints."""
import time

from flask import Blueprint, current_app, jsonify

from .. import alerts, collector, database as db, monitor
from ._util import choice_arg, int_arg

bp = Blueprint("metrics", __name__, url_prefix="/api")

# which columns each "metric" filter returns for history charts
GROUPS = {
    "cpu": ["cpu_percent", "load1", "load5", "load15"],
    "memory": ["mem_percent", "mem_total", "mem_used", "mem_available"],
    "disk": ["disk_percent", "disk_total", "disk_used", "disk_free"],
    "network": ["net_sent_rate", "net_recv_rate", "net_bytes_sent", "net_bytes_recv",
                "net_packets_sent", "net_packets_recv"],
}


@bp.get("/health")
def health():
    """Liveness probe used by Docker HEALTHCHECK and load balancers."""
    cfg = current_app.config["LG"]
    try:
        db.get_thresholds(cfg.db_path)
        db_ok = True
    except Exception:
        db_ok = False
    agent = collector.get_agent()
    stats = agent.status() if agent else {"running": False}
    # degraded if DB is broken, or the collector is enabled but failing / not alive
    healthy = db_ok and (cfg.disable_collector or (stats["running"] and stats.get("consecutive_failures", 0) < 5))
    return jsonify(status="ok" if healthy else "degraded", database=db_ok,
                   collector_running=stats["running"], collector_enabled=not cfg.disable_collector,
                   collector=stats), (200 if healthy else 503)


@bp.get("/overview")
def overview():
    cfg = current_app.config["LG"]
    return jsonify(system=monitor.get_system_info(),
                   status=alerts.overall_status(cfg.db_path),
                   systemd_available=monitor.systemd_available(),
                   poll_seconds=cfg.poll_seconds,
                   server_time=time.time())


@bp.get("/metrics/current")
def current():
    cfg = current_app.config["LG"]
    row = db.latest_metric(cfg.db_path)
    source = "database"
    if row is None:  # collector has not written yet: take a live reading instead
        row = monitor.collect_metrics(None, cfg.disk_path, cpu_interval=0.3).to_dict()
        source = "live"
    age = max(0.0, time.time() - row["ts"])
    stale = source == "database" and not cfg.disable_collector and age > cfg.poll_seconds * 3 + 5
    return jsonify(source=source, metrics=row, age_seconds=round(age, 1), stale=stale)


@bp.get("/metrics/history")
def history():
    cfg = current_app.config["LG"]
    group = choice_arg("metric", "all", set(GROUPS) | {"all"})
    minutes = int_arg("minutes", 60, 1, cfg.retention_days * 1440)
    limit = int_arg("limit", 300, 10, 2000)
    rows = db.metric_history(cfg.db_path, time.time() - minutes * 60, limit)
    if group != "all":
        keep = ["ts", "hostname"] + GROUPS[group]
        rows = [{k: r[k] for k in keep} for r in rows]
    return jsonify(metric=group, minutes=minutes, count=len(rows), points=rows)

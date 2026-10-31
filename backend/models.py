"""Data structures and the SQLite schema."""
from dataclasses import dataclass, asdict

# Default alert thresholds: metric -> (warning %, critical %)
DEFAULT_THRESHOLDS = {
    "cpu": (80.0, 95.0),
    "memory": (85.0, 95.0),
    "disk": (80.0, 90.0),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,                 -- unix epoch seconds (UTC)
    hostname TEXT NOT NULL,           -- lets us support many servers later
    cpu_percent REAL, load1 REAL, load5 REAL, load15 REAL,
    mem_percent REAL, mem_total INTEGER, mem_used INTEGER, mem_available INTEGER,
    disk_percent REAL, disk_total INTEGER, disk_used INTEGER, disk_free INTEGER,
    net_bytes_sent INTEGER, net_bytes_recv INTEGER,
    net_packets_sent INTEGER, net_packets_recv INTEGER,
    net_sent_rate REAL, net_recv_rate REAL   -- bytes/second, derived from counters
);
CREATE INDEX IF NOT EXISTS idx_metrics_host_ts ON metrics(hostname, ts);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    hostname TEXT NOT NULL,
    metric TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('warning','critical')),
    value REAL NOT NULL,
    threshold REAL NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','resolved')),
    resolved_ts REAL
);
CREATE INDEX IF NOT EXISTS idx_alerts_lookup ON alerts(hostname, metric, status);

CREATE TABLE IF NOT EXISTS thresholds (
    metric TEXT PRIMARY KEY,
    warning REAL NOT NULL,
    critical REAL NOT NULL
);
"""

METRIC_COLUMNS = [
    "cpu_percent", "load1", "load5", "load15",
    "mem_percent", "mem_total", "mem_used", "mem_available",
    "disk_percent", "disk_total", "disk_used", "disk_free",
    "net_bytes_sent", "net_bytes_recv", "net_packets_sent", "net_packets_recv",
    "net_sent_rate", "net_recv_rate",
]


@dataclass
class MetricSample:
    ts: float
    hostname: str
    cpu_percent: float
    load1: float
    load5: float
    load15: float
    mem_percent: float
    mem_total: int
    mem_used: int
    mem_available: int
    disk_percent: float
    disk_total: int
    disk_used: int
    disk_free: int
    net_bytes_sent: int
    net_bytes_recv: int
    net_packets_sent: int
    net_packets_recv: int
    net_sent_rate: float = 0.0
    net_recv_rate: float = 0.0

    def to_dict(self):
        return asdict(self)

# Architecture

## Components and responsibilities
| Module | Responsibility | Depends on |
|---|---|---|
| `monitor.py` | Read CPU/RAM/disk/network/processes/systemd from the OS. Read-only. | psutil, `/proc`, `systemctl is-active` |
| `collector.py` | Background thread: every N s collect → store → evaluate alerts → hourly prune. Singleton per process. | monitor, database, alerts |
| `database.py` | All SQLite access, parameterised SQL, WAL mode, short-lived connections | sqlite3 |
| `alerts.py` | Threshold classification, de-duplication, escalation, resolution | database |
| `routes/*` | HTTP layer: validate input, call modules, return JSON | everything above |
| `security.py` | Optional API-token checks | config |
| `app.py` | App factory, error handlers, security headers, static files, waitress server | all |
| `frontend/` | Dashboard polls the API and draws cards/tables/charts | Chart.js |

Separation rule: `monitor.py` knows nothing about HTTP or SQL; routes contain no business logic; alerts never touch psutil. That makes each piece unit-testable (see `tests/`).

## Data flow
1. Collector wakes every `POLL_SECONDS`.
2. `collect_metrics()` reads the OS and computes network rates from the previous sample.
3. Row inserted into `metrics`.
4. `evaluate_sample()` compares CPU/memory/disk to `thresholds` and opens/escalates/resolves rows in `alerts`.
5. Browser calls `/api/*`; the API reads SQLite (and live process/service data). The dashboard being closed changes nothing.

## Database schema
- `metrics(id, ts, hostname, cpu_percent, load1/5/15, mem_percent/total/used/available, disk_percent/total/used/free, net_bytes_sent/recv, net_packets_sent/recv, net_sent_rate, net_recv_rate)` — index `(hostname, ts)`
- `alerts(id, ts, hostname, metric, severity[warning|critical], value, threshold, message, status[active|resolved], resolved_ts)` — index `(hostname, metric, status)`
- `thresholds(metric PK, warning, critical)`

## Key design decisions (and why)
- **SQLite + WAL:** zero-admin, one file, readers don't block the collector. Trade-off: single writer, fine for one host.
- **Thread inside the web process, not cron:** needs previous counters in memory for network rates and 5-second resolution. Cron's minimum interval is 1 minute. Cron/systemd are used for *backups, health checks and process supervision* instead. A module-level singleton prevents duplicate collectors; run **one** server process (waitress threads, not multiple workers).
- **Alert state machine with hysteresis:** one active alert per (host, metric); `next_level()` is a pure function of (current level, value, thresholds, margin). Raise at the threshold, clear only below threshold − margin; critical steps down to warning before resolving. Prevents spam and flapping; resolved rows remain as history.
- **psutil disk percent:** `used/(used+free)` matches `df`; `used/total` under-reports with reserved blocks (a bug found and fixed during testing: 3.4% vs real 46%).
- **Counter reset handling:** network counters are cumulative; a smaller value than before means reset → rate 0.
- **Read-only by design:** no kill endpoint, no shell; service names are allow-listed and regex-checked.
- **Multi-server readiness:** every row carries `hostname`; alert de-dup is per host.

## Cron vs systemd
- **cron** runs short jobs on a schedule (`deploy/linuxguard.cron`: nightly backup, 15-minute health check).
- **systemd** supervises long-running daemons: start at boot, restart on failure, journald logs, sandboxing (`deploy/linuxguard.service`).

## Collector reliability design
- **Singleton:** `start_collector()` returns the existing live thread. One process = one collector. **Run a single server process per DB** (waitress threads); multi-worker servers would each start a collector.
- **Failure isolation:** exceptions in a cycle are logged, counted (`consecutive_failures`, `last_error`) and retried; DB errors back off exponentially (poll × 2ⁿ, max 60 s). `/api/health` returns 503 when the collector is dead or failing ≥ 5 cycles.
- **Network-rate baseline** is stored before the DB write, so a failed insert never corrupts the next rate.
- **Graceful shutdown:** SIGTERM → `sys.exit` → `stop_collector()` sets the stop event and joins the thread (Docker `stop_grace_period` allows time).
- **Retention:** hourly `DELETE` of rows older than `RETENTION_DAYS`.
- **Staleness:** `/api/metrics/current` reports `age_seconds`/`stale`; the dashboard shows a banner if data stops updating.

## Process monitoring design
psutil reuses `Process` objects across `process_iter()` calls, so `cpu_percent(None)` = CPU since the previous call. A process seen for the first time has no baseline → reported as `null` (dashboard `—`). The collector primes counters at start-up. Exited processes (`NoSuchProcess`), zombies and `AccessDenied` are skipped or shown with `null` fields. Nothing in the code can signal a process.

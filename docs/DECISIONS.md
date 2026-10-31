# Architecture Decisions
- **Flask:** small, readable REST API; no ORM/framework overhead for a beginner-defensible project.
- **psutil:** cross-distro access to `/proc` metrics; avoids parsing command output. Disk % uses `used/(used+free)` to match `df`.
- **SQLite (WAL):** zero-admin, one file, readers don't block the collector. Single-writer limit accepted (one host).
- **Collector in a daemon thread:** needs previous counters for network rates and 5 s resolution (cron minimum is 1 min). Singleton per process; **deployment assumption: ONE server process** (waitress threads, not multiple workers/processes), because each process would start its own collector.
- **Docker:** reproducible run; non-root, read-only rootfs, dropped capabilities, named volume for SQLite.
- **Alerts:** one active alert per (host, metric); severity change resolves+reopens; **hysteresis**: raise at threshold, clear only when value falls below threshold − margin (default 5 points) so values hovering near a limit do not flap.
- **Security:** read-only monitoring, no shell, no kill endpoint, allow-listed `systemctl` with regex validation, optional constant-time API token (writes disabled without one), parameterised SQL, validated inputs, CSP/security headers.
- **systemd services:** `systemctl is-active` via argument list; detect `/run/systemd/system`; degrade gracefully (WSL/containers).

# Interview Preparation — LinuxGuard

## A. Resume bullets (all supported by what is implemented and tested)
**LinuxGuard | Linux Server Monitoring & Infrastructure Automation Platform**
- Built a Linux monitoring platform in Python/Flask: a background collector reads CPU, memory, disk, network, process and systemd data via psutil and `/proc`, stores history in SQLite, and serves a REST API and a responsive Chart.js dashboard (verified in headless Chromium).
- Implemented a threshold alert engine with hysteresis, de-duplication, escalation and auto-resolution; made the collector fault-tolerant (error isolation, DB-failure backoff, graceful SIGTERM shutdown); wrote 68 pytest tests covering alerts, processes, collector, API validation and token auth.
- Automated operations with Bash (health check with exit codes, safe SQLite online backup with rotation, system report), systemd unit and cron examples, and a hardened Docker/Compose configuration (non-root, read-only rootfs); documented an AWS EC2 deployment.

*Do not claim:* a completed AWS deployment, a Docker run, multi-server monitoring, users, uptime, performance numbers or production readiness.

## B. 30-second explanation
"LinuxGuard is a small monitoring tool like a mini Grafana/Nagios. A Python agent samples the server's CPU, RAM, disk and network every few seconds using psutil, saves them to SQLite, and checks them against thresholds. If something is too high it opens one alert and keeps it open until it recovers. A Flask API feeds a dashboard with live cards, history charts, top processes and systemd service status. Bash scripts, cron, systemd and Docker handle backups, health checks and running it as a service."

## C. Simple architecture explanation
Think of three layers: **collect** (`monitor.py` + `collector.py` read the OS), **store/decide** (`database.py` saves rows, `alerts.py` decides what is an alert), **show** (Flask routes + dashboard). The collector runs in the background so history keeps building even when nobody is looking.

## D. Key files
- `monitor.py` — `collect_metrics()` (one OS reading), `compute_rate()` (network bytes/sec, handles counter reset), `list_processes()`, `get_services()`
- `collector.py` — `Collector` thread loop; `start_collector()` singleton prevents duplicates
- `alerts.py` — `classify()`, `evaluate_sample()` (the de-dup state machine), `overall_status()`
- `database.py` — schema init, inserts, history with down-sampling, pruning
- `routes/*.py` — endpoints with input validation
- `scripts/*.sh` — operations automation

## E. Questions and answers
1. **What is a process vs a thread?** A process is a running program with its own address space and PID; threads share one process's memory. LinuxGuard's collector is a *thread* inside the web server process so it shares config and state.
2. **How does Linux report memory, and why use "available" not "free"?** Free RAM is unused; Linux also uses RAM as disk cache, which is reclaimable. `MemAvailable` estimates what applications can get without swapping, so used% = (total − available)/total is the meaningful number.
3. **What is load average?** Average number of runnable (and uninterruptible-sleep) tasks over 1/5/15 minutes. Compare to core count: load 4 on 4 cores ≈ fully busy. CPU % is instantaneous busy time; load shows queueing.
4. **How is CPU % computed?** psutil reads `/proc/stat` cumulative jiffies twice and computes busy/total over the interval — which is why the first call needs priming.
5. **Why did your disk % bug happen?** `used/total` ignores filesystem reserved blocks, giving 3.4% where `df` showed 47%. psutil uses `used/(used+free)`, matching `df`. I found it by comparing against `df` during testing.
6. **How do you handle cumulative network counters?** Rate = (now − previous)/seconds. If the counter decreased (reboot/interface reset) I return 0 instead of a negative spike. Covered by a unit test.
7. **How do you avoid duplicate alerts?** One active alert per host+metric. Same severity → nothing written; severity change → resolve old and open new; back to normal → resolve. Tests cover each case.
8. **cron vs systemd?** cron schedules short periodic jobs (min 1 minute). systemd supervises daemons: boot start, restart on failure, logs to journald, sandbox options. I use systemd for the service and cron for backups/health checks.
9. **Why a background thread instead of cron for collection?** Need 5s resolution and previous counters in memory for rates. Trade-off: must run exactly one process (singleton guard).
10. **What do Linux file permissions mean? How did you use them?** rwx for user/group/other. Scripts are `chmod +x`; `backup.sh` sets `umask 077` so backups are owner-only; the container and systemd unit run as an unprivileged user.
11. **Why SQLite and what are its limits?** Zero administration, single file, WAL lets readers work during writes. Single writer, not for many hosts writing concurrently — I'd move to PostgreSQL/TimescaleDB for multi-host.
12. **Why not just `cp` the database for backup?** In WAL mode a copy can miss uncommitted WAL data and be inconsistent. I use SQLite's online backup API and run `PRAGMA integrity_check`.
13. **How is the Flask API secured?** Input validation (enum/range), parameterised SQL, no shell, read-only endpoints, optional constant-time-compared API token (writes disabled without one), security headers, generic error messages, no debug mode, production server (waitress).
14. **Why is there no "kill process" feature?** It is a remote-control risk; a monitoring tool should be read-only. Least privilege.
15. **How do you call systemctl safely?** Argument list (no shell), names validated by regex and taken from a configured allow-list, 5s timeout. A unit test proves a malicious name is skipped.
16. **What happens without systemd (WSL/containers)?** I detect `/run/systemd/system` and `systemctl`; if absent the API returns `systemd_available:false` with a message instead of failing.
17. **Explain your Dockerfile.** Slim Python image, deps installed before code for layer caching, non-root user, only `/app/data` writable, HEALTHCHECK hits `/api/health`. Compose adds a named volume (SQLite persistence), restart policy, read-only rootfs, dropped capabilities.
18. **Container limits for monitoring?** A container has its own PID namespace and mount view, so it lists container processes unless `pid: host`. CPU/memory figures usually reflect the host kernel. For true host monitoring I'd use the systemd install.
19. **What goes in an AWS Security Group?** It is a stateful firewall on the instance: SSH only from my IP, no public dashboard port; reach the UI via SSH tunnel or an HTTPS reverse proxy.
20. **How would you troubleshoot a slow server using this?** Dashboard: which metric is high? Top processes by CPU/memory; load vs cores; disk % and `du -sh`; history chart for when it began; on the box `top`, `free -h`, `iostat`, `journalctl`.
21. **What is the difference between used and cached memory, and what is swap?** Cache is reclaimable file data; swap is disk used as overflow memory — heavy swapping means RAM exhaustion and slowness.
22. **How would you scale to many servers?** Lightweight agents push samples to the API (token auth), `hostname` is already in every row, move to PostgreSQL, add per-host dashboards, alert routing.
23. **What are the weaknesses of your design?** No TLS/user auth built in, alerts only in the UI, no hysteresis, single host, Docker/AWS not run by me yet. Knowing these is part of the engineering.
24. **How did you test?** pytest: unit tests for collection/rates/alerts/DB, Flask test client for API + validation + auth, plus manual end-to-end (lowered a threshold, watched a real alert open once and resolve), and script exit-code checks.

## E2. Additional code-focused questions
25. **Explain your hysteresis.** `alerts.next_level(current, value, warning, critical, margin)`: value ≥ threshold raises; an active level only clears below threshold − margin (default 5). With warning 80: opens at 80, stays through 75–79.9, clears below 75. Critical 95 steps down to warning below 90 (if ≥ 75), else resolves. A test feeds `78, 81, 79, 82, 77…` and asserts exactly one alert.
26. **Explain Linux CPU scheduling and how it relates to load average.** The kernel scheduler (CFS/EEVDF) time-slices runnable tasks across cores. When more tasks are runnable than cores, they queue, load average rises above the core count. I show CPU % (busy time) next to load (queue length).
27. **How are file systems and `df` related to your disk metric?** A filesystem reserves some blocks for root, so `used/total` under-reports what users can use. `df` and psutil compute `used/(used+available)`. I fixed a bug where my first version showed 3.4% against `df`'s 47%.
28. **Linux permissions in this project?** Scripts need `x` (`chmod +x`); `umask 077` makes backups owner-only; the service runs as a non-root user with `ProtectSystem=strict` writing only to `data/`; the container user (uid 10001) owns only `/app/data`.
29. **How does psutil get per-process CPU?** From `/proc/<pid>/stat` jiffies; `cpu_percent(None)` compares with the previous call, so the first reading has no baseline. I return `null` for first sightings rather than a false 0.0.
30. **What if a process exits while you list processes?** psutil raises `NoSuchProcess`; I catch it (and `AccessDenied`, `ZombieProcess`) and skip that process. Tested with fake process objects.
31. **How do you guarantee one collector?** A module-level singleton guarded by a lock returns the live thread. It only protects one process; running several workers would start several collectors, so deployment is single-process (documented).
32. **What happens if SQLite fails during a cycle?** The exception is caught in `Collector.run`, counted, logged and retried with exponential backoff (max 60 s); `/api/health` goes 503 after 5 consecutive failures. The network-rate baseline is saved before the write so rates stay correct.
33. **How does shutdown work?** `docker stop`/`systemctl stop` send SIGTERM; a handler calls `sys.exit(0)`, `finally: stop_collector()` sets the stop event and joins the thread. I tested exit code 0 and the log line.
34. **Why a hard-coded allow-list of services?** Prevents command injection and information leaks: only configured names matching `^[A-Za-z0-9@._-]{1,64}$` reach `systemctl is-active`, called without a shell.
35. **How do you know the dashboard isn't showing fake data?** There is no hardcoded metric in the JS; every number comes from `/api/*`. I compared values with `uname -r`, `df`, `free`, generated real CPU load with `while True: pass`, and saw it in the cards, chart and alerts.
36. **What is `stale` in `/api/metrics/current`?** If the newest row is older than 3 × poll interval + 5 s, the collector is probably stuck; the UI shows a banner instead of silently displaying old numbers.
37. **Docker health check vs restart policy?** HEALTHCHECK marks a container healthy/unhealthy by calling `/api/health`; `restart: unless-stopped` restarts it if the process exits or the daemon reboots. (Unhealthy containers are not restarted by plain Docker/Compose.)
38. **Security weaknesses you know about?** No TLS/user accounts, token in a header, read endpoints are open when no token is set, so bind to localhost or use a tunnel/HTTPS proxy.

## F. Troubleshooting cheat-sheet
See `docs/TROUBLESHOOTING.md`. Fast triage: `curl /api/health` → server up? `collector_running` true? → logs (`journalctl -u linuxguard` / `docker compose logs`) → `ss -tulpn` for ports → `df -h` / `free -h` for the host.

## G. Demo script (5 minutes)
1. `python -m backend.app`; open the dashboard. Point out real hostname/kernel/uptime (compare with `uname -r`, `uptime`).
2. Run `./scripts/system_info.sh` and show it matches the Server information panel.
3. Generate load: `python3 -c "while True: pass"` (Ctrl-C after). Watch CPU card/chart rise; show it in Top processes.
4. Lower the CPU threshold (explain hysteresis: it clears only 5 points below): `curl -X PUT -H "X-API-Key: $TOKEN" -H 'Content-Type: application/json' -d '{"warning":5,"critical":90}' localhost:5000/api/thresholds/cpu`; show ONE alert appearing, not repeating; stop the load → alert resolves. Restore thresholds.
5. `./scripts/health_check.sh; echo $?` then `./scripts/backup.sh` and `ls data/backups`.
6. Show `pytest -q` passing, `Dockerfile`/compose, and `deploy/linuxguard.service`. Explain the limitations honestly.

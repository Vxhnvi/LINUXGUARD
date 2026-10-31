# LinuxGuard — HANDOVER (read this first)

## PROJECT STATUS
- **Completed:** backend (collector, SQLite, alert engine **with hysteresis**, REST API), dashboard (browser-verified), 3 Bash scripts, **68 pytest tests**, Dockerfile + Compose, systemd unit, cron examples, all docs, 3 genuine screenshots
- **In progress:** nothing
- **Pending:** run Docker build/up on a Docker host; test systemd unit on a real systemd host; execute AWS guide; optional improvements (section 21)
- **Known bugs:** none open. Limitations: global hysteresis margin, single host/one process per DB, no TLS/user auth, Docker/AWS/systemd-unit never executed (see FINAL_AUDIT.md)
- **Last verified working state:** clean venv → `python -m pytest -q` = 68 passed; server start, SIGTERM exit 0, restart persistence, scripts, Chromium dashboard check (Session 2)
- **Latest checkpoint:** docs/SESSION_CHECKPOINT.md (Session 3 release-readiness check; no code changed since Session 2)
- **Release check (Session 3):** ZIP contents, hygiene, README-vs-code and clean-venv run verified; Docker still untested; AWS not deployed; single host only
- **Immediate next action:** on a machine with Docker: `docker compose up -d --build && docker compose ps && curl http://127.0.0.1:5000/api/health`; record result in FINAL_AUDIT.md

## 1. Objective
LinuxGuard — Linux server monitoring & infrastructure automation, a portfolio project for Infrastructure/Cloud Engineer roles. Owner is a beginner in practical Linux admin; keep explanations simple and honest; never claim untested things.

## 2. Continuity files
HANDOVER.md (this), PROGRESS_LOG.md (chronological), SESSION_CHECKPOINT.md (exact current state), DECISIONS.md (why), FINAL_AUDIT.md (verified/untested), ARCHITECTURE.md, INTERVIEW_PREPARATION.md, TROUBLESHOOTING.md, AWS_DEPLOYMENT.md.

## 3. Stack
Python 3.12, Flask 3, psutil, waitress, SQLite (WAL), HTML/CSS/JS, Chart.js 4.4.1 (vendored, MIT), Bash, Docker/Compose, systemd, cron, pytest; playwright/Chromium used only for screenshots (not a project dependency).

## 4. Architecture (details: docs/ARCHITECTURE.md)
OS → `monitor.py` → `collector.py` (thread, singleton, backoff, graceful stop) → `database.py` (SQLite) + `alerts.py` (thresholds, hysteresis, de-dup) → Flask `routes/` → dashboard. **Run ONE process per DB.**

## 5. Folder structure
```
backend/ app.py config.py models.py database.py monitor.py alerts.py collector.py security.py
         routes/ metrics.py alert_routes.py processes.py services.py _util.py
frontend/ index.html style.css dashboard.js vendor/{chart.umd.js,CHARTJS_LICENSE.md}
scripts/ system_info.sh health_check.sh backup.sh
deploy/ linuxguard.service linuxguard.cron
tests/ conftest.py test_monitor.py test_alerts.py test_collector.py test_api.py
docs/ (continuity + docs above) screenshots/{dashboard-desktop,dashboard-mobile,dashboard-error-state}.png
Dockerfile docker-compose.yml requirements.txt .env.example .gitignore .dockerignore README.md
```

## 6. Features completed
Overview, CPU/memory/disk/network metrics + history, rates with counter-reset handling, top processes (read-only, null first-sample CPU), systemd service status (graceful without systemd), configurable thresholds (PUT with token), alerts with hysteresis/escalation/auto-resolve/history, retention pruning, health endpoint with collector stats, stale-data detection, dashboard with loading/empty/error/stale states, scripts, Docker files.

## 7. Features pending
Multi-host agents, notifications, per-metric hysteresis, HTTPS proxy config, Docker/systemd/AWS execution.

## 8. Bugs
None open (fixed this project: disk % calculation; chart label granularity; chart spline overshoot).

## 9. Database schema (DDL in backend/models.py)
`metrics`(ts, hostname, cpu_percent, load1/5/15, mem_percent/total/used/available, disk_percent/total/used/free, net_bytes_sent/recv, net_packets_sent/recv, net_sent_rate, net_recv_rate); `alerts`(ts, hostname, metric, severity warning|critical, value, threshold, message, status active|resolved, resolved_ts); `thresholds`(metric PK, warning, critical). Defaults cpu 80/95, memory 85/95, disk 80/90.

## 10. API
`GET /api/health` · `/api/overview` · `/api/metrics/current` (+`age_seconds`,`stale`) · `/api/metrics/history?metric=all|cpu|memory|disk|network&minutes=1..&limit=10..2000` · `/api/alerts?status=&limit=` · `/api/thresholds` · `PUT /api/thresholds/<cpu|memory|disk>` (X-API-Key; 403 if no token configured) · `/api/processes?sort=cpu|memory&limit=1..100` and `/api/services` (X-API-Key required only if token configured).

## 11. Dependencies / install
`python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

## 12. Environment variables
LINUXGUARD_HOST, _PORT, _DB, _POLL_SECONDS, _RETENTION_DAYS, _DISK_PATH, _SERVICES, _API_TOKEN, _HYSTERESIS (default 5), _DISABLE_COLLECTOR (see `.env.example`).

## 13. Run
`python -m backend.app` → http://127.0.0.1:5000 · Docker (untested): `docker compose up -d --build`

## 14. Tests
`python -m pytest -q` · `./scripts/health_check.sh; echo $?` · `./scripts/backup.sh`

## 15. Actual results
68 passed (clean venv, Session 2). Manual checks in FINAL_AUDIT.md. Docker: not run.

## 16. Files modified in Session 2
backend/{alerts,collector,monitor,config,app}.py, backend/routes/metrics.py, frontend/dashboard.js, docker-compose.yml, .env.example, README.md, docs/{ARCHITECTURE,AWS_DEPLOYMENT,TROUBLESHOOTING,INTERVIEW_PREPARATION,FINAL_AUDIT,HANDOVER}.md; new: docs/{PROGRESS_LOG,SESSION_CHECKPOINT,DECISIONS}.md, docs/screenshots/*, tests/test_collector.py, additions to tests/test_{alerts,monitor,api}.py.

## 17. Technical decisions
See docs/DECISIONS.md.

## 18. Git
Working repo at `LinuxGuard/.git` (commits: bee92d7 initial; Phase 3; dashboard/docs; final). The distributable ZIP excludes `.git`; to publish: `git init -b main && git add . && git commit -m "LinuxGuard" && git remote add origin <url> && git push -u origin main` (or push the original repo).

## 19. Docker status
Dockerfile + Compose reviewed/improved (stop_grace_period, hysteresis env). **Never built or run** — Docker unavailable here.

## 20. AWS status
Guide only (docs/AWS_DEPLOYMENT.md). **Nothing deployed.**

## 21. Next steps for another Claude conversation
1. Inspect files; `python -m pytest -q` (expect 68 pass).
2. If Docker is available: build/run, confirm `healthy`, volume persistence, non-root; update FINAL_AUDIT/HANDOVER.
3. Optional: webhook notifications; per-metric hysteresis; multi-host push API; HTTPS proxy example.
4. Update all four continuity files after every change; never delete them.

## Ready-to-copy continuation prompt
Continue developing LinuxGuard using the uploaded project ZIP. First inspect the project and read docs/HANDOVER.md, docs/SESSION_CHECKPOINT.md, docs/PROGRESS_LOG.md, docs/DECISIONS.md and docs/FINAL_AUDIT.md. Verify the existing implementation (create a clean virtual environment, install requirements.txt, run python -m pytest -q), identify incomplete work, and resume from the last checkpoint. Preserve all existing working functionality and never rebuild completed components unnecessarily. Update HANDOVER.md, PROGRESS_LOG.md, SESSION_CHECKPOINT.md and DECISIONS.md after every major change. Do not claim anything is tested unless you actually ran it.

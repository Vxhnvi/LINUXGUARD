# Final Audit (Session 2)

Environment: Ubuntu 24.04 sandbox, 1 vCPU, Python 3.12.3, Flask 3.1.3, psutil 7.2.2, Chromium 141 (playwright). **No Docker, no AWS access, systemd not running.**
Baseline: git commit `bee92d7` (32 tests). Current: see `git log`.

## A. Verified working (executed this session)
| Check | Command / method | Result |
|---|---|---|
| Unit + API + collector tests | clean venv from `requirements.txt`, `python -m pytest -q` | **68 passed** |
| Syntax | `python -m compileall -q backend tests`; `bash -n scripts/*.sh`; `node --check frontend/dashboard.js` | all OK |
| Alert hysteresis | parametrised boundary tests + no-flapping test (`78,81,79,82,77,80,78` → 1 alert) + step-down critical→warning→resolved | pass |
| Alert lifecycle on real data | CPU burn with CPU warning=20: alert opened/escalated/resolved in API and dashboard | observed |
| Process monitoring | first sighting → `null`; vanished/denied/zombie skipped; sort desc with null last; exited pids forgotten | pass (mocked + real psutil) |
| Collector | singleton, graceful stop, error in one cycle doesn't stop it, DB error recorded + backoff, baseline kept on failed write, retention prune | pass |
| Health | `/api/health` → collector stats; 503 when collector enabled but dead | pass |
| Staleness | `/api/metrics/current` `stale:true` for 10-min-old row | pass |
| Graceful shutdown | `kill -TERM` of running server | exit code 0, logs "collector stopped" + "shut down cleanly" |
| Persistence | restart with same DB | rows before 5 → after 8; alert history retained |
| API validation/auth | bad params → 400, wrong/no token → 401, no token configured → 403 on PUT, bad JSON → 400, DELETE → 405, `/app.py` → 404 | pass |
| Real OS data | hostname `vm`, Ubuntu 24.04.4, kernel 6.18.44, disk % ≈ `df` (46.x vs 47) | observed |
| Bash scripts | `health_check.sh` exit 0/1/2 (forced thresholds, session 1), `system_info.sh`, `backup.sh` (integrity check, rotation, missing-DB error) | pass |
| Dashboard in a real browser | headless Chromium: values populated, 2 Chart.js instances stable after repeated polls, mobile (390 px) no horizontal overflow, API-down banner + "offline" badge, token-required message | observed; screenshots in `docs/screenshots/` |
| Secrets / hygiene | no `.env` in tree, `.gitignore` covers `.env`, DB files, backups; Chart.js MIT license included in `frontend/vendor/` | OK |

## B. Tested with limitations
- **Dashboard:** Chromium only; not Firefox/Safari/real phones (390 px viewport emulation).
- **systemd services:** tested with mocked `systemctl` and the no-systemd path only.
- **Network rates:** formula unit-tested; sandbox traffic was low (tens–hundreds of KB/s seen).
- **Chart.js loaded from `frontend/vendor/` (v4.4.1):** works offline; not upgraded.
- Single-core VM: multi-core CPU behaviour (>100 % per-process) not observed.

## C. Not tested
- `docker build`, `docker compose up -d --build`, container `HEALTHCHECK`, volume persistence, non-root/read-only rootfs behaviour — **Docker unavailable**. Run: `docker compose up -d --build && docker compose ps && docker compose logs && curl http://127.0.0.1:5000/api/health`.
- systemd unit (`deploy/linuxguard.service`) and cron jobs (`deploy/linuxguard.cron`) installation.
- AWS EC2 deployment (guide only; nothing deployed).
- WSL2 specifics (documented only).
- Load/stress behaviour, long-duration (24 h+) retention.

## D. Known issues
- Hysteresis margin is global, not per metric.
- Dashboard polls every few seconds with one request per panel (6 requests/cycle); fine for one user.
- No TLS or user accounts; read endpoints are open unless a token is configured.
- Single host only; one process per database.
- Process CPU is per core (can exceed 100 %).

## E. Remaining improvements
Docker verification on a Docker host; real systemd test; notifications (webhook/email); per-metric hysteresis; multi-host agents; HTTPS reverse proxy config; LICENSE choice (not added — your decision).

## Documentation vs code agreement
README (config table incl. `LINUXGUARD_HYSTERESIS`, API table incl. `stale`/health stats, 68 tests, limitations), ARCHITECTURE (collector/process design), DECISIONS, TROUBLESHOOTING and AWS guide were updated to match the code in this session.

## Release-readiness check (Session 3, no code changes)
Run against the extracted `LinuxGuard_Final.zip` (clean venv):
- All source, tests, scripts (3, executable), deploy files, docs (9) and 3 screenshots present; `LinuxGuard_Final.zip` is the delivered name.
- No `.git`, `.env`, `*.db`, `.venv`, caches, logs or backups in the ZIP; secret scan found only code that reads the token from config (no credentials).
- README env vars, API endpoints and commands match the code: `.env.example` sourcing works, `python -m pytest -q` → **68 passed** (68 collected), server starts, `/api/health` ok, dashboard `/` returns 200, SIGTERM exit 0.
- Docker: **still NOT AVAILABLE → untested.** AWS: **not deployed.** Multi-server monitoring: **not supported** (single host; `hostname` columns are only groundwork).
- The only "32 tests" mention (this file's Baseline line) is the historical baseline, intentionally unchanged.

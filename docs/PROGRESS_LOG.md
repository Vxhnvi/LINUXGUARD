# Progress Log

## Session 1 (2026-10-30) — initial build
- Built backend, dashboard, scripts, tests (32), Docker files, docs. Verified via pytest + manual E2E. Commit `bee92d7`.

## Session 2 (2026-10-30/31) — audit & improvement
- Phase 1: baseline verified — git clean, 32 passed, Chromium (playwright) available, Docker NOT available. Original saved at /tmp/LinuxGuard_baseline_backup and git commit bee92d7.
- Phase 3 (done): alert hysteresis (`next_level`, margin `LINUXGUARD_HYSTERESIS`, default 5), process monitoring (first-sighting CPU = null, vanished/denied processes skipped, stable sort), collector reliability (health stats, backoff, graceful SIGTERM shutdown, baseline kept on DB failure), `/api/health` degraded state, `/api/metrics/current` stale flag. Files modified: backend/{alerts,collector,monitor,config,app}.py, routes/metrics.py, frontend/dashboard.js, docker-compose.yml, .env.example. Tests added: 36 (→ 68 total), all pass.
- Phase 5 (done): dashboard verified in headless Chromium (playwright): real data, 2 chart instances stable across polls, no mobile overflow, error banner, protected-endpoint message. Fixed: chart x-labels (seconds), removed spline smoothing (overshoot), null CPU rendering, stale banner. Screenshots in docs/screenshots/ (3, genuine).
- Phase 6 (done): clean-venv run: compileall OK, 68 passed, scripts OK, SIGTERM exit 0 + "shut down cleanly", rows persisted across restart.
- Phase 7: Docker NOT available → config reviewed only (added stop_grace_period, LINUXGUARD_HYSTERESIS passthrough); compose YAML parses. AWS guide improved (token step, secure access, cost note). Not executed.
- Phase 8 (in progress): README/ARCHITECTURE/TROUBLESHOOTING/AWS updated. Remaining: INTERVIEW_PREPARATION, FINAL_AUDIT, HANDOVER, final ZIP.
- Phase 8/9 (done): INTERVIEW_PREPARATION (38 Q&A, updated resume bullets), FINAL_AUDIT rewritten with actual results, HANDOVER rewritten, DECISIONS added.
- Phase 10 (done): clean ZIP built (excludes .git, venvs, caches, DB, logs, backups), extracted and re-tested (68 passed). Remaining: Docker/systemd/AWS execution on suitable hosts.

## Session 3 (2026-10-31) — release-readiness check
- No code changes. Extracted LinuxGuard_Final.zip into a clean venv: all required files present, 3 scripts executable, no .git/.env/db/venv/cache/log/backups, no credentials, README env vars/endpoints/commands match code, 68 tests pass, server health OK, SIGTERM exit 0.
- Docker unavailable → untested (status preserved). AWS not deployed. Single host only.
- Updated FINAL_AUDIT, HANDOVER, SESSION_CHECKPOINT; rebuilt ZIP.

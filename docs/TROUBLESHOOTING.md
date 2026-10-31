# Troubleshooting

| Symptom | Likely cause | Check / fix |
|---|---|---|
| `ModuleNotFoundError: backend` | Started from the wrong directory or as a script | Run `python -m backend.app` from the project root |
| `Address already in use` | Port 5000 busy | `ss -tulpn \| grep 5000`; set `LINUXGUARD_PORT` |
| Dashboard says "Cannot reach the API" | Server stopped / wrong port | `curl localhost:5000/api/health` |
| Charts empty | Fewer than 2 samples yet | wait ~2 × `POLL_SECONDS`; check `collector_running` in `/api/health` |
| `collector_running: false` | `LINUXGUARD_DISABLE_COLLECTOR=1` or thread crashed | unset it; read the server log |
| Services panel: "systemd is not running" | WSL without systemd, or container | WSL: `[boot]\nsystemd=true` in `/etc/wsl.conf`, then `wsl --shutdown`. Containers never have it — use the systemd install |
| Processes/Services panel says "set your API token" | `LINUXGUARD_API_TOKEN` is set | click **API token** in the header and paste it |
| `PUT /api/thresholds` → 403 | No token configured | set `LINUXGUARD_API_TOKEN` and restart |
| `/api/health` returns 503 / `degraded` | collector thread dead or ≥ 5 consecutive failures | read `collector.last_error` in the response and the server log; check disk space and DB file permissions |
| Banner: "Monitoring data is stale" | collector stopped or blocked | `curl /api/health`; restart the service |
| Duplicate samples / double rows | two LinuxGuard processes on one DB | run exactly one process (no multi-worker servers) |
| Alert stays ACTIVE below the threshold | hysteresis: clears only below threshold − margin | expected; adjust `LINUXGUARD_HYSTERESIS` |
| Process CPU shows `—` | process seen for the first time | appears on the next refresh |
| `database is locked` | Another process holds a long write | only one LinuxGuard process per DB file |
| Docker shows only container processes | Containers have their own PID namespace | uncomment `pid: "host"` in compose (wider visibility — security trade-off) or run via systemd |
| `backup.sh: database not found` | wrong `LINUXGUARD_DB` | export the same path the app uses |
| Disk % differs from expectation | `LINUXGUARD_DISK_PATH` points at another mount | `df -h <path>` |
| Permission denied on `data/` | Directory owned by another user | `chown` it to the service user |

Useful Linux commands: `top`/`htop`, `free -h`, `df -h`, `du -sh *`, `ss -tulpn`, `journalctl -u linuxguard -f`, `systemctl status linuxguard`, `docker compose logs -f`.

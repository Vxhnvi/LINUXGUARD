#!/usr/bin/env bash
# backup.sh - consistent backup of the LinuxGuard SQLite database.
# Uses SQLite's online backup API (via python3's sqlite3 module), which is safe while the
# collector is writing. A plain `cp` of a WAL-mode database can produce a corrupt copy.
# Usage: ./scripts/backup.sh            (env: LINUXGUARD_DB, BACKUP_DIR, KEEP)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${LINUXGUARD_DB:-$ROOT/data/linuxguard.db}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/data/backups}"
KEEP="${KEEP:-7}"

[ -f "$DB" ] || { echo "ERROR: database not found: $DB" >&2; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 is required" >&2; exit 1; }
mkdir -p "$BACKUP_DIR"
umask 077   # backups readable by owner only

DEST="$BACKUP_DIR/linuxguard-$(date -u +%Y%m%d-%H%M%S).db"
python3 - "$DB" "$DEST" <<'PY'
import sqlite3, sys
src, dest = sys.argv[1], sys.argv[2]
s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
d = sqlite3.connect(dest)
with d:
    s.backup(d)
ok = d.execute("PRAGMA integrity_check").fetchone()[0]
s.close(); d.close()
if ok != "ok":
    sys.exit(f"integrity check failed: {ok}")
PY

echo "Backup created: $DEST ($(du -h "$DEST" | cut -f1))"
# keep only the newest $KEEP backups
ls -1t "$BACKUP_DIR"/linuxguard-*.db 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
  rm -f -- "$old" && echo "Removed old backup: $old"
done

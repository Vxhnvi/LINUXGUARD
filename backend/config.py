"""Configuration loaded from environment variables (see .env.example)."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9@._-]{1,64}$")


def _int(name, default, lo, hi):
    """Read an int env var, falling back to default if missing/invalid/out of range."""
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if lo <= value <= hi else default


@dataclass
class Config:
    host: str
    port: int
    db_path: str
    poll_seconds: int
    retention_days: int
    disk_path: str
    services: list
    api_token: str
    disable_collector: bool
    hysteresis: float = 5.0


def load_config():
    services = [s.strip() for s in os.environ.get("LINUXGUARD_SERVICES", "ssh,cron,docker,nginx").split(",")]
    services = [s for s in services if SERVICE_NAME_RE.match(s)]  # reject anything odd
    db = os.environ.get("LINUXGUARD_DB", str(BASE_DIR / "data" / "linuxguard.db"))
    if not os.path.isabs(db):
        db = str(BASE_DIR / db)
    return Config(
        host=os.environ.get("LINUXGUARD_HOST", "127.0.0.1"),
        port=_int("LINUXGUARD_PORT", 5000, 1, 65535),
        db_path=db,
        poll_seconds=_int("LINUXGUARD_POLL_SECONDS", 5, 1, 3600),
        retention_days=_int("LINUXGUARD_RETENTION_DAYS", 7, 1, 365),
        disk_path=os.environ.get("LINUXGUARD_DISK_PATH", "/"),
        services=services,
        api_token=os.environ.get("LINUXGUARD_API_TOKEN", ""),
        disable_collector=os.environ.get("LINUXGUARD_DISABLE_COLLECTOR", "0") == "1",
        hysteresis=float(_int("LINUXGUARD_HYSTERESIS", 5, 0, 20)),
    )

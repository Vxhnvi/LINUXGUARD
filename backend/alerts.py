"""Alert engine: threshold evaluation with hysteresis and de-duplication.

Rules (per host + metric, at most ONE active alert):
- RAISE   a level when value >= its threshold (warning / critical).
- ESCALATE warning -> critical when value >= critical: old alert resolved, new one opened.
- HYSTERESIS: an active level is only CLEARED when the value falls below
  (threshold - margin). Example (margin 5): warning at 80 clears below 75;
  critical at 95 clears below 90 and, if still >= 75, drops to a warning alert.
  This stops alerts flapping when a value hovers around a threshold.
- Unchanged level -> nothing is written (no duplicate alerts each poll).
- Resolved alerts stay in the table as history.
"""
from . import database as db

LABELS = {"cpu": "CPU", "memory": "Memory", "disk": "Disk"}
DEFAULT_MARGIN = 5.0  # percentage points


def classify(value, warning, critical):
    """Plain threshold check without hysteresis: 'critical', 'warning' or None."""
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return None


def next_level(current, value, warning, critical, margin=DEFAULT_MARGIN):
    """Decide the alert level given the currently active level (or None). Pure function."""
    if value >= critical:
        return "critical"
    if current == "critical":
        if value >= critical - margin:
            return "critical"            # still inside the recovery band
        return "warning" if value >= warning - margin else None
    if value >= warning:
        return "warning"
    if current == "warning" and value >= warning - margin:
        return "warning"                 # still inside the recovery band
    return None


def _message(label, value, level, th, was):
    if was == "critical" and level == "warning" and value < th["warning"]:
        return f"{label} usage {value:.1f}% recovered from critical but is still near the warning threshold ({th['warning']:.0f}%)"
    if was == "critical" and level == "warning":
        return f"{label} usage {value:.1f}% dropped below critical but is still above the warning threshold ({th['warning']:.0f}%)"
    return f"{label} usage {value:.1f}% is above the {level} threshold ({th[level]:.0f}%)"


def evaluate_sample(db_path, sample, margin=DEFAULT_MARGIN):
    """Compare a sample with stored thresholds. Returns the list of newly opened alerts."""
    thresholds = db.get_thresholds(db_path)
    values = {"cpu": sample.cpu_percent, "memory": sample.mem_percent, "disk": sample.disk_percent}
    opened = []
    for metric, value in values.items():
        th = thresholds.get(metric)
        if not th:
            continue
        active = db.get_active_alert(db_path, sample.hostname, metric)
        current = active["severity"] if active else None
        level = next_level(current, value, th["warning"], th["critical"], margin)
        if level == current:
            continue                      # nothing to do: no duplicate, no flapping
        if active:
            db.resolve_alert(db_path, active["id"], sample.ts)
        if level:
            msg = _message(LABELS[metric], value, level, th, current)
            alert_id = db.create_alert(db_path, sample.ts, sample.hostname, metric, level,
                                       value, th[level], msg)
            opened.append({"id": alert_id, "metric": metric, "severity": level, "message": msg})
    return opened


def overall_status(db_path):
    """healthy / warning / critical from currently active alerts."""
    active = db.list_alerts(db_path, status="active", limit=100)
    if any(a["severity"] == "critical" for a in active):
        return "critical"
    return "warning" if active else "healthy"

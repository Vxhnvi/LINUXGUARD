from backend import alerts, database as db
from tests.conftest import make_sample


def test_classify():
    assert alerts.classify(50, 80, 95) is None
    assert alerts.classify(80, 80, 95) == "warning"
    assert alerts.classify(95, 80, 95) == "critical"


def test_alert_created_on_breach(dbpath):
    opened = alerts.evaluate_sample(dbpath, make_sample(cpu=85))
    assert len(opened) == 1 and opened[0]["severity"] == "warning" and opened[0]["metric"] == "cpu"
    row = db.list_alerts(dbpath)[0]
    assert row["status"] == "active" and row["ts"] == 1000.0 and "CPU" in row["message"]


def test_no_duplicate_alert_while_condition_persists(dbpath):
    for i in range(10):
        alerts.evaluate_sample(dbpath, make_sample(ts=1000 + i, cpu=88))
    assert len(db.list_alerts(dbpath)) == 1


def test_escalation_warning_to_critical(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(ts=1, disk=85))
    alerts.evaluate_sample(dbpath, make_sample(ts=2, disk=93))
    rows = db.list_alerts(dbpath)  # newest first
    assert [(r["severity"], r["status"]) for r in rows] == [("critical", "active"), ("warning", "resolved")]


def test_alert_resolves_when_back_to_normal(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(ts=1, mem=90))
    alerts.evaluate_sample(dbpath, make_sample(ts=2, mem=40))
    row = db.list_alerts(dbpath)[0]
    assert row["status"] == "resolved" and row["resolved_ts"] == 2
    assert alerts.overall_status(dbpath) == "healthy"


def test_new_alert_after_resolution(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(ts=1, cpu=90))
    alerts.evaluate_sample(dbpath, make_sample(ts=2, cpu=10))
    alerts.evaluate_sample(dbpath, make_sample(ts=3, cpu=90))
    assert len(db.list_alerts(dbpath)) == 2


def test_multiple_metrics_and_overall_status(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(cpu=85, disk=95))
    assert len(db.list_alerts(dbpath, status="active")) == 2
    assert alerts.overall_status(dbpath) == "critical"


def test_configurable_thresholds_change_behaviour(dbpath):
    db.set_threshold(dbpath, "cpu", 20, 30)
    opened = alerts.evaluate_sample(dbpath, make_sample(cpu=35))
    assert opened[0]["severity"] == "critical"


def test_separate_hosts_do_not_share_alerts(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(cpu=90, host="a"))
    alerts.evaluate_sample(dbpath, make_sample(cpu=90, host="b"))
    assert len(db.list_alerts(dbpath)) == 2


# ---------------- hysteresis ----------------
import pytest  # noqa: E402


@pytest.mark.parametrize("current,value,expected", [
    (None, 79.9, None), (None, 80.0, "warning"),            # boundary: raise AT threshold
    ("warning", 79.0, "warning"), ("warning", 75.0, "warning"),  # inside recovery band
    ("warning", 74.9, None),                                 # clears below threshold - margin
    (None, 77.0, None),                                      # band does not RAISE a new alert
    ("warning", 95.0, "critical"), (None, 99.0, "critical"),  # escalation
    ("critical", 94.0, "critical"), ("critical", 90.0, "critical"),
    ("critical", 89.9, "warning"),                           # drops to warning, still >= 75
    ("critical", 70.0, None),                                # below both recovery levels
    ("critical", 74.9, None), ("critical", 75.0, "warning"),
])
def test_next_level_boundaries(current, value, expected):
    assert alerts.next_level(current, value, 80, 95, 5) == expected


def test_no_flapping_near_threshold(dbpath):
    # hovering 78..82 around the 80 warning threshold must produce exactly ONE alert
    for i, v in enumerate([82, 78, 81, 79, 82, 77, 80, 78]):
        alerts.evaluate_sample(dbpath, make_sample(ts=i, cpu=v))
    rows = db.list_alerts(dbpath)
    assert len(rows) == 1 and rows[0]["status"] == "active"


def test_clears_only_below_recovery_level(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(ts=1, cpu=85), margin=5)
    alerts.evaluate_sample(dbpath, make_sample(ts=2, cpu=76), margin=5)
    assert db.list_alerts(dbpath)[0]["status"] == "active"
    alerts.evaluate_sample(dbpath, make_sample(ts=3, cpu=74), margin=5)
    row = db.list_alerts(dbpath)[0]
    assert row["status"] == "resolved" and row["resolved_ts"] == 3


def test_critical_steps_down_to_warning_then_resolves(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(ts=1, mem=97))
    alerts.evaluate_sample(dbpath, make_sample(ts=2, mem=88))     # < 90 -> warning (>= 80)
    rows = db.list_alerts(dbpath)
    assert [(r["severity"], r["status"]) for r in rows] == [("warning", "active"), ("critical", "resolved")]
    alerts.evaluate_sample(dbpath, make_sample(ts=3, mem=60))
    assert db.list_alerts(dbpath)[0]["status"] == "resolved"
    assert len(db.list_alerts(dbpath)) == 2                        # history preserved


def test_zero_margin_behaves_like_plain_thresholds(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(ts=1, cpu=85), margin=0)
    alerts.evaluate_sample(dbpath, make_sample(ts=2, cpu=79), margin=0)
    assert db.list_alerts(dbpath)[0]["status"] == "resolved"


def test_hysteresis_applies_to_cpu_memory_disk(dbpath):
    alerts.evaluate_sample(dbpath, make_sample(ts=1, cpu=85, mem=90, disk=85))
    alerts.evaluate_sample(dbpath, make_sample(ts=2, cpu=78, mem=82, disk=77))  # all inside bands
    assert len(db.list_alerts(dbpath, status="active")) == 3
    alerts.evaluate_sample(dbpath, make_sample(ts=3, cpu=50, mem=50, disk=50))
    assert len(db.list_alerts(dbpath, status="active")) == 0
    assert len(db.list_alerts(dbpath)) == 3


def test_threshold_change_takes_effect_with_hysteresis(dbpath):
    db.set_threshold(dbpath, "disk", 50, 60)
    alerts.evaluate_sample(dbpath, make_sample(ts=1, disk=55))
    alerts.evaluate_sample(dbpath, make_sample(ts=2, disk=47))    # >= 45 -> stays
    assert db.list_alerts(dbpath)[0]["status"] == "active"

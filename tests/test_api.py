import time

from backend import database as db
from tests.conftest import make_sample


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json["database"] is True


def test_overview_has_real_system_data(client):
    j = client.get("/api/overview").json
    assert j["system"]["hostname"] and j["system"]["kernel"] and j["status"] == "healthy"


def test_current_live_fallback_then_database(client, dbpath):
    assert client.get("/api/metrics/current").json["source"] == "live"
    db.insert_metric(dbpath, make_sample(ts=time.time(), cpu=33))
    j = client.get("/api/metrics/current").json
    assert j["source"] == "database" and j["metrics"]["cpu_percent"] == 33


def test_history_groups_and_validation(client, dbpath):
    for i in range(5):
        db.insert_metric(dbpath, make_sample(ts=time.time() - i))
    j = client.get("/api/metrics/history?metric=cpu&minutes=5").json
    assert j["count"] == 5 and "cpu_percent" in j["points"][0] and "mem_percent" not in j["points"][0]
    for bad in ("minutes=abc", "minutes=0", "minutes=99999999", "limit=5", "metric=bogus"):
        assert client.get("/api/metrics/history?" + bad).status_code == 400


def test_processes_endpoint_and_validation(client):
    j = client.get("/api/processes?limit=3&sort=memory").json
    assert 0 < j["count"] <= 3
    assert client.get("/api/processes?sort=name;rm").status_code == 400
    assert client.get("/api/processes?limit=1000").status_code == 400
    assert client.post("/api/processes").status_code == 405   # no write/kill route


def test_services_endpoint_ok_with_or_without_systemd(client):
    j = client.get("/api/services").json
    assert "systemd_available" in j and isinstance(j["services"], list)


def test_alerts_endpoint(client, dbpath):
    db.create_alert(dbpath, 1.0, "h", "cpu", "warning", 90, 80, "msg")
    assert client.get("/api/alerts?status=active").json["count"] == 1
    assert client.get("/api/alerts?status=resolved").json["count"] == 0
    assert client.get("/api/alerts?status=hack").status_code == 400


def test_threshold_update_disabled_without_token(client):
    r = client.put("/api/thresholds/cpu", json={"warning": 50, "critical": 70})
    assert r.status_code == 403


def test_threshold_update_with_token_and_validation(secure_client):
    h = {"X-API-Key": "s3cret"}
    assert secure_client.put("/api/thresholds/cpu", json={"warning": 50, "critical": 70}).status_code == 401
    assert secure_client.put("/api/thresholds/cpu", json={"warning": 50, "critical": 70},
                             headers={"X-API-Key": "wrong"}).status_code == 401
    assert secure_client.put("/api/thresholds/cpu", json={"warning": 50, "critical": 70}, headers=h).status_code == 200
    assert secure_client.get("/api/thresholds").json["thresholds"]["cpu"]["warning"] == 50
    for body in ({"warning": 90, "critical": 80}, {"warning": "x", "critical": 90}, {"warning": 10},
                 {"warning": 10, "critical": 500}, [1, 2]):
        assert secure_client.put("/api/thresholds/cpu", json=body, headers=h).status_code == 400
    assert secure_client.put("/api/thresholds/evil", json={"warning": 1, "critical": 2}, headers=h).status_code == 400


def test_sensitive_reads_protected_when_token_set(secure_client):
    assert secure_client.get("/api/processes").status_code == 401
    assert secure_client.get("/api/services").status_code == 401
    assert secure_client.get("/api/processes", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert secure_client.get("/api/health").status_code == 200   # health stays open for probes


def test_frontend_and_unknown_paths(client):
    assert client.get("/").status_code == 200
    assert client.get("/dashboard.js").status_code == 200
    assert client.get("/backend/app.py").status_code == 404
    assert client.get("/../../etc/passwd").status_code == 404
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_health_reports_collector_stats(client):
    j = client.get("/api/health").json
    assert "collector" in j and j["collector_enabled"] is False


def test_health_degraded_when_collector_enabled_but_dead(tmp_path):
    from backend.app import create_app
    from backend import collector
    from tests.conftest import make_cfg
    cfg = make_cfg(tmp_path)
    cfg.disable_collector = False
    collector.stop_collector()
    c = create_app(cfg, start_agent=False).test_client()   # collector deliberately not started
    r = c.get("/api/health")
    assert r.status_code == 503 and r.json["status"] == "degraded"


def test_current_flags_stale_data(tmp_path):
    from backend.app import create_app
    from tests.conftest import make_cfg
    cfg = make_cfg(tmp_path)
    cfg.disable_collector = False
    c = create_app(cfg, start_agent=False).test_client()
    db.insert_metric(cfg.db_path, make_sample(ts=time.time() - 600))
    j = c.get("/api/metrics/current").json
    assert j["stale"] is True and j["age_seconds"] > 500


def test_processes_null_cpu_serialises_as_json_null(client):
    from backend import monitor
    monitor._SEEN.clear()
    j = client.get("/api/processes?limit=2").json
    assert all(p["cpu_percent"] is None for p in j["processes"])


def test_missing_and_malformed_inputs(client, secure_client):
    assert client.get("/api/alerts?limit=0").status_code == 400
    assert client.get("/api/alerts?limit=abc").status_code == 400
    assert client.get("/api/metrics/history?limit=99999").status_code == 400
    h = {"X-API-Key": "s3cret"}
    assert secure_client.put("/api/thresholds/cpu", data="not json", headers=h).status_code == 400
    assert secure_client.put("/api/thresholds/cpu", json={"warning": 0, "critical": 50}, headers=h).status_code == 400
    assert secure_client.put("/api/thresholds/cpu", json={"warning": 50, "critical": 50}, headers=h).status_code == 400
    assert secure_client.delete("/api/thresholds/cpu", headers=h).status_code == 405

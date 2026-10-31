"""Alert history and threshold configuration."""
from flask import Blueprint, current_app, jsonify, request

from .. import database as db
from ..security import require_token
from ._util import BadRequest, choice_arg, int_arg

bp = Blueprint("alerts", __name__, url_prefix="/api")
VALID_METRICS = {"cpu", "memory", "disk"}


@bp.get("/alerts")
def list_alerts():
    cfg = current_app.config["LG"]
    status = choice_arg("status", "all", {"all", "active", "resolved"})
    limit = int_arg("limit", 50, 1, 500)
    rows = db.list_alerts(cfg.db_path, None if status == "all" else status, limit)
    return jsonify(count=len(rows), alerts=rows)


@bp.get("/thresholds")
def get_thresholds():
    return jsonify(thresholds=db.get_thresholds(current_app.config["LG"].db_path))


@bp.put("/thresholds/<metric>")
@require_token
def put_threshold(metric):
    if metric not in VALID_METRICS:
        raise BadRequest(f"metric must be one of: {', '.join(sorted(VALID_METRICS))}")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise BadRequest("JSON body required: {\"warning\": 70, \"critical\": 90}")
    try:
        warning, critical = float(body["warning"]), float(body["critical"])
    except (KeyError, TypeError, ValueError):
        raise BadRequest("'warning' and 'critical' must be numbers")
    if not (0 < warning < critical <= 100):
        raise BadRequest("require 0 < warning < critical <= 100")
    db.set_threshold(current_app.config["LG"].db_path, metric, warning, critical)
    return jsonify(metric=metric, warning=warning, critical=critical)

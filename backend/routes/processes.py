"""Read-only process listing. There is deliberately NO kill/signal endpoint."""
from flask import Blueprint, jsonify

from .. import monitor
from ..security import protect_if_configured
from ._util import choice_arg, int_arg

bp = Blueprint("processes", __name__, url_prefix="/api")


@bp.get("/processes")
@protect_if_configured
def processes():
    sort_by = choice_arg("sort", "cpu", {"cpu", "memory"})
    limit = int_arg("limit", 15, 1, 100)
    rows = monitor.list_processes(sort_by, limit)
    return jsonify(sort=sort_by, count=len(rows), processes=rows)

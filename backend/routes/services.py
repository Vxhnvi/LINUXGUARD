"""Read-only systemd service status."""
from flask import Blueprint, current_app, jsonify

from .. import monitor
from ..security import protect_if_configured

bp = Blueprint("services", __name__, url_prefix="/api")


@bp.get("/services")
@protect_if_configured
def services():
    return jsonify(monitor.get_services(current_app.config["LG"].services))

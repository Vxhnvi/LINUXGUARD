"""Flask application factory.  Run:  python -m backend.app"""
import logging
import os
import signal
import sys

from flask import Flask, jsonify, send_from_directory

from . import database as db
from .collector import start_collector, stop_collector
from .config import BASE_DIR, load_config
from .routes import alert_routes, metrics, processes, services
from .routes._util import BadRequest

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def create_app(cfg=None, start_agent=True):
    cfg = cfg or load_config()
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="/static-ui")
    app.config["LG"] = cfg
    db.init_db(cfg.db_path)

    for module in (metrics, alert_routes, processes, services):
        app.register_blueprint(module.bp)

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def frontend_files(filename):
        # Only serve the dashboard's own assets; anything else is a JSON 404.
        if filename in ("style.css", "dashboard.js") or filename.startswith("vendor/"):
            return send_from_directory(FRONTEND_DIR, filename)
        return jsonify(error="not_found"), 404

    @app.errorhandler(BadRequest)
    def bad_request(e):
        return jsonify(error="bad_request", message=str(e)), 400

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="not_found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_):
        return jsonify(error="method_not_allowed"), 405

    @app.errorhandler(Exception)
    def server_error(e):
        app.logger.exception("unhandled error")
        return jsonify(error="internal_error"), 500  # never leak tracebacks

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'"
        return resp

    if start_agent and not cfg.disable_collector:
        start_collector(cfg)
    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    app = create_app(cfg)
    from waitress import serve  # production WSGI server; Flask's dev server is never used
    # `docker stop` / `systemctl stop` send SIGTERM: turn it into a clean exit so we can stop the collector
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    logging.info("LinuxGuard listening on http://%s:%s", cfg.host, cfg.port)
    try:
        serve(app, host=cfg.host, port=cfg.port, threads=4)
    finally:
        stop_collector()
        logging.info("LinuxGuard shut down cleanly")


if __name__ == "__main__":
    main()

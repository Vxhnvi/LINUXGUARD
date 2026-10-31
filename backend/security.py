"""Optional shared-secret protection for sensitive endpoints."""
import hmac
from functools import wraps

from flask import current_app, jsonify, request


def _token_ok(expected):
    supplied = request.headers.get("X-API-Key", "")
    return hmac.compare_digest(supplied.encode(), expected.encode())  # constant-time compare


def protect_if_configured(fn):
    """If LINUXGUARD_API_TOKEN is set, require it. If unset, endpoint stays open (read-only data)."""
    @wraps(fn)
    def wrapper(*a, **kw):
        token = current_app.config["LG"].api_token
        if token and not _token_ok(token):
            return jsonify(error="unauthorized", message="Valid X-API-Key header required"), 401
        return fn(*a, **kw)
    return wrapper


def require_token(fn):
    """Write endpoints: refused outright when no token is configured."""
    @wraps(fn)
    def wrapper(*a, **kw):
        token = current_app.config["LG"].api_token
        if not token:
            return jsonify(error="forbidden", message="Write endpoints are disabled: set LINUXGUARD_API_TOKEN"), 403
        if not _token_ok(token):
            return jsonify(error="unauthorized", message="Valid X-API-Key header required"), 401
        return fn(*a, **kw)
    return wrapper

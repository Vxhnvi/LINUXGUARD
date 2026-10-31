"""Small helpers for validating query parameters."""
from flask import request


class BadRequest(Exception):
    pass


def int_arg(name, default, lo, hi):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise BadRequest(f"'{name}' must be an integer")
    if not lo <= value <= hi:
        raise BadRequest(f"'{name}' must be between {lo} and {hi}")
    return value


def choice_arg(name, default, allowed):
    value = request.args.get(name, default)
    if value not in allowed:
        raise BadRequest(f"'{name}' must be one of: {', '.join(sorted(allowed))}")
    return value

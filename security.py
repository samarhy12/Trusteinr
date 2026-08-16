import secrets

from flask import session, request, abort


def get_csrf_token():
    """Return the current session's CSRF token, creating one if needed."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def init_csrf(app):
    """Register the csrf_token() Jinja helper and a before_request check on all
    state-changing requests. Safe methods (GET/HEAD/OPTIONS) are never checked."""

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": get_csrf_token}

    @app.before_request
    def verify_csrf():
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None
        if request.blueprint == "static" or request.endpoint == "static":
            return None

        submitted = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        expected = session.get("_csrf_token")

        if not expected or not submitted or not secrets.compare_digest(submitted, expected):
            abort(400, description="Your session has expired or the form was submitted incorrectly. Please go back and try again.")
        return None

import os
from datetime import date

from flask import Flask, render_template, redirect, url_for, request
from flask_login import LoginManager, current_user
from flask_migrate import Migrate

from config import Config
from extensions import db, login_manager
from models import Staff, is_weekend, is_business_day_open
from security import init_csrf


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    init_csrf(app)
    migrate = Migrate(app, db)

    @login_manager.user_loader
    def load_user(user_id):
        return Staff.query.get(int(user_id))

    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.customers import bp as customers_bp
    from routes.loans import bp as loans_bp
    from routes.staff import bp as staff_bp
    from routes.expenses import bp as expenses_bp
    from routes.agents import bp as agents_bp
    from routes.business import bp as business_bp
    from routes.notifications import bp as notifications_bp
    from routes.reports import bp as reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(loans_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(business_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reports_bp)
    # -----------------------------------------------------------------
    # Access control
    # -----------------------------------------------------------------
    ALWAYS_ALLOWED_ENDPOINTS = {"static", "auth.logout", "dashboard.system_closed"}
    PASSWORD_CHANGE_ALLOWED_ENDPOINTS = ALWAYS_ALLOWED_ENDPOINTS | {"auth.change_password"}

    @app.before_request
    def enforce_access_rules():
        if not current_user.is_authenticated:
            return None
        if request.endpoint in ALWAYS_ALLOWED_ENDPOINTS:
            return None

        # A forced password change (e.g. first login on the default admin account)
        # takes priority over every other page — nothing else is reachable until it's done.
        if current_user.must_change_password and request.endpoint not in PASSWORD_CHANGE_ALLOWED_ENDPOINTS:
            return redirect(url_for("auth.change_password"))
        if request.endpoint == "auth.change_password":
            return None

        # Weekends and a closed business day lock out office staff and agents
        # entirely. Admin is never blocked from viewing — individual routes
        # handle blocking admin from *recording* new transactions while closed.
        if current_user.role in ("office_staff", "agent"):
            if is_weekend() or not is_business_day_open():
                return redirect(url_for("dashboard.system_closed"))
        return None

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"  # deprecated header; modern browsers rely on CSP instead
        return response

    @app.context_processor
    def inject_globals():
        from models import current_cash_in_hand, Notification
        cash = None
        unread_count = 0
        if current_user.is_authenticated:
            try:
                cash = current_cash_in_hand()
                unread_count = Notification.query.filter(
                    (Notification.recipient_id == current_user.id) |
                    (Notification.recipient_role == current_user.role) |
                    (Notification.recipient_role == "all"),
                    Notification.is_read == False
                ).count()
            except Exception:
                cash = None
                unread_count = 0
        return {"current_year": date.today().year, "app_name": "Trustline Finance", "global_cash_in_hand": cash, "unread_notification_count": unread_count}

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    with app.app_context():
        db.create_all()
        _ensure_default_admin()

    return app


def _ensure_default_admin():
    if Staff.query.count() == 0:
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD") or os.environ.get("INITIAL_ADMIN_PASSWORD")
        if not password:
            raise RuntimeError("ADMIN_PASSWORD must be configured in the environment or .env file")

        admin = Staff(full_name="System Administrator", username=username, role="admin")
        admin.set_password(password)
        admin.must_change_password = True
        db.session.add(admin)
        db.session.commit()
        print(f">> Default admin account created — username: {username} / password: {password}")
        print(">> You will be required to set a new password on first login.")


app = create_app()

if __name__ == "__main__":
    app.run()

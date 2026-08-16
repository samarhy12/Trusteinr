from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import Staff

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        staff = Staff.query.filter_by(username=username).first()

        if staff and staff.is_locked:
            minutes_left = max(1, int((staff.locked_until - datetime.now()).total_seconds() // 60) + 1)
            flash(f"This account is temporarily locked after too many failed attempts. "
                  f"Try again in about {minutes_left} minute{'s' if minutes_left != 1 else ''}.", "error")
            return render_template("login.html", username=username)

        if staff is None or not staff.check_password(password):
            if staff is not None:
                staff.register_failed_login(
                    current_app.config["LOGIN_MAX_ATTEMPTS"], current_app.config["LOGIN_LOCKOUT_MINUTES"]
                )
                db.session.commit()
            flash("Incorrect username or password.", "error")
            return render_template("login.html", username=username)

        if not staff.is_active_staff:
            flash("This account has been deactivated. Contact your administrator.", "error")
            return render_template("login.html", username=username)

        staff.register_successful_login()
        db.session.commit()

        login_user(staff, remember=remember)
        from flask import session
        session.permanent = True

        next_page = request.args.get("next")
        return redirect(next_page or url_for("dashboard.index"))

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    forced = current_user.must_change_password

    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")
        min_len = current_app.config["PASSWORD_MIN_LENGTH"]

        errors = []
        if not current_user.check_password(current_pw):
            errors.append("Your current password is incorrect.")
        if len(new_pw) < min_len:
            errors.append(f"New password must be at least {min_len} characters.")
        if new_pw != confirm_pw:
            errors.append("New password and confirmation do not match.")
        if new_pw and current_user.check_password(new_pw):
            errors.append("New password must be different from your current password.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("change_password.html", forced=forced)

        current_user.set_password(new_pw)
        current_user.must_change_password = False
        db.session.commit()
        flash("Your password has been updated.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("change_password.html", forced=forced)

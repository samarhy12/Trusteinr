from functools import wraps
from datetime import datetime, date
import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

from extensions import db
from models import Staff, CashTransaction, current_cash_in_hand
from pagination_utils import paginate_items

bp = Blueprint("staff", __name__, url_prefix="/staff")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.route("/")
@login_required
@admin_required
def list_staff():
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    members_all = Staff.query.order_by(Staff.created_at.asc()).all()
    pagination = paginate_items(members_all, page, per_page)
    return render_template("staff/list.html", members=pagination.items, pagination=pagination, query_params={})


@bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_staff():
    min_len = current_app.config["PASSWORD_MIN_LENGTH"]

    if request.method == "POST":
        form = request.form
        errors = []

        full_name = form.get("full_name", "").strip()
        username = form.get("username", "").strip().lower()
        password = form.get("password", "")
        role = form.get("role", "agent")

        if not full_name:
            errors.append("Full name is required.")
        if not username:
            errors.append("Username is required.")
        elif Staff.query.filter_by(username=username).first():
            errors.append("That username is already taken.")
        if len(password) < min_len:
            errors.append(f"Password must be at least {min_len} characters.")
        if role not in ("admin", "office_staff", "agent"):
            role = "agent"

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("staff/form.html", form=form, min_len=min_len)

        member = Staff(full_name=full_name, username=username, role=role, must_change_password=True)
        member.set_password(password)
        db.session.add(member)
        db.session.commit()

        flash(f"{member.role_label} account for {full_name} created. They'll be asked to set their own password on first login.", "success")
        return redirect(url_for("staff.list_staff"))

    return render_template("staff/form.html", form={}, min_len=min_len)


@bp.route("/<int:staff_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_staff(staff_id):
    member = Staff.query.get_or_404(staff_id)
    if member.id == current_user.id:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("staff.list_staff"))

    member.is_active_staff = not member.is_active_staff
    db.session.commit()
    state = "activated" if member.is_active_staff else "deactivated"
    flash(f"{member.full_name}'s account has been {state}.", "success")
    return redirect(url_for("staff.list_staff"))


@bp.route("/<int:staff_id>/toggle-edit-permission", methods=["POST"])
@login_required
@admin_required
def toggle_agent_edit_permission(staff_id):
    member = Staff.query.filter_by(id=staff_id, role="agent").first_or_404()
    member.agent_edit_permission = not member.agent_edit_permission
    db.session.commit()
    state = "granted" if member.agent_edit_permission else "revoked"
    flash(f"Customer-editing permission {state} for {member.full_name}.", "success")
    return redirect(url_for("staff.list_staff"))


@bp.route("/<int:staff_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_password(staff_id):
    member = Staff.query.get_or_404(staff_id)

    temp_password = secrets.token_urlsafe(9)  # e.g. "kQ3f9xLp2mZ" — share this with the staff member securely
    member.set_password(temp_password)
    member.must_change_password = True
    member.failed_login_attempts = 0
    member.locked_until = None
    db.session.commit()

    flash(f"Password reset for {member.full_name}. Temporary password: {temp_password} — "
          f"share this with them securely. They'll be asked to set their own on next login.", "success")
    return redirect(url_for("staff.list_staff"))


# ---------------------------------------------------------------------------
# Cash ledger / capital injection (admin only)
# ---------------------------------------------------------------------------
@bp.route("/transactions")
@login_required
def transactions():
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    txs_all = CashTransaction.query.order_by(CashTransaction.created_at.desc()).all()
    pagination = paginate_items(txs_all, page, per_page)
    return render_template(
        "staff/transactions.html",
        transactions=pagination.items,
        cash_in_hand=current_cash_in_hand(),
        pagination=pagination,
        query_params={},
    )


@bp.route("/transactions/capital", methods=["POST"])
@login_required
@admin_required
def add_capital():
    amount_raw = request.form.get("amount", "").strip()
    description = request.form.get("description", "").strip() or "Capital injection"
    password = request.form.get("password", "")

    if not password or not current_user.check_password(password):
        flash("Incorrect password. Cash ledger adjustments must be confirmed with your admin password.", "error")
        return redirect(url_for("staff.transactions"))

    try:
        amount = float(amount_raw)
        if amount == 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid, non-zero amount.", "error")
        return redirect(url_for("staff.transactions"))

    tx = CashTransaction(
        tx_type="capital_in" if amount > 0 else "adjustment",
        amount=amount,
        description=description,
        staff_id=current_user.id,
        date=date.today(),
    )
    db.session.add(tx)
    db.session.commit()
    flash("Cash ledger updated.", "success")
    return redirect(url_for("staff.transactions"))

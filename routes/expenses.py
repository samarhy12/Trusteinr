from datetime import datetime, date
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

from extensions import db
from models import Expense, CashTransaction, EXPENSE_CATEGORIES, is_business_day_open
from pagination_utils import paginate_items

bp = Blueprint("expenses", __name__, url_prefix="/expenses")


def can_record_expenses_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.can_record_expenses:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.route("/")
@login_required
def list_expenses():
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    expenses_all = Expense.query.order_by(Expense.date.desc(), Expense.created_at.desc()).all()
    pagination = paginate_items(expenses_all, page, per_page)

    today = date.today()
    month_total = sum(e.amount for e in expenses_all if e.date.year == today.year and e.date.month == today.month)
    week_total = sum(e.amount for e in expenses_all if (today - e.date).days < 7 and (today - e.date).days >= 0)

    return render_template(
        "expenses/list.html",
        expenses=pagination.items,
        month_total=round(month_total, 2),
        week_total=round(week_total, 2),
        pagination=pagination,
        query_params={},
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
@can_record_expenses_required
def new_expense():
    if request.method == "POST":
        if not is_business_day_open():
            flash("The business day is closed. Open the day before recording expenses.", "error")
            return redirect(url_for("expenses.new_expense"))

        form = request.form
        errors = []

        description = form.get("description", "").strip()
        category = form.get("category", "")
        amount_raw = form.get("amount", "").strip()
        date_raw = form.get("date", "").strip()

        if not description:
            errors.append("A short description is required.")
        if category not in EXPENSE_CATEGORIES:
            errors.append("Please choose a valid category.")

        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors.append("Amount must be greater than zero.")
        except ValueError:
            amount = None
            errors.append("Amount must be a number.")

        try:
            expense_date = datetime.strptime(date_raw, "%Y-%m-%d").date() if date_raw else date.today()
        except ValueError:
            expense_date = date.today()
            errors.append("Date is not valid.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("expenses/form.html", form=form, categories=EXPENSE_CATEGORIES,
                                    today=date.today().isoformat())

        expense = Expense(
            description=description,
            category=category,
            amount=amount,
            date=expense_date,
            recorded_by_id=current_user.id,
        )
        db.session.add(expense)
        db.session.flush()

        tx = CashTransaction(
            tx_type="expense",
            amount=-abs(amount),
            description=f"{category}: {description}",
            expense_id=expense.id,
            staff_id=current_user.id,
            date=expense_date,
        )
        db.session.add(tx)
        db.session.commit()

        flash(f"Expense of GHS {amount:,.2f} recorded ({expense.expense_code}).", "success")
        return redirect(url_for("expenses.list_expenses"))

    return render_template("expenses/form.html", form={}, categories=EXPENSE_CATEGORIES,
                            today=date.today().isoformat())

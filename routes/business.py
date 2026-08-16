from datetime import datetime, date
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from extensions import db
from models import (
    BusinessDay, CashTransaction, Repayment, Loan, Expense, Staff,
    is_weekend, get_business_day,
)

bp = Blueprint("business", __name__, url_prefix="/business")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_manage_business_day:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _day_breakdown(target_date):
    """Build the full per-day picture: per-agent collections, disbursements, expenses, totals."""
    repayments = (
        Repayment.query.filter(Repayment.date == target_date)
        .order_by(Repayment.created_at.asc()).all()
    )
    agent_groups = {}
    for r in repayments:
        agent_groups.setdefault(r.agent_id, {"agent": r.agent, "rows": [], "subtotal": 0.0})
        agent_groups[r.agent_id]["rows"].append(r)
        agent_groups[r.agent_id]["subtotal"] += r.amount

    for g in agent_groups.values():
        g["subtotal"] = round(g["subtotal"], 2)

    total_collected = round(sum(r.amount for r in repayments), 2)

    loans_disbursed = Loan.query.filter(Loan.start_date == target_date).order_by(Loan.created_at.asc()).all()
    total_disbursed = round(sum(l.principal for l in loans_disbursed), 2)

    expenses = Expense.query.filter(Expense.date == target_date).order_by(Expense.created_at.asc()).all()
    total_expenses = round(sum(e.amount for e in expenses), 2)

    net_change = round(total_collected - total_disbursed - total_expenses, 2)

    return {
        "agent_groups": sorted(agent_groups.values(), key=lambda g: g["agent"].full_name if g["agent"] else ""),
        "total_collected": total_collected,
        "loans_disbursed": loans_disbursed,
        "total_disbursed": total_disbursed,
        "expenses": expenses,
        "total_expenses": total_expenses,
        "net_change": net_change,
    }


@bp.route("/")
@login_required
@admin_required
def overview():
    today = date.today()
    today_row = BusinessDay.query.filter_by(date=today).first()
    history = BusinessDay.query.order_by(BusinessDay.date.desc()).limit(60).all()

    return render_template(
        "business/overview.html",
        today=today,
        today_row=today_row,
        is_open=bool(today_row and today_row.is_open),
        is_weekend_today=is_weekend(today),
        history=history,
    )


@bp.route("/open", methods=["POST"])
@login_required
@admin_required
def open_day():
    today = date.today()
    row = get_business_day(today, create_if_missing=True)
    row.opened_at = datetime.now()
    row.opened_by_id = current_user.id
    row.closed_at = None
    row.closed_by_id = None
    row.total_collected = None
    row.total_disbursed = None
    row.total_expenses = None
    row.net_change = None
    db.session.commit()
    flash(f"Business day for {today.strftime('%d %b %Y')} is now open.", "success")
    return redirect(url_for("business.overview"))


@bp.route("/close", methods=["POST"])
@login_required
@admin_required
def close_day():
    confirm = request.form.get("confirm")
    if confirm != "yes":
        flash("Please confirm you want to close the day before proceeding.", "error")
        return redirect(url_for("business.overview"))

    today = date.today()
    row = get_business_day(today, create_if_missing=True)
    if not row.is_open:
        flash("Today's business day is not currently open.", "error")
        return redirect(url_for("business.overview"))

    breakdown = _day_breakdown(today)
    row.closed_at = datetime.now()
    row.closed_by_id = current_user.id
    row.total_collected = breakdown["total_collected"]
    row.total_disbursed = breakdown["total_disbursed"]
    row.total_expenses = breakdown["total_expenses"]
    row.net_change = breakdown["net_change"]
    db.session.commit()

    flash(f"Business day for {today.strftime('%d %b %Y')} has been closed and totals recorded.", "success")
    return redirect(url_for("business.day_detail", date_str=today.isoformat()))


@bp.route("/day/<date_str>")
@login_required
def day_detail(date_str):
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        abort(404)

    row = BusinessDay.query.filter_by(date=target_date).first()
    breakdown = _day_breakdown(target_date)

    return render_template(
        "business/day_detail.html",
        target_date=target_date,
        row=row,
        **breakdown,
    )
